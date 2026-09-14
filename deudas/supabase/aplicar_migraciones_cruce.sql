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

-- ═══ migrations/20260912180000_pago_manual_antes_que_el_cruce.sql
-- El pago elegido a mano va antes que el cruce.
--
-- Hasta ahora `registrar_pago` cruzaba primero y pagaba después. Con deudas elegidas a
-- mano eso fallaba: el cruce ya se había comido parte de la deuda que ibas a pagar, así
-- que pagabas de más o pagabas una que igual se iba a anular sola.
--
-- La regla ahora, cuando hay deudas elegidas (`p_deudas_ids`):
--
--   1. El pago se reparte SOLO entre las deudas elegidas del lado de quien paga, de la
--      más antigua a la más reciente, hasta lo que de verdad les falta (neto del saldo a
--      favor ya entregado).
--   2. Lo que sobre del pago queda como saldo a favor de quien pagó. La app pide
--      confirmación antes de mandarlo.
--   3. El cruce se calcula DESPUÉS, sobre lo que quedó, en FIFO puro por cada lado: la
--      más antigua primero, aunque sea una deuda elegida que el pago no completó.
--
-- > Tú debes Cena $40 (vieja) y Gasolina $30; él te debe $15. Eliges Cena y pagas $30:
-- > el pago deja Cena en $10, el cruce tapa esos $10 y los $5 que sobran van a
-- > Gasolina. Cena queda saldada y Gasolina en $25.
--
-- Sin deudas elegidas (modo automático) todo sigue exactamente igual: cruce primero y
-- el pago FIFO sobre el lado de quien paga.
--
-- Para que la app enseñe lo mismo que se va a guardar, `estado_cuenta` acepta ese pago
-- planeado (`p_pago`) y devuelve el estado tal como quedaría: con el pago repartido y el
-- cruce recalculado, sin escribir nada. `registrar_pago` usa ese mismo cálculo para
-- escribir los detalles, así que no hay dos definiciones del reparto.
--
-- Sustituye a las migraciones 20260909120000 y 20260910180000/180100, que nunca llegaron
-- a producción: su idea (empujar al final del FIFO las deudas elegidas) queda descartada.
-- De ellas se conserva lo que sí servía:
--   * `estado_cuenta` sin tabla temporal: LANGUAGE sql STABLE con sumas acumuladas, en vez
--     de CREATE TEMP TABLE + bucles de UPDATE (cada lectura era una escritura en el WAL).
--   * `aplicar_cruce(p_con_estado)`: `registrar_pago` no le pide un estado que va a tirar.
--
-- Sin `p_pago` la salida de `estado_cuenta` es idéntica a la de la versión anterior; se
-- comprobó con los 11 deudores reales (owner y debtor) en una réplica de producción.

DROP FUNCTION IF EXISTS _ec_lado(TEXT, BOOLEAN);
DROP FUNCTION IF EXISTS estado_cuenta(UUID, TEXT);
DROP FUNCTION IF EXISTS estado_cuenta(UUID, TEXT, UUID[]);
DROP FUNCTION IF EXISTS estado_cuenta(UUID, TEXT, JSONB);

CREATE FUNCTION estado_cuenta(p_deudor_id UUID,
                              p_pov       TEXT  DEFAULT 'owner',
                              p_pago      JSONB DEFAULT NULL)
RETURNS JSONB
LANGUAGE sql
STABLE
AS $$
WITH
-- El pago planeado: {"monto": 30, "es_mi_pago": true, "deudas_ids": ["…", "…"]}.
-- Sin él, monto 0 y ninguna deuda: las dos pasadas de abajo dan lo mismo.
pago_planeado AS (
    SELECT COALESCE((p_pago ->> 'monto')::NUMERIC, 0)          AS monto,
           COALESCE((p_pago ->> 'es_mi_pago')::BOOLEAN, FALSE) AS es_mi_pago,
           ARRAY(SELECT jsonb_array_elements_text(
                     CASE WHEN jsonb_typeof(p_pago -> 'deudas_ids') = 'array'
                          THEN p_pago -> 'deudas_ids' ELSE '[]'::JSONB END))::UUID[]
                                                               AS deudas_ids
),

-- ── Pasada 1: el estado de hoy, para saber cuánto le falta a cada deuda ──────────
base_hoy AS (
    SELECT d.id,
           d.titulo,
           d.fecha_gasto,
           d.es_mi_deuda,
           d.monto::NUMERIC                                            AS monto_original,
           COALESCE(SUM(dp.monto_asignado), 0)::NUMERIC                AS monto_pagado,
           GREATEST(d.monto - COALESCE(SUM(dp.monto_asignado), 0), 0)::NUMERIC
                                                                       AS saldo_pendiente
    FROM deudas d
    LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
    WHERE d.deudor_id = p_deudor_id
    GROUP BY d.id
),

-- Saldo a favor de cada parte: sobrante de los pagos reales (los cruces no cuentan).
favor_hoy AS (
    SELECT COALESCE(SUM(sobrante) FILTER (WHERE es_mi_pago), 0)     AS favor_owner_ini,
           COALESCE(SUM(sobrante) FILTER (WHERE NOT es_mi_pago), 0) AS favor_debtor_ini
    FROM (
        SELECT p.es_mi_pago,
               p.monto_total - COALESCE(SUM(dp.monto_asignado), 0) AS sobrante
        FROM pagos p
        LEFT JOIN detalle_pagos dp ON dp.pago_id = p.id
        WHERE p.deudor_id = p_deudor_id
          AND NOT COALESCE(p.es_compensacion, FALSE)
        GROUP BY p.id, p.es_mi_pago, p.monto_total
    ) s
    WHERE sobrante > 0.01
),

