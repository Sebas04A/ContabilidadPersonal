-- Deudas v2 — migración base.
--
-- Copia fiel del esquema de producción (rcmdzvbxerumzxvnubfo) volcado el 2026-09-23 con
-- `supabase db dump --linked --schema public`, generada por
-- scripts/v2/generar_migracion_base.py. NO editar a mano: los cambios van en migraciones
-- nuevas. Diferencias con producción (a propósito):
--   * sin las policies USING (true) ni los GRANT a anon (agujeros de seguridad, ver
--     deudas/PLAN_MULTIUSUARIO.md §1.5);
--   * REVOKE explícito a anon al final.



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

CREATE SCHEMA IF NOT EXISTS "public";

ALTER SCHEMA "public" OWNER TO "pg_database_owner";

COMMENT ON SCHEMA "public" IS 'standard public schema';

CREATE OR REPLACE FUNCTION "public"."_editar_cruce_aplicar"("p_cruce_id" "uuid", "p_excluir" "uuid"[]) RETURNS "jsonb"
    LANGUAGE "plpgsql"
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
$$;

ALTER FUNCTION "public"."_editar_cruce_aplicar"("p_cruce_id" "uuid", "p_excluir" "uuid"[]) OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."_idem_derivada"("p_idem_key" "uuid", "p_sufijo" "text") RETURNS "uuid"
    LANGUAGE "sql" IMMUTABLE
    AS $$
    SELECT CASE WHEN p_idem_key IS NULL THEN NULL
                ELSE md5(p_idem_key::TEXT || '|' || p_sufijo)::UUID END;
$$;

ALTER FUNCTION "public"."_idem_derivada"("p_idem_key" "uuid", "p_sufijo" "text") OWNER TO "postgres";

CREATE OR REPLACE FUNCTION "public"."aplicar_cruce"("p_deudor_id" "uuid", "p_fecha" "date" DEFAULT CURRENT_DATE, "p_idem_key" "uuid" DEFAULT NULL::"uuid", "p_con_estado" boolean DEFAULT true) RETURNS "jsonb"
    LANGUAGE "plpgsql"
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

ALTER FUNCTION "public"."aplicar_cruce"("p_deudor_id" "uuid", "p_fecha" "date", "p_idem_key" "uuid", "p_con_estado" boolean) OWNER TO "postgres";

COMMENT ON FUNCTION "public"."aplicar_cruce"("p_deudor_id" "uuid", "p_fecha" "date", "p_idem_key" "uuid", "p_con_estado" boolean) IS 'Materializa el cruce disponible de un deudor (FIFO por lado). Atómico e idempotente por idem_key. Con p_con_estado=FALSE no recalcula el estado final.';

