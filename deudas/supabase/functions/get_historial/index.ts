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

    // 2. Fetch pagos con detalles (incluye deuda_id para asignaciones)
    const { data: pagosFullData, error: pagosFullError } = await supabaseClient
      .from('pagos')
      .select(`
        id, monto_total, es_mi_pago, fecha_pago, es_compensacion, created_at,
        detalle_pagos (monto_asignado, deuda_id, deudas(titulo, es_mi_deuda))
      `)
      .eq('deudor_id', deudor_id)

    if (pagosFullError) throw pagosFullError

    // 3. Monto total pagado por deuda (para mostrar progreso en cada deuda)
    const montoPagadoPorDeuda: Record<string, number> = {}
    pagosFullData?.forEach(pago => {
      pago.detalle_pagos?.forEach((det: any) => {
        if (!montoPagadoPorDeuda[det.deuda_id]) montoPagadoPorDeuda[det.deuda_id] = 0
        montoPagadoPorDeuda[det.deuda_id] += det.monto_asignado
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

    // Orden cronológico ascendente (más antiguo primero) para el saldo acumulado
    history.sort((a, b) => a.createdAt - b.createdAt)

    // Saldo acumulado GLOBAL (perspectiva 'owner'): + te deben, − tú debes.
    let balance = 0
    history.forEach(item => {
      if (item.type === 'deuda') {
        if (item.esMiDeuda) balance -= item.amount
        else balance += item.amount
      } else if (!item.esCompensacion) {
        if (item.esMiPago) balance += item.amount
        else balance -= item.amount
      }
      item.balance = balance
    })
    // NOTA: item.balance queda SIEMPRE en perspectiva 'owner' (+ te deben, − tú debes).
    // Cada cliente aplica su POV: la app (owner) lo usa directo; el visor (debtor) lo niega.

    const deudaById = new Map<string, any>()
    deudasData?.forEach(d => deudaById.set(d.id, d))

    // --- Bundle de cruces (compensaciones) en el pago manual adyacente (<2s) ---
    // Se preserva la lógica de cruces: cada bundle deja un "pago principal" que
    // arrastra el cruce (linkedCruce*) y combina los detalles de asignación.
    const pagosHistory = history.filter(h => h.type === 'pago') // ASC cronológico
    const displayPagos: any[] = []
    for (let i = 0; i < pagosHistory.length; i++) {
        const curr = pagosHistory[i]
        const bundle = [curr]
        let j = i + 1
        while (j < pagosHistory.length && Math.abs(pagosHistory[j].createdAt - curr.createdAt) < 2000) {
            bundle.push(pagosHistory[j]); j++
        }

        let cruceAmount = 0
        const cruceDetails: any[] = []
        const bundleDetalles: any[] = []
        bundle.forEach(p => {
            if (p.esCompensacion) {
                cruceAmount += p.amount
                if (p.detalles) cruceDetails.push(...p.detalles)
            }
            if (p.detalles) bundleDetalles.push(...p.detalles)
        })

        const mainPago = bundle.find(p => !p.esCompensacion) || bundle[0]
        if (!mainPago.esCompensacion && cruceAmount > 0) {
            mainPago.linkedCruceAmount = cruceAmount
            mainPago.linkedCruceDetails = cruceDetails
        }
        // Detalles combinados del bundle (a qué deudas fue el pago; para parciales y UI)
        mainPago.detalles = bundleDetalles
        displayPagos.push(mainPago)
        i = j - 1
    }

    // --- Parciales: deudas que quedan PARCIALMENTE cubiertas tras cada pago ---
    // displayPagos está en orden cronológico ascendente (por construcción del bundle).
    const cumPaid: Record<string, number> = {}
    displayPagos.forEach(mp => {
        ;(mp.detalles || []).forEach((det: any) => {
            if (det.deuda_id == null) return
            cumPaid[det.deuda_id] = (cumPaid[det.deuda_id] || 0) + (det.monto_asignado || 0)
        })
        const seen = new Set<string>()
        const parciales: any[] = []
        ;(mp.detalles || []).forEach((det: any) => {
            const did = det.deuda_id
            if (did == null || seen.has(did)) return
            seen.add(did)
            const d = deudaById.get(did)
            if (!d) return
            const orig = d.monto
            const pagado = Math.round(cumPaid[did] * 100) / 100
            const saldo = Math.round((orig - pagado) * 100) / 100
            if (pagado > 0.01 && saldo > 0.01) {
                parciales.push({
                    deuda_id: did, titulo: d.titulo,
                    monto_original: orig, pagado_acumulado: pagado, saldo,
                })
            }
        })
        mp.parciales = parciales
    })

    // --- Lista plana cronológica DESCENDENTE (presente → pasado) ---
    // El pago, al tener fecha posterior a las deudas que abonó, queda ARRIBA de ellas.
    const flat = [...displayPagos, ...history.filter(h => h.type === 'deuda')]
    flat.sort((a, b) => {
        const tA = new Date(a.date).getTime()
        const tB = new Date(b.date).getTime()
        if (tA === tB) return b.createdAt - a.createdAt
        return tB - tA
    })

    return new Response(JSON.stringify(flat), {
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
