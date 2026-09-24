// Estado de cuenta de un deudor.
//
// Toda la matemática (saldos, saldo a favor y cruce sugerido) vive en la función SQL
// `estado_cuenta`, que es la única definición del sistema. Esta edge solo la llama y
// adapta la respuesta al contrato que ya consumen el visor web y la app.
//
// `pago` (opcional) es el pago que la pantalla de saldar cuentas está armando con deudas
// elegidas a mano: `{ monto, es_mi_pago, deudas_ids }`. Con él la respuesta es la vista
// previa de lo que `registrar_pago` va a guardar: el pago repartido entre las elegidas y
// el cruce recalculado DESPUÉS, sobre lo que quedó.
//
// v2: este módulo es el cuerpo de la edge `get_estado_cuenta` de v1 SIN CAMBIOS; lo usan
// `get_estado_cuenta` (el dueño, con su JWT) y `visor` (el deudor, por token). Quién
// llama y con qué punto de vista lo decide cada edge, no este módulo.
//
// v2 fase 6: si la función SQL trae los datos del acuerdo (solo pasa con un deudor
// vinculado y el JWT de una de las partes), se pasan tal cual: `saldo_acordado` y
// `pendiente_acuerdo` en el resumen y `estado_acuerdo` en cada deuda. Sin vínculo no
// vienen y la respuesta es la de siempre. El visor (service_role) nunca los recibe.

import type { SupabaseClient } from 'https://esm.sh/@supabase/supabase-js@2.39.3'

export async function armarEstadoCuenta(
    supabaseClient: SupabaseClient,
    deudor_id: string,
    pov: 'owner' | 'debtor',
    pago: any = null,
) {
    // Sin pago (o sin deudas elegidas) no se manda el parámetro: la función devuelve el
    // estado de siempre, byte a byte.
    const pagoPlaneado = pago && Array.isArray(pago.deudas_ids)
        ? {
            monto: Number(pago.monto) || 0,
            es_mi_pago: pago.es_mi_pago === true,
            deudas_ids: pago.deudas_ids,
        }
        : null

    const { data, error } = await supabaseClient.rpc('estado_cuenta', {
        p_deudor_id: deudor_id,
        p_pov: pov,
        ...(pagoPlaneado ? { p_pago: pagoPlaneado } : {}),
    })
    if (error) throw error

    const resumen = data?.resumen ?? {}
    const deudas = (data?.deudas ?? []) as any[]

    // Con pago planeado, la función ya descuenta el pago de `saldo_pendiente` y
    // `monto_pagado`. La pantalla necesita verlos como están HOY para pintar el pago
    // aparte ("-$30 del pago"), así que se le devuelve lo que el pago quitó.
    const pagoDe = (d: any) => d.pago_planeado ?? 0
    const saldoHoy = (d: any) => Math.round((d.saldo_pendiente + pagoDe(d)) * 100) / 100
    const saldoReal = (d: any) =>
        d.saldo_pendiente - (d.cruce_sugerido ?? 0) - (d.abono_saldo_favor ?? 0)

    // Contrato histórico: solo las deudas con saldo pendiente, las ya saldadas por
    // cruce o por saldo a favor al final (se muestran tachadas, no desaparecen).
    const deudas_pendientes = deudas
        .filter((d: any) => saldoHoy(d) > 0.01)
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
            monto_pagado: Math.round((d.monto_pagado - pagoDe(d)) * 100) / 100,
            saldo_pendiente: saldoHoy(d),
            abono_saldo_favor: d.abono_saldo_favor,
            es_tu_deuda: d.es_tu_deuda,
            fecha_gasto: d.fecha_gasto,
            // Desempate del FIFO a igual fecha: la vista previa de la app lo necesita.
            creado: d.creado,
            cruce_sugerido: d.cruce_sugerido,
            ...(pagoPlaneado ? { pago_planeado: pagoDe(d) } : {}),
            ...(d.estado_acuerdo ? { estado_acuerdo: d.estado_acuerdo } : {}),
        }))

    const respuesta = {
        resumen: {
            total_deuda: resumen.neto ?? 0,
            monto_ideal_a_cruzar: resumen.monto_ideal_a_cruzar ?? 0,
            // Ojo: en este contrato `saldo_favor` es el crédito de QUIEN MIRA, que
            // en la función SQL se llama `saldo_favor_owner` (el del POV).
            saldo_favor: resumen.saldo_favor_owner ?? 0,
            su_saldo_favor: resumen.saldo_favor ?? 0,
            // { monto, es_mi_pago, asignado, sobrante }: el sobrante es lo que quedaría
            // como saldo a favor de quien paga.
            ...(pagoPlaneado ? { pago_planeado: resumen.pago_planeado } : {}),
            ...('saldo_acordado' in resumen
                ? { saldo_acordado: resumen.saldo_acordado,
                    pendiente_acuerdo: resumen.pendiente_acuerdo }
                : {}),
        },
        deudas_pendientes,
    }

    return respuesta
}
