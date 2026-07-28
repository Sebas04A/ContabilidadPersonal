-- Fuente única de lectura del estado de cuenta.
--
-- Toda la matemática de deudas vivía repetida en cuatro sitios (Dart, la edge, reading.py
-- y el visor) y ya divergían entre sí. Esta función es la definición: el resto pasa a ser
-- un wrapper.
--
-- Convención de signo (POV dueño): `+ te deben`, `− tú debes`.
--   1. Por deuda: saldo_pendiente = monto − Σ detalle_pagos.
--   2. Saldo a favor = dinero entregado que no se asignó a ninguna deuda. Es crédito de
--      quien pagó, así que cubre SUS deudas, de la más antigua a la más reciente.
--   3. saldo_real = saldo_pendiente − abono_saldo_favor: lo que se debe de verdad.
--   4. Cruce sugerido = min(Σ te deben, Σ tú debes) sobre el saldo_real, emparejado FIFO.
--      Es derivado: NO se escribe nada. Es lo que se podría cruzar hoy.

DROP FUNCTION IF EXISTS estado_cuenta(UUID, TEXT);

CREATE OR REPLACE FUNCTION estado_cuenta(p_deudor_id UUID, p_pov TEXT DEFAULT 'owner')
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_favor_owner   NUMERIC := 0;   -- crédito del dueño (pagó de más)
    v_favor_debtor  NUMERIC := 0;   -- crédito del deudor
    v_credito       NUMERIC;
    v_abono         NUMERIC;
    v_total_te_deben NUMERIC := 0;
    v_total_tu_debes NUMERIC := 0;
    v_neto          NUMERIC;
    v_cruzable      NUMERIC;
    v_restante      NUMERIC;
    v_signo         INT := CASE WHEN p_pov = 'owner' THEN 1 ELSE -1 END;
    r               RECORD;
    v_out           JSONB;