CREATE OR REPLACE FUNCTION "public"."editar_cruce"("p_cruce_id" "uuid", "p_excluir" "uuid"[] DEFAULT NULL::"uuid"[], "p_simular" boolean DEFAULT false, "p_idem_key" "uuid" DEFAULT NULL::"uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql"
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

ALTER FUNCTION "public"."editar_cruce"("p_cruce_id" "uuid", "p_excluir" "uuid"[], "p_simular" boolean, "p_idem_key" "uuid") OWNER TO "postgres";

COMMENT ON FUNCTION "public"."editar_cruce"("p_cruce_id" "uuid", "p_excluir" "uuid"[], "p_simular" boolean, "p_idem_key" "uuid") IS 'Saca deudas del cruce de la última operación (NULL = deshacerlo entero). El pago real no se toca; el cruce se recorta para que cuadre. Con p_simular no escribe nada.';

CREATE OR REPLACE FUNCTION "public"."editar_pago"("p_pago_id" "uuid", "p_fecha" "date" DEFAULT NULL::"date", "p_nota" "text" DEFAULT NULL::"text", "p_idem_key" "uuid" DEFAULT NULL::"uuid") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    v_pago    pagos%ROWTYPE;
    v_previa  pagos_editados%ROWTYPE;
    v_fecha   DATE;
    v_nota    TEXT;
    v_ids     UUID[];
    v_antes   JSONB;
    v_despues JSONB;
BEGIN
    IF p_idem_key IS NOT NULL THEN
        SELECT * INTO v_previa FROM pagos_editados WHERE idem_key = p_idem_key;
        IF FOUND THEN
            SELECT * INTO v_pago FROM pagos WHERE id = v_previa.pago_id;
            RETURN jsonb_build_object('pago_id', v_previa.pago_id,
                                      'deudor_id', v_previa.deudor_id,
                                      'fecha', v_pago.fecha_pago,
                                      'nota', v_pago.nota,
                                      'pagos_movidos', jsonb_array_length(v_previa.despues),
                                      'repetido', TRUE);
        END IF;
    END IF;

    SELECT * INTO v_pago FROM pagos WHERE id = p_pago_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe el pago %', p_pago_id;
    END IF;
    IF COALESCE(v_pago.es_compensacion, FALSE) THEN
        RAISE EXCEPTION 'Un cruce no se edita solo: edita el pago que lo disparó';
    END IF;

    -- El mismo lock que `registrar_pago`, `aplicar_cruce` y `editar_cruce`.
    PERFORM pg_advisory_xact_lock(hashtext(v_pago.deudor_id::TEXT));
    SELECT * INTO v_pago FROM pagos WHERE id = p_pago_id;

    v_fecha := COALESCE(p_fecha, v_pago.fecha_pago);
    v_nota  := CASE WHEN p_nota IS NULL THEN v_pago.nota
                    ELSE NULLIF(btrim(p_nota), '') END;
    IF length(v_nota) > 500 THEN
        RAISE EXCEPTION 'La nota no puede pasar de 500 caracteres';
    END IF;

    IF v_fecha = v_pago.fecha_pago AND v_nota IS NOT DISTINCT FROM v_pago.nota THEN
        RAISE EXCEPTION 'No hay cambios que guardar';
    END IF;

    -- El pago real y, si la fecha cambia, el cruce de su misma operación.
    SELECT array_agg(id) INTO v_ids
      FROM pagos
     WHERE id = p_pago_id
        OR (v_fecha <> v_pago.fecha_pago
            AND deudor_id = v_pago.deudor_id
            AND COALESCE(es_compensacion, FALSE)
            AND fecha_pago = v_pago.fecha_pago
            AND abs(extract(epoch FROM created_at - v_pago.created_at)) < 2);

    SELECT jsonb_agg(to_jsonb(p) ORDER BY p.es_compensacion, p.id)
      INTO v_antes FROM pagos p WHERE p.id = ANY(v_ids);

    UPDATE pagos SET fecha_pago = v_fecha WHERE id = ANY(v_ids);
    UPDATE pagos SET nota = v_nota WHERE id = p_pago_id;

    SELECT jsonb_agg(to_jsonb(p) ORDER BY p.es_compensacion, p.id)
      INTO v_despues FROM pagos p WHERE p.id = ANY(v_ids);

    INSERT INTO pagos_editados(idem_key, pago_id, deudor_id, antes, despues)
    VALUES (p_idem_key, p_pago_id, v_pago.deudor_id, v_antes, v_despues);

    RETURN jsonb_build_object('pago_id', p_pago_id,
                              'deudor_id', v_pago.deudor_id,
                              'fecha_antes', v_pago.fecha_pago,
                              'fecha', v_fecha,
                              'nota_antes', v_pago.nota,
                              'nota', v_nota,
                              'pagos_movidos', cardinality(v_ids),
                              'repetido', FALSE);
END;
$$;

ALTER FUNCTION "public"."editar_pago"("p_pago_id" "uuid", "p_fecha" "date", "p_nota" "text", "p_idem_key" "uuid") OWNER TO "postgres";

COMMENT ON FUNCTION "public"."editar_pago"("p_pago_id" "uuid", "p_fecha" "date", "p_nota" "text", "p_idem_key" "uuid") IS 'Cambia la fecha y/o la nota de un pago real. La fecha arrastra al cruce de su misma operación; el monto y el reparto no se tocan.';

CREATE OR REPLACE FUNCTION "public"."estado_cuenta"("p_deudor_id" "uuid", "p_pov" "text" DEFAULT 'owner'::"text", "p_pago" "jsonb" DEFAULT NULL::"jsonb") RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    AS $$
WITH
pago_planeado AS (
    SELECT COALESCE((p_pago ->> 'monto')::NUMERIC, 0)          AS monto,
           COALESCE((p_pago ->> 'es_mi_pago')::BOOLEAN, FALSE) AS es_mi_pago,
           ARRAY(SELECT jsonb_array_elements_text(
                     CASE WHEN jsonb_typeof(p_pago -> 'deudas_ids') = 'array'
                          THEN p_pago -> 'deudas_ids' ELSE '[]'::JSONB END))::UUID[]
                                                               AS deudas_ids
),

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

base AS (
    SELECT b.id, b.titulo, b.fecha_gasto, b.created_at, b.es_mi_deuda, b.monto_original,
           b.monto_pagado + COALESCE(r.pago, 0)                        AS monto_pagado,
           GREATEST(b.saldo_pendiente - COALESCE(r.pago, 0), 0)        AS saldo_pendiente,
           COALESCE(r.pago, 0)                                         AS pago_planeado
    FROM base_hoy b
    LEFT JOIN reparto r ON r.id = b.id
),

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
$$;

ALTER FUNCTION "public"."estado_cuenta"("p_deudor_id" "uuid", "p_pov" "text", "p_pago" "jsonb") OWNER TO "postgres";

COMMENT ON FUNCTION "public"."estado_cuenta"("p_deudor_id" "uuid", "p_pov" "text", "p_pago" "jsonb") IS 'Estado de cuenta completo de un deudor, con cruce sugerido. Con p_pago devuelve el estado tal como quedaría tras registrar ese pago. Derivado puro: no escribe.';

CREATE OR REPLACE FUNCTION "public"."registrar_pago"("p_deudor_id" "uuid", "p_monto" numeric, "p_es_mi_pago" boolean DEFAULT false, "p_fecha" "date" DEFAULT CURRENT_DATE, "p_idem_key" "uuid" DEFAULT NULL::"uuid", "p_deudas_ids" "uuid"[] DEFAULT NULL::"uuid"[]) RETURNS "jsonb"
    LANGUAGE "plpgsql"
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
$$;

ALTER FUNCTION "public"."registrar_pago"("p_deudor_id" "uuid", "p_monto" numeric, "p_es_mi_pago" boolean, "p_fecha" "date", "p_idem_key" "uuid", "p_deudas_ids" "uuid"[]) OWNER TO "postgres";

COMMENT ON FUNCTION "public"."registrar_pago"("p_deudor_id" "uuid", "p_monto" numeric, "p_es_mi_pago" boolean, "p_fecha" "date", "p_idem_key" "uuid", "p_deudas_ids" "uuid"[]) IS 'Registra un pago. Automático: cruza y reparte FIFO. Con p_deudas_ids: reparte solo entre esas deudas y cruza después. Atómico e idempotente por idem_key.';

SET default_tablespace = '';

SET default_table_access_method = "heap";

CREATE TABLE IF NOT EXISTS "public"."cruces_editados" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "idem_key" "uuid",
    "cruce_id" "uuid" NOT NULL,
    "deudor_id" "uuid" NOT NULL,
    "excluidas" "uuid"[],
    "monto_antes" numeric NOT NULL,
    "monto_despues" numeric NOT NULL,
    "antes" "jsonb" NOT NULL,
    "despues" "jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE "public"."cruces_editados" OWNER TO "postgres";

COMMENT ON TABLE "public"."cruces_editados" IS 'Bitácora de editar_cruce: qué deudas se sacaron de un cruce y cómo estaba antes.';

CREATE TABLE IF NOT EXISTS "public"."detalle_pagos" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "pago_id" "uuid" NOT NULL,
    "deuda_id" "uuid" NOT NULL,
    "monto_asignado" numeric(10,2) NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "synced" boolean DEFAULT false
);

