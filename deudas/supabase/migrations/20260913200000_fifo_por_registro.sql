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
