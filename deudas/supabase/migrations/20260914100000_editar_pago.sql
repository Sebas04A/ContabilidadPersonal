-- Nota del pago y editar su fecha.
--
-- Un pago no tenía dónde decir de qué fue ("transferencia del almuerzo", "en efectivo").
-- `pagos.nota` lo guarda. `editar_pago` cambia la fecha y la nota de un pago ya
-- registrado.
--
-- La regla:
--
--   * Solo fecha y nota. El monto y la dirección no se tocan: están repartidos entre
--     deudas y un cruce se calculó encima; eso es borrar y volver a registrar.
--   * La fecha no mueve dinero: el reparto ya está en `detalle_pagos` y el FIFO ordena
--     por la fecha de las DEUDAS. Cambia dónde se ve el pago y qué día cuenta.
--   * El cruce que disparó el pago lo acompaña: sus dos pagos virtuales se escribieron en
--     la misma transacción (mismo `created_at`, misma fecha) y se muestran juntos. Si solo
--     cambiara el pago real, el bloque "cruce + pago" se partiría. Los cruces viejos de la
--     app llegaban con milisegundos de diferencia, de ahí el margen de 2 s.
--   * Un pago virtual de cruce no se edita solo: se edita el pago real que lo disparó.
--   * `p_fecha` NULL deja la fecha; `p_nota` NULL deja la nota y '' la borra.
--
-- Cada edición deja el antes y el después en `pagos_editados`, que además da la
-- idempotencia por `idem_key`.

ALTER TABLE pagos ADD COLUMN IF NOT EXISTS nota TEXT;

COMMENT ON COLUMN pagos.nota IS 'Texto libre del pago: de qué fue, cómo se entregó.';

CREATE TABLE IF NOT EXISTS pagos_editados (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idem_key   UUID,
    pago_id    UUID        NOT NULL,
    deudor_id  UUID        NOT NULL REFERENCES deudores(id) ON DELETE CASCADE,
    -- Las filas de `pagos` que cambiaron (el real y su cruce) tal como estaban y quedaron.
    antes      JSONB       NOT NULL,
    despues    JSONB       NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pagos_editados_idem
    ON pagos_editados(idem_key) WHERE idem_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pagos_editados_deudor ON pagos_editados(deudor_id);

COMMENT ON TABLE pagos_editados IS
    'Bitácora de editar_pago: la fecha y la nota de un pago antes y después.';

ALTER TABLE pagos_editados ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Admin full access pagos_editados" ON pagos_editados;
CREATE POLICY "Admin full access pagos_editados" ON pagos_editados
    FOR ALL USING (true) WITH CHECK (true);
GRANT SELECT, INSERT ON pagos_editados TO anon, authenticated, service_role;


CREATE OR REPLACE FUNCTION editar_pago(
    p_pago_id  UUID,
    p_fecha    DATE DEFAULT NULL,
    p_nota     TEXT DEFAULT NULL,
    p_idem_key UUID DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
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

COMMENT ON FUNCTION editar_pago(UUID, DATE, TEXT, UUID) IS
    'Cambia la fecha y/o la nota de un pago real. La fecha arrastra al cruce de su misma '
    'operación; el monto y el reparto no se tocan.';

GRANT EXECUTE ON FUNCTION editar_pago(UUID, DATE, TEXT, UUID) TO anon, authenticated, service_role;