ALTER TABLE "public"."detalle_pagos" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."deudas" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "deudor_id" "uuid" NOT NULL,
    "titulo" "text" NOT NULL,
    "monto" numeric(10,2) NOT NULL,
    "fecha_gasto" "date" DEFAULT CURRENT_DATE NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "synced" boolean DEFAULT false,
    "es_mi_deuda" boolean DEFAULT false
);

ALTER TABLE "public"."deudas" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."deudores" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "nombre" "text" NOT NULL,
    "token" "text" DEFAULT ("gen_random_uuid"())::"text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "synced" boolean DEFAULT false
);

ALTER TABLE "public"."deudores" OWNER TO "postgres";

CREATE TABLE IF NOT EXISTS "public"."pagos" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "deudor_id" "uuid" NOT NULL,
    "monto_total" numeric(10,2) NOT NULL,
    "fecha_pago" "date" DEFAULT CURRENT_DATE NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "synced" boolean DEFAULT false,
    "es_compensacion" boolean DEFAULT false,
    "es_mi_pago" boolean DEFAULT false,
    "cruce_id" "uuid",
    "idem_key" "uuid",
    "nota" "text"
);

ALTER TABLE "public"."pagos" OWNER TO "postgres";

COMMENT ON COLUMN "public"."pagos"."cruce_id" IS 'Los dos pagos virtuales de un mismo cruce comparten este id. NULL si no es un cruce.';

