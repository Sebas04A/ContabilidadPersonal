-- Decisión 36 de §3.3 (deudas/PLAN_MULTIUSUARIO.md), confirmada por el dueño el 2026-09-25
-- "avisando correctamente al usuario": cuando alguien propone exactamente el mismo cambio
-- que el otro ya había propuesto, queda el más nuevo (decisión 17) y el aviso que recibe
-- quien propuso primero lo explica, con `datos.mismo_que_el_tuyo = true`.
--
-- `proponer_cambio` es copia exacta de su versión de 20260925100000 más las líneas
-- marcadas «v2 decisión 36».

CREATE OR REPLACE FUNCTION public.proponer_cambio(
    p_entidad text, p_fila uuid, p_tipo text, p_payload jsonb DEFAULT '{}',
    p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid     uuid := auth.uid();
    v_idem    uuid;
    v_previa  uuid;
    v_fila    jsonb;
    v_vinc    public.vinculos;
    v_otra    uuid;
    v_actual  jsonb;
    v_payload jsonb;
    v_id      uuid;
    v_juntada boolean;  -- v2 decisión 36
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    IF p_entidad NOT IN ('deuda', 'pago') OR p_tipo NOT IN ('editar', 'borrar') THEN
        RAISE EXCEPTION 'Entidad o tipo desconocido: % %', p_entidad, p_tipo USING ERRCODE = '22023';
    END IF;
    -- La clave del cliente, mezclada con el usuario: `propuestas.idem_key` es global.
    v_idem := _idem_derivada(p_idem_key, 'cambio|' || v_uid);
    IF v_idem IS NOT NULL THEN
        SELECT id INTO v_previa FROM propuestas WHERE idem_key = v_idem AND de_usuario = v_uid;
        IF FOUND THEN
            RETURN jsonb_build_object('propuesta_id', v_previa, 'repetido', true);
        END IF;
    END IF;

    v_fila := CASE WHEN p_entidad = 'deuda'
                   THEN (SELECT to_jsonb(d) FROM deudas d WHERE id = p_fila AND owner_id = v_uid)
                   ELSE (SELECT to_jsonb(p) FROM pagos p WHERE id = p_fila AND owner_id = v_uid) END;
    IF v_fila IS NULL THEN
        RAISE EXCEPTION 'La fila % no existe o no es tuya', p_fila USING ERRCODE = '42501';
    END IF;
    IF v_fila ->> 'estado_acuerdo' <> 'acordada' THEN
        RAISE EXCEPTION 'Solo se proponen cambios sobre filas acordadas; esta se edita directo'
            USING ERRCODE = '22023';
    END IF;
    v_vinc := _vinculo_de((v_fila ->> 'deudor_id')::uuid);
    IF v_vinc.id IS NULL THEN
        RAISE EXCEPTION 'El contacto ya no está vinculado: esta fila se edita directo' USING ERRCODE = '22023';
    END IF;
    PERFORM _bloquear_vinculo(v_vinc);

    SELECT CASE WHEN fila_a = p_fila THEN fila_b ELSE fila_a END INTO v_otra
      FROM acuerdos WHERE vinculo_id = v_vinc.id AND entidad = p_entidad AND p_fila IN (fila_a, fila_b);
    -- v2 fase 9: lo que es parte de un gasto dividido cambia desde el gasto (editar_gasto   -- v2 fase 9
    -- y borrar_gasto llegan aquí con `deudas.en_gasto`); el otro, si no lo reconoce, lo     -- v2 fase 9
    -- rechaza.                                                                              -- v2 fase 9
    IF p_entidad = 'deuda' AND NOT _en_gasto()                                               -- v2 fase 9
       AND EXISTS (SELECT 1 FROM deudas WHERE id IN (p_fila, v_otra) AND gasto_id IS NOT NULL) THEN -- v2 fase 9
        RAISE EXCEPTION 'Es parte de un gasto dividido: se cambia desde el gasto (o se rechaza si no la reconoces)' -- v2 fase 9
            USING ERRCODE = '22023';                                                         -- v2 fase 9
    END IF;                                                                                  -- v2 fase 9
    -- v2 decisión 17: ya no hay un solo cambio pendiente por acuerdo (antes 23505). Si hay
    -- uno idéntico se anula más abajo, antes de insertar el nuevo.

    v_actual := _payload_de(p_entidad, v_fila) - 'titulo' - 'nota';
    IF p_tipo = 'borrar' THEN
        v_payload := v_actual;
    ELSE
        v_payload := v_actual || (COALESCE(p_payload, '{}') - 'titulo' - 'nota');
        IF (v_payload ->> 'monto')::numeric IS NULL OR (v_payload ->> 'monto')::numeric <= 0
           OR (v_payload ->> 'fecha')::date IS NULL OR (v_payload ->> 'es_mia')::boolean IS NULL THEN
            RAISE EXCEPTION 'Cambio inválido: %', p_payload USING ERRCODE = '22023';
        END IF;
        v_payload := jsonb_build_object('monto', round((v_payload ->> 'monto')::numeric, 2),
                                        'fecha', (v_payload ->> 'fecha')::date,
                                        'es_mia', (v_payload ->> 'es_mia')::boolean);
        IF v_payload = v_actual THEN
            RAISE EXCEPTION 'No hay cambios que proponer' USING ERRCODE = '22023';
        END IF;
    END IF;
    -- v2 decisión 17 (inicio): pueden convivir varios cambios sobre el mismo acuerdo, pero
    -- si ya hay uno pendiente que dice exactamente lo mismo, venga de quien venga, queda
    -- el más nuevo. `es_mia` es desde quien propone: el del otro va al revés.
    WITH anuladas AS (  -- v2 decisión 36: saber si el reemplazado era del otro
    UPDATE propuestas
       SET estado = 'anulada', resuelta_at = now()
     WHERE fila_origen IN (p_fila, v_otra) AND estado = 'pendiente' AND tipo = p_tipo
       AND (p_tipo = 'borrar'
            OR ((payload ->> 'monto')::numeric = (v_payload ->> 'monto')::numeric
                AND (payload ->> 'fecha')::date = (v_payload ->> 'fecha')::date
                AND (payload ->> 'es_mia')::boolean
                    = ((v_payload ->> 'es_mia')::boolean = (de_usuario = v_uid))))
    RETURNING de_usuario)  -- v2 decisión 36
    SELECT COALESCE(bool_or(de_usuario <> v_uid), false) INTO v_juntada FROM anuladas;  -- v2 decisión 36
    -- v2 decisión 17 (fin)
    -- Para que el otro sepa de qué fila hablamos: cómo estaba.
    v_payload := v_payload || jsonb_build_object('antes', v_actual);

    INSERT INTO propuestas (vinculo_id, de_usuario, para_usuario, entidad, tipo, fila_origen,
                            payload, idem_key)
    VALUES (v_vinc.id, v_uid,
            CASE WHEN v_vinc.usuario_a = v_uid THEN v_vinc.usuario_b ELSE v_vinc.usuario_a END,
            p_entidad, p_tipo, p_fila, v_payload, v_idem)
    RETURNING id INTO v_id;
    -- v2 decisión 36 (inicio): si reemplazó uno idéntico que había propuesto el otro, su aviso
    -- de este cambio lo dice: "propone lo mismo que tú; acéptalo para que quede". Lo
    -- inserta _aviso_propuesta en el AFTER INSERT de arriba.
    IF v_juntada THEN
        UPDATE avisos SET datos = datos || '{"mismo_que_el_tuyo": true}'
         WHERE propuesta_id = v_id AND tipo IN ('cambio', 'borrado');
    END IF;
    -- v2 decisión 36 (fin)
    RETURN jsonb_build_object('propuesta_id', v_id, 'repetido', false);
END $$;
