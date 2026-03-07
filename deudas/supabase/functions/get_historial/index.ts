import { serve } from "https://deno.land/std@0.177.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.3"

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { deudor_id, pov = 'debtor' } = await req.json()

    if (!deudor_id) {
      throw new Error('Missing deudor_id')
    }

    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_ANON_KEY') ?? ''
    )

    // 1. Fetch deudas
    const { data: deudasData, error: deudasError } = await supabaseClient
      .from('deudas')
      .select('id, titulo, monto, es_mi_deuda, fecha_gasto, created_at')
      .eq('deudor_id', deudor_id)

    if (deudasError) throw deudasError

    // 2. Fetch pagos con detalles
    const { data: pagosData, error: pagosError } = await supabaseClient
      .from('pagos')
      .select(`
        id, monto_total, es_mi_pago, fecha_pago, es_compensacion, created_at,
        detalle_pagos (monto_asignado, deudas(titulo, es_mi_deuda))
      `)
      .eq('deudor_id', deudor_id)

    if (pagosError) throw pagosError

    // 3. Procesar montos pagados por deuda
    const pagosPorDeuda: Record<string, number> = {}
    pagosData?.forEach(pago => {
      pago.detalle_pagos?.forEach((det: any) => {
        // En este mock simplificado, si tuvieras el deuda_id en el detach, lo sumarias.
        // Dado que la query trae deudas(...), necesitamos el ID de la deuda (no pedido arriba pero necesario).
        // Si no está, lo asociaremos genéricamente, o deberíamos pedirlo.
      })
    })

    // Corregimos la query para pedir deuda_id en detalles
    const { data: pagosFullData, error: pagosFullError } = await supabaseClient
      .from('pagos')
      .select(`
        id, monto_total, es_mi_pago, fecha_pago, es_compensacion, created_at,
        detalle_pagos (monto_asignado, deuda_id, deudas(titulo, es_mi_deuda))
      `)
      .eq('deudor_id', deudor_id)
      
    if (pagosFullError) throw pagosFullError

    const montoPagadoPorDeuda: Record<string, number> = {}
    pagosFullData?.forEach(pago => {
      pago.detalle_pagos?.forEach((det: any) => {
        if (!montoPagadoPorDeuda[det.deuda_id]) montoPagadoPorDeuda[det.deuda_id] = 0;
        montoPagadoPorDeuda[det.deuda_id] += det.monto_asignado;
      })
    })

    let history: any[] = []

    deudasData?.forEach(d => {
      history.push({
        id: d.id,
        type: 'deuda',
        date: d.fecha_gasto,
        createdAt: new Date(d.created_at).getTime(),
        title: d.titulo,
        amount: d.monto,
        esMiDeuda: d.es_mi_deuda,
        montoPagado: montoPagadoPorDeuda[d.id] || 0
      })
    })

    pagosFullData?.forEach(p => {
      let title = 'Cruce de cuentas'
      if (!p.es_compensacion) {
          if (pov === 'owner') {
             title = p.es_mi_pago ? 'Pago entregado por ti' : 'Pago recibido'
          } else {
             title = p.es_mi_pago ? 'Pago recibido' : 'Pago entregado por ti'
          }
      }

      history.push({
        id: p.id,
        type: 'pago',
        date: p.fecha_pago,
        createdAt: new Date(p.created_at).getTime(),
        title: title,
        amount: p.monto_total,
        esMiPago: p.es_mi_pago,
        esCompensacion: p.es_compensacion,
        detalles: p.detalle_pagos || []
      })
    })

    // Sort Ascending (Oldest First)
    history.sort((a, b) => a.createdAt - b.createdAt)

    // Calculate Running Balance
    let balance = 0
    history.forEach(item => {
      if (item.type === 'deuda') {
        if (item.esMiDeuda) balance -= item.amount;
        else balance += item.amount;
      } else if (!item.esCompensacion) { 
        if (item.esMiPago) balance += item.amount;
        else balance -= item.amount;
      }
      item.balance = balance;
    })

    const deudaItems = new Map<string, any>()
    history.forEach(item => {
      if (item.type === 'deuda') deudaItems.set(item.id, item)
    })

    // Agrupar Pagos y sus Cruces adyacentes estrictamente por tiempo
    let pagosHistory = history.filter(h => h.type === 'pago') // ASC (Chronological)
    let logicalPagos: any[] = []
    
    for (let i = 0; i < pagosHistory.length; i++) {
        let curr = pagosHistory[i]
        let bundle = [curr]
        let j = i + 1
        
        while (j < pagosHistory.length) {
            let next = pagosHistory[j]
            // Agrupar si ocurrieron con menos de 2 segundos de diferencia (Cruce + Pago manual)
            if (Math.abs(next.createdAt - curr.createdAt) < 2000) {
                bundle.push(next)
                j++
            } else {
                break
            }
        }
        
        let assignedIds = new Set<string>()
        let cruceAmount = 0
        let cruceDetails: any[] = []

        bundle.forEach(p => {
             if (p.esCompensacion) {
                 cruceAmount += p.amount
                 if (p.detalles) cruceDetails.push(...p.detalles)
             }
             if (p.detalles) {
                 p.detalles.forEach((d:any) => { if(d.deuda_id) assignedIds.add(d.deuda_id) })
             }
        })

        // Anotar cruce logic en el pago manual principal
        let mainPago = bundle.find(p => !p.esCompensacion)
        if (mainPago && cruceAmount > 0) {
             mainPago.linkedCruceAmount = cruceAmount
             mainPago.linkedCruceDetails = cruceDetails
        } else if (!mainPago && bundle.length > 0) {
             // Es un cruce solitario sin pago manual asociado
             mainPago = bundle[0]
             mainPago.linkedCruceAmount = cruceAmount
             mainPago.linkedCruceDetails = cruceDetails
        }

        let deudas = Array.from(assignedIds).map(id => deudaItems.get(id)).filter(Boolean)

        logicalPagos.push({
             pagos: bundle,
             deudas: deudas,
             saldoPosterior: bundle[bundle.length - 1].balance
        })

        i = j - 1
    }

    let mergedGroups: any[] = []

    for (let lp of logicalPagos) {
        let matchingGroupIndices: number[] = []
        
        for (let i = 0; i < mergedGroups.length; i++) {
            let mg = mergedGroups[i]
            let sharesDebt = lp.deudas.some((d1: any) => mg.deudaMap.has(d1.id))
            if (sharesDebt) {
                matchingGroupIndices.push(i)
            }
        }

        let newDeudasMap = new Map<string, any>()
        lp.deudas.forEach((d: any) => newDeudasMap.set(d.id, d))

        if (matchingGroupIndices.length === 0) {
            mergedGroups.push({
                pagos: [...lp.pagos],
                deudaMap: newDeudasMap
            })
        } else {
            let targetGroup = mergedGroups[matchingGroupIndices[0]]
            
            lp.deudas.forEach((d: any) => targetGroup.deudaMap.set(d.id, d))
            targetGroup.pagos.push(...lp.pagos)

            for (let i = 1; i < matchingGroupIndices.length; i++) {
                let otherGroup = mergedGroups[matchingGroupIndices[i]]
                for (let [id, d] of otherGroup.deudaMap.entries()) {
                    targetGroup.deudaMap.set(id, d)
                }
                targetGroup.pagos.push(...otherGroup.pagos)
            }
            
            for (let i = matchingGroupIndices.length - 1; i >= 1; i--) {
                mergedGroups.splice(matchingGroupIndices[i], 1)
            }
        }
    }

    let groupedData = mergedGroups.map(mg => {
        let deudas = Array.from(mg.deudaMap.values())
        let allPagos = mg.pagos

        // Separar cruces de manuales
        let manualPagos = allPagos.filter((p: any) => !p.esCompensacion)
        let cruces = allPagos.filter((p: any) => p.esCompensacion)

        // Si no hay pagos manuales pero sí hay cruces (grupo solo de cruces)
        // Dejaremos 1 cruce principal en pagos manuales para que la UI renderice la tarjeta de transacción
        if (manualPagos.length === 0 && cruces.length > 0) {
            manualPagos.push(cruces[0])
            cruces = cruces.slice(1)
        }

        let totalDeudas = 0
        deudas.forEach((d: any) => {
            if (pov === 'owner') {
                if (d.esMiDeuda) totalDeudas -= d.amount
                else totalDeudas += d.amount
            } else {
                if (d.esMiDeuda) totalDeudas += d.amount
                else totalDeudas -= d.amount
            }
        })

        let totalPagos = 0
        manualPagos.forEach((p: any) => {
             if (!p.esCompensacion) {
                 if (pov === 'owner') {
                     if (p.esMiPago) totalPagos -= p.amount
                     else totalPagos += p.amount
                 } else {
                     if (p.esMiPago) totalPagos += p.amount
                     else totalPagos -= p.amount
                 }
             }
        })

        let saldoPosteriorLocal = totalDeudas - totalPagos
        
        // Sorting items from newest to oldest for display
        const descSort = (a: any, b: any) => {
             let tA = new Date(a.date).getTime()
             let tB = new Date(b.date).getTime()
             if (tA === tB) return b.createdAt - a.createdAt
             return tB - tA
        }
        manualPagos.sort(descSort)
        deudas.sort(descSort)

        // Asignar los "saldos" progresivos visuales de cada item usando orden cronológico (fecha semántica > createdAt)
        let currentVisualBalance = 0
        let progressiveItems = [...manualPagos, ...deudas].sort((a: any, b: any) => {
             let tA = new Date(a.date).getTime()
             let tB = new Date(b.date).getTime()
             if (tA === tB) return a.createdAt - b.createdAt
             return tA - tB
        })
        
        progressiveItems.forEach((item: any) => {
             if (item.type === 'pago') {
                 let effect = 0
                 if (pov === 'owner') {
                     effect = item.esMiPago ? item.amount : -item.amount
                 } else {
                     effect = item.esMiPago ? -item.amount : item.amount
                 }
                 currentVisualBalance += effect
             } else {
                 let effect = 0
                 if (pov === 'owner') {
                     effect = item.esMiDeuda ? -item.amount : item.amount
                 } else {
                     effect = item.esMiDeuda ? item.amount : -item.amount
                 }
                 currentVisualBalance += effect
             }
             item.balance = pov === 'debtor' ? -currentVisualBalance : currentVisualBalance
        })

        return {
             pagos: manualPagos, 
             cruces: cruces, // los mandamos aparte como solicitaste
             deudas: deudas,
             totalDeudas: totalDeudas,
             totalPagos: totalPagos,
             saldoAnterior: 0,
             saldoPosterior: pov === 'debtor' ? -saldoPosteriorLocal : saldoPosteriorLocal
        }
    })

    // Sort final groups newest first
    groupedData.sort((a, b) => {
        let maxA = a.pagos.length > 0 ? a.pagos[0].createdAt : 0
        let maxB = b.pagos.length > 0 ? b.pagos[0].createdAt : 0
        return maxB - maxA
    })

    return new Response(JSON.stringify(groupedData), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 200,
    })
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      status: 400,
    })
  }
})