COMMENT ON COLUMN "public"."pagos"."idem_key" IS 'Clave de idempotencia del cliente: reintentar el mismo pago no lo duplica.';

COMMENT ON COLUMN "public"."pagos"."nota" IS 'Texto libre del pago: de qué fue, cómo se entregó.';

CREATE TABLE IF NOT EXISTS "public"."pagos_editados" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "idem_key" "uuid",
    "pago_id" "uuid" NOT NULL,
    "deudor_id" "uuid" NOT NULL,
    "antes" "jsonb" NOT NULL,
    "despues" "jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE "public"."pagos_editados" OWNER TO "postgres";

COMMENT ON TABLE "public"."pagos_editados" IS 'Bitácora de editar_pago: la fecha y la nota de un pago antes y después.';

CREATE OR REPLACE VIEW "public"."vista_estado_deudas" AS
SELECT
    NULL::"uuid" AS "id",
    NULL::"text" AS "titulo",
    NULL::numeric(10,2) AS "monto_original",
    NULL::"date" AS "fecha_gasto",
    NULL::"uuid" AS "deudor_id",
    NULL::boolean AS "es_mi_deuda",
    NULL::numeric AS "monto_pagado",
    NULL::numeric AS "saldo_pendiente",
    NULL::"text" AS "estado";

ALTER VIEW "public"."vista_estado_deudas" OWNER TO "postgres";

ALTER TABLE ONLY "public"."cruces_editados"
    ADD CONSTRAINT "cruces_editados_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."detalle_pagos"
    ADD CONSTRAINT "detalle_pagos_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."deudas"
    ADD CONSTRAINT "deudas_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."deudores"
    ADD CONSTRAINT "deudores_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."deudores"
    ADD CONSTRAINT "deudores_token_key" UNIQUE ("token");

ALTER TABLE ONLY "public"."pagos_editados"
    ADD CONSTRAINT "pagos_editados_pkey" PRIMARY KEY ("id");

ALTER TABLE ONLY "public"."pagos"
    ADD CONSTRAINT "pagos_pkey" PRIMARY KEY ("id");

CREATE INDEX "idx_cruces_editados_deudor" ON "public"."cruces_editados" USING "btree" ("deudor_id");

