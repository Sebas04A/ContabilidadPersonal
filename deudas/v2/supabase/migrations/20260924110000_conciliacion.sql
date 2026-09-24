-- Fase 5 (deudas/PLAN_MULTIUSUARIO.md §4.1, §4.6 y §5.3): conciliación inicial.
--
-- Al vincularse, cada libreta ya trae su historial. Aquí se emparejan:
--   * `candidatos_conciliacion(vínculo)` propone pares (misma deuda o pago anotado por los
--     dos) y lista lo que solo tiene cada uno;
--   * `confirmar_conciliacion(vínculo, pares)` deja los pares confirmados `acordada` en las
--     dos libretas y manda como `propuesta` lo que solo tiene quien confirma.
--
-- Esta fase solo agrega el esquema de estados: `estado_cuenta()` NO cambia (las filas
-- `propuesta` y `acordada` cuentan en mi saldo igual que las `local`; lo `rechazada` recién
-- aparece en la fase 6, junto con aceptar y rechazar propuestas).

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;

-- ====================================================================================
-- Estados de una fila (§4.1)
-- ====================================================================================

ALTER TABLE public.deudas
    ADD COLUMN estado_acuerdo text NOT NULL DEFAULT 'local'
        CHECK (estado_acuerdo IN ('local', 'propuesta', 'acordada', 'rechazada')),
    ADD COLUMN origen_id uuid,
    ADD CONSTRAINT deudas_origen_unico UNIQUE (owner_id, origen_id);

ALTER TABLE public.pagos
    ADD COLUMN estado_acuerdo text NOT NULL DEFAULT 'local'
        CHECK (estado_acuerdo IN ('local', 'propuesta', 'acordada', 'rechazada')),
    ADD COLUMN origen_id uuid,
    ADD CONSTRAINT pagos_origen_unico UNIQUE (owner_id, origen_id),
    -- Los cruces son derivados y no mueven el neto: nunca se acuerdan.
    ADD CONSTRAINT cruce_siempre_local CHECK (NOT es_compensacion OR estado_acuerdo = 'local');

-- ====================================================================================
-- Propuestas y acuerdos (§5.3). En esta fase solo las crea la conciliación; aceptarlas y
-- rechazarlas es la fase 6.
-- ====================================================================================

CREATE TABLE public.propuestas (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vinculo_id   uuid NOT NULL REFERENCES public.vinculos ON DELETE CASCADE,
    de_usuario   uuid NOT NULL DEFAULT auth.uid(),
    para_usuario uuid NOT NULL,
    entidad      text NOT NULL CHECK (entidad IN ('deuda', 'pago')),
    tipo         text NOT NULL CHECK (tipo IN ('crear', 'editar', 'borrar')),
    fila_origen  uuid NOT NULL,   -- fila en la libreta de quien propone
    payload      jsonb NOT NULL,  -- {monto, fecha, es_mia} desde el punto de vista de quien propone
    estado       text NOT NULL DEFAULT 'pendiente'
                 CHECK (estado IN ('pendiente', 'aceptada', 'rechazada', 'anulada')),
    motivo       text,
    fila_espejo  uuid,
    idem_key     uuid UNIQUE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    resuelta_at  timestamptz
);
CREATE UNIQUE INDEX idx_propuestas_fila_pendiente ON public.propuestas (fila_origen, tipo)
    WHERE estado = 'pendiente';
CREATE INDEX idx_propuestas_para ON public.propuestas (para_usuario) WHERE estado = 'pendiente';
CREATE INDEX idx_propuestas_vinculo ON public.propuestas (vinculo_id);

CREATE TABLE public.acuerdos (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    vinculo_id uuid NOT NULL REFERENCES public.vinculos ON DELETE CASCADE,
    entidad    text NOT NULL CHECK (entidad IN ('deuda', 'pago')),
    fila_a     uuid NOT NULL,  -- fila del usuario_a del vínculo
    fila_b     uuid NOT NULL,  -- fila del usuario_b
    created_at timestamptz NOT NULL DEFAULT now(),
    -- Capa 3 de §4.5: una fila nunca queda atada a dos filas del otro.
    UNIQUE (entidad, fila_a),
    UNIQUE (entidad, fila_b)
);
CREATE INDEX idx_acuerdos_vinculo ON public.acuerdos (vinculo_id);

