// "Borrar mi cuenta" (PLAN_MULTIUSUARIO.md, fase 7.2).
//
// Un usuario no puede borrar su propia fila de auth.users: hace falta la service_role, y
// esa key no puede salir del servidor. Esta edge recibe la sesión del usuario
// (verify_jwt = true), comprueba quién es y:
//   1. llama a `preparar_baja()` CON SU SESIÓN: rompe sus vínculos como `desvincular`
//      (lo que esperaba respuesta vuelve a su dueño; lo acordado queda como está);
//   2. borra el usuario de Auth con la service_role. La cascada se lleva su libreta
//      entera (perfil, deudores, deudas, pagos, invitaciones, vínculos) y no deja lápidas.
// Las filas espejo en la libreta del otro son del otro y no se tocan.
//
//   POST { confirmar: "BORRAR" }  →  { borrada: true }
//
// La palabra de confirmación evita que una llamada por error (o un cliente viejo que
// reintenta algo) borre una cuenta.

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'
import { corsHeaders, responder } from '../_shared/http.ts'

serve(async (req: Request) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders })
    }

    try {
        const { confirmar } = await req.json().catch(() => ({}))
        if (confirmar !== 'BORRAR') {
            return responder({ error: 'Falta la confirmación' }, 400)
        }

        const url = Deno.env.get('SUPABASE_URL') ?? ''
        const autorizacion = req.headers.get('Authorization') ?? ''
        const usuario = createClient(url, Deno.env.get('SUPABASE_ANON_KEY') ?? '', {
            global: { headers: { Authorization: autorizacion } },
            auth: { persistSession: false },
        })
        // Con el JWT explícito: sin él, getUser() busca una sesión guardada, que aquí no hay.
        const jwt = autorizacion.replace(/^Bearer\s+/i, '')
        const { data: { user }, error: errorSesion } = await usuario.auth.getUser(jwt)
        if (errorSesion || !user) {
            console.error('borrar_cuenta: sesión inválida', errorSesion?.message)
            return responder({ error: 'Sesión inválida' }, 401)
        }

        const { error: errorBaja } = await usuario.rpc('preparar_baja')
        if (errorBaja) throw errorBaja

        const admin = createClient(url, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '', {
            auth: { persistSession: false },
        })
        const { error: errorBorrar } = await admin.auth.admin.deleteUser(user.id)
        if (errorBorrar) throw errorBorrar

        return responder({ borrada: true })
    } catch (error: unknown) {
        console.error(error)
        return responder({ error: 'No se pudo borrar la cuenta' }, 500)
    }
})