BEGIN
    DROP TABLE IF EXISTS _ec_deudas;
    CREATE TEMP TABLE _ec_deudas AS
    SELECT d.id,
           d.titulo,
           d.fecha_gasto,
           d.es_mi_deuda,
           d.monto::NUMERIC                                   AS monto_original,
           COALESCE(SUM(dp.monto_asignado), 0)::NUMERIC        AS monto_pagado,
           GREATEST(d.monto - COALESCE(SUM(dp.monto_asignado), 0), 0)::NUMERIC
                                                               AS saldo_pendiente,
           0::NUMERIC                                          AS abono_saldo_favor,
           0::NUMERIC                                          AS saldo_real,
           0::NUMERIC                                          AS cruce_sugerido
    FROM deudas d
    LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
    WHERE d.deudor_id = p_deudor_id
    GROUP BY d.id;

    -- 2. Saldo a favor de cada parte: sobrante de los pagos reales (los cruces no cuentan).
    SELECT COALESCE(SUM(sobrante) FILTER (WHERE es_mi_pago), 0),
           COALESCE(SUM(sobrante) FILTER (WHERE NOT es_mi_pago), 0)
      INTO v_favor_owner, v_favor_debtor
    FROM (
        SELECT p.es_mi_pago,
               p.monto_total - COALESCE(SUM(dp.monto_asignado), 0) AS sobrante
        FROM pagos p
        LEFT JOIN detalle_pagos dp ON dp.pago_id = p.id
        WHERE p.deudor_id = p_deudor_id AND NOT COALESCE(p.es_compensacion, FALSE)
        GROUP BY p.id, p.es_mi_pago, p.monto_total
    ) s
    WHERE sobrante > 0.01;

    -- Ese crédito abona las deudas de quien pagó, de la más antigua a la más reciente.
    FOR r IN SELECT id, es_mi_deuda, saldo_pendiente FROM _ec_deudas
             WHERE saldo_pendiente > 0.01 ORDER BY fecha_gasto, id
    LOOP
        v_credito := CASE WHEN r.es_mi_deuda THEN v_favor_owner ELSE v_favor_debtor END;
        CONTINUE WHEN v_credito <= 0.01;

        v_abono := LEAST(r.saldo_pendiente, v_credito);
        UPDATE _ec_deudas SET abono_saldo_favor = v_abono WHERE id = r.id;

        IF r.es_mi_deuda THEN
            v_favor_owner := v_favor_owner - v_abono;
        ELSE
            v_favor_debtor := v_favor_debtor - v_abono;
        END IF;
    END LOOP;

    -- El WHERE es obligatorio aunque toque todas las filas: la API de Supabase corre con
    -- pg_safeupdate, que aborta cualquier UPDATE sin cláusula WHERE.
    UPDATE _ec_deudas SET saldo_real = ROUND(saldo_pendiente - abono_saldo_favor, 2)
    WHERE TRUE;

    SELECT COALESCE(SUM(saldo_real) FILTER (WHERE NOT es_mi_deuda), 0),
           COALESCE(SUM(saldo_real) FILTER (WHERE es_mi_deuda), 0)
      INTO v_total_te_deben, v_total_tu_debes
    FROM _ec_deudas;

    -- El crédito que no alcanzó a abonar ninguna deuda es deuda pura: lo que el deudor
    -- pagó de más se lo debes, lo que pagaste de más te lo debe.
    v_neto := ROUND(v_total_te_deben - v_total_tu_debes
                    - v_favor_debtor + v_favor_owner, 2);

    -- 4. Cruce sugerido: se compensa el solapamiento, FIFO en cada lado.
    v_cruzable := ROUND(LEAST(v_total_te_deben, v_total_tu_debes), 2);

    IF v_cruzable > 0.01 THEN
        -- lado "te deben"
        v_restante := v_cruzable;
        FOR r IN SELECT id, saldo_real FROM _ec_deudas
                 WHERE NOT es_mi_deuda AND saldo_real > 0.01 ORDER BY fecha_gasto, id
        LOOP
            EXIT WHEN v_restante <= 0.01;
            v_abono := LEAST(r.saldo_real, v_restante);
            UPDATE _ec_deudas SET cruce_sugerido = v_abono WHERE id = r.id;
            v_restante := v_restante - v_abono;
        END LOOP;

        -- lado "tú debes"
        v_restante := v_cruzable;
        FOR r IN SELECT id, saldo_real FROM _ec_deudas
                 WHERE es_mi_deuda AND saldo_real > 0.01 ORDER BY fecha_gasto, id
        LOOP
            EXIT WHEN v_restante <= 0.01;
            v_abono := LEAST(r.saldo_real, v_restante);
            UPDATE _ec_deudas SET cruce_sugerido = v_abono WHERE id = r.id;
            v_restante := v_restante - v_abono;
        END LOOP;
    END IF;

    SELECT jsonb_build_object(
        'deudas', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'id', id,
                'titulo', titulo,
                'fecha_gasto', fecha_gasto,
                'monto_original', ROUND(monto_original, 2),
                'monto_pagado', ROUND(monto_pagado, 2),
                'saldo_pendiente', ROUND(saldo_pendiente, 2),
                'abono_saldo_favor', ROUND(abono_saldo_favor, 2),
                'saldo_real', ROUND(saldo_real, 2),
                'cruce_sugerido', ROUND(cruce_sugerido, 2),
                -- El POV del deudor ve las deudas al revés que el dueño.
                'es_tu_deuda', CASE WHEN p_pov = 'owner' THEN es_mi_deuda ELSE NOT es_mi_deuda END,
                'estado', CASE
                    WHEN saldo_real <= 0.01 THEN 'PAGADA'
                    WHEN monto_pagado > 0.01 OR abono_saldo_favor > 0.01 THEN 'PARCIAL'
                    ELSE 'PENDIENTE' END
            ) ORDER BY fecha_gasto DESC, id)
            FROM _ec_deudas), '[]'::JSONB),
        'resumen', jsonb_build_object(
            'total_original', COALESCE((SELECT ROUND(SUM(monto_original), 2) FROM _ec_deudas), 0),
            'total_pagado', COALESCE((SELECT ROUND(SUM(monto_pagado), 2) FROM _ec_deudas), 0),
            'total_pendiente', COALESCE((SELECT ROUND(SUM(saldo_real), 2) FROM _ec_deudas), 0),
            'total_te_deben', CASE WHEN p_pov = 'owner' THEN v_total_te_deben ELSE v_total_tu_debes END,
            'total_tu_debes', CASE WHEN p_pov = 'owner' THEN v_total_tu_debes ELSE v_total_te_deben END,
            'neto', v_signo * v_neto,
            'saldo_favor', CASE WHEN p_pov = 'owner' THEN ROUND(v_favor_debtor, 2) ELSE ROUND(v_favor_owner, 2) END,
            'saldo_favor_owner', CASE WHEN p_pov = 'owner' THEN ROUND(v_favor_owner, 2) ELSE ROUND(v_favor_debtor, 2) END,
            'monto_ideal_a_cruzar', v_cruzable,
            'count', (SELECT COUNT(*) FROM _ec_deudas),
            'count_pagadas', (SELECT COUNT(*) FROM _ec_deudas WHERE saldo_real <= 0.01),
            'count_pendientes', (SELECT COUNT(*) FROM _ec_deudas WHERE saldo_real > 0.01)
        ),
        'cruce_sugerido', jsonb_build_object(
            'monto', v_cruzable,
            'lados', jsonb_build_object(
                'te_deben', _ec_lado(p_pov, FALSE),
                'tu_debes', _ec_lado(p_pov, TRUE)
            )
        )
    ) INTO v_out;

    DROP TABLE IF EXISTS _ec_deudas;
    RETURN v_out;
END;
$$;

COMMENT ON FUNCTION estado_cuenta(UUID, TEXT) IS
    'Estado de cuenta completo de un deudor, con cruce sugerido. Derivado puro: no escribe.';

-- Un lado del cruce sugerido, con la misma forma que consume el frontend.
CREATE OR REPLACE FUNCTION _ec_lado(p_pov TEXT, p_es_mi_deuda BOOLEAN)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_lado BOOLEAN := CASE WHEN p_pov = 'owner' THEN p_es_mi_deuda ELSE NOT p_es_mi_deuda END;
BEGIN
    RETURN jsonb_build_object(
        'total', COALESCE((SELECT ROUND(SUM(cruce_sugerido), 2) FROM _ec_deudas
                           WHERE es_mi_deuda = v_lado AND cruce_sugerido > 0.01), 0),
        'items', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'deuda_id', id,
                'titulo', titulo,
                'fecha_gasto', fecha_gasto,
                'es_tu_deuda', p_es_mi_deuda,
                'monto_original', ROUND(monto_original, 2),
                'saldo_antes', ROUND(saldo_real, 2),
                'aplicado', ROUND(cruce_sugerido, 2),
                'pagado_acumulado', ROUND(monto_original - saldo_real + cruce_sugerido, 2),
                'saldo_despues', ROUND(saldo_real - cruce_sugerido, 2),
                'cerrada', (saldo_real - cruce_sugerido) <= 0.01,
                'abono_saldo_favor', ROUND(abono_saldo_favor, 2)
            ) ORDER BY fecha_gasto, id)
            FROM _ec_deudas
            WHERE es_mi_deuda = v_lado AND cruce_sugerido > 0.01), '[]'::JSONB)
    );
END;
$$;
