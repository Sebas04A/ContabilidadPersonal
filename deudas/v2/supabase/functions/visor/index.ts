// Visor público: el deudor abre su enlace (?token=…) y ve su estado de cuenta.
//
// Es la ÚNICA puerta sin sesión de v2 (verify_jwt = false en config.toml). Recibe solo el
// token, nunca un deudor_id: en v1 las edges aceptaban un deudor_id crudo y el token era
// decorativo (PLAN_MULTIUSUARIO.md §1.5). Resuelve el deudor con la service_role y
// devuelve lo mismo que devolvían get_estado_cuenta / get_historial con pov 'debtor'.
//
//   POST { token, accion: 'deudor' | 'estado' | 'historial' }
//
// Un token inexistente o vencido responde siempre el mismo 404, sin decir cuál de las dos
// cosas pasó.

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'
import { corsHeaders, responder } from '../_shared/http.ts'
import { armarEstadoCuenta } from '../_shared/estado_cuenta.ts'
import { armarHistorial } from '../_shared/historial.ts'

const ENLACE_INVALIDO = { error: 'Enlace inválido o vencido' }

// Límite de uso (fase 7.3): consultas por IP y minuto. Abrir el visor hace 3 (deudor,
// estado, historial), así que 60 da para recargar de sobra.
const VISITAS_POR_MINUTO = 60

serve(async (req: Request) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders })
    }

    try {
        const admin = createClient(
            Deno.env.get('SUPABASE_URL') ?? '',
            Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '',
            { auth: { persistSession: false } },
        )

        // Cuenta también las consultas con tokens malos: son las que interesa frenar. Si
        // el contador falla, el visor sigue funcionando (el límite es una defensa extra).
        const ip = (req.headers.get('x-forwarded-for') ?? '').split(',')[0].trim() || 'sin-ip'
        const { data: visitas, error: errorVisitas } = await admin.rpc('contar_visita_visor', { p_ip: ip })
        if (errorVisitas) {
            console.error(errorVisitas)
        } else if (visitas > VISITAS_POR_MINUTO) {
            return responder({ error: 'Demasiadas consultas seguidas. Espera un minuto.' }, 429)
        }

        const { token, accion = 'estado' } = await req.json()
        if (typeof token !== 'string' || token.length === 0 || token.length > 200) {
            return responder(ENLACE_INVALIDO, 404)
        }

        const { data: deudor, error } = await admin
            .from('deudores')
            .select('id, nombre, moneda, token_expira')
            .eq('token', token)
            .maybeSingle()
        if (error) throw error
        if (!deudor || (deudor.token_expira && new Date(deudor.token_expira) < new Date())) {
            return responder(ENLACE_INVALIDO, 404)
        }

        switch (accion) {
            case 'deudor':
                // Sin el id: el visor no lo necesita y no hay por qué repartirlo.
                return responder({ nombre: deudor.nombre, moneda: deudor.moneda })
            case 'estado':
                return responder(await armarEstadoCuenta(admin, deudor.id, 'debtor'))
            case 'historial':
                return responder(await armarHistorial(admin, deudor.id, 'debtor'))
            default:
                return responder({ error: 'Acción desconocida' }, 400)
        }
    } catch (error: unknown) {
        console.error(error)
        return responder({ error: 'Error interno' }, 500)
    }
})
