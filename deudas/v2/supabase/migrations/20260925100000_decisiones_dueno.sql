-- Decisiones del dueño del 2026-09-25 (deudas/PLAN_MULTIUSUARIO.md §3.3, revisión de las
-- decisiones 10 a 20 y 32 a 34):
--
--   12. Al desvincular, las dos libretas quedan exactamente como con una Persona sin app:
--       lo acordado vuelve a `local`, se olvida quién anotó cada fila y se borran los
--       acuerdos. El saldo de cada uno no cambia. La app avisa antes de desvincular.
--   14. "¿Es la misma?" admite fechas a ±2 días (antes ±3), en todos los emparejamientos:
--       conciliación, candidatos al aceptar, posibles duplicados y fusionar. Siempre lo
--       confirma el usuario.
--   17. Sobre un acuerdo pueden convivir varios cambios pendientes. Si dos dicen
--       exactamente lo mismo, queda el más nuevo; aceptar uno anula los demás.
--   32. El enlace de un grupo vence a los 5 días (antes 7).
--   34. Un grupo que se queda sin ninguna cuenta con app se borra a los 30 días, no en el
--       acto.
--
-- Cada función es copia exacta de su última versión más las líneas marcadas
-- «v2 decisión N». Conservan su modo de seguridad y sus permisos (CREATE OR REPLACE).

-- ====================================================================================
-- 32: enlaces de grupo de 5 días
-- ====================================================================================

ALTER TABLE public.grupo_invitaciones ALTER COLUMN expira SET DEFAULT now() + interval '5 days';
-- Los enlaces vivos creados con 7 días se acortan a 5 desde que nacieron.
UPDATE public.grupo_invitaciones
   SET expira = created_at + interval '5 days'
 WHERE expira > created_at + interval '5 days';

-- ====================================================================================
-- 34: grupos sin nadie, 30 días de gracia
-- ====================================================================================

ALTER TABLE public.grupos ADD COLUMN sin_nadie_desde timestamptz;
COMMENT ON COLUMN public.grupos.sin_nadie_desde IS
    'Desde cuándo no queda ninguna cuenta con app. A los 30 días el grupo se borra.';

-- Borra los grupos que llevan más de 30 días sin ninguna cuenta con app, con sus lápidas.
-- Vuelve a comprobar que sigan sin nadie. SECURITY DEFINER: nadie puede verlos.
CREATE FUNCTION public._purgar_grupos_sin_nadie() RETURNS int
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_n int;
BEGIN
    DELETE FROM grupos g
     WHERE g.sin_nadie_desde < now() - interval '30 days'
       AND NOT EXISTS (SELECT 1 FROM grupo_miembros m WHERE m.grupo_id = g.id AND m.usuario_id IS NOT NULL);
    GET DIAGNOSTICS v_n = ROW_COUNT;
    DELETE FROM borrados_gastos b
     WHERE b.grupo_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM grupos g WHERE g.id = b.grupo_id);
    RETURN v_n;
END $$;
REVOKE ALL ON FUNCTION public._purgar_grupos_sin_nadie() FROM PUBLIC, anon, authenticated;

-- A diario a las 04:17 UTC. pg_cron viene en Supabase (local y nube); se instala en
-- pg_catalog, como indica su documentación.
CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;
SELECT cron.schedule('purgar-grupos-sin-nadie', '17 4 * * *', 'SELECT public._purgar_grupos_sin_nadie()');

-- ====================================================================================
-- 34: _perfil_sin_gastos
-- ====================================================================================