ALTER TABLE public.propuestas ENABLE ROW LEVEL SECURITY;
CREATE POLICY partes_leer ON public.propuestas FOR SELECT TO authenticated
    USING (auth.uid() IN (de_usuario, para_usuario));
REVOKE ALL ON public.propuestas FROM anon, authenticated;
GRANT SELECT ON public.propuestas TO authenticated;

ALTER TABLE public.acuerdos ENABLE ROW LEVEL SECURITY;
CREATE POLICY partes_leer ON public.acuerdos FOR SELECT TO authenticated
    USING (EXISTS (SELECT 1 FROM public.vinculos v
                    WHERE v.id = vinculo_id AND auth.uid() IN (v.usuario_a, v.usuario_b)));
REVOKE ALL ON public.acuerdos FROM anon, authenticated;
GRANT SELECT ON public.acuerdos TO authenticated;

-- ====================================================================================
-- Conciliación (§4.6)
-- ====================================================================================

-- El vínculo en conciliación visto por quien llama: su deudor, el del otro y quién es el
-- otro. Falla con 42501 si no es parte o si el vínculo ya no está conciliando.
CREATE FUNCTION public._conciliacion_de(
    p_vinculo_id uuid,
    OUT vinculo public.vinculos, OUT soy_a boolean,
    OUT mi_deudor uuid, OUT su_deudor uuid, OUT otro uuid)
    LANGUAGE plpgsql STABLE SET search_path = public AS $$
BEGIN
    SELECT * INTO vinculo FROM public.vinculos
     WHERE id = p_vinculo_id AND auth.uid() IN (usuario_a, usuario_b);
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El vínculo % no existe o no es tuyo', p_vinculo_id USING ERRCODE = '42501';
    END IF;
    IF vinculo.estado <> 'conciliando' THEN
        RAISE EXCEPTION 'El vínculo ya no está en conciliación (%)', vinculo.estado
            USING ERRCODE = '22023';
    END IF;
    soy_a     := vinculo.usuario_a = auth.uid();
    mi_deudor := CASE WHEN soy_a THEN vinculo.deudor_a ELSE vinculo.deudor_b END;
    su_deudor := CASE WHEN soy_a THEN vinculo.deudor_b ELSE vinculo.deudor_a END;
    otro      := CASE WHEN soy_a THEN vinculo.usuario_b ELSE vinculo.usuario_a END;
END $$;

-- Filas conciliables de un deudor: deudas y pagos `local`, sin cruces. `mio` es la
-- dirección vista por QUIEN LLAMA (yo debo / yo pagué): en las filas del otro se invierte.
-- `titulo` solo se muestra en mis filas: el título es privado de cada libreta (§4.3).
CREATE FUNCTION public._filas_conciliables(p_deudor uuid, p_owner uuid, p_son_mias boolean)
    RETURNS TABLE (entidad text, id uuid, titulo text, monto numeric, fecha date, mio boolean,
                   titulo_interno text)
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT 'deuda', d.id, CASE WHEN p_son_mias THEN d.titulo END, d.monto, d.fecha_gasto,
           d.es_mi_deuda = p_son_mias, d.titulo
      FROM public.deudas d
     WHERE d.deudor_id = p_deudor AND d.owner_id = p_owner AND d.estado_acuerdo = 'local'
    UNION ALL
    SELECT 'pago', p.id, CASE WHEN p_son_mias THEN p.nota END, p.monto_total, p.fecha_pago,
           p.es_mi_pago = p_son_mias, NULL
      FROM public.pagos p
     WHERE p.deudor_id = p_deudor AND p.owner_id = p_owner AND p.estado_acuerdo = 'local'
       AND NOT COALESCE(p.es_compensacion, false)