-- Mismo abono que la pasada 2 (ver allí): hace falta aquí porque el pago se reparte
-- sobre lo que falta NETO del crédito ya entregado, no sobre el saldo bruto.
saldo_hoy AS (
    SELECT a.id, a.fecha_gasto, a.es_mi_deuda,
           ROUND(a.saldo_pendiente - CASE
               WHEN a.saldo_pendiente > 0.01
                    AND (a.credito_ini - a.consumido_antes) > 0.01
               THEN LEAST(a.saldo_pendiente, a.credito_ini - a.consumido_antes)
               ELSE 0
           END, 2) AS saldo_real
    FROM (
        SELECT b.*,
               CASE WHEN b.es_mi_deuda THEN f.favor_owner_ini ELSE f.favor_debtor_ini END
                   AS credito_ini,
               COALESCE(
                   SUM(b.saldo_pendiente) FILTER (WHERE b.saldo_pendiente > 0.01)
                       OVER (PARTITION BY b.es_mi_deuda
                             ORDER BY b.fecha_gasto, b.id
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
                   0) AS consumido_antes
        FROM base_hoy b
        CROSS JOIN favor_hoy f
    ) a
),

-- ── El reparto del pago planeado ─────────────────────────────────────────────────
-- Solo deudas elegidas, del lado de quien paga, de la más antigua a la más reciente.
-- Es el bucle `EXIT WHEN restante <= 0.01; asignar := LEAST(saldo, restante)` escrito
-- con una suma acumulada. Redondeado a centavos porque así se va a escribir.
reparto AS (
    SELECT e.id,
           ROUND(CASE WHEN pp.monto - e.repartido_antes > 0.01
                      THEN LEAST(e.saldo_real, pp.monto - e.repartido_antes)
                      ELSE 0 END, 2) AS pago
    FROM (
        SELECT s.id, s.saldo_real,
               COALESCE(SUM(s.saldo_real)
                            OVER (ORDER BY s.fecha_gasto, s.id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
                        0) AS repartido_antes
        FROM saldo_hoy s
        CROSS JOIN pago_planeado pp
        WHERE s.id = ANY(pp.deudas_ids)
          AND s.es_mi_deuda = pp.es_mi_pago
          AND s.saldo_real > 0.01
    ) e
    CROSS JOIN pago_planeado pp
),
reparto_total AS (
    SELECT pp.monto,
           pp.es_mi_pago,
           COALESCE((SELECT SUM(pago) FROM reparto), 0)          AS asignado,
           pp.monto - COALESCE((SELECT SUM(pago) FROM reparto), 0) AS sobrante
    FROM pago_planeado pp
),

-- ── Pasada 2: el estado con el pago ya puesto ────────────────────────────────────
-- Es exactamente lo que habrá en las tablas después de `registrar_pago`, antes de
-- materializar el cruce. Sin pago planeado coincide con la pasada 1.
base AS (
    SELECT b.id, b.titulo, b.fecha_gasto, b.es_mi_deuda, b.monto_original,
           b.monto_pagado + COALESCE(r.pago, 0)                        AS monto_pagado,
           GREATEST(b.saldo_pendiente - COALESCE(r.pago, 0), 0)        AS saldo_pendiente,
           COALESCE(r.pago, 0)                                         AS pago_planeado
    FROM base_hoy b
    LEFT JOIN reparto r ON r.id = b.id
),

-- El sobrante del pago planeado es crédito de quien paga, igual que el de un pago real
-- (y con el mismo umbral: un sobrante de un centavo no cuenta).
favor AS (
    SELECT f.favor_owner_ini
             + CASE WHEN rt.es_mi_pago AND rt.sobrante > 0.01 THEN rt.sobrante ELSE 0 END
               AS favor_owner_ini,
           f.favor_debtor_ini
             + CASE WHEN NOT rt.es_mi_pago AND rt.sobrante > 0.01 THEN rt.sobrante ELSE 0 END
               AS favor_debtor_ini
    FROM favor_hoy f
    CROSS JOIN reparto_total rt
),

-- Ese crédito abona las deudas de quien pagó, de la más antigua a la más reciente.
-- `consumido_antes` es lo que se llevaron las deudas anteriores DE SU MISMO LADO: es el
-- equivalente exacto de ir restando el crédito en un bucle.
abono_pos AS (
    SELECT b.*,
           CASE WHEN b.es_mi_deuda THEN f.favor_owner_ini ELSE f.favor_debtor_ini END
               AS credito_ini,
           COALESCE(
               SUM(b.saldo_pendiente) FILTER (WHERE b.saldo_pendiente > 0.01)
                   OVER (PARTITION BY b.es_mi_deuda
                         ORDER BY b.fecha_gasto, b.id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
               0) AS consumido_antes
    FROM base b
    CROSS JOIN favor f
),
calc AS (
    SELECT a.id, a.titulo, a.fecha_gasto, a.es_mi_deuda,
           a.monto_original, a.monto_pagado, a.saldo_pendiente, a.pago_planeado,
           abono.v                                           AS abono_saldo_favor,
           ROUND(a.saldo_pendiente - abono.v, 2)             AS saldo_real
    FROM abono_pos a
    CROSS JOIN LATERAL (
        SELECT CASE
                   WHEN a.saldo_pendiente > 0.01
                        AND (a.credito_ini - a.consumido_antes) > 0.01
                   THEN LEAST(a.saldo_pendiente, a.credito_ini - a.consumido_antes)
                   ELSE 0
               END AS v
    ) abono
),
tot AS (
    SELECT COALESCE(SUM(saldo_real)        FILTER (WHERE NOT es_mi_deuda), 0) AS te_deben,
           COALESCE(SUM(saldo_real)        FILTER (WHERE es_mi_deuda),     0) AS tu_debes,
           COALESCE(SUM(abono_saldo_favor) FILTER (WHERE es_mi_deuda),     0) AS usado_owner,
           COALESCE(SUM(abono_saldo_favor) FILTER (WHERE NOT es_mi_deuda), 0) AS usado_debtor,
           COALESCE(SUM(monto_original), 0)                                   AS total_original,
           COALESCE(SUM(monto_pagado), 0)                                     AS total_pagado,
           COUNT(*)                                                           AS n,
           COUNT(*) FILTER (WHERE saldo_real <= 0.01)                         AS n_pagadas,
           COUNT(*) FILTER (WHERE saldo_real >  0.01)                         AS n_pendientes
    FROM calc
),
cruzable AS (
    SELECT ROUND(LEAST(t.te_deben, t.tu_debes), 2) AS monto FROM tot t
),

-- Cruce sugerido: FIFO puro en cada lado sobre el saldo_real, la más antigua primero.
cruce_pos AS (
    SELECT c.*,
           cz.monto AS cruzable,
           COALESCE(
               SUM(c.saldo_real) FILTER (WHERE c.saldo_real > 0.01)
                   OVER (PARTITION BY c.es_mi_deuda
                         ORDER BY c.fecha_gasto, c.id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
               0) AS cruzado_antes
    FROM calc c
    CROSS JOIN cruzable cz
),
final AS (
    SELECT p.id, p.titulo, p.fecha_gasto, p.es_mi_deuda,
           p.monto_original, p.monto_pagado, p.saldo_pendiente, p.pago_planeado,
           p.abono_saldo_favor, p.saldo_real,
           CASE
               WHEN p.cruzable > 0.01
                    AND p.saldo_real > 0.01
                    AND (p.cruzable - p.cruzado_antes) > 0.01
               THEN LEAST(p.saldo_real, p.cruzable - p.cruzado_antes)
               ELSE 0
           END AS cruce_sugerido
    FROM cruce_pos p
)

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
        )
        -- Solo con pago planeado, para que sin él la salida no cambie ni en una clave.
        || CASE WHEN p_pago IS NOT NULL
                THEN jsonb_build_object('pago_planeado', ROUND(pago_planeado, 2))
                ELSE '{}'::JSONB END
        ORDER BY fecha_gasto DESC, id)
        FROM final), '[]'::JSONB),

    'resumen', jsonb_build_object(
        'total_original',  ROUND(t.total_original, 2),
        'total_pagado',    ROUND(t.total_pagado, 2),
        'total_pendiente', ROUND(t.te_deben + t.tu_debes, 2),
        'total_te_deben',  CASE WHEN p_pov = 'owner' THEN t.te_deben ELSE t.tu_debes END,
        'total_tu_debes',  CASE WHEN p_pov = 'owner' THEN t.tu_debes ELSE t.te_deben END,
        -- El crédito que no abonó ninguna deuda es deuda pura: lo que el deudor pagó de
        -- más se lo debes, lo que pagaste de más te lo debe. Sobre el crédito RESTANTE.
        'neto', (CASE WHEN p_pov = 'owner' THEN 1 ELSE -1 END) * ROUND(
                    t.te_deben - t.tu_debes
                    - (f.favor_debtor_ini - t.usado_debtor)
                    + (f.favor_owner_ini  - t.usado_owner), 2),
        'saldo_favor', CASE WHEN p_pov = 'owner'
                            THEN ROUND(f.favor_debtor_ini - t.usado_debtor, 2)
                            ELSE ROUND(f.favor_owner_ini  - t.usado_owner,  2) END,
        'saldo_favor_owner', CASE WHEN p_pov = 'owner'
                            THEN ROUND(f.favor_owner_ini  - t.usado_owner,  2)
                            ELSE ROUND(f.favor_debtor_ini - t.usado_debtor, 2) END,
        'monto_ideal_a_cruzar', cz.monto,
        'count', t.n,
        'count_pagadas', t.n_pagadas,
        'count_pendientes', t.n_pendientes
    )
    || CASE WHEN p_pago IS NOT NULL
            THEN jsonb_build_object('pago_planeado', jsonb_build_object(
                     'monto',      ROUND(rt.monto, 2),
                     'es_mi_pago', rt.es_mi_pago,
                     'asignado',   ROUND(rt.asignado, 2),
                     'sobrante',   ROUND(rt.sobrante, 2)))
            ELSE '{}'::JSONB END,

    'cruce_sugerido', jsonb_build_object(
        'monto', cz.monto,
        'lados', jsonb_build_object(
            'te_deben', jsonb_build_object(
                'total', COALESCE((
                    SELECT ROUND(SUM(cruce_sugerido), 2) FROM final
                    WHERE es_mi_deuda = (p_pov <> 'owner') AND cruce_sugerido > 0.01), 0),
                'items', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'deuda_id', id,
                        'titulo', titulo,
                        'fecha_gasto', fecha_gasto,
                        'es_tu_deuda', FALSE,
                        'monto_original', ROUND(monto_original, 2),
                        'saldo_antes', ROUND(saldo_real, 2),
                        'aplicado', ROUND(cruce_sugerido, 2),
                        'pagado_acumulado', ROUND(monto_original - saldo_real + cruce_sugerido, 2),
                        'saldo_despues', ROUND(saldo_real - cruce_sugerido, 2),
                        'cerrada', (saldo_real - cruce_sugerido) <= 0.01,
                        'abono_saldo_favor', ROUND(abono_saldo_favor, 2)
                    ) ORDER BY fecha_gasto, id)
                    FROM final
                    WHERE es_mi_deuda = (p_pov <> 'owner') AND cruce_sugerido > 0.01), '[]'::JSONB)
            ),
            'tu_debes', jsonb_build_object(
                'total', COALESCE((
                    SELECT ROUND(SUM(cruce_sugerido), 2) FROM final
                    WHERE es_mi_deuda = (p_pov =  'owner') AND cruce_sugerido > 0.01), 0),
                'items', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'deuda_id', id,
                        'titulo', titulo,
                        'fecha_gasto', fecha_gasto,
                        'es_tu_deuda', TRUE,
                        'monto_original', ROUND(monto_original, 2),
                        'saldo_antes', ROUND(saldo_real, 2),
                        'aplicado', ROUND(cruce_sugerido, 2),
                        'pagado_acumulado', ROUND(monto_original - saldo_real + cruce_sugerido, 2),
                        'saldo_despues', ROUND(saldo_real - cruce_sugerido, 2),
                        'cerrada', (saldo_real - cruce_sugerido) <= 0.01,
                        'abono_saldo_favor', ROUND(abono_saldo_favor, 2)
                    ) ORDER BY fecha_gasto, id)
                    FROM final
                    WHERE es_mi_deuda = (p_pov =  'owner') AND cruce_sugerido > 0.01), '[]'::JSONB)
            )
        )
    )
)
FROM tot t, favor f, cruzable cz, reparto_total rt;
$$;