CREATE OR REPLACE FUNCTION public._perfil_sin_gastos() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM gastos WHERE grupo_id IS NULL AND creado_por IS NULL;
    DELETE FROM borrados_gastos WHERE owner_id = OLD.id;
    -- «v2 fase 9, grupos sin nadie»: el FK ya pasó a persona sin app la fila de miembro de
    -- esta cuenta; el grupo en el que no queda ninguna cuenta se va, con sus lápidas.
    -- v2 decisión 34: ya no se borra en el acto; se marca y se borra a los 30 días
    -- (_purgar_grupos_sin_nadie, a diario por pg_cron y también aquí).
    UPDATE grupos g
       SET sin_nadie_desde = now()
     WHERE sin_nadie_desde IS NULL
       AND NOT EXISTS (SELECT 1 FROM grupo_miembros m WHERE m.grupo_id = g.id AND m.usuario_id IS NOT NULL);
    PERFORM _purgar_grupos_sin_nadie();  -- v2 decisión 34
    -- «fin v2 fase 9, grupos sin nadie»
    RETURN NULL;
END $$;

-- ====================================================================================
-- 14: fecha a ±2 días
-- ====================================================================================

CREATE OR REPLACE FUNCTION public.candidatos_conciliacion(p_vinculo_id uuid) RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, extensions AS $$
DECLARE
    c        record;
    v_cands  jsonb;
    v_pares  jsonb := '[]';
    v_usadas uuid[] := '{}';
    e        jsonb;
BEGIN
    SELECT * INTO c FROM public._conciliacion_de(p_vinculo_id);

    WITH mias AS (SELECT * FROM public._filas_conciliables(c.mi_deudor, auth.uid(), true)),
         suyas AS (SELECT * FROM public._filas_conciliables(c.su_deudor, c.otro, false)),
         cand AS (
             SELECT m.entidad, m.id AS mia, s.id AS suya,
                    round((1 - abs(m.fecha - s.fecha) / 4.0)
                          + COALESCE(similarity(lower(m.titulo_interno), lower(s.titulo_interno))::numeric, 0),
                          4) AS puntaje
               FROM mias m
               JOIN suyas s ON s.entidad = m.entidad AND s.monto = m.monto
                           AND s.mio = m.mio               -- misma dirección vista por mí
                           AND abs(m.fecha - s.fecha) <= 2)  -- v2 decisión 14
    SELECT COALESCE(jsonb_agg(to_jsonb(cand) ORDER BY puntaje DESC, mia, suya), '[]')
      INTO v_cands FROM cand;

    FOR e IN SELECT * FROM jsonb_array_elements(v_cands) LOOP
        CONTINUE WHEN (e->>'mia')::uuid = ANY (v_usadas) OR (e->>'suya')::uuid = ANY (v_usadas);
        v_usadas := v_usadas || (e->>'mia')::uuid || (e->>'suya')::uuid;
        v_pares := v_pares || jsonb_build_object(
            'entidad', e->>'entidad', 'mia', e->'mia', 'suya', e->'suya',
            'puntaje', e->'puntaje',
            'dudoso', EXISTS (
                SELECT 1 FROM jsonb_array_elements(v_cands) o
                 WHERE (o->>'mia' = e->>'mia' OR o->>'suya' = e->>'suya')
                   AND NOT (o->>'mia' = e->>'mia' AND o->>'suya' = e->>'suya')
                   AND (o->>'puntaje')::numeric >= (e->>'puntaje')::numeric - 0.5));
    END LOOP;

    RETURN jsonb_build_object(
        'vinculo_id', p_vinculo_id,
        'yo_confirme', CASE WHEN c.soy_a THEN (c.vinculo).conciliado_a ELSE (c.vinculo).conciliado_b END,
        'otro_confirmo', CASE WHEN c.soy_a THEN (c.vinculo).conciliado_b ELSE (c.vinculo).conciliado_a END,
        'pares', v_pares,
        'mias', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                     'entidad', entidad, 'id', id, 'titulo', titulo, 'monto', monto,
                     'fecha', fecha, 'mio', mio) ORDER BY fecha, id), '[]')
                   FROM public._filas_conciliables(c.mi_deudor, auth.uid(), true)),
        'suyas', (SELECT COALESCE(jsonb_agg(jsonb_build_object(
                      'entidad', entidad, 'id', id, 'monto', monto, 'fecha', fecha, 'mio', mio)
                      ORDER BY fecha, id), '[]')
                    FROM public._filas_conciliables(c.su_deudor, c.otro, false)));
