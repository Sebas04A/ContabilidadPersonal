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

        // 1. Fetch ALL deudas first, since we calculate saldo_pendiente in JS
        const { data: deudasData, error: deudasError } = await supabaseClient
            .from('deudas')
            .select('*')
            .eq('deudor_id', deudor_id)

        if (deudasError) throw deudasError

        const deudas = deudasData || []

        // 2. Fetch detalles para saber monto pagado
        const deudasIds = deudas.map((d: any) => d.id)
        
        let detalles: any[] = []
        if (deudasIds.length > 0) {
            const { data: detallesData, error: detallesError } = await supabaseClient
                .from('detalle_pagos')
                .select('*')
                .in('deuda_id', deudasIds)
            if (detallesError) throw detallesError
            detalles = detallesData || []
        }

        // 3. Evaluar saldos
        let totalOwnerOwesDebtor = 0
        let totalDebtorOwesOwner = 0

        deudas.forEach((deuda: any) => {
            let montoPagado = 0
            const misDetalles = detalles.filter((det: any) => det.deuda_id === deuda.id)
            misDetalles.forEach((det: any) => {
                montoPagado += det.monto_asignado
            })
            
            deuda.monto_pagado = montoPagado
            deuda.saldo_pendiente = deuda.monto - montoPagado

            // Si es_mi_deuda (Owner owes Debtor)
            if (deuda.es_mi_deuda) {
                totalOwnerOwesDebtor += deuda.saldo_pendiente
            } else {
                totalDebtorOwesOwner += deuda.saldo_pendiente
            }
        })

        // Identificar "Yo debo" y "Me deben" según el POV
        let totalYoDebo = 0
        let totalMeDeben = 0

        if (pov === 'owner') {
             totalYoDebo = totalOwnerOwesDebtor
             totalMeDeben = totalDebtorOwesOwner
        } else {
             // POV Debtor
             totalYoDebo = totalDebtorOwesOwner
             totalMeDeben = totalOwnerOwesDebtor
        }

        // Calcular compensación ideal
        const montoIdealACruzar = Math.min(totalYoDebo, totalMeDeben)

        // Filtrar solo las deudas pendientes
        const deudasPendientes = deudas.filter((d: any) => d.saldo_pendiente > 0.01)

        // Asignar los cruces a las deudas cronológicamente
        deudasPendientes.sort((a: any, b: any) => {
             return new Date(a.fecha_gasto).getTime() - new Date(b.fecha_gasto).getTime()
        })

        let remanenteMis = montoIdealACruzar
        let remanenteSus = montoIdealACruzar

        deudasPendientes.forEach((d: any) => {
             d.cruce_sugerido = 0
             // Determinamos "de quién" es la deuda relativa al POV para hacer el match de cruces
             const isMiDeudaLocal = pov === 'owner' ? d.es_mi_deuda : !d.es_mi_deuda

             if (isMiDeudaLocal) {
                 if (remanenteMis > 0.01) {
                     const aC = Math.min(d.saldo_pendiente, remanenteMis)
                     d.cruce_sugerido = aC
                     remanenteMis -= aC
                 }
             } else {
                 if (remanenteSus > 0.01) {
                     const aC = Math.min(d.saldo_pendiente, remanenteSus)
                     d.cruce_sugerido = aC
                     remanenteSus -= aC
                 }
             }
        })
        
        // Orden final de visualización: las que tienen saldo pendiente por encima y las cruzadas abajo, y luego por fecha
        deudasPendientes.sort((a: any, b: any) => {
            const isA_crossed = (a.saldo_pendiente - a.cruce_sugerido) <= 0.01
            const isB_crossed = (b.saldo_pendiente - b.cruce_sugerido) <= 0.01

            if (!isA_crossed && isB_crossed) return -1
            if (isA_crossed && !isB_crossed) return 1

            return new Date(b.fecha_gasto).getTime() - new Date(a.fecha_gasto).getTime()
        })

        // 4. Saldo a favor (remanente de pagos que sobró)
        const { data: pagosData, error: pagosError } = await supabaseClient
            .from('pagos')
            .select('*')
            .eq('deudor_id', deudor_id)
        if (pagosError) throw pagosError

        const pagos = pagosData || []
        
        const { data: todosDetallesData, error: todosDetallesError } = await supabaseClient
            .from('detalle_pagos')
            .select('pago_id, monto_asignado')
        if (todosDetallesError) throw todosDetallesError
        const todosDetalles = todosDetallesData || []

        let saldoFavorDebtor = 0
        let saldoFavorOwner = 0

        pagos.forEach((p: any) => {
             if (p.es_compensacion) return
             
             let asignado = 0
             const relDetalles = todosDetalles.filter((det: any) => det.pago_id === p.id)
             relDetalles.forEach((det: any) => {
                  asignado += det.monto_asignado
             })

             const sobrante = p.monto_total - asignado
             if (sobrante > 0.01) {
                  if (p.es_mi_pago) {
                       saldoFavorOwner += sobrante
                  } else {
                       saldoFavorDebtor += sobrante
                  }
             }
        })

        let miSaldoFavor = pov === 'owner' ? saldoFavorOwner : saldoFavorDebtor
        let suSaldoFavor = pov === 'owner' ? saldoFavorDebtor : saldoFavorOwner
        
        const total_deuda = totalMeDeben - totalYoDebo // Positivo: te deben, Negativo: tú debes

        const respuesta = {
            resumen: {
                total_deuda: total_deuda,
                monto_ideal_a_cruzar: montoIdealACruzar,
                saldo_favor: miSaldoFavor
            },
            deudas_pendientes: deudasPendientes.map((d: any) => ({
                id: d.id,
                titulo: d.titulo,
                monto_original: d.monto,
                monto_pagado: d.monto_pagado,
                saldo_pendiente: d.saldo_pendiente,
                es_tu_deuda: pov === 'owner' ? d.es_mi_deuda : !d.es_mi_deuda,
                fecha_gasto: d.fecha_gasto,
                cruce_sugerido: d.cruce_sugerido
            }))
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