CREATE UNIQUE INDEX "idx_cruces_editados_idem" ON "public"."cruces_editados" USING "btree" ("idem_key") WHERE ("idem_key" IS NOT NULL);

CREATE INDEX "idx_detalle_deuda" ON "public"."detalle_pagos" USING "btree" ("deuda_id");

CREATE INDEX "idx_detalle_pago" ON "public"."detalle_pagos" USING "btree" ("pago_id");

CREATE INDEX "idx_deudas_deudor" ON "public"."deudas" USING "btree" ("deudor_id");

CREATE INDEX "idx_pagos_cruce" ON "public"."pagos" USING "btree" ("cruce_id") WHERE ("cruce_id" IS NOT NULL);

CREATE INDEX "idx_pagos_deudor" ON "public"."pagos" USING "btree" ("deudor_id");

CREATE INDEX "idx_pagos_editados_deudor" ON "public"."pagos_editados" USING "btree" ("deudor_id");

CREATE UNIQUE INDEX "idx_pagos_editados_idem" ON "public"."pagos_editados" USING "btree" ("idem_key") WHERE ("idem_key" IS NOT NULL);

CREATE UNIQUE INDEX "idx_pagos_idem_key" ON "public"."pagos" USING "btree" ("idem_key") WHERE ("idem_key" IS NOT NULL);

CREATE OR REPLACE VIEW "public"."vista_estado_deudas" AS
 SELECT "d"."id",
    "d"."titulo",
    "d"."monto" AS "monto_original",
    "d"."fecha_gasto",
    "d"."deudor_id",
    "d"."es_mi_deuda",
    COALESCE("sum"("dp"."monto_asignado"), (0)::numeric) AS "monto_pagado",
    ("d"."monto" - COALESCE("sum"("dp"."monto_asignado"), (0)::numeric)) AS "saldo_pendiente",
        CASE
            WHEN (("d"."monto" - COALESCE("sum"("dp"."monto_asignado"), (0)::numeric)) <= 0.001) THEN 'PAGADA'::"text"
            WHEN (COALESCE("sum"("dp"."monto_asignado"), (0)::numeric) > (0)::numeric) THEN 'PARCIAL'::"text"
            ELSE 'PENDIENTE'::"text"
        END AS "estado"
   FROM ("public"."deudas" "d"
     LEFT JOIN "public"."detalle_pagos" "dp" ON (("d"."id" = "dp"."deuda_id")))
  GROUP BY "d"."id";