END $$;

CREATE OR REPLACE FUNCTION public._candidatos_espejo(p_entidad text, p_origen jsonb, p_mi_deudor uuid)
    RETURNS jsonb
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT COALESCE(jsonb_agg(c ORDER BY abs(dias), id), '[]')
      FROM (
        SELECT d.id, d.titulo AS texto, d.monto, d.fecha_gasto AS fecha, d.estado_acuerdo,
               d.fecha_gasto - (p_origen ->> 'fecha_gasto')::date AS dias
          FROM deudas d
         WHERE p_entidad = 'deuda'
           AND d.deudor_id = p_mi_deudor AND d.owner_id = auth.uid()
           AND d.estado_acuerdo IN ('local', 'propuesta')
           AND d.es_mi_deuda = NOT (p_origen ->> 'es_mi_deuda')::boolean
           AND d.monto = (p_origen ->> 'monto')::numeric
           AND abs(d.fecha_gasto - (p_origen ->> 'fecha_gasto')::date) <= 2  -- v2 decisión 14
        UNION ALL
        SELECT p.id, p.nota, p.monto_total, p.fecha_pago, p.estado_acuerdo,
               p.fecha_pago - (p_origen ->> 'fecha_pago')::date
          FROM pagos p
         WHERE p_entidad = 'pago'
           AND p.deudor_id = p_mi_deudor AND p.owner_id = auth.uid()
           AND p.estado_acuerdo IN ('local', 'propuesta')
           AND NOT COALESCE(p.es_compensacion, false)
           AND p.es_mi_pago = NOT (p_origen ->> 'es_mi_pago')::boolean
           AND p.monto_total = (p_origen ->> 'monto_total')::numeric
           AND abs(p.fecha_pago - (p_origen ->> 'fecha_pago')::date) <= 2  -- v2 decisión 14
      ) c
$$;

CREATE OR REPLACE FUNCTION public._candidatos_duplicado(p_entidad text, p_origen jsonb, p_mi_deudor uuid)
    RETURNS jsonb
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT COALESCE(jsonb_agg(c ORDER BY abs(dias), id), '[]')
      FROM (
        SELECT d.id, d.titulo AS texto, d.monto, d.fecha_gasto AS fecha, d.estado_acuerdo,
               d.fecha_gasto - (p_origen ->> 'fecha_gasto')::date AS dias
          FROM deudas d
         WHERE p_entidad = 'deuda'
           AND d.deudor_id = p_mi_deudor AND d.owner_id = auth.uid()
           AND d.estado_acuerdo IN ('local', 'propuesta', 'acordada')
           AND d.es_mi_deuda = NOT (p_origen ->> 'es_mi_deuda')::boolean
           AND d.monto = (p_origen ->> 'monto')::numeric
           AND abs(d.fecha_gasto - (p_origen ->> 'fecha_gasto')::date) <= 2  -- v2 decisión 14
        UNION ALL
        SELECT p.id, p.nota, p.monto_total, p.fecha_pago, p.estado_acuerdo,
               p.fecha_pago - (p_origen ->> 'fecha_pago')::date
          FROM pagos p
         WHERE p_entidad = 'pago'
           AND p.deudor_id = p_mi_deudor AND p.owner_id = auth.uid()
           AND p.estado_acuerdo IN ('local', 'propuesta', 'acordada')
           AND NOT COALESCE(p.es_compensacion, false)
           AND p.es_mi_pago = NOT (p_origen ->> 'es_mi_pago')::boolean
           AND p.monto_total = (p_origen ->> 'monto_total')::numeric
           AND abs(p.fecha_pago - (p_origen ->> 'fecha_pago')::date) <= 2  -- v2 decisión 14
      ) c
$$;

