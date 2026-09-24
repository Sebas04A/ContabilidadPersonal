// Estado de cuenta de un deudor, para su DUEÑO (app Flutter).
//
// v2: corre con el JWT de quien llama, así el RLS decide qué deudores existen para él: con
// un deudor ajeno la respuesta sale vacía. El punto de vista es siempre el del dueño; el
// del deudor solo lo sirve la edge `visor`, por token. La lógica está en
// `_shared/estado_cuenta.ts`.

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'
import { corsHeaders, responder } from '../_shared/http.ts'
import { armarEstadoCuenta } from '../_shared/estado_cuenta.ts'

serve(async (req: Request) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders })
    }

    try {
        const supabaseClient = createClient(
            Deno.env.get('SUPABASE_URL') ?? '',
            Deno.env.get('SUPABASE_ANON_KEY') ?? '',
            { global: { headers: { Authorization: req.headers.get('Authorization') ?? '' } } },
        )

        // `pov` se ignora a propósito: los clientes viejos lo mandan y no molesta.
        const { deudor_id, pago = null } = await req.json()
        if (!deudor_id) {
            return responder({ error: 'Falta deudor_id' }, 400)
        }

        return responder(await armarEstadoCuenta(supabaseClient, deudor_id, 'owner', pago))
    } catch (error: unknown) {
        return responder({ error: (error as Error).message }, 400)
    }
})
