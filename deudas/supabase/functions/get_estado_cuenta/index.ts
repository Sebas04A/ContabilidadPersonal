// Estado de cuenta de un deudor.
//
// Toda la matemática (saldos, saldo a favor y cruce sugerido) vive en la función SQL
// `estado_cuenta`, que es la única definición del sistema. Esta edge solo la llama y
// adapta la respuesta al contrato que ya consumen el visor web y la app.

import { serve } from 'https://deno.land/std@0.177.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'

const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req: any) => {
    if (req.method === 'OPTIONS') {
        return new Response('ok', { headers: corsHeaders })
    }

    try {
        const supabaseClient = createClient(
            Deno.env.get('SUPABASE_URL') ?? '',
            Deno.env.get('SUPABASE_ANON_KEY') ?? ''
        )

        const { deudor_id, pov = 'debtor' } = await req.json()

        if (!deudor_id) {
            return new Response(JSON.stringify({ error: 'Falta deudor_id' }), {
                headers: { ...corsHeaders, 'Content-Type': 'application/json' },
                status: 400,
            })
        }

        const { data, error } = await supabaseClient.rpc('estado_cuenta', {
            p_deudor_id: deudor_id,
            p_pov: pov,
        })
        if (error) throw error

        const resumen = data?.resumen ?? {}
        const deudas = (data?.deudas ?? []) as any[]

        // Contrato histórico: solo las deudas con saldo pendiente, las ya saldadas por
        // cruce o por saldo a favor al final (se muestran tachadas, no desaparecen).
        const saldoReal = (d: any) =>
            d.saldo_pendiente - (d.cruce_sugerido ?? 0) - (d.abono_saldo_favor ?? 0)

        const deudas_pendientes = deudas
            .filter((d: any) => d.saldo_pendiente > 0.01)
            .sort((a: any, b: any) => {
                const aCruzada = saldoReal(a) <= 0.01
                const bCruzada = saldoReal(b) <= 0.01
                if (aCruzada !== bCruzada) return aCruzada ? 1 : -1
                return new Date(b.fecha_gasto).getTime() - new Date(a.fecha_gasto).getTime()
            })
            .map((d: any) => ({
                id: d.id,
                titulo: d.titulo,
                monto_original: d.monto_original,
                monto_pagado: d.monto_pagado,
                saldo_pendiente: d.saldo_pendiente,
                abono_saldo_favor: d.abono_saldo_favor,
                es_tu_deuda: d.es_tu_deuda,
                fecha_gasto: d.fecha_gasto,
                cruce_sugerido: d.cruce_sugerido,
            }))

        const respuesta = {
            resumen: {
                total_deuda: resumen.neto ?? 0,
                monto_ideal_a_cruzar: resumen.monto_ideal_a_cruzar ?? 0,
                // Ojo: en este contrato `saldo_favor` es el crédito de QUIEN MIRA, que
                // en la función SQL se llama `saldo_favor_owner` (el del POV).
                saldo_favor: resumen.saldo_favor_owner ?? 0,
                su_saldo_favor: resumen.saldo_favor ?? 0,
            },
            deudas_pendientes,
        }

        return new Response(JSON.stringify(respuesta), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
            status: 200,
        })
    } catch (error: unknown) {
        return new Response(JSON.stringify({ error: (error as Error).message }), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
            status: 400,
        })
    }
})