CREATE OR REPLACE FUNCTION public.fusionar_espejo(
    p_entidad text, p_espejo uuid, p_existente uuid, p_idem_key uuid DEFAULT NULL)
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid  uuid := auth.uid();
    v_esp  jsonb;
    v_ex   jsonb;
    v_vinc public.vinculos;
    v_otra uuid;
    v_ok   boolean;
    v_modo text;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    IF p_entidad IS NULL OR p_entidad NOT IN ('deuda', 'pago') THEN
        RAISE EXCEPTION 'Entidad desconocida: %', p_entidad USING ERRCODE = '22023';
    END IF;
    v_ex := CASE WHEN p_entidad = 'deuda'
                 THEN (SELECT to_jsonb(d) FROM deudas d WHERE id = p_existente AND owner_id = v_uid)
                 ELSE (SELECT to_jsonb(p) FROM pagos p WHERE id = p_existente AND owner_id = v_uid) END;
    IF v_ex IS NULL THEN
        RAISE EXCEPTION 'La fila % no existe o no es tuya', p_existente USING ERRCODE = '42501';
    END IF;
    v_vinc := _vinculo_de((v_ex ->> 'deudor_id')::uuid);
    IF v_vinc.id IS NULL THEN
        RAISE EXCEPTION 'El contacto ya no está vinculado' USING ERRCODE = '22023';
    END IF;
    PERFORM _bloquear_vinculo(v_vinc);
    v_ex  := _fila(p_entidad, p_existente);
    v_esp := _fila(p_entidad, p_espejo);

    -- Ya hecho: el espejo se borró (la mía ocupó su lugar) o quedó rechazado (sobraba).
    IF (v_esp IS NULL AND v_ex ->> 'estado_acuerdo' = 'acordada')
       OR ((v_esp ->> 'owner_id')::uuid = v_uid AND v_esp ->> 'estado_acuerdo' = 'rechazada') THEN
        RETURN jsonb_build_object('resultado', 'fusionada', 'fila', p_existente, 'repetido', true);
    END IF;
    IF v_esp IS NULL OR (v_esp ->> 'owner_id')::uuid <> v_uid THEN
        RAISE EXCEPTION 'La fila % no existe o no es tuya', p_espejo USING ERRCODE = '42501';
    END IF;
    IF v_esp ->> 'estado_acuerdo' <> 'acordada' OR v_esp ->> 'origen_id' IS NULL THEN
        RAISE EXCEPTION 'Solo se fusiona una fila que anotó la otra persona' USING ERRCODE = '22023';
    END IF;
    -- La existente tiene que ser un candidato (_candidatos_duplicado): mismo contacto,
    -- misma dirección y monto que el espejo, fecha a ±3 días, sin rechazar.
    v_ok := p_existente <> p_espejo
        AND v_ex ->> 'deudor_id' = v_esp ->> 'deudor_id'
        AND v_ex ->> 'estado_acuerdo' IN ('local', 'propuesta', 'acordada');
    IF p_entidad = 'deuda' THEN
        v_ok := v_ok
            AND (v_ex ->> 'es_mi_deuda')::boolean = (v_esp ->> 'es_mi_deuda')::boolean
            AND (v_ex ->> 'monto')::numeric = (v_esp ->> 'monto')::numeric
            AND abs((v_ex ->> 'fecha_gasto')::date - (v_esp ->> 'fecha_gasto')::date) <= 2;  -- v2 decisión 14
    ELSE
        v_ok := v_ok
            AND NOT COALESCE((v_ex ->> 'es_compensacion')::boolean, false)
            AND (v_ex ->> 'es_mi_pago')::boolean = (v_esp ->> 'es_mi_pago')::boolean
            AND (v_ex ->> 'monto_total')::numeric = (v_esp ->> 'monto_total')::numeric
            AND abs((v_ex ->> 'fecha_pago')::date - (v_esp ->> 'fecha_pago')::date) <= 2;  -- v2 decisión 14
    END IF;
    IF NOT COALESCE(v_ok, false) THEN
        RAISE EXCEPTION 'Esas dos filas no pueden ser la misma (contacto, dirección, monto o fecha)'
            USING ERRCODE = '22023';
    END IF;
    SELECT CASE WHEN fila_a = p_espejo THEN fila_b ELSE fila_a END INTO v_otra
      FROM acuerdos
     WHERE vinculo_id = v_vinc.id AND entidad = p_entidad AND p_espejo IN (fila_a, fila_b);
    IF v_otra IS NULL THEN
        RAISE EXCEPTION 'La fila ya no está acordada' USING ERRCODE = '22023';
    END IF;

    PERFORM set_config('deudas.en_rpc', 'on', true);
    IF v_ex ->> 'estado_acuerdo' = 'acordada' THEN
        PERFORM _rechazar_par(p_entidad, p_espejo, v_otra, 'Ya estaba anotada');
        v_modo := 'sobraba';
    ELSE
        -- Mi propuesta, si la había, la resuelve el enlace (sin "confirmado": la resolví
        -- yo); lo que el otro tenía por responder de ella queda visto.
        PERFORM set_config('deudas.sin_aviso', 'on', true);
        UPDATE propuestas SET estado = 'aceptada', fila_espejo = v_otra, resuelta_at = now()
         WHERE fila_origen = p_existente AND tipo = 'crear' AND estado = 'pendiente';
        PERFORM set_config('deudas.sin_aviso', 'off', true);
        UPDATE avisos SET visto_at = now()
         WHERE visto_at IS NULL
           AND propuesta_id IN (SELECT id FROM propuestas
                                 WHERE fila_origen = p_existente AND tipo = 'crear');
        -- El espejo se va antes de marcar la mía: las dos llevarían el mismo origen_id.
        IF p_entidad = 'deuda' THEN
            PERFORM _soltar_deuda(p_espejo, NULL);
            DELETE FROM deudas WHERE id = p_espejo;
            UPDATE deudas SET estado_acuerdo = 'acordada', origen_id = COALESCE(origen_id, v_otra)
             WHERE id = p_existente;
        ELSE
            PERFORM _soltar_pago(p_espejo, NULL);
            DELETE FROM pagos WHERE id = p_espejo;
            UPDATE pagos SET estado_acuerdo = 'acordada', origen_id = COALESCE(origen_id, v_otra)
             WHERE id = p_existente;
        END IF;
        UPDATE acuerdos
           SET fila_a = CASE WHEN fila_a = p_espejo THEN p_existente ELSE fila_a END,
               fila_b = CASE WHEN fila_b = p_espejo THEN p_existente ELSE fila_b END
         WHERE vinculo_id = v_vinc.id AND entidad = p_entidad AND p_espejo IN (fila_a, fila_b);
        UPDATE propuestas SET fila_espejo = p_existente
         WHERE fila_origen = v_otra AND tipo = 'crear' AND estado = 'aceptada';
        v_modo := 'enlazada';
    END IF;
    UPDATE avisos SET visto_at = now()
     WHERE usuario_id = v_uid AND fila_id = p_espejo AND visto_at IS NULL;
    PERFORM set_config('deudas.en_rpc', 'off', true);
    RETURN jsonb_build_object('resultado', 'fusionada', 'modo', v_modo, 'fila', p_existente,
                              'repetido', false);
