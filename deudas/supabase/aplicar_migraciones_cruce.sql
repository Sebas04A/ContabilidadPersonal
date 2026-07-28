-- Migraciones del cruce de cuentas, consolidadas y en orden.
-- Generado desde migrations/. Ejecutar completo en el SQL Editor de Supabase.
-- Es idempotente: se puede volver a ejecutar sin efectos secundarios.

-- ═══ migrations/20260727100000_pagos_cruce_id_idem_key.sql
-- Identidad del cruce e idempotencia del sync.
--
-- Hasta ahora un cruce eran dos pagos virtuales sueltos que solo se podían reconocer
-- por heurística (misma fecha ±1s, y una ventana de 2s en get_historial). Con `cruce_id`
-- los dos lados quedan atados de verdad.
--
-- `idem_key` es la clave que genera el cliente al crear la intención de pago: permite
-- reintentar el sync tantas veces como haga falta sin duplicar pagos ni cruces.

ALTER TABLE pagos ADD COLUMN IF NOT EXISTS cruce_id UUID;
ALTER TABLE pagos ADD COLUMN IF NOT EXISTS idem_key UUID;

COMMENT ON COLUMN pagos.cruce_id IS
    'Los dos pagos virtuales de un mismo cruce comparten este id. NULL si no es un cruce.';
COMMENT ON COLUMN pagos.idem_key IS
    'Clave de idempotencia del cliente: reintentar el mismo pago no lo duplica.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_pagos_idem_key
    ON pagos(idem_key) WHERE idem_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pagos_cruce ON pagos(cruce_id) WHERE cruce_id IS NOT NULL;

-- ── Backfill de los cruces históricos ───────────────────────────────────────
-- Los dos lados de un cruce se crearon con el mismo deudor, el mismo monto y la misma
-- fecha (`fecha_pago` es DATE, así que el desempate de −1 segundo no sobrevivió). Se
-- emparejan de dos en dos por `created_at` dentro de cada grupo.
-- Solo se marcan los grupos que forman parejas completas. Si un grupo quedó impar es que
-- ese "cruce" nunca estuvo bien formado (un lado sin el otro, o montos que no cuadran):
-- se deja en NULL a propósito, para que se vea, en vez de inventarle una pareja.
WITH numerados AS (
    SELECT id,
           row_number() OVER (PARTITION BY deudor_id, fecha_pago, monto_total
                              ORDER BY created_at, id) - 1 AS pos,
           count(*)     OVER (PARTITION BY deudor_id, fecha_pago, monto_total) AS en_grupo,
           deudor_id, fecha_pago, monto_total
    FROM pagos
    WHERE es_compensacion AND cruce_id IS NULL
), asignado AS (
    -- Determinístico a propósito: si el backfill se corre dos veces, da el mismo id.
    SELECT id,
           md5(deudor_id::text || '|' || fecha_pago::text || '|' ||
               monto_total::text || '|' || (pos / 2)::text)::uuid AS nuevo_cruce_id
    FROM numerados
    WHERE en_grupo % 2 = 0
)
UPDATE pagos p
SET cruce_id = a.nuevo_cruce_id
FROM asignado a
WHERE p.id = a.id;

-- ═══ migrations/20260727100100_fn_estado_cuenta.sql
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

-- ═══ migrations/20260727100200_fn_aplicar_cruce_registrar_pago.sql
-- Escritura del cruce y del pago, del lado del servidor.
--
-- Antes esto lo hacía el cliente: la app calculaba el cruce, escribía los dos pagos
-- virtuales uno por uno en Hive y los subía sueltos. Si el sync moría a la mitad quedaba
-- un cruce con un solo lado y el saldo de la persona mentía.
--
-- Aquí las dos operaciones son atómicas, se calculan sobre datos frescos (la app puede
-- estar sincronizando algo de hace días) y son idempotentes: reintentar el mismo
-- `idem_key` no duplica nada. La matemática NO se reimplementa: se lee de
-- `estado_cuenta()`, que sigue siendo la única definición.

-- Deriva una clave estable a partir de la del cliente, para poder marcar varias filas
-- de una misma operación sin chocar con el índice único de `idem_key`.
CREATE OR REPLACE FUNCTION _idem_derivada(p_idem_key UUID, p_sufijo TEXT)
RETURNS UUID
LANGUAGE SQL IMMUTABLE AS $$
    SELECT CASE WHEN p_idem_key IS NULL THEN NULL
                ELSE md5(p_idem_key::TEXT || '|' || p_sufijo)::UUID END;
$$;


