// Historial de un deudor, para su DUEÑO (app Flutter).
//
// v2: corre con el JWT de quien llama (el RLS decide qué ve) y siempre con el punto de
// vista del dueño; el del deudor lo sirve la edge `visor`. La lógica está en
// `_shared/historial.ts`.

import { serve } from "https://deno.land/std@0.177.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3"
import { corsHeaders, responder } from "../_shared/http.ts"
import { armarHistorial } from "../_shared/historial.ts"

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { deudor_id } = await req.json()
    if (!deudor_id) {
      throw new Error('Missing deudor_id')
    }

    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? '',
      { global: { headers: { Authorization: req.headers.get('Authorization') ?? '' } } },
    )

    return responder(await armarHistorial(supabaseClient, deudor_id, 'owner'))
  } catch (error) {
    return responder({ error: (error as Error).message }, 400)
  }
})