ALTER TABLE ONLY "public"."cruces_editados"
    ADD CONSTRAINT "cruces_editados_deudor_id_fkey" FOREIGN KEY ("deudor_id") REFERENCES "public"."deudores"("id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."detalle_pagos"
    ADD CONSTRAINT "detalle_pagos_deuda_id_fkey" FOREIGN KEY ("deuda_id") REFERENCES "public"."deudas"("id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."detalle_pagos"
    ADD CONSTRAINT "detalle_pagos_pago_id_fkey" FOREIGN KEY ("pago_id") REFERENCES "public"."pagos"("id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."deudas"
    ADD CONSTRAINT "deudas_deudor_id_fkey" FOREIGN KEY ("deudor_id") REFERENCES "public"."deudores"("id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."pagos"
    ADD CONSTRAINT "pagos_deudor_id_fkey" FOREIGN KEY ("deudor_id") REFERENCES "public"."deudores"("id") ON DELETE CASCADE;

ALTER TABLE ONLY "public"."pagos_editados"
    ADD CONSTRAINT "pagos_editados_deudor_id_fkey" FOREIGN KEY ("deudor_id") REFERENCES "public"."deudores"("id") ON DELETE CASCADE;

ALTER TABLE "public"."cruces_editados" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."detalle_pagos" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."deudas" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."deudores" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."pagos" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "public"."pagos_editados" ENABLE ROW LEVEL SECURITY;

GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

GRANT ALL ON FUNCTION "public"."_editar_cruce_aplicar"("p_cruce_id" "uuid", "p_excluir" "uuid"[]) TO "authenticated";
GRANT ALL ON FUNCTION "public"."_editar_cruce_aplicar"("p_cruce_id" "uuid", "p_excluir" "uuid"[]) TO "service_role";

GRANT ALL ON FUNCTION "public"."_idem_derivada"("p_idem_key" "uuid", "p_sufijo" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."_idem_derivada"("p_idem_key" "uuid", "p_sufijo" "text") TO "service_role";

GRANT ALL ON FUNCTION "public"."aplicar_cruce"("p_deudor_id" "uuid", "p_fecha" "date", "p_idem_key" "uuid", "p_con_estado" boolean) TO "authenticated";
GRANT ALL ON FUNCTION "public"."aplicar_cruce"("p_deudor_id" "uuid", "p_fecha" "date", "p_idem_key" "uuid", "p_con_estado" boolean) TO "service_role";

GRANT ALL ON FUNCTION "public"."editar_cruce"("p_cruce_id" "uuid", "p_excluir" "uuid"[], "p_simular" boolean, "p_idem_key" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."editar_cruce"("p_cruce_id" "uuid", "p_excluir" "uuid"[], "p_simular" boolean, "p_idem_key" "uuid") TO "service_role";

GRANT ALL ON FUNCTION "public"."editar_pago"("p_pago_id" "uuid", "p_fecha" "date", "p_nota" "text", "p_idem_key" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."editar_pago"("p_pago_id" "uuid", "p_fecha" "date", "p_nota" "text", "p_idem_key" "uuid") TO "service_role";

GRANT ALL ON FUNCTION "public"."estado_cuenta"("p_deudor_id" "uuid", "p_pov" "text", "p_pago" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."estado_cuenta"("p_deudor_id" "uuid", "p_pov" "text", "p_pago" "jsonb") TO "service_role";

GRANT ALL ON FUNCTION "public"."registrar_pago"("p_deudor_id" "uuid", "p_monto" numeric, "p_es_mi_pago" boolean, "p_fecha" "date", "p_idem_key" "uuid", "p_deudas_ids" "uuid"[]) TO "authenticated";
GRANT ALL ON FUNCTION "public"."registrar_pago"("p_deudor_id" "uuid", "p_monto" numeric, "p_es_mi_pago" boolean, "p_fecha" "date", "p_idem_key" "uuid", "p_deudas_ids" "uuid"[]) TO "service_role";

GRANT ALL ON TABLE "public"."cruces_editados" TO "authenticated";
GRANT ALL ON TABLE "public"."cruces_editados" TO "service_role";

GRANT ALL ON TABLE "public"."detalle_pagos" TO "authenticated";
GRANT ALL ON TABLE "public"."detalle_pagos" TO "service_role";

GRANT ALL ON TABLE "public"."deudas" TO "authenticated";
GRANT ALL ON TABLE "public"."deudas" TO "service_role";

GRANT ALL ON TABLE "public"."deudores" TO "authenticated";
GRANT ALL ON TABLE "public"."deudores" TO "service_role";

GRANT ALL ON TABLE "public"."pagos" TO "authenticated";
GRANT ALL ON TABLE "public"."pagos" TO "service_role";

GRANT ALL ON TABLE "public"."pagos_editados" TO "authenticated";
GRANT ALL ON TABLE "public"."pagos_editados" TO "service_role";

GRANT ALL ON TABLE "public"."vista_estado_deudas" TO "authenticated";
GRANT ALL ON TABLE "public"."vista_estado_deudas" TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";

ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";

-- ------------------------------------------------------------------------------------
-- Agregado por generar_migracion_base.py: anon no toca nada.
-- ------------------------------------------------------------------------------------
REVOKE ALL ON ALL TABLES IN SCHEMA "public" FROM "anon";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA "public" FROM "anon";
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA "public" FROM "anon", PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON TABLES FROM "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON SEQUENCES FROM "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" REVOKE ALL ON FUNCTIONS FROM "anon", PUBLIC;