COMMENT ON FUNCTION estado_cuenta(UUID, TEXT, JSONB) IS
    'Estado de cuenta completo de un deudor, con cruce sugerido. Con p_pago devuelve el '
    'estado tal como quedaría tras registrar ese pago. Derivado puro: no escribe.';


-- ── aplicar_cruce: FIFO puro, y sin recalcular un estado que se va a tirar ────────
DROP FUNCTION IF EXISTS aplicar_cruce(UUID, DATE, UUID);
DROP FUNCTION IF EXISTS aplicar_cruce(UUID, DATE, UUID, UUID[]);
DROP FUNCTION IF EXISTS aplicar_cruce(UUID, DATE, UUID, UUID[], BOOLEAN);
DROP FUNCTION IF EXISTS aplicar_cruce(UUID, DATE, UUID, BOOLEAN);

CREATE FUNCTION aplicar_cruce(
    p_deudor_id  UUID,
    p_fecha      DATE    DEFAULT CURRENT_DATE,
    p_idem_key   UUID    DEFAULT NULL,
    p_con_estado BOOLEAN DEFAULT TRUE
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_estado     JSONB;
    v_monto      NUMERIC;
    v_cruce_id   UUID;
    v_pago_mias  UUID;
    v_pago_suyas UUID;
    v_idem_a     UUID := _idem_derivada(p_idem_key, 'cruce_mias');
    v_idem_b     UUID := _idem_derivada(p_idem_key, 'cruce_suyas');
    v_existente  UUID;
    it           JSONB;
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
                                      'estado', CASE WHEN p_con_estado
                                                     THEN estado_cuenta(p_deudor_id)
                                                     ELSE NULL END);
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
                              'repetido', FALSE,
                              'estado', CASE WHEN p_con_estado
                                             THEN estado_cuenta(p_deudor_id)
                                             ELSE NULL END);
END;
$$;

COMMENT ON FUNCTION aplicar_cruce(UUID, DATE, UUID, BOOLEAN) IS
    'Materializa el cruce disponible de un deudor (FIFO por lado). Atómico e idempotente '
    'por idem_key. Con p_con_estado=FALSE no recalcula el estado final.';


-- ── registrar_pago: con deudas elegidas, el pago va antes que el cruce ────────────
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
    v_plan      JSONB;
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

    -- Sin dinero no hay reparto: solo se cruza lo que se pueda.
    IF p_monto IS NULL OR p_monto <= 0.01 THEN
        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);
        RETURN jsonb_build_object('pago_id', NULL, 'cruce', v_cruce - 'estado',
                                  'repetido', FALSE, 'estado', estado_cuenta(p_deudor_id));
    END IF;

    v_pago_id := gen_random_uuid();

    IF p_deudas_ids IS NULL THEN
        -- Automático: el cruce va antes del dinero físico, que no tiene sentido pasarse
        -- billetes por deudas que se anulan entre sí; luego el pago FIFO sobre el lado de
        -- quien paga. Igual que siempre.
        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);

        INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                          es_mi_pago, idem_key, synced)
        VALUES (v_pago_id, p_deudor_id, p_monto, p_fecha, FALSE, p_es_mi_pago,
                p_idem_key, TRUE);

        FOR r IN
            SELECT d.id,
                   d.monto - COALESCE(SUM(dp.monto_asignado), 0) AS saldo
            FROM deudas d
            LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
            WHERE d.deudor_id = p_deudor_id
              AND d.es_mi_deuda = p_es_mi_pago
            GROUP BY d.id
            HAVING d.monto - COALESCE(SUM(dp.monto_asignado), 0) > 0.01
            ORDER BY d.fecha_gasto, d.id
        LOOP
            EXIT WHEN v_restante <= 0.01;
            v_asignar := LEAST(r.saldo, v_restante);
            INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
            VALUES (v_pago_id, r.id, v_asignar, TRUE);
            v_restante := v_restante - v_asignar;
        END LOOP;
    ELSE
        -- Deudas elegidas a mano: primero el pago, solo sobre ellas, y después el cruce
        -- sobre lo que quedó. El reparto es el mismo que la app vio: lo calcula
        -- `estado_cuenta` con este pago planeado.
        v_plan := estado_cuenta(p_deudor_id, 'owner', jsonb_build_object(
                      'monto', p_monto,
                      'es_mi_pago', p_es_mi_pago,
                      'deudas_ids', to_jsonb(p_deudas_ids)));

        INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                          es_mi_pago, idem_key, synced)
        VALUES (v_pago_id, p_deudor_id, p_monto, p_fecha, FALSE, p_es_mi_pago,
                p_idem_key, TRUE);

        FOR r IN
            SELECT (d ->> 'id')::UUID AS id, (d ->> 'pago_planeado')::NUMERIC AS pago
            FROM jsonb_array_elements(v_plan -> 'deudas') d
            WHERE (d ->> 'pago_planeado')::NUMERIC > 0
        LOOP
            INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
            VALUES (v_pago_id, r.id, r.pago, TRUE);
            v_restante := v_restante - r.pago;
        END LOOP;

        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);
    END IF;

    -- Lo que no se asignó queda como saldo a favor de quien pagó (no se fuerza).
    RETURN jsonb_build_object('pago_id', v_pago_id,
                              'cruce', v_cruce - 'estado',
                              'sobrante', ROUND(v_restante, 2),
                              'repetido', FALSE,
                              'estado', estado_cuenta(p_deudor_id));
END;
$$;

COMMENT ON FUNCTION registrar_pago(UUID, NUMERIC, BOOLEAN, DATE, UUID, UUID[]) IS
    'Registra un pago. Automático: cruza y reparte FIFO. Con p_deudas_ids: reparte solo '
    'entre esas deudas y cruza después. Atómico e idempotente por idem_key.';


-- Los mismos permisos que tenían las versiones anteriores.
GRANT EXECUTE ON FUNCTION estado_cuenta(UUID, TEXT, JSONB)       TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION aplicar_cruce(UUID, DATE, UUID, BOOLEAN) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION registrar_pago(UUID, NUMERIC, BOOLEAN, DATE, UUID, UUID[])
    TO anon, authenticated, service_role;