-- ── Cruce de cuentas ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION aplicar_cruce(
    p_deudor_id UUID,
    p_fecha     DATE DEFAULT CURRENT_DATE,
    p_idem_key  UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_estado    JSONB;
    v_monto     NUMERIC;
    v_cruce_id  UUID;
    v_pago_mias UUID;
    v_pago_suyas UUID;
    v_idem_a    UUID := _idem_derivada(p_idem_key, 'cruce_mias');
    v_idem_b    UUID := _idem_derivada(p_idem_key, 'cruce_suyas');
    v_existente UUID;
    it          JSONB;
BEGIN
    -- Serializa las operaciones sobre un mismo deudor: dos pagos simultáneos no pueden
    -- cruzar las mismas deudas dos veces.
    PERFORM pg_advisory_xact_lock(hashtext(p_deudor_id::TEXT));

    -- Idempotencia: si esta misma operación ya se aplicó, no se repite.
    IF v_idem_a IS NOT NULL THEN
        SELECT cruce_id INTO v_existente FROM pagos WHERE idem_key = v_idem_a;
        IF v_existente IS NOT NULL THEN
            RETURN jsonb_build_object('cruce_id', v_existente, 'aplicado', 0,
                                      'repetido', TRUE,
                                      'estado', estado_cuenta(p_deudor_id));
        END IF;
    END IF;

    v_estado := estado_cuenta(p_deudor_id);
    v_monto := (v_estado -> 'cruce_sugerido' ->> 'monto')::NUMERIC;

    IF v_monto IS NULL OR v_monto <= 0.01 THEN
        RETURN jsonb_build_object('cruce_id', NULL, 'aplicado', 0,
                                  'repetido', FALSE, 'estado', v_estado);
    END IF;

    v_cruce_id   := gen_random_uuid();
    v_pago_mias  := gen_random_uuid();
    v_pago_suyas := gen_random_uuid();

    -- Dos pagos virtuales, uno por lado, atados por `cruce_id`. No mueven dinero real.
    INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                      es_mi_pago, cruce_id, idem_key, synced)
    VALUES (v_pago_mias, p_deudor_id, v_monto, p_fecha, TRUE, TRUE,
            v_cruce_id, v_idem_a, TRUE),
           (v_pago_suyas, p_deudor_id, v_monto, p_fecha, TRUE, FALSE,
            v_cruce_id, v_idem_b, TRUE);

    -- El reparto por deuda ya viene resuelto (FIFO) en el cruce sugerido.
    FOR it IN SELECT * FROM jsonb_array_elements(
                  v_estado -> 'cruce_sugerido' -> 'lados' -> 'tu_debes' -> 'items')
    LOOP
        INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
        VALUES (v_pago_mias, (it ->> 'deuda_id')::UUID, (it ->> 'aplicado')::NUMERIC, TRUE);
    END LOOP;

    FOR it IN SELECT * FROM jsonb_array_elements(
                  v_estado -> 'cruce_sugerido' -> 'lados' -> 'te_deben' -> 'items')
    LOOP
        INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
        VALUES (v_pago_suyas, (it ->> 'deuda_id')::UUID, (it ->> 'aplicado')::NUMERIC, TRUE);
    END LOOP;

    RETURN jsonb_build_object('cruce_id', v_cruce_id, 'aplicado', v_monto,
                              'repetido', FALSE, 'estado', estado_cuenta(p_deudor_id));
END;
$$;

COMMENT ON FUNCTION aplicar_cruce(UUID, DATE, UUID) IS
    'Materializa el cruce disponible de un deudor. Atómico e idempotente por idem_key.';


-- ── Pago (que cruza primero, como hace la app) ──────────────────────────────
CREATE OR REPLACE FUNCTION registrar_pago(
    p_deudor_id  UUID,
    p_monto      NUMERIC,
    p_es_mi_pago BOOLEAN DEFAULT FALSE,
    p_fecha      DATE DEFAULT CURRENT_DATE,
    p_idem_key   UUID DEFAULT NULL,
    p_deudas_ids UUID[] DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_cruce     JSONB;
    v_pago_id   UUID;
    v_restante  NUMERIC := p_monto;
    v_asignar   NUMERIC;
    v_existente UUID;
    r           RECORD;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(p_deudor_id::TEXT));

    IF p_idem_key IS NOT NULL THEN
        SELECT id INTO v_existente FROM pagos WHERE idem_key = p_idem_key;
        IF v_existente IS NOT NULL THEN
            RETURN jsonb_build_object('pago_id', v_existente, 'repetido', TRUE,
                                      'estado', estado_cuenta(p_deudor_id));
        END IF;
    END IF;

    -- El cruce va SIEMPRE antes del dinero físico: no tiene sentido pasarse billetes
    -- por deudas que se anulan entre sí.
    v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key);

    IF p_monto IS NULL OR p_monto <= 0.01 THEN
        RETURN jsonb_build_object('pago_id', NULL, 'cruce', v_cruce - 'estado',
                                  'repetido', FALSE, 'estado', estado_cuenta(p_deudor_id));
    END IF;

    v_pago_id := gen_random_uuid();
    INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                      es_mi_pago, idem_key, synced)
    VALUES (v_pago_id, p_deudor_id, p_monto, p_fecha, FALSE, p_es_mi_pago,
            p_idem_key, TRUE);

    -- Reparto FIFO sobre las deudas del lado de quien paga; si se pidieron deudas
    -- concretas, esas van primero.
    FOR r IN
        SELECT d.id,
               d.monto - COALESCE(SUM(dp.monto_asignado), 0) AS saldo
        FROM deudas d
        LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
        WHERE d.deudor_id = p_deudor_id
          AND d.es_mi_deuda = p_es_mi_pago
        GROUP BY d.id
        HAVING d.monto - COALESCE(SUM(dp.monto_asignado), 0) > 0.01
        ORDER BY (p_deudas_ids IS NOT NULL AND d.id = ANY(p_deudas_ids)) DESC,
                 d.fecha_gasto, d.id
    LOOP
        EXIT WHEN v_restante <= 0.01;
        v_asignar := LEAST(r.saldo, v_restante);
        INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
        VALUES (v_pago_id, r.id, v_asignar, TRUE);
        v_restante := v_restante - v_asignar;
    END LOOP;

    -- Lo que no se asignó queda como saldo a favor de quien pagó (no se fuerza).
    RETURN jsonb_build_object('pago_id', v_pago_id,
                              'cruce', v_cruce - 'estado',
                              'sobrante', ROUND(v_restante, 2),
                              'repetido', FALSE,
                              'estado', estado_cuenta(p_deudor_id));
END;
$$;

COMMENT ON FUNCTION registrar_pago(UUID, NUMERIC, BOOLEAN, DATE, UUID, UUID[]) IS
    'Cruza lo que se pueda y reparte el pago FIFO. Atómico e idempotente por idem_key.';

