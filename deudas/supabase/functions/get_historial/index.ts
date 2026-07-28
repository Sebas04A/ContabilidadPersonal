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
        id, monto_total, es_mi_pago, fecha_pago, es_compensacion, created_at, cruce_id,
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
        cruceId: p.cruce_id,
        detalles: p.detalle_pagos || []
      })
    })

    // Las deudas ordenan el historial: por su fecha, y `created_at` desempata dentro del
    // día (`fecha_gasto` es DATE, así que una tarde entera de deudas empata).
    const deudasAsc = history.filter(h => h.type === 'deuda').sort((a, b) => {
      const fa = String(a.date ?? '')
      const fb = String(b.date ?? '')
      if (fa !== fb) return fa < fb ? -1 : 1
      return a.createdAt - b.createdAt
    })
    const posDeuda = new Map<string, number>()
    deudasAsc.forEach((d, i) => posDeuda.set(d.id, i))

    const deudaById = new Map<string, any>()
    deudasData?.forEach(d => deudaById.set(d.id, d))

    // --- Bundle de cruces (compensaciones) en el pago adyacente ---
    // Los dos pagos virtuales de un cruce comparten `cruce_id`, así que se agrupan por
    // ese id. Para los cruces viejos (anteriores a la columna) queda el heurístico de
    // siempre: pagos creados con menos de 2 segundos de diferencia.
    // Se recorren por instante, y el cruce antes que su pago físico (comparten
    // `created_at`: `registrar_pago` los escribe en la misma transacción).
    const pagosHistory = history.filter(h => h.type === 'pago').sort((a, b) => {
        if (a.createdAt !== b.createdAt) return a.createdAt - b.createdAt
        return (a.esCompensacion ? 0 : 1) - (b.esCompensacion ? 0 : 1)
    })
    const displayPagos: any[] = []
    const usados = new Set<string>()

    for (const curr of pagosHistory) {
        if (usados.has(curr.id)) continue

        const bundle = [curr]
        for (const p of pagosHistory) {
            if (p === curr || usados.has(p.id) || bundle.includes(p)) continue
            // El otro lado del mismo cruce.
            const mismoCruce = !!curr.cruceId && p.cruceId === curr.cruceId
            // El pago físico que disparó el cruce: no lleva cruce_id, se reconoce porque
            // se escribió en el mismo momento.
            const mismaOperacion = curr.esCompensacion && !p.esCompensacion &&
                                   Math.abs(p.createdAt - curr.createdAt) < 2000
            // Cruces viejos, de antes de la columna: solo queda la cercanía temporal.
            const cerca = !curr.cruceId && !p.cruceId &&
                          Math.abs(p.createdAt - curr.createdAt) < 2000
            if (mismoCruce || mismaOperacion || cerca) bundle.push(p)
        }
        bundle.forEach(p => usados.add(p.id))

        // Cada lado del cruce se registra por el mismo monto: el cruce es ese monto, no
        // la suma de los dos lados.
        let cruceAmount = 0
        const cruceDetails: any[] = []
        const bundleDetalles: any[] = []
        bundle.forEach(p => {
            if (p.esCompensacion) {
                cruceAmount = Math.max(cruceAmount, p.amount)
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
    }

    // --- Dónde se coloca cada pago ---
    // Un pago NO va por su propia fecha: va justo DESPUÉS de la última deuda que pagó o
    // cruzó, que es donde se entiende su efecto. Pagar mañana lo de ayer se lee como el
    // cierre de ayer, no como un evento suelto al final. De paso, el orden deja de
    // depender del reloj de quien escribió la fila: la app manda hora local y el servidor
    // UTC, y por eso las deudas caían todas juntas debajo de los pagos.
    // El cruce ya viene fundido en su pago físico (el bundle), así que los dos se mueven
    // juntos: `detalles` trae las deudas de ambos.
    const anclaDe = (mp: any) => {
      let ancla = -1
      ;(mp.detalles || []).forEach((det: any) => {
        const p = posDeuda.get(det.deuda_id)
        if (p !== undefined && p > ancla) ancla = p
      })
      if (ancla >= 0) return ancla
      // No abonó a ninguna deuda (quedó como saldo a favor): ahí sí manda su fecha.
      let ultima = -1
      deudasAsc.forEach((d, i) => {
        if (String(d.date ?? '') <= String(mp.date ?? '')) ultima = i
      })
      return ultima
    }

    const pagosPorAncla = new Map<number, any[]>()
    displayPagos.forEach(mp => {
      const ancla = anclaDe(mp)
      const enEsaAncla = pagosPorAncla.get(ancla) ?? []
      enEsaAncla.push(mp)
      pagosPorAncla.set(ancla, enEsaAncla)
    })
    // Varios pagos sobre la misma deuda: entre ellos sí manda el orden en que se hicieron.
    const pagosDe = (i: number) => (pagosPorAncla.get(i) ?? []).sort((a, b) => {
      const fa = String(a.date ?? '')
      const fb = String(b.date ?? '')
      if (fa !== fb) return fa < fb ? -1 : 1
      return a.createdAt - b.createdAt
    })

    // Secuencia ascendente (pasado → presente) tal como se va a leer.
    const asc: any[] = [...pagosDe(-1)]
    deudasAsc.forEach((d, i) => {
      asc.push(d)
      asc.push(...pagosDe(i))
    })

    // Saldo acumulado GLOBAL (perspectiva 'owner'): + te deben, − tú debes. Se acumula en
    // ese mismo orden, así el saldo de cada fila es el que se lee en pantalla.
    let balance = 0
    asc.forEach(item => {
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

    // --- Parciales: deudas que quedan PARCIALMENTE cubiertas tras cada pago ---
    const cumPaid: Record<string, number> = {}
    asc.filter(h => h.type === 'pago').forEach(mp => {
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

    // --- Lista plana, presente → pasado ---
    const flat = [...asc].reverse()

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