-- ═══ migrations/20260913180000_editar_cruce.sql
-- Editar el cruce de la última operación: sacarle deudas o deshacerlo entero.
--
-- Al registrar un pago el cruce se aplica solo, y a veces cruza deudas que uno quería
-- dejar pendientes todavía. `editar_cruce` saca esas deudas del cruce; como el cruce se
-- deriva del estado, quedan disponibles y se vuelven a cruzar en el siguiente pago.
--
-- La regla:
--
--   * El pago real NO se toca. Solo cambian los dos pagos virtuales del cruce y sus
--     `detalle_pagos`; el dinero entregado sigue repartido igual.
--   * Un cruce siempre cuadra: los dos lados suman lo mismo. Sin las deudas excluidas, el
--     cruce nuevo es lo que quede en el lado más chico, y el lado más grande se recorta
--     desde la deuda más reciente (se conservan las más antiguas, igual que el FIFO que lo
--     creó). Nunca se agregan deudas que no estaban en el cruce.
--   * Sin `p_excluir` (NULL) se deshace el cruce entero. Si queda en $0, se borra.
--   * Solo el cruce de la última operación del deudor: una operación posterior se calculó
--     encima de él.
--
-- > Cruce de $15. Tu lado: Cena $15. Su lado: Taxi $10 + Uber $5.
-- > Sacas Uber: su lado queda en $10, así que el cruce baja a $10 (Cena $10 con Taxi $10).
-- > Quedan pendientes Uber $5 y $5 de Cena.
--
-- Con `p_simular` hace exactamente lo mismo dentro de un subbloque que se revierte, y
-- devuelve el estado de cuenta tal como quedaría: la vista previa y la escritura son el
-- mismo código.
--
-- Cada edición real deja el antes y el después en `cruces_editados`, que además da la
-- idempotencia por `idem_key`.

