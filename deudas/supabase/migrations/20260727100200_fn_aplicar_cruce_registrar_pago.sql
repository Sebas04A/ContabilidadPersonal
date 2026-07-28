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
