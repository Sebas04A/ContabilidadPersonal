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