END $$;

-- ====================================================================================
-- 17: varios cambios pendientes
-- ====================================================================================

-- El índice único era (fila_origen, tipo) entre las pendientes: también impedía un segundo
-- cambio sobre la misma fila. Queda único solo para 'crear' (una fila nueva se propone una
-- vez); los cambios tienen un índice normal para buscarlos.
DROP INDEX public.idx_propuestas_fila_pendiente;
CREATE UNIQUE INDEX idx_propuestas_fila_pendiente ON public.propuestas (fila_origen)
    WHERE estado = 'pendiente' AND tipo = 'crear';
CREATE INDEX idx_propuestas_cambios_pendientes ON public.propuestas (fila_origen)
    WHERE estado = 'pendiente' AND tipo IN ('editar', 'borrar');

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
    UPDATE propuestas
       SET estado = 'anulada', resuelta_at = now()
     WHERE fila_origen IN (p_fila, v_otra) AND estado = 'pendiente' AND tipo = p_tipo
       AND (p_tipo = 'borrar'
            OR ((payload ->> 'monto')::numeric = (v_payload ->> 'monto')::numeric
                AND (payload ->> 'fecha')::date = (v_payload ->> 'fecha')::date
                AND (payload ->> 'es_mia')::boolean
                    = ((v_payload ->> 'es_mia')::boolean = (de_usuario = v_uid))));
    -- v2 decisión 17 (fin)
    -- Para que el otro sepa de qué fila hablamos: cómo estaba.
    v_payload := v_payload || jsonb_build_object('antes', v_actual);

    INSERT INTO propuestas (vinculo_id, de_usuario, para_usuario, entidad, tipo, fila_origen,
                            payload, idem_key)
    VALUES (v_vinc.id, v_uid,
            CASE WHEN v_vinc.usuario_a = v_uid THEN v_vinc.usuario_b ELSE v_vinc.usuario_a END,
            p_entidad, p_tipo, p_fila, v_payload, v_idem)
    RETURNING id INTO v_id;
    RETURN jsonb_build_object('propuesta_id', v_id, 'repetido', false);