$$;

-- SECURITY DEFINER: lee la libreta del otro (solo monto, fecha y dirección; nunca sus
-- títulos). Emparejamiento voraz uno a uno, del mejor puntaje al peor:
--   * misma entidad, mismo monto al centavo, dirección invertida, fecha a ±3 días;
--   * puntaje = cercanía de fecha (1 el mismo día … 0.25 a 3 días) + parecido de títulos
--     (pg_trgm, solo deudas).
-- Un par es `dudoso` si otro candidato que comparte una de sus filas quedó a menos de 0.5
-- de su puntaje: la UI no lo marca por defecto y se lo pregunta al usuario. El 0.5 sale de
-- scripts/v2/medir_conciliacion.py (datos reales, 12 semillas): con 0.15 se colaba un par
-- incorrecto sin marcar; con 0.5, ninguno, a cambio de ~10 de 239 pares correctos dudosos.
CREATE FUNCTION public.candidatos_conciliacion(p_vinculo_id uuid) RETURNS jsonb
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
                           AND abs(m.fecha - s.fecha) <= 3)
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

-- SECURITY DEFINER: marca filas de las dos libretas. La puede llamar cualquiera de las dos
-- partes, una vez (una segunda llamada no hace nada). `p_pares` =
-- [{"entidad": "deuda"|"pago", "mia": uuid, "suya": uuid}, …], validados de nuevo aquí:
-- el cliente no es de fiar.
--   1. Cada par pasa a `acordada` en las dos libretas y queda en `acuerdos`.
--   2. Mis filas sin par pasan a `propuesta` para el otro (una propuesta 'crear' cada una).
--   3. Si el otro ya confirmó, o no le queda nada que conciliar, el vínculo pasa a `activo`.
CREATE FUNCTION public.confirmar_conciliacion(p_vinculo_id uuid, p_pares jsonb DEFAULT '[]')
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    c            record;
    par          jsonb;
    v_mia        uuid;
    v_suya       uuid;
    v_ent        text;
    v_ok         boolean;
    v_acordadas  int := 0;
    v_propuestas int := 0;
    v_estado     text;
    f            record;