CREATE TABLE IF NOT EXISTS cruces_editados (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idem_key      UUID,
    cruce_id      UUID        NOT NULL,
    deudor_id     UUID        NOT NULL REFERENCES deudores(id) ON DELETE CASCADE,
    excluidas     UUID[],
    monto_antes   NUMERIC     NOT NULL,
    monto_despues NUMERIC     NOT NULL,
    -- Los dos pagos virtuales y sus detalles tal como estaban: basta para restaurarlo.
    antes         JSONB       NOT NULL,
    despues       JSONB       NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cruces_editados_idem
    ON cruces_editados(idem_key) WHERE idem_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cruces_editados_deudor ON cruces_editados(deudor_id);

COMMENT ON TABLE cruces_editados IS
    'Bitácora de editar_cruce: qué deudas se sacaron de un cruce y cómo estaba antes.';

ALTER TABLE cruces_editados ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Admin full access cruces_editados" ON cruces_editados;
CREATE POLICY "Admin full access cruces_editados" ON cruces_editados
    FOR ALL USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON cruces_editados TO anon, authenticated, service_role;


-- ── El recorte, escrito ─────────────────────────────────────────────────────────
-- Valida, calcula y escribe. No toma el lock ni registra la bitácora: eso es de
-- `editar_cruce`, que es el único que la llama.
CREATE OR REPLACE FUNCTION _editar_cruce_aplicar(p_cruce_id UUID, p_excluir UUID[])
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_deudor    UUID;
    v_pago_mias UUID;
    v_pago_suya UUID;
    v_n_pagos   INT;
    v_creado    TIMESTAMPTZ;
    v_antes     JSONB;
    v_monto_ant NUMERIC;
    v_nuevo     NUMERIC;
    v_items     JSONB;
    v_ajenas    UUID[];
BEGIN
    SELECT min(deudor_id::TEXT)::UUID, count(*), max(created_at),
           (array_agg(id) FILTER (WHERE es_mi_pago))[1],
           (array_agg(id) FILTER (WHERE NOT es_mi_pago))[1],
           max(monto_total)
      INTO v_deudor, v_n_pagos, v_creado, v_pago_mias, v_pago_suya, v_monto_ant
      FROM pagos
     WHERE cruce_id = p_cruce_id AND COALESCE(es_compensacion, FALSE);

    IF v_n_pagos = 0 THEN
        RAISE EXCEPTION 'No existe el cruce %', p_cruce_id;
    END IF;
    IF v_n_pagos <> 2 OR v_pago_mias IS NULL OR v_pago_suya IS NULL THEN
        RAISE EXCEPTION 'El cruce % está mal formado (% pagos virtuales)', p_cruce_id, v_n_pagos;
    END IF;

    -- La última operación. El pago y su cruce se crean en la misma transacción, así que
    -- comparten `created_at`; los cruces viejos de la app llegaban con unos milisegundos
    -- de diferencia, de ahí el margen.
    IF EXISTS (SELECT 1 FROM pagos
                WHERE deudor_id = v_deudor
                  AND cruce_id IS DISTINCT FROM p_cruce_id
                  AND created_at > v_creado + INTERVAL '5 seconds') THEN
        RAISE EXCEPTION 'Solo se puede editar el cruce de la última operación del deudor';
    END IF;

    SELECT array_agg(x) INTO v_ajenas
      FROM unnest(p_excluir) x
     WHERE NOT EXISTS (SELECT 1 FROM detalle_pagos dp
                        WHERE dp.pago_id IN (v_pago_mias, v_pago_suya) AND dp.deuda_id = x);
    IF v_ajenas IS NOT NULL THEN
        RAISE EXCEPTION 'Estas deudas no están en el cruce: %', v_ajenas;
    END IF;
    IF p_excluir IS NOT NULL AND cardinality(p_excluir) = 0 THEN
        RAISE EXCEPTION 'No se eligió ninguna deuda para sacar del cruce';
    END IF;

    -- Cómo estaba, para la bitácora y para devolver el antes.
    SELECT jsonb_build_object(
               'pagos', (SELECT jsonb_agg(to_jsonb(p) ORDER BY p.es_mi_pago DESC)
                           FROM pagos p WHERE p.cruce_id = p_cruce_id),
               'detalle_pagos', (SELECT jsonb_agg(to_jsonb(dp) ORDER BY dp.pago_id, dp.deuda_id)
                                   FROM detalle_pagos dp
                                  WHERE dp.pago_id IN (v_pago_mias, v_pago_suya)))
      INTO v_antes;

    -- El recorte. `lado` = TRUE es el pago virtual del dueño: cubre las deudas que tú
    -- debes. `previo` es lo que conservan las deudas anteriores del mismo lado, que se
    -- quedan con lo suyo primero (FIFO, igual que `aplicar_cruce`).
    WITH items AS (
        SELECT p.es_mi_pago                           AS lado,
               d.id                                   AS deuda_id,
               d.titulo,
               d.fecha_gasto,
               ROUND(SUM(dp.monto_asignado), 2)       AS antes,
               (p_excluir IS NULL OR d.id = ANY(p_excluir)) AS excluida
          FROM pagos p
          JOIN detalle_pagos dp ON dp.pago_id = p.id
          JOIN deudas d         ON d.id = dp.deuda_id
         WHERE p.cruce_id = p_cruce_id
         GROUP BY p.es_mi_pago, d.id, d.titulo, d.fecha_gasto
    ),
    nuevo AS (
        SELECT ROUND(LEAST(
                   COALESCE(SUM(antes) FILTER (WHERE lado     AND NOT excluida), 0),
                   COALESCE(SUM(antes) FILTER (WHERE NOT lado AND NOT excluida), 0)), 2) AS monto
          FROM items
    ),
    pos AS (
        SELECT i.*, n.monto AS cruce_nuevo,
               COALESCE(SUM(i.antes) FILTER (WHERE NOT i.excluida)
                            OVER (PARTITION BY i.lado ORDER BY i.fecha_gasto, i.deuda_id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS previo
          FROM items i CROSS JOIN nuevo n
    )
    SELECT (SELECT monto FROM nuevo),
           COALESCE(jsonb_agg(jsonb_build_object(
               'lado',        CASE WHEN lado THEN 'tu_debes' ELSE 'te_deben' END,
               'deuda_id',    deuda_id,
               'titulo',      titulo,
               'fecha_gasto', fecha_gasto,
               'excluida',    excluida,
               'antes',       antes,
               'despues',     despues
           ) ORDER BY lado DESC, fecha_gasto, deuda_id), '[]'::JSONB)
      INTO v_nuevo, v_items
      FROM (
        SELECT pos.*,
               CASE WHEN excluida OR cruce_nuevo <= 0.01 THEN 0
                    ELSE ROUND(GREATEST(LEAST(antes, cruce_nuevo - previo), 0), 2)
               END AS despues
          FROM pos
      ) r;

    IF v_nuevo <= 0.01 THEN
        -- Borra los dos pagos virtuales; sus detalles se van en cascada.
        DELETE FROM pagos WHERE cruce_id = p_cruce_id;
        v_nuevo := 0;
    ELSE
        UPDATE pagos SET monto_total = v_nuevo WHERE cruce_id = p_cruce_id;
        DELETE FROM detalle_pagos WHERE pago_id IN (v_pago_mias, v_pago_suya);
        INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
        SELECT CASE WHEN it ->> 'lado' = 'tu_debes' THEN v_pago_mias ELSE v_pago_suya END,
               (it ->> 'deuda_id')::UUID,
               (it ->> 'despues')::NUMERIC,
               TRUE
          FROM jsonb_array_elements(v_items) it
         WHERE (it ->> 'despues')::NUMERIC > 0.01;
    END IF;

    RETURN jsonb_build_object(
        'cruce_id',      p_cruce_id,
        'deudor_id',     v_deudor,
        'monto_antes',   ROUND(v_monto_ant, 2),
        'monto_despues', ROUND(v_nuevo, 2),
        'eliminado',     v_nuevo = 0,
        'items',         v_items,
        'antes',         v_antes);
END;
$$;


-- ── editar_cruce: lock, simulación, bitácora e idempotencia ─────────────────────
CREATE OR REPLACE FUNCTION editar_cruce(
    p_cruce_id UUID,
    p_excluir  UUID[]  DEFAULT NULL,
    p_simular  BOOLEAN DEFAULT FALSE,
    p_idem_key UUID    DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
AS $$
DECLARE
    v_deudor UUID;
    v_res    JSONB;
    v_estado JSONB;
    v_previa cruces_editados%ROWTYPE;
BEGIN
    -- Idempotencia antes que nada: si el cruce ya se deshizo entero, ya no existe.
    IF p_idem_key IS NOT NULL AND NOT p_simular THEN
        SELECT * INTO v_previa FROM cruces_editados WHERE idem_key = p_idem_key;
        IF FOUND THEN
            RETURN jsonb_build_object('cruce_id', v_previa.cruce_id,
                                      'deudor_id', v_previa.deudor_id,
                                      'monto_antes', v_previa.monto_antes,
                                      'monto_despues', v_previa.monto_despues,
                                      'eliminado', v_previa.monto_despues = 0,
                                      'repetido', TRUE, 'simulado', FALSE,
                                      'estado', estado_cuenta(v_previa.deudor_id));
        END IF;
    END IF;

    SELECT deudor_id INTO v_deudor FROM pagos WHERE cruce_id = p_cruce_id LIMIT 1;
    IF v_deudor IS NULL THEN
        RAISE EXCEPTION 'No existe el cruce %', p_cruce_id;
    END IF;

    -- El mismo lock que `registrar_pago` y `aplicar_cruce`.
    PERFORM pg_advisory_xact_lock(hashtext(v_deudor::TEXT));

    IF p_simular THEN
        -- Las variables de PL/pgSQL no se revierten con el subbloque: el resultado y el
        -- estado sobreviven, las escrituras no.
        BEGIN
            v_res    := _editar_cruce_aplicar(p_cruce_id, p_excluir);
            v_estado := estado_cuenta(v_deudor);
            RAISE EXCEPTION USING ERRCODE = 'EC000', MESSAGE = 'simulación';
        EXCEPTION WHEN SQLSTATE 'EC000' THEN
            NULL;
        END;
        RETURN (v_res - 'antes') || jsonb_build_object('repetido', FALSE, 'simulado', TRUE,
                                                       'estado', v_estado);
    END IF;

    v_res := _editar_cruce_aplicar(p_cruce_id, p_excluir);

    INSERT INTO cruces_editados(idem_key, cruce_id, deudor_id, excluidas,
                                monto_antes, monto_despues, antes, despues)
    VALUES (p_idem_key, p_cruce_id, v_deudor, p_excluir,
            (v_res ->> 'monto_antes')::NUMERIC, (v_res ->> 'monto_despues')::NUMERIC,
            v_res -> 'antes', v_res -> 'items');

    RETURN (v_res - 'antes') || jsonb_build_object('repetido', FALSE, 'simulado', FALSE,
                                                   'estado', estado_cuenta(v_deudor));
END;
$$;

COMMENT ON FUNCTION editar_cruce(UUID, UUID[], BOOLEAN, UUID) IS
    'Saca deudas del cruce de la última operación (NULL = deshacerlo entero). El pago real '
    'no se toca; el cruce se recorta para que cuadre. Con p_simular no escribe nada.';

-- La interna también: las funciones corren con los permisos de quien llama.
GRANT EXECUTE ON FUNCTION _editar_cruce_aplicar(UUID, UUID[]) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION editar_cruce(UUID, UUID[], BOOLEAN, UUID)
    TO anon, authenticated, service_role;

-- ═══ migrations/20260913200000_fifo_por_registro.sql
-- A igual fecha, primero la deuda que se registró antes.
--
-- El FIFO de pagos, cruces y saldo a favor ordenaba por (fecha_gasto, id). Varias deudas
-- del mismo día empatan en la fecha y el `id` es un UUID aleatorio, así que cuál se pagaba
-- primero —y cuál quedaba a medias cuando el dinero no alcanzaba— era cuestión de suerte.
-- Ahora el desempate es `created_at`: la registrada antes se paga antes, y la que queda a
-- medias es la más nueva. `id` queda como último desempate.
--
-- No toca datos: los pagos y cruces ya escritos siguen repartidos como están. Cambia el
-- cruce sugerido y el reparto de los pagos que se registren desde ahora.
--
-- Cada deuda de `estado_cuenta` trae además `creado` (su `created_at`), para que la vista
-- previa del teléfono (`PlanPago`) desempate igual.
--
-- Definiciones bajadas de producción el 2026-09-13 y parcheadas solo en el ORDER BY (y en
-- las columnas que hacen falta para ordenar).

CREATE OR REPLACE FUNCTION public.estado_cuenta(p_deudor_id uuid, p_pov text DEFAULT 'owner'::text, p_pago jsonb DEFAULT NULL::jsonb)
 RETURNS jsonb
 LANGUAGE sql
 STABLE
AS $function$
WITH
-- El pago planeado: {"monto": 30, "es_mi_pago": true, "deudas_ids": ["…", "…"]}.
-- Sin él, monto 0 y ninguna deuda: las dos pasadas de abajo dan lo mismo.
pago_planeado AS (
    SELECT COALESCE((p_pago ->> 'monto')::NUMERIC, 0)          AS monto,
           COALESCE((p_pago ->> 'es_mi_pago')::BOOLEAN, FALSE) AS es_mi_pago,
           ARRAY(SELECT jsonb_array_elements_text(
                     CASE WHEN jsonb_typeof(p_pago -> 'deudas_ids') = 'array'
                          THEN p_pago -> 'deudas_ids' ELSE '[]'::JSONB END))::UUID[]
                                                               AS deudas_ids
),

-- ── Pasada 1: el estado de hoy, para saber cuánto le falta a cada deuda ──────────
base_hoy AS (
    SELECT d.id,
           d.titulo,
           d.fecha_gasto,
           d.created_at,
           d.es_mi_deuda,
           d.monto::NUMERIC                                            AS monto_original,
           COALESCE(SUM(dp.monto_asignado), 0)::NUMERIC                AS monto_pagado,
           GREATEST(d.monto - COALESCE(SUM(dp.monto_asignado), 0), 0)::NUMERIC
                                                                       AS saldo_pendiente
    FROM deudas d
    LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
    WHERE d.deudor_id = p_deudor_id
    GROUP BY d.id
),

-- Saldo a favor de cada parte: sobrante de los pagos reales (los cruces no cuentan).
favor_hoy AS (
    SELECT COALESCE(SUM(sobrante) FILTER (WHERE es_mi_pago), 0)     AS favor_owner_ini,
           COALESCE(SUM(sobrante) FILTER (WHERE NOT es_mi_pago), 0) AS favor_debtor_ini
    FROM (
        SELECT p.es_mi_pago,
               p.monto_total - COALESCE(SUM(dp.monto_asignado), 0) AS sobrante
        FROM pagos p
        LEFT JOIN detalle_pagos dp ON dp.pago_id = p.id
        WHERE p.deudor_id = p_deudor_id
          AND NOT COALESCE(p.es_compensacion, FALSE)
        GROUP BY p.id, p.es_mi_pago, p.monto_total
    ) s
    WHERE sobrante > 0.01
),

-- Mismo abono que la pasada 2 (ver allí): hace falta aquí porque el pago se reparte
-- sobre lo que falta NETO del crédito ya entregado, no sobre el saldo bruto.
saldo_hoy AS (
    SELECT a.id, a.fecha_gasto, a.created_at, a.es_mi_deuda,
           ROUND(a.saldo_pendiente - CASE
               WHEN a.saldo_pendiente > 0.01
                    AND (a.credito_ini - a.consumido_antes) > 0.01
               THEN LEAST(a.saldo_pendiente, a.credito_ini - a.consumido_antes)
               ELSE 0
           END, 2) AS saldo_real
    FROM (
        SELECT b.*,
               CASE WHEN b.es_mi_deuda THEN f.favor_owner_ini ELSE f.favor_debtor_ini END
                   AS credito_ini,
               COALESCE(
                   SUM(b.saldo_pendiente) FILTER (WHERE b.saldo_pendiente > 0.01)
                       OVER (PARTITION BY b.es_mi_deuda
                             ORDER BY b.fecha_gasto, b.created_at, b.id
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
                   0) AS consumido_antes
        FROM base_hoy b
        CROSS JOIN favor_hoy f
    ) a
),

-- ── El reparto del pago planeado ─────────────────────────────────────────────────
-- Solo deudas elegidas, del lado de quien paga, de la más antigua a la más reciente.
-- Es el bucle `EXIT WHEN restante <= 0.01; asignar := LEAST(saldo, restante)` escrito
-- con una suma acumulada. Redondeado a centavos porque así se va a escribir.
reparto AS (
    SELECT e.id,
           ROUND(CASE WHEN pp.monto - e.repartido_antes > 0.01
                      THEN LEAST(e.saldo_real, pp.monto - e.repartido_antes)
                      ELSE 0 END, 2) AS pago
    FROM (
        SELECT s.id, s.saldo_real,
               COALESCE(SUM(s.saldo_real)
                            OVER (ORDER BY s.fecha_gasto, s.created_at, s.id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
                        0) AS repartido_antes
        FROM saldo_hoy s
        CROSS JOIN pago_planeado pp
        WHERE s.id = ANY(pp.deudas_ids)
          AND s.es_mi_deuda = pp.es_mi_pago
          AND s.saldo_real > 0.01
    ) e
    CROSS JOIN pago_planeado pp
),
reparto_total AS (
    SELECT pp.monto,
           pp.es_mi_pago,
           COALESCE((SELECT SUM(pago) FROM reparto), 0)          AS asignado,
           pp.monto - COALESCE((SELECT SUM(pago) FROM reparto), 0) AS sobrante
    FROM pago_planeado pp
),

-- ── Pasada 2: el estado con el pago ya puesto ────────────────────────────────────
-- Es exactamente lo que habrá en las tablas después de `registrar_pago`, antes de
-- materializar el cruce. Sin pago planeado coincide con la pasada 1.
base AS (
    SELECT b.id, b.titulo, b.fecha_gasto, b.created_at, b.es_mi_deuda, b.monto_original,
           b.monto_pagado + COALESCE(r.pago, 0)                        AS monto_pagado,
           GREATEST(b.saldo_pendiente - COALESCE(r.pago, 0), 0)        AS saldo_pendiente,
           COALESCE(r.pago, 0)                                         AS pago_planeado
    FROM base_hoy b
    LEFT JOIN reparto r ON r.id = b.id
),

-- El sobrante del pago planeado es crédito de quien paga, igual que el de un pago real
-- (y con el mismo umbral: un sobrante de un centavo no cuenta).
favor AS (
    SELECT f.favor_owner_ini
             + CASE WHEN rt.es_mi_pago AND rt.sobrante > 0.01 THEN rt.sobrante ELSE 0 END
               AS favor_owner_ini,
           f.favor_debtor_ini
             + CASE WHEN NOT rt.es_mi_pago AND rt.sobrante > 0.01 THEN rt.sobrante ELSE 0 END
               AS favor_debtor_ini
    FROM favor_hoy f
    CROSS JOIN reparto_total rt
),

-- Ese crédito abona las deudas de quien pagó, de la más antigua a la más reciente.
-- `consumido_antes` es lo que se llevaron las deudas anteriores DE SU MISMO LADO: es el
-- equivalente exacto de ir restando el crédito en un bucle.
abono_pos AS (
    SELECT b.*,
           CASE WHEN b.es_mi_deuda THEN f.favor_owner_ini ELSE f.favor_debtor_ini END
               AS credito_ini,
           COALESCE(
               SUM(b.saldo_pendiente) FILTER (WHERE b.saldo_pendiente > 0.01)
                   OVER (PARTITION BY b.es_mi_deuda
                         ORDER BY b.fecha_gasto, b.created_at, b.id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
               0) AS consumido_antes
    FROM base b
    CROSS JOIN favor f
),
calc AS (
    SELECT a.id, a.titulo, a.fecha_gasto, a.created_at, a.es_mi_deuda,
           a.monto_original, a.monto_pagado, a.saldo_pendiente, a.pago_planeado,
           abono.v                                           AS abono_saldo_favor,
           ROUND(a.saldo_pendiente - abono.v, 2)             AS saldo_real
    FROM abono_pos a
    CROSS JOIN LATERAL (
        SELECT CASE
                   WHEN a.saldo_pendiente > 0.01
                        AND (a.credito_ini - a.consumido_antes) > 0.01
                   THEN LEAST(a.saldo_pendiente, a.credito_ini - a.consumido_antes)
                   ELSE 0
               END AS v
    ) abono
),
tot AS (
    SELECT COALESCE(SUM(saldo_real)        FILTER (WHERE NOT es_mi_deuda), 0) AS te_deben,
           COALESCE(SUM(saldo_real)        FILTER (WHERE es_mi_deuda),     0) AS tu_debes,
           COALESCE(SUM(abono_saldo_favor) FILTER (WHERE es_mi_deuda),     0) AS usado_owner,
           COALESCE(SUM(abono_saldo_favor) FILTER (WHERE NOT es_mi_deuda), 0) AS usado_debtor,
           COALESCE(SUM(monto_original), 0)                                   AS total_original,
           COALESCE(SUM(monto_pagado), 0)                                     AS total_pagado,
           COUNT(*)                                                           AS n,
           COUNT(*) FILTER (WHERE saldo_real <= 0.01)                         AS n_pagadas,
           COUNT(*) FILTER (WHERE saldo_real >  0.01)                         AS n_pendientes
    FROM calc
),
cruzable AS (
    SELECT ROUND(LEAST(t.te_deben, t.tu_debes), 2) AS monto FROM tot t
),

-- Cruce sugerido: FIFO puro en cada lado sobre el saldo_real, la más antigua primero.
cruce_pos AS (
    SELECT c.*,
           cz.monto AS cruzable,
           COALESCE(
               SUM(c.saldo_real) FILTER (WHERE c.saldo_real > 0.01)
                   OVER (PARTITION BY c.es_mi_deuda
                         ORDER BY c.fecha_gasto, c.created_at, c.id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
               0) AS cruzado_antes
    FROM calc c
    CROSS JOIN cruzable cz
),
final AS (
    SELECT p.id, p.titulo, p.fecha_gasto, p.created_at, p.es_mi_deuda,
           p.monto_original, p.monto_pagado, p.saldo_pendiente, p.pago_planeado,
           p.abono_saldo_favor, p.saldo_real,
           CASE
               WHEN p.cruzable > 0.01
                    AND p.saldo_real > 0.01
                    AND (p.cruzable - p.cruzado_antes) > 0.01
               THEN LEAST(p.saldo_real, p.cruzable - p.cruzado_antes)
               ELSE 0
           END AS cruce_sugerido
    FROM cruce_pos p
)

SELECT jsonb_build_object(
    'deudas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'id', id,
            'titulo', titulo,
            'fecha_gasto', fecha_gasto,
            -- El desempate del FIFO: la app lo necesita para calcular igual sin red.
            'creado', created_at,
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
        )
        -- Solo con pago planeado, para que sin él la salida no cambie ni en una clave.
        || CASE WHEN p_pago IS NOT NULL
                THEN jsonb_build_object('pago_planeado', ROUND(pago_planeado, 2))
                ELSE '{}'::JSONB END
        ORDER BY fecha_gasto DESC, created_at DESC, id)
        FROM final), '[]'::JSONB),

    'resumen', jsonb_build_object(
        'total_original',  ROUND(t.total_original, 2),
        'total_pagado',    ROUND(t.total_pagado, 2),
        'total_pendiente', ROUND(t.te_deben + t.tu_debes, 2),
        'total_te_deben',  CASE WHEN p_pov = 'owner' THEN t.te_deben ELSE t.tu_debes END,
        'total_tu_debes',  CASE WHEN p_pov = 'owner' THEN t.tu_debes ELSE t.te_deben END,
        -- El crédito que no abonó ninguna deuda es deuda pura: lo que el deudor pagó de
        -- más se lo debes, lo que pagaste de más te lo debe. Sobre el crédito RESTANTE.
        'neto', (CASE WHEN p_pov = 'owner' THEN 1 ELSE -1 END) * ROUND(
                    t.te_deben - t.tu_debes
                    - (f.favor_debtor_ini - t.usado_debtor)
                    + (f.favor_owner_ini  - t.usado_owner), 2),
        'saldo_favor', CASE WHEN p_pov = 'owner'
                            THEN ROUND(f.favor_debtor_ini - t.usado_debtor, 2)
                            ELSE ROUND(f.favor_owner_ini  - t.usado_owner,  2) END,
        'saldo_favor_owner', CASE WHEN p_pov = 'owner'
                            THEN ROUND(f.favor_owner_ini  - t.usado_owner,  2)
                            ELSE ROUND(f.favor_debtor_ini - t.usado_debtor, 2) END,
        'monto_ideal_a_cruzar', cz.monto,
        'count', t.n,
        'count_pagadas', t.n_pagadas,
        'count_pendientes', t.n_pendientes
    )
    || CASE WHEN p_pago IS NOT NULL
            THEN jsonb_build_object('pago_planeado', jsonb_build_object(
                     'monto',      ROUND(rt.monto, 2),
                     'es_mi_pago', rt.es_mi_pago,
                     'asignado',   ROUND(rt.asignado, 2),
                     'sobrante',   ROUND(rt.sobrante, 2)))
            ELSE '{}'::JSONB END,

    'cruce_sugerido', jsonb_build_object(
        'monto', cz.monto,
        'lados', jsonb_build_object(
            'te_deben', jsonb_build_object(
                'total', COALESCE((
                    SELECT ROUND(SUM(cruce_sugerido), 2) FROM final
                    WHERE es_mi_deuda = (p_pov <> 'owner') AND cruce_sugerido > 0.01), 0),
                'items', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'deuda_id', id,
                        'titulo', titulo,
                        'fecha_gasto', fecha_gasto,
                        'es_tu_deuda', FALSE,
                        'monto_original', ROUND(monto_original, 2),
                        'saldo_antes', ROUND(saldo_real, 2),
                        'aplicado', ROUND(cruce_sugerido, 2),
                        'pagado_acumulado', ROUND(monto_original - saldo_real + cruce_sugerido, 2),
                        'saldo_despues', ROUND(saldo_real - cruce_sugerido, 2),
                        'cerrada', (saldo_real - cruce_sugerido) <= 0.01,
                        'abono_saldo_favor', ROUND(abono_saldo_favor, 2)
                    ) ORDER BY fecha_gasto, created_at, id)
                    FROM final
                    WHERE es_mi_deuda = (p_pov <> 'owner') AND cruce_sugerido > 0.01), '[]'::JSONB)
            ),
            'tu_debes', jsonb_build_object(
                'total', COALESCE((
                    SELECT ROUND(SUM(cruce_sugerido), 2) FROM final
                    WHERE es_mi_deuda = (p_pov =  'owner') AND cruce_sugerido > 0.01), 0),
                'items', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'deuda_id', id,
                        'titulo', titulo,
                        'fecha_gasto', fecha_gasto,
                        'es_tu_deuda', TRUE,
                        'monto_original', ROUND(monto_original, 2),
                        'saldo_antes', ROUND(saldo_real, 2),
                        'aplicado', ROUND(cruce_sugerido, 2),
                        'pagado_acumulado', ROUND(monto_original - saldo_real + cruce_sugerido, 2),
                        'saldo_despues', ROUND(saldo_real - cruce_sugerido, 2),
                        'cerrada', (saldo_real - cruce_sugerido) <= 0.01,
                        'abono_saldo_favor', ROUND(abono_saldo_favor, 2)
                    ) ORDER BY fecha_gasto, created_at, id)
                    FROM final
                    WHERE es_mi_deuda = (p_pov =  'owner') AND cruce_sugerido > 0.01), '[]'::JSONB)
            )
        )
    )
)
FROM tot t, favor f, cruzable cz, reparto_total rt;
$function$;