END $$;

CREATE OR REPLACE FUNCTION public._aplicar_cambio(p_prop public.propuestas) RETURNS uuid
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_ac     public.acuerdos;
    v_otra   uuid;
    v_fila   uuid;
    v_actual jsonb;
    v_monto  numeric := (p_prop.payload ->> 'monto')::numeric;
    v_fecha  date    := (p_prop.payload ->> 'fecha')::date;
    v_es_mia boolean := (p_prop.payload ->> 'es_mia')::boolean;
    v_mia    boolean;
BEGIN
    SELECT * INTO v_ac FROM acuerdos
     WHERE vinculo_id = p_prop.vinculo_id AND entidad = p_prop.entidad
       AND p_prop.fila_origen IN (fila_a, fila_b);
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La fila ya no está acordada' USING ERRCODE = '22023';
    END IF;
    v_otra := CASE WHEN v_ac.fila_a = p_prop.fila_origen THEN v_ac.fila_b ELSE v_ac.fila_a END;

    FOREACH v_fila IN ARRAY ARRAY[p_prop.fila_origen, v_otra] LOOP
        v_actual := _fila(p_prop.entidad, v_fila);
        IF v_actual IS NULL THEN
            RAISE EXCEPTION 'Una de las dos filas del acuerdo ya no existe' USING ERRCODE = '22023';
        END IF;
        -- En la fila de quien propuso, la dirección es la del payload; en la otra, al revés.
        v_mia := CASE WHEN v_fila = p_prop.fila_origen THEN v_es_mia ELSE NOT v_es_mia END;

        IF p_prop.entidad = 'deuda' THEN
            IF p_prop.tipo = 'borrar' THEN
                PERFORM _soltar_deuda(v_fila, NULL);
                DELETE FROM deudas WHERE id = v_fila;
            ELSE
                IF (v_actual ->> 'es_mi_deuda')::boolean IS DISTINCT FROM v_mia THEN
                    PERFORM _soltar_deuda(v_fila, NULL);
                ELSIF v_monto < (v_actual ->> 'monto')::numeric THEN
                    PERFORM _soltar_deuda(v_fila, v_monto);
                END IF;
                UPDATE deudas SET monto = v_monto, fecha_gasto = v_fecha, es_mi_deuda = v_mia
                 WHERE id = v_fila;
            END IF;
        ELSE
            IF p_prop.tipo = 'borrar' THEN
                DELETE FROM pagos WHERE id = v_fila;
            ELSE
                IF (v_actual ->> 'es_mi_pago')::boolean IS DISTINCT FROM v_mia THEN
                    PERFORM _soltar_pago(v_fila, NULL);
                ELSIF v_monto < (v_actual ->> 'monto_total')::numeric THEN
                    PERFORM _soltar_pago(v_fila, v_monto);
                END IF;
                UPDATE pagos SET monto_total = v_monto, fecha_pago = v_fecha, es_mi_pago = v_mia
                 WHERE id = v_fila;
            END IF;
        END IF;
    END LOOP;

    IF p_prop.tipo = 'borrar' THEN
        DELETE FROM acuerdos WHERE id = v_ac.id;
    END IF;
    -- v2 decisión 17: los otros cambios pendientes sobre este acuerdo se propusieron sobre
    -- cómo estaba antes: aceptar uno los anula. (Un borrado ya los anuló al irse las filas.)
    UPDATE propuestas
       SET estado = 'anulada', resuelta_at = now()
     WHERE fila_origen IN (p_prop.fila_origen, v_otra) AND tipo IN ('editar', 'borrar')
       AND estado = 'pendiente' AND id <> p_prop.id;  -- v2 decisión 17
    RETURN v_otra;
