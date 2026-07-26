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

        // 3. Saldo a favor: pagos cuyo monto_total no quedó asignado por completo.
        //    Es dinero YA entregado, así que abona automáticamente las deudas de quien
        //    lo entregó (ver paso 5). Se calcula antes que los totales.
        const { data: pagosData, error: pagosError } = await supabaseClient
            .from('pagos')
            .select('*')
            .eq('deudor_id', deudor_id)
        if (pagosError) throw pagosError

        const pagos = pagosData || []
        const pagosIds = pagos.map((p: any) => p.id)

        let todosDetalles: any[] = []
        if (pagosIds.length > 0) {
            const { data: todosDetallesData, error: todosDetallesError } = await supabaseClient
                .from('detalle_pagos')
                .select('pago_id, monto_asignado')
                .in('pago_id', pagosIds)
            if (todosDetallesError) throw todosDetallesError
            todosDetalles = todosDetallesData || []
        }

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

        // 4. Evaluar saldos por deuda (solo con lo asignado en detalle_pagos)
        deudas.forEach((deuda: any) => {
            let montoPagado = 0
            const misDetalles = detalles.filter((det: any) => det.deuda_id === deuda.id)
            misDetalles.forEach((det: any) => {
                montoPagado += det.monto_asignado
            })

            deuda.monto_pagado = montoPagado
            deuda.saldo_pendiente = deuda.monto - montoPagado
            deuda.abono_saldo_favor = 0
        })

        // 5. Abonar el saldo a favor de cada parte a SUS deudas, de la más antigua a la
        //    más reciente. El crédito del dueño (pagó de más) cubre las deudas que el
        //    dueño tiene (es_mi_deuda), y el del deudor cubre las que le debe al dueño.
        const porFecha = deudas
            .filter((d: any) => d.saldo_pendiente > 0.01)
            .sort((a: any, b: any) =>
                new Date(a.fecha_gasto).getTime() - new Date(b.fecha_gasto).getTime())

        let creditoOwner = saldoFavorOwner
        let creditoDebtor = saldoFavorDebtor

        porFecha.forEach((d: any) => {
            const disponible = d.es_mi_deuda ? creditoOwner : creditoDebtor
            if (disponible <= 0.01) return

            const abono = Math.min(d.saldo_pendiente, disponible)
            d.abono_saldo_favor = abono
            if (d.es_mi_deuda) creditoOwner -= abono
            else creditoDebtor -= abono
        })

        // Remanente de crédito que no alcanzó a cubrir ninguna deuda
        const remanenteFavorOwner = Math.round(creditoOwner * 100) / 100
        const remanenteFavorDebtor = Math.round(creditoDebtor * 100) / 100

        // 6. Totales sobre el saldo REAL (pendiente − saldo a favor ya abonado)
        let totalOwnerOwesDebtor = 0
        let totalDebtorOwesOwner = 0

        deudas.forEach((deuda: any) => {
            const saldoReal = deuda.saldo_pendiente - deuda.abono_saldo_favor
            if (deuda.es_mi_deuda) {
                totalOwnerOwesDebtor += saldoReal
            } else {
                totalDebtorOwesOwner += saldoReal
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

        // 7. Compensación ideal: se calcula sobre lo que queda REALMENTE debido, es decir
        //    después de aplicar el saldo a favor.
        const montoIdealACruzar = Math.min(totalYoDebo, totalMeDeben)

        // Filtrar solo las deudas pendientes. Una deuda cubierta por completo con saldo a
        // favor SIGUE en la lista (aparece tachada, igual que una cruzada) para que se vea
        // de dónde salió el abono.
        const deudasPendientes = deudas.filter((d: any) => d.saldo_pendiente > 0.01)

        // Asignar los cruces a las deudas cronológicamente
        deudasPendientes.sort((a: any, b: any) => {
             return new Date(a.fecha_gasto).getTime() - new Date(b.fecha_gasto).getTime()
        })

        let remanenteMis = montoIdealACruzar
        let remanenteSus = montoIdealACruzar

        deudasPendientes.forEach((d: any) => {
             d.cruce_sugerido = 0
             // El cruce solo puede tomar lo que el saldo a favor no cubrió ya.
             const saldoCruzable = d.saldo_pendiente - d.abono_saldo_favor
             if (saldoCruzable <= 0.01) return

             // Determinamos "de quién" es la deuda relativa al POV para hacer el match de cruces
             const isMiDeudaLocal = pov === 'owner' ? d.es_mi_deuda : !d.es_mi_deuda

             if (isMiDeudaLocal) {
                 if (remanenteMis > 0.01) {
                     const aC = Math.min(saldoCruzable, remanenteMis)
                     d.cruce_sugerido = aC
                     remanenteMis -= aC
                 }
             } else {
                 if (remanenteSus > 0.01) {
                     const aC = Math.min(saldoCruzable, remanenteSus)
                     d.cruce_sugerido = aC
                     remanenteSus -= aC
                 }
             }
        })

        // Orden final de visualización: las que tienen saldo real por encima y las ya
        // saldadas (por cruce o por saldo a favor) abajo, y luego por fecha
        const saldoReal = (d: any) => d.saldo_pendiente - d.cruce_sugerido - d.abono_saldo_favor
        deudasPendientes.sort((a: any, b: any) => {
            const isA_crossed = saldoReal(a) <= 0.01
            const isB_crossed = saldoReal(b) <= 0.01

            if (!isA_crossed && isB_crossed) return -1
            if (isA_crossed && !isB_crossed) return 1

            return new Date(b.fecha_gasto).getTime() - new Date(a.fecha_gasto).getTime()
        })

        // 8. Saldo a favor que quedó SIN abonar a ninguna deuda (crédito real vigente)
        const miSaldoFavor = pov === 'owner' ? remanenteFavorOwner : remanenteFavorDebtor
        const suSaldoFavor = pov === 'owner' ? remanenteFavorDebtor : remanenteFavorOwner

        // Positivo: te deben, Negativo: tú debes.
        // Los remanentes de saldo a favor son deuda pura: lo que pagué de más me lo deben,
        // lo que pagó de más se lo debo. Con esto total_deuda coincide con el último
        // saldo acumulado del historial (get_historial).
        const total_deuda = Math.round(
            (totalMeDeben - totalYoDebo + miSaldoFavor - suSaldoFavor) * 100
        ) / 100

        const respuesta = {
            resumen: {
                total_deuda: total_deuda,
                monto_ideal_a_cruzar: montoIdealACruzar,
                saldo_favor: miSaldoFavor,
                su_saldo_favor: suSaldoFavor
            },
            deudas_pendientes: deudasPendientes.map((d: any) => ({
                id: d.id,
                titulo: d.titulo,
                monto_original: d.monto,
                monto_pagado: d.monto_pagado,
                saldo_pendiente: d.saldo_pendiente,
                // Parte del saldo_pendiente ya cubierta con dinero entregado pero sin
                // asignar (saldo a favor). El saldo REAL es:
                //   saldo_pendiente − cruce_sugerido − abono_saldo_favor
                abono_saldo_favor: Math.round(d.abono_saldo_favor * 100) / 100,
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