CREATE OR REPLACE FUNCTION public.registrar_pago(p_deudor_id uuid, p_monto numeric, p_es_mi_pago boolean DEFAULT false, p_fecha date DEFAULT CURRENT_DATE, p_idem_key uuid DEFAULT NULL::uuid, p_deudas_ids uuid[] DEFAULT NULL::uuid[])
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_cruce     JSONB;
    v_plan      JSONB;
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

    -- Sin dinero no hay reparto: solo se cruza lo que se pueda.
    IF p_monto IS NULL OR p_monto <= 0.01 THEN
        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);
        RETURN jsonb_build_object('pago_id', NULL, 'cruce', v_cruce - 'estado',
                                  'repetido', FALSE, 'estado', estado_cuenta(p_deudor_id));
    END IF;

    v_pago_id := gen_random_uuid();

    IF p_deudas_ids IS NULL THEN
        -- Automático: el cruce va antes del dinero físico, que no tiene sentido pasarse
        -- billetes por deudas que se anulan entre sí; luego el pago FIFO sobre el lado de
        -- quien paga. Igual que siempre.
        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);

        INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                          es_mi_pago, idem_key, synced)
        VALUES (v_pago_id, p_deudor_id, p_monto, p_fecha, FALSE, p_es_mi_pago,
                p_idem_key, TRUE);

        FOR r IN
            SELECT d.id,
                   d.monto - COALESCE(SUM(dp.monto_asignado), 0) AS saldo
            FROM deudas d
            LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
            WHERE d.deudor_id = p_deudor_id
              AND d.es_mi_deuda = p_es_mi_pago
            GROUP BY d.id
            HAVING d.monto - COALESCE(SUM(dp.monto_asignado), 0) > 0.01
            ORDER BY d.fecha_gasto, d.created_at, d.id
        LOOP
            EXIT WHEN v_restante <= 0.01;
            v_asignar := LEAST(r.saldo, v_restante);
            INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
            VALUES (v_pago_id, r.id, v_asignar, TRUE);
            v_restante := v_restante - v_asignar;
        END LOOP;
    ELSE
        -- Deudas elegidas a mano: primero el pago, solo sobre ellas, y después el cruce
        -- sobre lo que quedó. El reparto es el mismo que la app vio: lo calcula
        -- `estado_cuenta` con este pago planeado.
        v_plan := estado_cuenta(p_deudor_id, 'owner', jsonb_build_object(
                      'monto', p_monto,
                      'es_mi_pago', p_es_mi_pago,
                      'deudas_ids', to_jsonb(p_deudas_ids)));

        INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                          es_mi_pago, idem_key, synced)
        VALUES (v_pago_id, p_deudor_id, p_monto, p_fecha, FALSE, p_es_mi_pago,
                p_idem_key, TRUE);

        FOR r IN
            SELECT (d ->> 'id')::UUID AS id, (d ->> 'pago_planeado')::NUMERIC AS pago
            FROM jsonb_array_elements(v_plan -> 'deudas') d
            WHERE (d ->> 'pago_planeado')::NUMERIC > 0
        LOOP
            INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
            VALUES (v_pago_id, r.id, r.pago, TRUE);
            v_restante := v_restante - r.pago;
        END LOOP;

        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);
    END IF;

    -- Lo que no se asignó queda como saldo a favor de quien pagó (no se fuerza).
    RETURN jsonb_build_object('pago_id', v_pago_id,
                              'cruce', v_cruce - 'estado',
                              'sobrante', ROUND(v_restante, 2),
                              'repetido', FALSE,
                              'estado', estado_cuenta(p_deudor_id));