END $$;

-- ====================================================================================
-- 12: desvincular
-- ====================================================================================

CREATE OR REPLACE FUNCTION public.desvincular(p_vinculo_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v public.vinculos;
BEGIN
    SELECT * INTO v FROM public.vinculos
     WHERE id = p_vinculo_id AND estado <> 'roto' AND auth.uid() IN (usuario_a, usuario_b);
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El vínculo % no existe o no es tuyo', p_vinculo_id
            USING ERRCODE = '42501';
    END IF;
    PERFORM _bloquear_vinculo(v);

    PERFORM set_config('deudas.en_rpc', 'on', true);
    UPDATE deudas SET estado_acuerdo = 'local'
     WHERE estado_acuerdo = 'propuesta'
       AND id IN (SELECT fila_origen FROM propuestas
                   WHERE vinculo_id = p_vinculo_id AND estado = 'pendiente'
                     AND tipo = 'crear' AND entidad = 'deuda');
    UPDATE pagos SET estado_acuerdo = 'local'
     WHERE estado_acuerdo = 'propuesta'
       AND id IN (SELECT fila_origen FROM propuestas
                   WHERE vinculo_id = p_vinculo_id AND estado = 'pendiente'
                     AND tipo = 'crear' AND entidad = 'pago');
    UPDATE propuestas SET estado = 'anulada', resuelta_at = now()
     WHERE vinculo_id = p_vinculo_id AND estado = 'pendiente';
    -- v2 decisión 12 (inicio): roto el vínculo, cada libreta queda exactamente como con una
    -- Persona sin app. Lo acordado vuelve a `local` y se olvida quién anotó cada fila
    -- (`origen_id`), en las dos libretas; los acuerdos se borran. El saldo no cambia:
    -- lo rechazado sigue rechazado (no contaba y no empieza a contar).
    DELETE FROM acuerdos WHERE vinculo_id = p_vinculo_id;
    UPDATE deudas
       SET estado_acuerdo = CASE WHEN estado_acuerdo = 'acordada' THEN 'local' ELSE estado_acuerdo END,
           origen_id = NULL
     WHERE deudor_id IN (v.deudor_a, v.deudor_b)
       AND (estado_acuerdo = 'acordada' OR origen_id IS NOT NULL);
    UPDATE pagos
       SET estado_acuerdo = CASE WHEN estado_acuerdo = 'acordada' THEN 'local' ELSE estado_acuerdo END,
           origen_id = NULL
     WHERE deudor_id IN (v.deudor_a, v.deudor_b)
       AND (estado_acuerdo = 'acordada' OR origen_id IS NOT NULL);
    -- v2 decisión 12 (fin)
    UPDATE public.vinculos SET estado = 'roto', roto_at = now()
     WHERE id = p_vinculo_id AND estado <> 'roto';
    PERFORM set_config('deudas.en_rpc', 'off', true);
END $$;

