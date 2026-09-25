-- Arreglo (deudas/PLAN_MULTIUSUARIO.md, notas de la fase 9): rechazar o borrar una deuda
-- que está en un cruce mal formado fallaba y la dejaba trabada.
--
--   1. `_sacar_de_cruces`: una deuda en un pago de compensación viejo, sin cruce_id,
--      lanzaba una excepción. Ahora sale de esos pagos, y se borran los que quedan sin
--      detalle, solo entre los que tocó.
--   2. `_editar_cruce_aplicar`: un cruce con los dos pagos virtuales en es_mi_pago = false
--      se repara deduciendo cuál es cuál por las deudas que cubren. Si ni así se puede y
--      viene del recorte libre, saca las deudas excluidas y borra los pagos vacíos.
--
-- Las dos funciones son copia exacta de su versión de 20260924120000 más las líneas
-- marcadas «v2 arreglo cruces mal formados». Conservan su modo: SECURITY INVOKER.
-- `_editar_cruce_aplicar` se puede llamar por la API y depende del RLS para no tocar cruces
-- ajenos; con SECURITY DEFINER cualquiera con sesión editaría el cruce de otro sabiendo su
-- id (la primera versión de esta migración lo hacía y no llegó a la nube).

CREATE OR REPLACE FUNCTION public._sacar_de_cruces(p_deuda_id uuid) RETURNS int
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_cruce uuid;
    v_n     int := 0;
    v_pagos uuid[];  -- v2 arreglo cruces mal formados
BEGIN
    IF EXISTS (SELECT 1 FROM detalle_pagos dp JOIN pagos p ON p.id = dp.pago_id
                WHERE dp.deuda_id = p_deuda_id AND COALESCE(p.es_compensacion, false)
                  AND p.cruce_id IS NULL) THEN
        -- v2 arreglo cruces mal formados (inicio).
        -- Antes esto lanzaba y la deuda no se podía rechazar ni borrar. Ahora la deuda
        -- sale de esos pagos de compensación viejos, y se borran solo los que se quedan
        -- sin ningún detalle. Únicamente los pagos que tocó este DELETE: esta función
        -- corre dentro de RPC SECURITY DEFINER (rechazar_fila, rechazar_propuesta), donde
        -- el RLS no filtra, y un DELETE por condición borraría los huérfanos de otros
        -- usuarios.
        WITH soltados AS (
            DELETE FROM detalle_pagos dp
             USING pagos p
             WHERE p.id = dp.pago_id AND dp.deuda_id = p_deuda_id
               AND COALESCE(p.es_compensacion, false) AND p.cruce_id IS NULL
            RETURNING dp.pago_id)
        SELECT array_agg(DISTINCT pago_id) INTO v_pagos FROM soltados;
        -- En otra sentencia: dentro de la del CTE, el NOT EXISTS todavía vería los
        -- detalles recién borrados.
        DELETE FROM pagos
         WHERE id = ANY(v_pagos)
           AND NOT EXISTS (SELECT 1 FROM detalle_pagos dp WHERE dp.pago_id = pagos.id);
        v_n := v_n + 1;
        -- v2 arreglo cruces mal formados (fin)
    END IF;
    FOR v_cruce IN SELECT DISTINCT p.cruce_id
                     FROM detalle_pagos dp JOIN pagos p ON p.id = dp.pago_id
                    WHERE dp.deuda_id = p_deuda_id AND COALESCE(p.es_compensacion, false)
                      AND p.cruce_id IS NOT NULL LOOP  -- v2 arreglo cruces mal formados
        PERFORM set_config('deudas.recorte_libre', 'on', true);
        PERFORM _editar_cruce_aplicar(v_cruce, ARRAY[p_deuda_id]);
        PERFORM set_config('deudas.recorte_libre', 'off', true);
        v_n := v_n + 1;
    END LOOP;
    RETURN v_n;
END $$;

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
    v_mias_inf  UUID;  -- v2 arreglo cruces mal formados
    v_suya_inf  UUID;  -- v2 arreglo cruces mal formados
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
    -- v2 arreglo cruces mal formados (inicio).
    -- Hay cruces con los dos pagos virtuales en es_mi_pago = false. Cuál es cuál se
    -- deduce de las deudas que cubre cada uno (el pago del dueño cubre lo que él debe) y
    -- se corrige la marca. Solo si da dos pagos distintos; si no, sigue siendo un cruce
    -- mal formado.
    IF v_n_pagos = 2 AND (v_pago_mias IS NULL OR v_pago_suya IS NULL) THEN
        SELECT (array_agg(DISTINCT p.id) FILTER (WHERE d.es_mi_deuda))[1],
               (array_agg(DISTINCT p.id) FILTER (WHERE NOT d.es_mi_deuda))[1]
          INTO v_mias_inf, v_suya_inf
          FROM pagos p
          JOIN detalle_pagos dp ON dp.pago_id = p.id
          JOIN deudas d         ON d.id = dp.deuda_id
         WHERE p.cruce_id = p_cruce_id AND COALESCE(p.es_compensacion, FALSE);
        IF v_mias_inf IS NOT NULL AND v_suya_inf IS NOT NULL AND v_mias_inf <> v_suya_inf THEN
            v_pago_mias := v_mias_inf;
            v_pago_suya := v_suya_inf;
            UPDATE pagos SET es_mi_pago = (id = v_pago_mias) WHERE id IN (v_pago_mias, v_pago_suya);
        END IF;
    END IF;
    -- v2 arreglo cruces mal formados (fin)
    IF v_n_pagos <> 2 OR v_pago_mias IS NULL OR v_pago_suya IS NULL THEN
        -- v2 arreglo cruces mal formados (inicio).
        -- _sacar_de_cruces (recorte libre) no puede quedarse trabado en un cruce que no se
        -- puede recomponer: saca de él las deudas excluidas y borra los pagos que quedan
        -- vacíos. Filtra por cruce_id, que es de un solo dueño.
        IF COALESCE(current_setting('deudas.recorte_libre', true), '') = 'on' THEN
            DELETE FROM detalle_pagos
             WHERE deuda_id = ANY(p_excluir)
               AND pago_id IN (SELECT id FROM pagos WHERE cruce_id = p_cruce_id);
            DELETE FROM pagos
             WHERE cruce_id = p_cruce_id
               AND NOT EXISTS (SELECT 1 FROM detalle_pagos dp WHERE dp.pago_id = pagos.id);
            RETURN jsonb_build_object('cruce_id', p_cruce_id, 'eliminado', true, 'reparado', true);
        END IF;
        -- v2 arreglo cruces mal formados (fin)
        RAISE EXCEPTION 'El cruce % está mal formado (% pagos virtuales)', p_cruce_id, v_n_pagos;
    END IF;

    -- La última operación. El pago y su cruce se crean en la misma transacción, así que
    -- comparten `created_at`; los cruces viejos de la app llegaban con unos milisegundos
    -- de diferencia, de ahí el margen.
    -- v2 fase 6: `deudas.recorte_libre` la salta. La pone solo _sacar_de_cruces, que al
    -- rechazar o editar algo acordado tiene que recortar cruces viejos (§4.2).
    IF COALESCE(current_setting('deudas.recorte_libre', true), '') <> 'on'
       AND EXISTS (SELECT 1 FROM pagos
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