END;
$function$;

CREATE OR REPLACE FUNCTION public._editar_cruce_aplicar(p_cruce_id uuid, p_excluir uuid[])
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_deudor    UUID;
    v_pago_mias UUID;
    v_pago_suya UUID;
    v_n_pagos   INT;
    v_creado    TIMESTAMPTZ;
    v_antes     JSONB;
    v_monto_ant NUMERIC;
    v_nuevo     NUMERIC;
    v_items     JSONB;
    v_ajenas    UUID[];
BEGIN
    SELECT min(deudor_id::TEXT)::UUID, count(*), max(created_at),
           (array_agg(id) FILTER (WHERE es_mi_pago))[1],
           (array_agg(id) FILTER (WHERE NOT es_mi_pago))[1],
           max(monto_total)
      INTO v_deudor, v_n_pagos, v_creado, v_pago_mias, v_pago_suya, v_monto_ant
      FROM pagos
     WHERE cruce_id = p_cruce_id AND COALESCE(es_compensacion, FALSE);

    IF v_n_pagos = 0 THEN
        RAISE EXCEPTION 'No existe el cruce %', p_cruce_id;
    END IF;
    IF v_n_pagos <> 2 OR v_pago_mias IS NULL OR v_pago_suya IS NULL THEN
        RAISE EXCEPTION 'El cruce % está mal formado (% pagos virtuales)', p_cruce_id, v_n_pagos;
    END IF;

    -- La última operación. El pago y su cruce se crean en la misma transacción, así que
    -- comparten `created_at`; los cruces viejos de la app llegaban con unos milisegundos
    -- de diferencia, de ahí el margen.
    IF EXISTS (SELECT 1 FROM pagos
                WHERE deudor_id = v_deudor
                  AND cruce_id IS DISTINCT FROM p_cruce_id
                  AND created_at > v_creado + INTERVAL '5 seconds') THEN
        RAISE EXCEPTION 'Solo se puede editar el cruce de la última operación del deudor';
    END IF;

    SELECT array_agg(x) INTO v_ajenas
      FROM unnest(p_excluir) x
     WHERE NOT EXISTS (SELECT 1 FROM detalle_pagos dp
                        WHERE dp.pago_id IN (v_pago_mias, v_pago_suya) AND dp.deuda_id = x);
    IF v_ajenas IS NOT NULL THEN
        RAISE EXCEPTION 'Estas deudas no están en el cruce: %', v_ajenas;
    END IF;
    IF p_excluir IS NOT NULL AND cardinality(p_excluir) = 0 THEN
        RAISE EXCEPTION 'No se eligió ninguna deuda para sacar del cruce';
    END IF;

    -- Cómo estaba, para la bitácora y para devolver el antes.
    SELECT jsonb_build_object(
               'pagos', (SELECT jsonb_agg(to_jsonb(p) ORDER BY p.es_mi_pago DESC)
                           FROM pagos p WHERE p.cruce_id = p_cruce_id),
               'detalle_pagos', (SELECT jsonb_agg(to_jsonb(dp) ORDER BY dp.pago_id, dp.deuda_id)
                                   FROM detalle_pagos dp
                                  WHERE dp.pago_id IN (v_pago_mias, v_pago_suya)))
      INTO v_antes;

    -- El recorte. `lado` = TRUE es el pago virtual del dueño: cubre las deudas que tú
    -- debes. `previo` es lo que conservan las deudas anteriores del mismo lado, que se
    -- quedan con lo suyo primero (FIFO, igual que `aplicar_cruce`).
    WITH items AS (
        SELECT p.es_mi_pago                           AS lado,
               d.id                                   AS deuda_id,
               d.titulo,
               d.fecha_gasto,
               d.created_at,
               ROUND(SUM(dp.monto_asignado), 2)       AS antes,
               (p_excluir IS NULL OR d.id = ANY(p_excluir)) AS excluida
          FROM pagos p
          JOIN detalle_pagos dp ON dp.pago_id = p.id
          JOIN deudas d         ON d.id = dp.deuda_id
         WHERE p.cruce_id = p_cruce_id
         GROUP BY p.es_mi_pago, d.id, d.titulo, d.fecha_gasto, d.created_at
    ),
    nuevo AS (
        SELECT ROUND(LEAST(
                   COALESCE(SUM(antes) FILTER (WHERE lado     AND NOT excluida), 0),
                   COALESCE(SUM(antes) FILTER (WHERE NOT lado AND NOT excluida), 0)), 2) AS monto
          FROM items
    ),
    pos AS (
        SELECT i.*, n.monto AS cruce_nuevo,
               COALESCE(SUM(i.antes) FILTER (WHERE NOT i.excluida)
                            OVER (PARTITION BY i.lado ORDER BY i.fecha_gasto, i.created_at, i.deuda_id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS previo
          FROM items i CROSS JOIN nuevo n
    )
    SELECT (SELECT monto FROM nuevo),
           COALESCE(jsonb_agg(jsonb_build_object(
               'lado',        CASE WHEN lado THEN 'tu_debes' ELSE 'te_deben' END,
               'deuda_id',    deuda_id,
               'titulo',      titulo,
               'fecha_gasto', fecha_gasto,
               'excluida',    excluida,
               'antes',       antes,
               'despues',     despues
           ) ORDER BY lado DESC, fecha_gasto, created_at, deuda_id), '[]'::JSONB)
      INTO v_nuevo, v_items
      FROM (
        SELECT pos.*,
               CASE WHEN excluida OR cruce_nuevo <= 0.01 THEN 0
                    ELSE ROUND(GREATEST(LEAST(antes, cruce_nuevo - previo), 0), 2)
               END AS despues
          FROM pos
      ) r;

    IF v_nuevo <= 0.01 THEN
        -- Borra los dos pagos virtuales; sus detalles se van en cascada.
        DELETE FROM pagos WHERE cruce_id = p_cruce_id;
        v_nuevo := 0;
    ELSE
        UPDATE pagos SET monto_total = v_nuevo WHERE cruce_id = p_cruce_id;
        DELETE FROM detalle_pagos WHERE pago_id IN (v_pago_mias, v_pago_suya);
        INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
        SELECT CASE WHEN it ->> 'lado' = 'tu_debes' THEN v_pago_mias ELSE v_pago_suya END,
               (it ->> 'deuda_id')::UUID,
               (it ->> 'despues')::NUMERIC,
               TRUE
          FROM jsonb_array_elements(v_items) it
         WHERE (it ->> 'despues')::NUMERIC > 0.01;
    END IF;

    RETURN jsonb_build_object(
        'cruce_id',      p_cruce_id,
        'deudor_id',     v_deudor,
        'monto_antes',   ROUND(v_monto_ant, 2),
        'monto_despues', ROUND(v_nuevo, 2),
        'eliminado',     v_nuevo = 0,
        'items',         v_items,
        'antes',         v_antes);
END;
$function$;