BEGIN
    -- Mismo candado que los RPC de escritura de cada deudor (registrar_pago,
    -- aplicar_cruce), en orden fijo para no trabarse con la otra parte.
    -- Ya activo (lo cerró la otra parte, o una llamada anterior): nada que hacer.
    IF EXISTS (SELECT 1 FROM public.vinculos
                WHERE id = p_vinculo_id AND estado = 'activo'
                  AND auth.uid() IN (usuario_a, usuario_b)) THEN
        RETURN jsonb_build_object('estado', 'activo', 'acordadas', 0, 'propuestas', 0);
    END IF;
    SELECT * INTO c FROM public._conciliacion_de(p_vinculo_id);
    PERFORM pg_advisory_xact_lock(hashtext(d::text))
       FROM unnest(ARRAY[c.mi_deudor, c.su_deudor]) AS d ORDER BY d::text;
    -- Releer tras el candado: la otra parte pudo confirmar mientras esperábamos.
    SELECT * INTO c FROM public._conciliacion_de(p_vinculo_id);

    IF (c.soy_a AND (c.vinculo).conciliado_a) OR (NOT c.soy_a AND (c.vinculo).conciliado_b) THEN
        RETURN jsonb_build_object('estado', (c.vinculo).estado, 'acordadas', 0, 'propuestas', 0);
    END IF;

    FOR par IN SELECT * FROM jsonb_array_elements(COALESCE(p_pares, '[]')) LOOP
        v_ent  := par->>'entidad';
        v_mia  := (par->>'mia')::uuid;
        v_suya := (par->>'suya')::uuid;
        IF v_ent = 'deuda' THEN
            SELECT true INTO v_ok
              FROM public.deudas m, public.deudas s
             WHERE m.id = v_mia  AND m.owner_id = auth.uid() AND m.deudor_id = c.mi_deudor
               AND s.id = v_suya AND s.owner_id = c.otro     AND s.deudor_id = c.su_deudor
               AND m.estado_acuerdo = 'local' AND s.estado_acuerdo = 'local'
               AND m.monto = s.monto AND m.es_mi_deuda <> s.es_mi_deuda;
        ELSIF v_ent = 'pago' THEN
            SELECT true INTO v_ok
              FROM public.pagos m, public.pagos s
             WHERE m.id = v_mia  AND m.owner_id = auth.uid() AND m.deudor_id = c.mi_deudor
               AND s.id = v_suya AND s.owner_id = c.otro     AND s.deudor_id = c.su_deudor
               AND m.estado_acuerdo = 'local' AND s.estado_acuerdo = 'local'
               AND NOT COALESCE(m.es_compensacion, false) AND NOT COALESCE(s.es_compensacion, false)
               AND m.monto_total = s.monto_total AND m.es_mi_pago <> s.es_mi_pago;
        END IF;
        IF NOT COALESCE(v_ok, false) THEN
            RAISE EXCEPTION 'Par inválido: % % / %', v_ent, v_mia, v_suya USING ERRCODE = '22023';
        END IF;
        v_ok := NULL;

        IF v_ent = 'deuda' THEN
            UPDATE public.deudas SET estado_acuerdo = 'acordada' WHERE id IN (v_mia, v_suya);
        ELSE
            UPDATE public.pagos SET estado_acuerdo = 'acordada' WHERE id IN (v_mia, v_suya);
        END IF;
        INSERT INTO public.acuerdos (vinculo_id, entidad, fila_a, fila_b)
        VALUES (p_vinculo_id, v_ent,
                CASE WHEN c.soy_a THEN v_mia ELSE v_suya END,
                CASE WHEN c.soy_a THEN v_suya ELSE v_mia END);
        v_acordadas := v_acordadas + 1;
    END LOOP;

    -- Lo que me quedó sin par se le propone al otro. `es_mia` en MI punto de vista (§5.3).
    FOR f IN SELECT * FROM public._filas_conciliables(c.mi_deudor, auth.uid(), true) LOOP
        IF f.entidad = 'deuda' THEN
            UPDATE public.deudas SET estado_acuerdo = 'propuesta' WHERE id = f.id;
        ELSE
            UPDATE public.pagos SET estado_acuerdo = 'propuesta' WHERE id = f.id;
        END IF;
        INSERT INTO public.propuestas
            (vinculo_id, de_usuario, para_usuario, entidad, tipo, fila_origen, payload, idem_key)
        VALUES (p_vinculo_id, auth.uid(), c.otro, f.entidad, 'crear', f.id,
                jsonb_build_object('monto', f.monto, 'fecha', f.fecha, 'es_mia', f.mio),
                public._idem_derivada(f.id, 'conciliacion'));
        v_propuestas := v_propuestas + 1;
    END LOOP;

    UPDATE public.vinculos
       SET conciliado_a = conciliado_a OR c.soy_a,
           conciliado_b = conciliado_b OR NOT c.soy_a,
           estado = CASE
               WHEN (CASE WHEN c.soy_a THEN conciliado_b ELSE conciliado_a END)
                 OR NOT EXISTS (SELECT 1 FROM public._filas_conciliables(c.su_deudor, c.otro, false))
               THEN 'activo' ELSE estado END
     WHERE id = p_vinculo_id
    RETURNING estado INTO v_estado;

    RETURN jsonb_build_object('estado', v_estado, 'acordadas', v_acordadas, 'propuestas', v_propuestas);
END $$;

-- ====================================================================================
-- Permisos
-- ====================================================================================

REVOKE ALL ON FUNCTION public._conciliacion_de(uuid)                       FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._filas_conciliables(uuid, uuid, boolean)     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.candidatos_conciliacion(uuid)                FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.confirmar_conciliacion(uuid, jsonb)          FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.candidatos_conciliacion(uuid)       TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.confirmar_conciliacion(uuid, jsonb) TO authenticated, service_role;
