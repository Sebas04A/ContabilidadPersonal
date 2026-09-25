-- Fase 9B (deudas/PLAN_MULTIUSUARIO.md §4.8 y §5.4): grupos compartidos. Decisiones del
-- dueño de §3.2 y 25 a 31 de §3.3 (aprobadas el 2026-09-24).
--
--   * Un grupo (viaje, casa, almuerzos…) tiene miembros: usuarios, que entran con un
--     enlace (`/grupo/unirse/<código>`), o personas sin app, que agrega cualquier miembro.
--     Las mismas personas pueden estar en varios grupos, con saldos independientes.
--   * Los gastos del grupo QUEDAN EN EL GRUPO: no pasan a las libretas y no hace falta
--     ningún vínculo. Todo cuenta de una vez; cada participante con app recibe un aviso.
--   * Rechazar mi parte (`rechazar_parte`): queda rechazada solo para mí, el resto se
--     reparte de nuevo entre los demás y el gasto queda "en revisión" para ellos (vuelve
--     a activo cuando todos lo vieron o cuando se edita). En 'montos' lo absorbe quien
--     pagó (26); si rechaza quien pagó, o solo queda él, el gasto se rechaza entero (27).
--   * Pagos del grupo: si lo anota quien RECIBE (o quien recibe no tiene app), cuenta de
--     una vez; si lo anota quien lo ENTREGA, queda por confirmar y no cuenta (28).
--   * Saldo: el neto de cada par, sin FIFO ni cruces (29). Solo se sale con saldo 0; un
--     grupo se archiva, no se borra (30).
--   * Al borrarse una cuenta, sus filas de miembro quedan como persona sin app (el FK pone
--     `usuario_id` en NULL y el nombre se queda): los saldos de los demás no cambian (9.7).
--
-- Decisiones del agente al implementar (para que el dueño las revise, §3.3, 32 a 36):
--   * El enlace de un grupo sirve para VARIAS personas (se comparte en el chat del grupo)
--     hasta que vence (7 días) o quien lo creó genera otro.
--   * Editar o borrar un gasto del grupo lo pueden quien lo anotó y quien lo pagó; un pago
--     del grupo lo borra quien lo anotó.
--
-- `_crear_gasto_grupo`, `_editar_gasto_grupo` y `_borrar_gasto_grupo` reemplazan las ramas
-- que 20260924160000 dejó sin implementar. `cambios_gastos` y `exportar_mis_datos` son
-- copia exacta de su versión de 20260924160000 más las líneas marcadas «v2 fase 9B».

-- ====================================================================================
-- Tablas
-- ====================================================================================

CREATE TABLE public.grupos (
    id         uuid PRIMARY KEY,                 -- lo genera el teléfono
    creado_por uuid DEFAULT auth.uid() REFERENCES public.perfiles ON DELETE SET NULL,
    nombre     text NOT NULL CHECK (btrim(nombre) <> '' AND length(nombre) <= 80),
    tipo       text NOT NULL DEFAULT 'otro' CHECK (tipo IN ('viaje', 'comida', 'casa', 'otro')),
    moneda     text NOT NULL DEFAULT 'USD',
    archivado  boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.grupos IS 'Grupo compartido de gastos. Solo por RPC.';

CREATE TABLE public.grupo_miembros (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    grupo_id     uuid NOT NULL REFERENCES public.grupos ON DELETE CASCADE,
    -- NULL = persona sin app. SET NULL: quien borra su cuenta queda como persona (9.7).
    usuario_id   uuid REFERENCES public.perfiles ON DELETE SET NULL,
    nombre       text NOT NULL CHECK (btrim(nombre) <> '' AND length(nombre) <= 80),
    agregado_por uuid DEFAULT auth.uid(),
    salio_at     timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (grupo_id, usuario_id),
    UNIQUE (id, grupo_id)
);
CREATE INDEX idx_grupo_miembros_usuario ON public.grupo_miembros (usuario_id) WHERE salio_at IS NULL;
CREATE INDEX idx_grupo_miembros_grupo   ON public.grupo_miembros (grupo_id, created_at);

CREATE TABLE public.grupo_invitaciones (     -- como `invitaciones` (§5.2), con el límite de 7.3
    codigo     text PRIMARY KEY,
    grupo_id   uuid NOT NULL REFERENCES public.grupos ON DELETE CASCADE,
    creado_por uuid NOT NULL DEFAULT auth.uid() REFERENCES public.perfiles ON DELETE CASCADE,
    miembro_id uuid REFERENCES public.grupo_miembros ON DELETE CASCADE,  -- 9C: reclamar el lugar de una persona
    expira     timestamptz NOT NULL DEFAULT now() + interval '7 days',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_grupo_invitaciones_creador ON public.grupo_invitaciones (creado_por, created_at);

CREATE TABLE public.grupo_pagos (
    id             uuid PRIMARY KEY,             -- lo genera el teléfono
    grupo_id       uuid NOT NULL REFERENCES public.grupos ON DELETE CASCADE,
    de_miembro     uuid NOT NULL,                -- entrega la plata
    para_miembro   uuid NOT NULL,                -- la recibe
    monto          numeric(10,2) NOT NULL CHECK (monto > 0),
    fecha          date NOT NULL,
    nota           text CHECK (length(nota) <= 500),
    registrado_por uuid NOT NULL DEFAULT auth.uid(),  -- sin FK: su cuenta se puede borrar
    estado         text NOT NULL CHECK (estado IN ('confirmado', 'por_confirmar', 'rechazado')),
    motivo         text CHECK (length(motivo) <= 500),
    idem_key       uuid,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),
    -- Las dos puntas son miembros de ESTE grupo.
    FOREIGN KEY (de_miembro, grupo_id)   REFERENCES public.grupo_miembros (id, grupo_id),
    FOREIGN KEY (para_miembro, grupo_id) REFERENCES public.grupo_miembros (id, grupo_id),
    CHECK (de_miembro <> para_miembro)
);
CREATE UNIQUE INDEX idx_grupo_pagos_idem ON public.grupo_pagos (registrado_por, idem_key) WHERE idem_key IS NOT NULL;
CREATE INDEX idx_grupo_pagos_grupo      ON public.grupo_pagos (grupo_id, updated_at);

-- Lo que 20260924160000 dejó sin FK.
ALTER TABLE public.gastos
    ADD CONSTRAINT gastos_grupo_fkey FOREIGN KEY (grupo_id) REFERENCES public.grupos ON DELETE CASCADE;
ALTER TABLE public.gasto_participantes
    ADD CONSTRAINT gasto_participantes_miembro_fkey FOREIGN KEY (miembro_id) REFERENCES public.grupo_miembros;
CREATE INDEX idx_gasto_part_miembro ON public.gasto_participantes (miembro_id);

-- Los avisos del grupo (la fase 8 ya dejó los cuatro de §4.7; se suman editar, borrar y
-- lo que pasa con un pago).
ALTER TABLE public.avisos DROP CONSTRAINT avisos_tipo_check;
ALTER TABLE public.avisos ADD CONSTRAINT avisos_tipo_check CHECK (tipo IN (
    'deuda_nueva', 'pago_nuevo', 'pago_por_confirmar', 'propuesta',
    'cambio', 'borrado', 'confirmado', 'rechazo', 'desvinculado',
    'gasto_nuevo', 'gasto_en_revision', 'gasto_rechazado', 'pago_grupo_por_confirmar',
    'gasto_editado', 'gasto_borrado', 'pago_grupo_nuevo', 'pago_grupo_confirmado',
    'pago_grupo_rechazado', 'pago_grupo_borrado'));
CREATE INDEX idx_avisos_gasto ON public.avisos (gasto_id) WHERE gasto_id IS NOT NULL;

CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.grupos
    FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();
CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.grupo_miembros
    FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();
CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.grupo_pagos
    FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();
CREATE TRIGGER lapida AFTER DELETE ON public.grupo_pagos
    FOR EACH ROW EXECUTE FUNCTION public._lapida_gasto();

-- ====================================================================================
-- RLS: lo de un grupo lo ven sus miembros activos (también lo de los pares en los que no
-- están, §4.8). Nadie escribe directo: todo va por RPC.
-- ====================================================================================

-- SECURITY DEFINER: lo usan las policies de grupo_miembros, que no pueden leerse a sí
-- mismas sin recursión.
CREATE FUNCTION public._soy_miembro(p_grupo uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT EXISTS (SELECT 1 FROM grupo_miembros
                    WHERE grupo_id = p_grupo AND usuario_id = auth.uid() AND salio_at IS NULL)
$$;

ALTER TABLE public.grupos ENABLE ROW LEVEL SECURITY;
CREATE POLICY miembros ON public.grupos FOR SELECT TO authenticated USING (_soy_miembro(id));
REVOKE ALL ON public.grupos FROM anon, authenticated;
GRANT SELECT ON public.grupos TO authenticated;

ALTER TABLE public.grupo_miembros ENABLE ROW LEVEL SECURITY;
CREATE POLICY miembros ON public.grupo_miembros FOR SELECT TO authenticated USING (_soy_miembro(grupo_id));
REVOKE ALL ON public.grupo_miembros FROM anon, authenticated;
GRANT SELECT ON public.grupo_miembros TO authenticated;

ALTER TABLE public.grupo_pagos ENABLE ROW LEVEL SECURITY;
CREATE POLICY miembros ON public.grupo_pagos FOR SELECT TO authenticated USING (_soy_miembro(grupo_id));
REVOKE ALL ON public.grupo_pagos FROM anon, authenticated;
GRANT SELECT ON public.grupo_pagos TO authenticated;

ALTER TABLE public.grupo_invitaciones ENABLE ROW LEVEL SECURITY;
CREATE POLICY propio_leer ON public.grupo_invitaciones FOR SELECT TO authenticated
    USING (creado_por = (SELECT auth.uid()));
REVOKE ALL ON public.grupo_invitaciones FROM anon, authenticated;
GRANT SELECT ON public.grupo_invitaciones TO authenticated;

DROP POLICY ver ON public.gastos;
CREATE POLICY ver ON public.gastos FOR SELECT TO authenticated
    USING ((grupo_id IS NULL AND creado_por = (SELECT auth.uid()))
           OR (grupo_id IS NOT NULL AND _soy_miembro(grupo_id)));

DROP POLICY ver ON public.borrados_gastos;
CREATE POLICY ver ON public.borrados_gastos FOR SELECT TO authenticated
    USING (owner_id = (SELECT auth.uid()) OR (grupo_id IS NOT NULL AND _soy_miembro(grupo_id)));

-- ====================================================================================
-- Piezas internas
-- ====================================================================================

-- Mi fila de miembro activo en el grupo (NULL si no lo soy).
CREATE FUNCTION public._mi_miembro(p_grupo uuid) RETURNS uuid
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT id FROM grupo_miembros
     WHERE grupo_id = p_grupo AND usuario_id = auth.uid() AND salio_at IS NULL
$$;

-- Falla con 42501 si no soy miembro activo; si no, devuelve mi fila de miembro.
CREATE FUNCTION public._exigir_miembro(p_grupo uuid) RETURNS uuid
    LANGUAGE plpgsql STABLE SET search_path = public AS $$
DECLARE
    v uuid := _mi_miembro(p_grupo);
BEGIN
    IF auth.uid() IS NULL OR v IS NULL THEN
        RAISE EXCEPTION 'El grupo % no existe o no eres miembro', p_grupo USING ERRCODE = '42501';
    END IF;
    RETURN v;
END $$;

-- Cambió la lista de miembros: el pull de la app baja el grupo entero de nuevo.
CREATE FUNCTION public._tocar_grupo(p_grupo uuid) RETURNS void
    LANGUAGE sql SET search_path = public AS $$
    UPDATE grupos SET updated_at = now() WHERE id = p_grupo
$$;

-- Candado del grupo: los gastos y pagos de un grupo se escriben de a uno (los saldos y
-- los repartos no se pisan).
CREATE FUNCTION public._candado_grupo(p_grupo uuid) RETURNS void
    LANGUAGE sql AS $$
    SELECT pg_advisory_xact_lock(hashtext('grupo|' || p_grupo::text))
$$;

-- Las filas de un gasto de grupo como las entiende _partes_gasto (en orden), con quién
-- rechazó; y la posición de quien pagó.
CREATE FUNCTION public._filas_gasto(p_gasto uuid, OUT filas jsonb, OUT pagador int)
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT jsonb_agg(jsonb_build_object('peso', peso, 'pagado', pagado,
                                        'rechazada', estado = 'rechazada') ORDER BY orden),
           (SELECT orden FROM gasto_participantes WHERE gasto_id = p_gasto AND pagado > 0 LIMIT 1)
      FROM gasto_participantes WHERE gasto_id = p_gasto
$$;

-- El estado que corresponde a un gasto de grupo (27): rechazado si rechazó quien pagó o
-- si ya no queda nadie más que él en el reparto.
CREATE FUNCTION public._gasto_sin_nadie(p_gasto uuid) RETURNS boolean
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT EXISTS (SELECT 1 FROM gasto_participantes
                    WHERE gasto_id = p_gasto AND pagado > 0 AND estado = 'rechazada')
        OR NOT EXISTS (SELECT 1 FROM gasto_participantes
                        WHERE gasto_id = p_gasto AND pagado = 0 AND peso IS NOT NULL AND estado = 'activa')
$$;

-- Avisa del gasto a sus participantes con app y a quien lo anotó, menos a quien actúa.
-- `p_por_miembro` agrega datos a cada uno ({miembro_id: {...}}). Todo en el punto de vista
-- de quien recibe: `mi_parte` es la suya. Devuelve cuántos avisos escribió.
CREATE FUNCTION public._avisar_gasto(p_gasto uuid, p_tipo text, p_datos jsonb DEFAULT '{}',
                                     p_por_miembro jsonb DEFAULT '{}') RETURNS int
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_g     public.gastos;
    v_grupo public.grupos;
    v_quien text;
    v_n     int;
BEGIN
    SELECT * INTO v_g FROM gastos WHERE id = p_gasto;
    SELECT * INTO v_grupo FROM grupos WHERE id = v_g.grupo_id;
    SELECT nombre INTO v_quien FROM grupo_miembros
     WHERE grupo_id = v_g.grupo_id AND usuario_id = auth.uid();
    INSERT INTO avisos (usuario_id, tipo, de_usuario, grupo_id, gasto_id, datos)
    SELECT m.usuario_id, p_tipo, auth.uid(), v_g.grupo_id, v_g.id,
           jsonb_strip_nulls(jsonb_build_object(
               'grupo', v_grupo.nombre, 'titulo', v_g.titulo, 'monto_total', v_g.monto_total,
               'fecha', v_g.fecha, 'quien', v_quien,
               'mi_parte', CASE WHEN p.estado = 'activa' THEN p.parte END,
               'pague', CASE WHEN p.pagado > 0 THEN true END))
           || p_datos || COALESCE(p_por_miembro -> m.id::text, '{}')
      FROM grupo_miembros m
      LEFT JOIN gasto_participantes p ON p.gasto_id = v_g.id AND p.miembro_id = m.id
     WHERE m.grupo_id = v_g.grupo_id AND m.usuario_id IS NOT NULL AND m.salio_at IS NULL
       AND m.usuario_id IS DISTINCT FROM auth.uid()
       AND (p.id IS NOT NULL OR m.usuario_id = v_g.creado_por)
     ORDER BY m.usuario_id;
    GET DIAGNOSTICS v_n = ROW_COUNT;
    RETURN v_n;
END $$;

-- Aviso de un pago del grupo a una de sus puntas (la que no actúa).
CREATE FUNCTION public._avisar_pago(p_pago public.grupo_pagos, p_para uuid, p_tipo text) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF p_para IS NULL OR p_para = auth.uid() THEN
        RETURN;
    END IF;
    INSERT INTO avisos (usuario_id, tipo, de_usuario, grupo_id, datos)
    SELECT p_para, p_tipo, auth.uid(), p_pago.grupo_id, jsonb_strip_nulls(jsonb_build_object(
               'grupo', g.nombre, 'pago_id', p_pago.id, 'monto', p_pago.monto, 'fecha', p_pago.fecha,
               'nota', p_pago.nota, 'motivo', p_pago.motivo,
               'de', (SELECT nombre FROM grupo_miembros WHERE id = p_pago.de_miembro),
               'para', (SELECT nombre FROM grupo_miembros WHERE id = p_pago.para_miembro),
               'quien', (SELECT nombre FROM grupo_miembros WHERE grupo_id = p_pago.grupo_id
                                                            AND usuario_id = auth.uid())))
      FROM grupos g
     WHERE g.id = p_pago.grupo_id
       AND EXISTS (SELECT 1 FROM grupo_miembros WHERE grupo_id = g.id AND usuario_id = p_para
                                                  AND salio_at IS NULL);
END $$;

-- Los saldos de un grupo, por par (29): cada participante activo le debe su parte a quien
-- pagó; un pago confirmado de X a Y lo compensa. Solo los pares con saldo, cada uno una
-- vez: `debe` le debe `monto` a `a`. Gastos rechazados y pagos por confirmar o rechazados
-- no cuentan. lib/dominio/saldos_grupo.dart hace lo mismo sin conexión.
CREATE FUNCTION public._pares_grupo(p_grupo uuid)
    RETURNS TABLE (debe uuid, a uuid, monto numeric)
    LANGUAGE sql STABLE SET search_path = public AS $$
    WITH mov AS (
        SELECT p.miembro_id AS debe, pg.miembro_id AS a, p.parte AS monto
          FROM gastos g
          JOIN gasto_participantes pg ON pg.gasto_id = g.id AND pg.pagado > 0
          JOIN gasto_participantes p  ON p.gasto_id = g.id AND p.estado = 'activa'
                                     AND p.miembro_id <> pg.miembro_id AND p.parte > 0
         WHERE g.grupo_id = p_grupo AND g.estado <> 'rechazado'
        UNION ALL
        SELECT para_miembro, de_miembro, monto FROM grupo_pagos
         WHERE grupo_id = p_grupo AND estado = 'confirmado'
    ), par AS (
        -- x < y (como texto); m > 0: x le debe a y.
        SELECT LEAST(debe::text, a::text) AS x, GREATEST(debe::text, a::text) AS y,
               sum(CASE WHEN debe::text < a::text THEN monto ELSE -monto END) AS m
          FROM mov GROUP BY 1, 2
    )
    SELECT CASE WHEN m > 0 THEN x ELSE y END::uuid,
           CASE WHEN m > 0 THEN y ELSE x END::uuid,
           abs(m)
      FROM par
     WHERE abs(m) >= 0.005
     ORDER BY 1, 2
$$;

-- Neto de un miembro en el grupo: + le deben, − debe.
CREATE FUNCTION public._neto_miembro(p_grupo uuid, p_miembro uuid) RETURNS numeric
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT COALESCE(sum(CASE WHEN a = p_miembro THEN monto ELSE -monto END), 0)
      FROM _pares_grupo(p_grupo) WHERE p_miembro IN (debe, a)
$$;

-- Comprueba que las filas de un gasto de grupo son miembros de ese grupo. Los que se
-- fueron solo pueden seguir si ya estaban en el gasto (`p_gasto`).
CREATE FUNCTION public._validar_miembros(p_grupo uuid, p_leido jsonb, p_gasto uuid) RETURNS void
    LANGUAGE plpgsql STABLE SET search_path = public AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(p_leido -> 'filas') f
                WHERE f -> 'miembro_id' = 'null' OR f -> 'deudor_id' <> 'null') THEN
        RAISE EXCEPTION 'En un grupo, cada participante es un miembro del grupo' USING ERRCODE = '22023';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(p_leido -> 'filas') f
                WHERE NOT EXISTS (
                    SELECT 1 FROM grupo_miembros m
                     WHERE m.id = (f ->> 'miembro_id')::uuid AND m.grupo_id = p_grupo
                       AND (m.salio_at IS NULL
                            OR EXISTS (SELECT 1 FROM gasto_participantes x
                                        WHERE x.gasto_id = p_gasto AND x.miembro_id = m.id)))) THEN
        RAISE EXCEPTION 'Uno de los participantes no es miembro del grupo' USING ERRCODE = '22023';
    END IF;
END $$;

-- ====================================================================================
-- Ramas de grupo de crear_gasto, editar_gasto y borrar_gasto (20260924160000)
-- ====================================================================================

CREATE OR REPLACE FUNCTION public._crear_gasto_grupo(
    p_id uuid, p_grupo_id uuid, p_leido jsonb, p_idem_key uuid) RETURNS jsonb
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_partes numeric[];
    v_f      jsonb;
    k        int;
BEGIN
    PERFORM _exigir_miembro(p_grupo_id);
    IF (SELECT archivado FROM grupos WHERE id = p_grupo_id) THEN
        RAISE EXCEPTION 'El grupo está archivado: desarchívalo para anotar gastos' USING ERRCODE = '22023';
    END IF;
    PERFORM _validar_miembros(p_grupo_id, p_leido, NULL);
    PERFORM _candado_grupo(p_grupo_id);
    v_partes := _partes_gasto((p_leido ->> 'monto')::numeric, p_leido ->> 'modo', p_leido -> 'filas',
                              (p_leido ->> 'pagador')::int);
    INSERT INTO gastos (id, grupo_id, creado_por, titulo, monto_total, fecha, modo, idem_key)
    VALUES (p_id, p_grupo_id, auth.uid(), p_leido ->> 'titulo', (p_leido ->> 'monto')::numeric,
            (p_leido ->> 'fecha')::date, p_leido ->> 'modo', p_idem_key);
    FOR k IN 1..jsonb_array_length(p_leido -> 'filas') LOOP
        v_f := p_leido -> 'filas' -> (k - 1);
        INSERT INTO gasto_participantes (gasto_id, orden, miembro_id, pagado, parte, peso)
        VALUES (p_id, k, (v_f ->> 'miembro_id')::uuid, (v_f ->> 'pagado')::numeric, v_partes[k],
                (v_f ->> 'peso')::numeric);
    END LOOP;
    PERFORM _avisar_gasto(p_id, 'gasto_nuevo');
    RETURN _gasto_json(p_id) || jsonb_build_object('repetido', false);
END $$;

-- Editar un gasto del grupo: quien lo anotó o quien lo pagó (antes o después del cambio).
-- Quien había rechazado su parte sigue rechazado, salvo que venga con `reincluir`. Se
-- aplica de una vez (el gasto es del grupo, no de una libreta) y avisa a los participantes.
CREATE OR REPLACE FUNCTION public._editar_gasto_grupo(p_gasto public.gastos, p_leido jsonb, p_idem_key uuid)
    RETURNS jsonb
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_yo     uuid := _exigir_miembro(p_gasto.grupo_id);
    v_filas  jsonb := '[]';
    v_f      jsonb;
    v_prev   public.gasto_participantes;
    v_partes numeric[];
    k        int;
BEGIN
    IF p_gasto.creado_por IS DISTINCT FROM auth.uid()
       AND NOT EXISTS (SELECT 1 FROM gasto_participantes
                        WHERE gasto_id = p_gasto.id AND miembro_id = v_yo AND pagado > 0) THEN
        RAISE EXCEPTION 'Solo quien anotó el gasto o quien lo pagó lo puede cambiar' USING ERRCODE = '42501';
    END IF;
    PERFORM _validar_miembros(p_gasto.grupo_id, p_leido, p_gasto.id);
    PERFORM _candado_grupo(p_gasto.grupo_id);

    -- Los rechazos se conservan (con su motivo) salvo que se vuelva a incluir a alguien.
    FOR k IN 1..jsonb_array_length(p_leido -> 'filas') LOOP
        v_f := p_leido -> 'filas' -> (k - 1);
        SELECT * INTO v_prev FROM gasto_participantes
         WHERE gasto_id = p_gasto.id AND miembro_id = (v_f ->> 'miembro_id')::uuid;
        v_filas := v_filas || (v_f || jsonb_build_object(
            'rechazada', FOUND AND v_prev.estado = 'rechazada' AND NOT (v_f ->> 'reincluir')::boolean,
            'motivo', CASE WHEN FOUND AND NOT (v_f ->> 'reincluir')::boolean THEN v_prev.motivo END));
    END LOOP;
    v_partes := _partes_gasto((p_leido ->> 'monto')::numeric, p_leido ->> 'modo', v_filas,
                              (p_leido ->> 'pagador')::int);

    DELETE FROM gasto_participantes WHERE gasto_id = p_gasto.id;
    FOR k IN 1..jsonb_array_length(v_filas) LOOP
        v_f := v_filas -> (k - 1);
        INSERT INTO gasto_participantes (gasto_id, orden, miembro_id, pagado, parte, peso, estado, motivo)
        VALUES (p_gasto.id, k, (v_f ->> 'miembro_id')::uuid, (v_f ->> 'pagado')::numeric, v_partes[k],
                (v_f ->> 'peso')::numeric,
                CASE WHEN (v_f ->> 'rechazada')::boolean THEN 'rechazada' ELSE 'activa' END,
                v_f ->> 'motivo');
    END LOOP;
    UPDATE gastos
       SET titulo = p_leido ->> 'titulo', monto_total = (p_leido ->> 'monto')::numeric,
           fecha = (p_leido ->> 'fecha')::date, modo = p_leido ->> 'modo', edit_idem = p_idem_key,
           estado = CASE WHEN _gasto_sin_nadie(p_gasto.id) THEN 'rechazado' ELSE 'activo' END
     WHERE id = p_gasto.id;
    PERFORM _avisar_gasto(p_gasto.id, 'gasto_editado');
    RETURN _gasto_json(p_gasto.id) || jsonb_build_object('repetido', false);
END $$;

CREATE OR REPLACE FUNCTION public._borrar_gasto_grupo(p_gasto public.gastos) RETURNS jsonb
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_yo uuid := _exigir_miembro(p_gasto.grupo_id);
BEGIN
    IF p_gasto.creado_por IS DISTINCT FROM auth.uid()
       AND NOT EXISTS (SELECT 1 FROM gasto_participantes
                        WHERE gasto_id = p_gasto.id AND miembro_id = v_yo AND pagado > 0) THEN
        RAISE EXCEPTION 'Solo quien anotó el gasto o quien lo pagó lo puede borrar' USING ERRCODE = '42501';
    END IF;
    PERFORM _candado_grupo(p_gasto.grupo_id);
    PERFORM _avisar_gasto(p_gasto.id, 'gasto_borrado');
    DELETE FROM gastos WHERE id = p_gasto.id;
    RETURN jsonb_build_object('resultado', 'borrado', 'gasto_id', p_gasto.id, 'repetido', false);
END $$;

-- ====================================================================================
-- Triggers
-- ====================================================================================

-- AFTER UPDATE OF visto_at en avisos: un gasto "en revisión" vuelve a activo cuando todos
-- los que tenían que revisarlo vieron el aviso (§4.8).
CREATE FUNCTION public._revision_vista() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM avisos WHERE gasto_id = NEW.gasto_id
                      AND tipo = 'gasto_en_revision' AND visto_at IS NULL) THEN
        UPDATE gastos SET estado = 'activo' WHERE id = NEW.gasto_id AND estado = 'en_revision';
    END IF;
    RETURN NULL;
END $$;

CREATE TRIGGER revision_vista AFTER UPDATE OF visto_at ON public.avisos
    FOR EACH ROW WHEN (NEW.tipo = 'gasto_en_revision' AND NEW.visto_at IS NOT NULL
                       AND OLD.visto_at IS NULL)
    EXECUTE FUNCTION public._revision_vista();

-- ====================================================================================
-- RPC: grupos y miembros
-- ====================================================================================

-- Crea un grupo conmigo como primer miembro. `p_id` (y `p_mi_miembro_id`) los genera el
-- teléfono: repetirlo devuelve el mismo grupo. Hasta 20 grupos nuevos por día.
CREATE FUNCTION public.crear_grupo(
    p_id uuid, p_nombre text, p_tipo text DEFAULT 'otro', p_mi_miembro_id uuid DEFAULT NULL,
    p_moneda text DEFAULT 'USD', p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid  uuid := auth.uid();
    v_prev public.grupos;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v_prev FROM grupos WHERE id = p_id;
    IF FOUND THEN
        IF v_prev.creado_por = v_uid THEN
            RETURN to_jsonb(v_prev) || jsonb_build_object('mi_miembro_id', _mi_miembro(p_id), 'repetido', true);
        END IF;
        RAISE EXCEPTION 'El grupo % ya existe', p_id USING ERRCODE = '42501';
    END IF;
    IF btrim(COALESCE(p_nombre, '')) = '' OR length(p_nombre) > 80 THEN
        RAISE EXCEPTION 'El grupo necesita un nombre (hasta 80 caracteres)' USING ERRCODE = '22023';
    END IF;
    IF (SELECT count(*) FROM grupos WHERE creado_por = v_uid AND created_at > now() - interval '1 day') >= 20 THEN
        RAISE EXCEPTION 'Llegaste al límite de 20 grupos nuevos por día. Prueba mañana.' USING ERRCODE = 'PT429';
    END IF;
    INSERT INTO grupos (id, creado_por, nombre, tipo, moneda)
    VALUES (p_id, v_uid, btrim(p_nombre), COALESCE(p_tipo, 'otro'), COALESCE(p_moneda, 'USD'));
    INSERT INTO grupo_miembros (id, grupo_id, usuario_id, nombre, agregado_por)
    SELECT COALESCE(p_mi_miembro_id, gen_random_uuid()), p_id, v_uid, nombre, v_uid
      FROM perfiles WHERE id = v_uid;
    RETURN (SELECT to_jsonb(g) FROM grupos g WHERE id = p_id)
        || jsonb_build_object('mi_miembro_id', _mi_miembro(p_id), 'repetido', false);
END $$;

-- Agrega una persona sin app (solo un nombre). Cualquier miembro. `p_id` lo genera el
-- teléfono. Hasta 50 miembros activos por grupo.
CREATE FUNCTION public.agregar_persona(
    p_grupo_id uuid, p_nombre text, p_id uuid DEFAULT NULL, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_m public.grupo_miembros;
BEGIN
    PERFORM _exigir_miembro(p_grupo_id);
    IF p_id IS NOT NULL THEN
        SELECT * INTO v_m FROM grupo_miembros WHERE id = p_id;
        IF FOUND THEN
            IF v_m.grupo_id = p_grupo_id THEN
                RETURN to_jsonb(v_m) || jsonb_build_object('repetido', true);
            END IF;
            RAISE EXCEPTION 'El miembro % ya existe en otro grupo', p_id USING ERRCODE = '42501';
        END IF;
    END IF;
    IF btrim(COALESCE(p_nombre, '')) = '' OR length(p_nombre) > 80 THEN
        RAISE EXCEPTION 'Falta el nombre (hasta 80 caracteres)' USING ERRCODE = '22023';
    END IF;
    PERFORM _candado_grupo(p_grupo_id);
    IF (SELECT count(*) FROM grupo_miembros WHERE grupo_id = p_grupo_id AND salio_at IS NULL) >= 50 THEN
        RAISE EXCEPTION 'Un grupo tiene 50 miembros como mucho' USING ERRCODE = '22023';
    END IF;
    INSERT INTO grupo_miembros (id, grupo_id, usuario_id, nombre)
    VALUES (COALESCE(p_id, gen_random_uuid()), p_grupo_id, NULL, btrim(p_nombre))
    RETURNING * INTO v_m;
    PERFORM _tocar_grupo(p_grupo_id);
    RETURN to_jsonb(v_m) || jsonb_build_object('repetido', false);
END $$;

-- Enlace para entrar al grupo: `…/grupo/unirse/<código>`. Sirve para varias personas
-- (se comparte en el chat del grupo) durante 7 días; crear otro anula el mío anterior de
-- ese grupo. 20 por día, como las invitaciones de un contacto (7.3).
CREATE FUNCTION public.invitar_a_grupo(p_grupo_id uuid) RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid    uuid := auth.uid();
    v_codigo text;
BEGIN
    PERFORM _exigir_miembro(p_grupo_id);
    IF (SELECT count(*) FROM grupo_invitaciones
         WHERE creado_por = v_uid AND created_at > now() - interval '1 day') >= 20 THEN
        RAISE EXCEPTION 'Llegaste al límite de 20 invitaciones a grupos por día. Prueba mañana.'
            USING ERRCODE = 'PT429';
    END IF;
    UPDATE grupo_invitaciones SET expira = now()
     WHERE grupo_id = p_grupo_id AND creado_por = v_uid AND expira > now();
    LOOP
        v_codigo := _codigo_invitacion();
        BEGIN
            INSERT INTO grupo_invitaciones (codigo, grupo_id, creado_por) VALUES (v_codigo, p_grupo_id, v_uid);
            RETURN v_codigo;
        EXCEPTION WHEN unique_violation THEN
            -- Choque de códigos (1 en 2^50): otro intento.
        END;
    END LOOP;
END $$;

-- Entrar a un grupo con un código. Un código que no sirve (no existe, vencido o
-- reemplazado) devuelve NULL, siempre igual, y cuenta para el límite de 10 por hora de los
-- canjes (7.3): no se puede sondear. Si ya era miembro devuelve el grupo; si se había ido,
-- vuelve.
CREATE FUNCTION public.unirse_a_grupo(p_codigo text, p_idem_key uuid DEFAULT NULL) RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid uuid := auth.uid();
    v_inv public.grupo_invitaciones;
    v_m   public.grupo_miembros;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    IF (SELECT count(*) FROM intentos_canje
         WHERE usuario = v_uid AND at > now() - interval '1 hour') >= 10 THEN
        RAISE EXCEPTION 'Demasiados códigos que no sirven. Espera una hora y vuelve a intentarlo.'
            USING ERRCODE = 'PT429';
    END IF;
    SELECT * INTO v_inv FROM grupo_invitaciones WHERE codigo = upper(btrim(p_codigo));
    IF NOT FOUND OR v_inv.expira <= now() THEN
        RETURN _canje_fallido(v_uid);
    END IF;

    PERFORM _candado_grupo(v_inv.grupo_id);
    SELECT * INTO v_m FROM grupo_miembros WHERE grupo_id = v_inv.grupo_id AND usuario_id = v_uid;
    IF FOUND AND v_m.salio_at IS NULL THEN
        RETURN v_inv.grupo_id;
    END IF;
    IF (SELECT count(*) FROM grupo_miembros WHERE grupo_id = v_inv.grupo_id AND salio_at IS NULL) >= 50 THEN
        RAISE EXCEPTION 'El grupo ya tiene 50 miembros' USING ERRCODE = '22023';
    END IF;
    IF FOUND THEN
        UPDATE grupo_miembros SET salio_at = NULL WHERE id = v_m.id;
    ELSE
        INSERT INTO grupo_miembros (grupo_id, usuario_id, nombre, agregado_por)
        SELECT v_inv.grupo_id, v_uid, nombre, v_inv.creado_por FROM perfiles WHERE id = v_uid;
    END IF;
    PERFORM _tocar_grupo(v_inv.grupo_id);
    RETURN v_inv.grupo_id;
END $$;

-- Salir del grupo: solo con mi saldo en 0 y sin pagos por confirmar (30). Dejo de verlo;
-- mi fila queda (los gastos viejos la nombran) y mis enlaces dejan de servir.
CREATE FUNCTION public.salir_de_grupo(p_grupo_id uuid, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_yo   uuid;
    v_neto numeric;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    v_yo := _mi_miembro(p_grupo_id);
    IF v_yo IS NULL THEN
        IF EXISTS (SELECT 1 FROM grupo_miembros WHERE grupo_id = p_grupo_id AND usuario_id = auth.uid()) THEN
            RETURN jsonb_build_object('resultado', 'salio', 'repetido', true);
        END IF;
        RAISE EXCEPTION 'El grupo % no existe o no eres miembro', p_grupo_id USING ERRCODE = '42501';
    END IF;
    PERFORM _candado_grupo(p_grupo_id);
    v_neto := _neto_miembro(p_grupo_id, v_yo);
    IF abs(v_neto) >= 0.005 THEN
        RAISE EXCEPTION 'Para salir del grupo tu saldo tiene que ser 0 (hoy es %)', v_neto USING ERRCODE = '22023';
    END IF;
    IF EXISTS (SELECT 1 FROM grupo_pagos WHERE grupo_id = p_grupo_id AND estado = 'por_confirmar'
                  AND v_yo IN (de_miembro, para_miembro)) THEN
        RAISE EXCEPTION 'Tienes pagos por confirmar en el grupo: resuélvelos antes de salir' USING ERRCODE = '22023';
    END IF;
    UPDATE grupo_miembros SET salio_at = now() WHERE id = v_yo;
    UPDATE grupo_invitaciones SET expira = now()
     WHERE grupo_id = p_grupo_id AND creado_por = auth.uid() AND expira > now();
    PERFORM _tocar_grupo(p_grupo_id);
    RETURN jsonb_build_object('resultado', 'salio', 'repetido', false);
END $$;

-- Archivar (o desarchivar) un grupo: deja de aparecer entre los activos, no se borra
-- (30). Cualquier miembro.
CREATE FUNCTION public.archivar_grupo(p_grupo_id uuid, p_archivado boolean DEFAULT true,
                                      p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    PERFORM _exigir_miembro(p_grupo_id);
    UPDATE grupos SET archivado = COALESCE(p_archivado, true)
     WHERE id = p_grupo_id AND archivado IS DISTINCT FROM COALESCE(p_archivado, true);
    RETURN jsonb_build_object('grupo_id', p_grupo_id, 'archivado', COALESCE(p_archivado, true));
END $$;

-- ====================================================================================
-- RPC: rechazar mi parte
-- ====================================================================================

-- Rechazo mi parte de un gasto del grupo (§4.8): queda rechazada solo para mí; el gasto se
-- reparte de nuevo entre los demás y queda "en revisión" para ellos, con un aviso que dice
-- cuánto les tocaba y cuánto les toca ahora. Si rechaza quien pagó, o solo queda él, el
-- gasto se rechaza entero (27). En 'montos', lo mío lo absorbe quien pagó (26). Repetirlo
-- no hace nada.
CREATE FUNCTION public.rechazar_parte(p_gasto_id uuid, p_motivo text DEFAULT NULL,
                                      p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_g      public.gastos;
    v_yo     uuid;
    v_mia    public.gasto_participantes;
    v_antes  jsonb;
    v_x      record;
    v_partes numeric[];
    v_estado text;
    v_por    jsonb := '{}';
    v_n      int;
    v_motivo text := NULLIF(btrim(p_motivo), '');
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v_g FROM gastos WHERE id = p_gasto_id;
    IF NOT FOUND OR v_g.grupo_id IS NULL OR _mi_miembro(v_g.grupo_id) IS NULL THEN
        RAISE EXCEPTION 'El gasto % no existe o no es de un grupo tuyo', p_gasto_id USING ERRCODE = '42501';
    END IF;
    IF length(v_motivo) > 500 THEN
        RAISE EXCEPTION 'El motivo no puede pasar de 500 caracteres' USING ERRCODE = '22023';
    END IF;
    v_yo := _mi_miembro(v_g.grupo_id);
    PERFORM _candado_grupo(v_g.grupo_id);
    SELECT * INTO v_g FROM gastos WHERE id = p_gasto_id FOR UPDATE;
    SELECT * INTO v_mia FROM gasto_participantes WHERE gasto_id = v_g.id AND miembro_id = v_yo FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No participas de este gasto' USING ERRCODE = '22023';
    END IF;
    IF v_mia.estado = 'rechazada' OR v_g.estado = 'rechazado' THEN
        RETURN _gasto_json(v_g.id) || jsonb_build_object('repetido', true);
    END IF;

    SELECT jsonb_object_agg(miembro_id::text, parte) INTO v_antes
      FROM gasto_participantes WHERE gasto_id = v_g.id AND estado = 'activa';
    UPDATE gasto_participantes SET estado = 'rechazada', motivo = v_motivo WHERE id = v_mia.id;

    IF NOT _gasto_sin_nadie(v_g.id) THEN
        SELECT * INTO v_x FROM _filas_gasto(v_g.id);
        v_partes := _partes_gasto(v_g.monto_total, v_g.modo, v_x.filas, v_x.pagador);
        UPDATE gasto_participantes p SET parte = v_partes[p.orden]
         WHERE gasto_id = v_g.id AND estado = 'activa' AND parte IS DISTINCT FROM v_partes[p.orden];
        v_estado := 'en_revision';
    ELSE
        v_estado := 'rechazado';
    END IF;
    UPDATE gastos SET estado = v_estado WHERE id = v_g.id;

    IF v_estado = 'rechazado' THEN
        PERFORM _avisar_gasto(v_g.id, 'gasto_rechazado', jsonb_strip_nulls(jsonb_build_object('motivo', v_motivo)));
    ELSE
        SELECT jsonb_object_agg(miembro_id::text, jsonb_build_object(
                   'parte_antes', (v_antes ->> miembro_id::text)::numeric, 'parte_nueva', parte))
          INTO v_por
          FROM gasto_participantes WHERE gasto_id = v_g.id AND estado = 'activa';
        v_n := _avisar_gasto(v_g.id, 'gasto_en_revision',
                             jsonb_strip_nulls(jsonb_build_object('motivo', v_motivo)), COALESCE(v_por, '{}'));
        -- Nadie con app que tenga que revisarlo: queda activo.
        IF v_n = 0 THEN
            UPDATE gastos SET estado = 'activo' WHERE id = v_g.id;
        END IF;
    END IF;
    RETURN _gasto_json(v_g.id) || jsonb_build_object('repetido', false);
END $$;

-- ====================================================================================
-- RPC: pagos del grupo
-- ====================================================================================

-- Anota que `p_de` le pagó `p_monto` a `p_para` (§3.2 y 28). Lo anota una de sus dos
-- partes (cualquier miembro si las dos son personas sin app):
--   * quien recibe, o quien entrega a una persona sin app → cuenta de una vez;
--   * quien entrega a alguien con app → por confirmar: no cuenta hasta que lo confirme.
-- `p_id` lo genera el teléfono: repetirlo devuelve el mismo pago.
CREATE FUNCTION public.registrar_pago_grupo(
    p_id uuid, p_grupo_id uuid, p_de uuid, p_para uuid, p_monto numeric, p_fecha date,
    p_nota text DEFAULT NULL, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid    uuid := auth.uid();
    v_prev   public.grupo_pagos;
    v_de     public.grupo_miembros;
    v_para   public.grupo_miembros;
    v_estado text;
    v_pago   public.grupo_pagos;
BEGIN
    PERFORM _exigir_miembro(p_grupo_id);
    SELECT * INTO v_prev FROM grupo_pagos
     WHERE id = p_id OR (p_idem_key IS NOT NULL AND registrado_por = v_uid AND idem_key = p_idem_key)
     LIMIT 1;
    IF FOUND THEN
        IF v_prev.registrado_por = v_uid THEN
            RETURN to_jsonb(v_prev) || jsonb_build_object('repetido', true);
        END IF;
        RAISE EXCEPTION 'El pago % ya existe', p_id USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v_de   FROM grupo_miembros WHERE id = p_de   AND grupo_id = p_grupo_id AND salio_at IS NULL;
    SELECT * INTO v_para FROM grupo_miembros WHERE id = p_para AND grupo_id = p_grupo_id AND salio_at IS NULL;
    IF v_de.id IS NULL OR v_para.id IS NULL OR p_de = p_para THEN
        RAISE EXCEPTION 'El pago tiene que ser entre dos miembros distintos del grupo' USING ERRCODE = '22023';
    END IF;
    IF round(p_monto, 2) IS NULL OR round(p_monto, 2) <= 0 OR p_fecha IS NULL OR length(p_nota) > 500 THEN
        RAISE EXCEPTION 'Pago inválido: monto mayor que cero, fecha y nota de hasta 500 caracteres'
            USING ERRCODE = '22023';
    END IF;
    v_estado := CASE
        WHEN v_para.usuario_id = v_uid THEN 'confirmado'
        WHEN v_de.usuario_id = v_uid THEN CASE WHEN v_para.usuario_id IS NULL THEN 'confirmado' ELSE 'por_confirmar' END
        WHEN v_de.usuario_id IS NULL AND v_para.usuario_id IS NULL THEN 'confirmado'
    END;
    IF v_estado IS NULL THEN
        RAISE EXCEPTION 'Un pago lo anota quien lo entrega o quien lo recibe' USING ERRCODE = '42501';
    END IF;

    PERFORM _candado_grupo(p_grupo_id);
    INSERT INTO grupo_pagos (id, grupo_id, de_miembro, para_miembro, monto, fecha, nota,
                             registrado_por, estado, idem_key)
    VALUES (p_id, p_grupo_id, p_de, p_para, round(p_monto, 2), p_fecha, NULLIF(btrim(p_nota), ''),
            v_uid, v_estado, p_idem_key)
    RETURNING * INTO v_pago;
    IF v_estado = 'por_confirmar' THEN
        PERFORM _avisar_pago(v_pago, v_para.usuario_id, 'pago_grupo_por_confirmar');
    ELSE
        PERFORM _avisar_pago(v_pago, CASE WHEN v_para.usuario_id = v_uid THEN v_de.usuario_id
                                          ELSE v_para.usuario_id END, 'pago_grupo_nuevo');
    END IF;
    RETURN to_jsonb(v_pago) || jsonb_build_object('repetido', false);
END $$;

-- Quien recibe confirma un pago por confirmar: desde ahí cuenta. Repetirlo no hace nada.
CREATE FUNCTION public.confirmar_pago_grupo(p_pago_id uuid, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_pago public.grupo_pagos;
BEGIN
    SELECT * INTO v_pago FROM grupo_pagos WHERE id = p_pago_id;
    IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM grupo_miembros WHERE id = v_pago.para_miembro
                                   AND usuario_id = auth.uid() AND salio_at IS NULL) THEN
        RAISE EXCEPTION 'El pago % no existe o no lo recibiste tú', p_pago_id USING ERRCODE = '42501';
    END IF;
    PERFORM _candado_grupo(v_pago.grupo_id);
    SELECT * INTO v_pago FROM grupo_pagos WHERE id = p_pago_id FOR UPDATE;
    IF v_pago.estado = 'confirmado' THEN
        RETURN to_jsonb(v_pago) || jsonb_build_object('repetido', true);
    END IF;
    IF v_pago.estado <> 'por_confirmar' THEN
        RAISE EXCEPTION 'El pago ya está %', v_pago.estado USING ERRCODE = '22023';
    END IF;
    UPDATE grupo_pagos SET estado = 'confirmado' WHERE id = p_pago_id RETURNING * INTO v_pago;
    UPDATE avisos SET visto_at = now()
     WHERE usuario_id = auth.uid() AND tipo = 'pago_grupo_por_confirmar'
       AND datos ->> 'pago_id' = p_pago_id::text AND visto_at IS NULL;
    PERFORM _avisar_pago(v_pago, v_pago.registrado_por, 'pago_grupo_confirmado');
    RETURN to_jsonb(v_pago) || jsonb_build_object('repetido', false);
END $$;

-- Quien recibe dice "no lo recibí": queda rechazado (no cuenta) y a quien lo anotó le
-- llega el motivo.
CREATE FUNCTION public.rechazar_pago_grupo(p_pago_id uuid, p_motivo text DEFAULT NULL,
                                           p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_pago public.grupo_pagos;
BEGIN
    SELECT * INTO v_pago FROM grupo_pagos WHERE id = p_pago_id;
    IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM grupo_miembros WHERE id = v_pago.para_miembro
                                   AND usuario_id = auth.uid() AND salio_at IS NULL) THEN
        RAISE EXCEPTION 'El pago % no existe o no lo recibiste tú', p_pago_id USING ERRCODE = '42501';
    END IF;
    IF length(p_motivo) > 500 THEN
        RAISE EXCEPTION 'El motivo no puede pasar de 500 caracteres' USING ERRCODE = '22023';
    END IF;
    PERFORM _candado_grupo(v_pago.grupo_id);
    SELECT * INTO v_pago FROM grupo_pagos WHERE id = p_pago_id FOR UPDATE;
    IF v_pago.estado = 'rechazado' THEN
        RETURN to_jsonb(v_pago) || jsonb_build_object('repetido', true);
    END IF;
    IF v_pago.estado <> 'por_confirmar' THEN
        RAISE EXCEPTION 'El pago ya está confirmado: si fue un error, que lo borre quien lo anotó'
            USING ERRCODE = '22023';
    END IF;
    UPDATE grupo_pagos SET estado = 'rechazado', motivo = NULLIF(btrim(p_motivo), '')
     WHERE id = p_pago_id RETURNING * INTO v_pago;
    UPDATE avisos SET visto_at = now()
     WHERE usuario_id = auth.uid() AND tipo = 'pago_grupo_por_confirmar'
       AND datos ->> 'pago_id' = p_pago_id::text AND visto_at IS NULL;
    PERFORM _avisar_pago(v_pago, v_pago.registrado_por, 'pago_grupo_rechazado');
    RETURN to_jsonb(v_pago) || jsonb_build_object('repetido', false);
END $$;

-- Quien anotó un pago lo borra (un error de tipeo). Borrar lo que recibí solo me perjudica
-- a mí, y lo que entregué y el otro confirmó también: nadie se aprovecha. Avisa a la otra
-- punta. Repetirlo no hace nada.
CREATE FUNCTION public.borrar_pago_grupo(p_pago_id uuid, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_pago public.grupo_pagos;
    v_otro uuid;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v_pago FROM grupo_pagos WHERE id = p_pago_id;
    IF NOT FOUND THEN
        IF EXISTS (SELECT 1 FROM borrados_gastos b WHERE b.tabla = 'grupo_pagos' AND b.id = p_pago_id
                      AND _soy_miembro(b.grupo_id)) THEN
            RETURN jsonb_build_object('resultado', 'borrado', 'pago_id', p_pago_id, 'repetido', true);
        END IF;
        RAISE EXCEPTION 'El pago % no existe o no lo anotaste tú', p_pago_id USING ERRCODE = '42501';
    END IF;
    IF v_pago.registrado_por <> auth.uid() OR _mi_miembro(v_pago.grupo_id) IS NULL THEN
        RAISE EXCEPTION 'El pago % no existe o no lo anotaste tú', p_pago_id USING ERRCODE = '42501';
    END IF;
    PERFORM _candado_grupo(v_pago.grupo_id);
    SELECT usuario_id INTO v_otro FROM grupo_miembros
     WHERE id IN (v_pago.de_miembro, v_pago.para_miembro) AND usuario_id IS DISTINCT FROM auth.uid()
     LIMIT 1;
    DELETE FROM avisos WHERE tipo = 'pago_grupo_por_confirmar' AND datos ->> 'pago_id' = p_pago_id::text
                         AND visto_at IS NULL;
    IF v_pago.estado <> 'rechazado' THEN
        PERFORM _avisar_pago(v_pago, v_otro, 'pago_grupo_borrado');
    END IF;
    DELETE FROM grupo_pagos WHERE id = p_pago_id;
    RETURN jsonb_build_object('resultado', 'borrado', 'pago_id', p_pago_id, 'repetido', false);
END $$;

-- ====================================================================================
-- RPC: lectura
-- ====================================================================================

-- Los saldos del grupo, como los muestra la app: cada miembro con su neto (+ le deben),
-- los pares con saldo (quién le debe a quién), mi neto y los pagos que espero confirmar.
-- SECURITY INVOKER: el RLS limita a los grupos de los que soy miembro.
CREATE FUNCTION public.estado_grupo(p_grupo_id uuid) RETURNS jsonb
    LANGUAGE plpgsql STABLE SET search_path = public AS $$
DECLARE
    v_yo    uuid := _exigir_miembro(p_grupo_id);
    v_pares jsonb;
BEGIN
    SELECT COALESCE(jsonb_agg(jsonb_build_object('debe', debe, 'a', a, 'monto', monto) ORDER BY debe, a), '[]')
      INTO v_pares FROM _pares_grupo(p_grupo_id);
    RETURN jsonb_build_object(
        'grupo',    (SELECT to_jsonb(g) FROM grupos g WHERE id = p_grupo_id),
        'yo',       v_yo,
        'miembros', (SELECT jsonb_agg(jsonb_build_object(
                         'id', m.id, 'nombre', m.nombre, 'usuario_id', m.usuario_id,
                         'con_app', m.usuario_id IS NOT NULL, 'soy_yo', m.id = v_yo,
                         'salio', m.salio_at IS NOT NULL,
                         'neto', COALESCE((SELECT sum(CASE WHEN (p ->> 'a')::uuid = m.id THEN (p ->> 'monto')::numeric
                                                           ELSE -(p ->> 'monto')::numeric END)
                                             FROM jsonb_array_elements(v_pares) p
                                            WHERE m.id::text IN (p ->> 'debe', p ->> 'a')), 0))
                         ORDER BY m.created_at, m.id)
                       FROM grupo_miembros m WHERE m.grupo_id = p_grupo_id),
        'pares',    v_pares,
        'mi_neto',  _neto_miembro(p_grupo_id, v_yo),
        'por_confirmar', (SELECT COALESCE(jsonb_agg(to_jsonb(p) ORDER BY p.fecha, p.created_at, p.id), '[]')
                            FROM grupo_pagos p
                           WHERE p.grupo_id = p_grupo_id AND p.estado = 'por_confirmar'
                             AND p.para_miembro = v_yo));
END $$;

-- Los grupos en los que entré (o volví) después de `p_desde`: el pull tiene que bajar todo
-- lo suyo, aunque sea más viejo que el cursor.
CREATE FUNCTION public._grupos_nuevos(p_desde timestamptz) RETURNS uuid[]
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT COALESCE(array_agg(grupo_id), '{}') FROM grupo_miembros
     WHERE usuario_id = auth.uid() AND salio_at IS NULL
       AND (p_desde IS NULL OR updated_at > p_desde)
$$;

-- ====================================================================================
-- Funciones existentes (copia exacta + «v2 fase 9B»)
-- ====================================================================================

CREATE OR REPLACE FUNCTION public.cambios_gastos(p_desde timestamptz DEFAULT NULL) RETURNS jsonb
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT jsonb_build_object(
        'gastos', (SELECT COALESCE(jsonb_agg(_gasto_json(g.id) ORDER BY g.updated_at, g.id), '[]')
                     FROM gastos g
                    WHERE p_desde IS NULL OR g.updated_at > p_desde
                       OR g.grupo_id = ANY (_grupos_nuevos(p_desde))),                         -- v2 fase 9B
        -- Todos mis grupos, siempre (son pocos): el que falta es uno del que salí.           -- v2 fase 9B
        'grupos',   (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') -- v2 fase 9B
                       FROM grupos x),                                                       -- v2 fase 9B
        -- Los miembros de un grupo bajan todos juntos cuando cambia alguno (_tocar_grupo).   -- v2 fase 9B
        'miembros', (SELECT COALESCE(jsonb_agg(to_jsonb(m) ORDER BY m.grupo_id, m.created_at, m.id), '[]') -- v2 fase 9B
                       FROM grupo_miembros m JOIN grupos x ON x.id = m.grupo_id               -- v2 fase 9B
                      WHERE p_desde IS NULL OR x.updated_at > p_desde                        -- v2 fase 9B
                         OR x.id = ANY (_grupos_nuevos(p_desde))),                           -- v2 fase 9B
        'pagos',    (SELECT COALESCE(jsonb_agg(to_jsonb(p) ORDER BY p.updated_at, p.id), '[]') -- v2 fase 9B
                       FROM grupo_pagos p                                                    -- v2 fase 9B
                      WHERE p_desde IS NULL OR p.updated_at > p_desde                        -- v2 fase 9B
                         OR p.grupo_id = ANY (_grupos_nuevos(p_desde))),                     -- v2 fase 9B
        'borrados', (SELECT COALESCE(jsonb_agg(jsonb_build_object('tabla', b.tabla, 'id', b.id, 'at', b.at)
                                               ORDER BY b.at, b.id), '[]')
                       FROM borrados_gastos b
                      WHERE p_desde IS NULL OR b.at > p_desde))
$$;

CREATE OR REPLACE FUNCTION public.exportar_mis_datos() RETURNS jsonb
    LANGUAGE plpgsql STABLE SET search_path = public AS $$
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    RETURN jsonb_build_object(
        'formato',         'deudas-v2/exportacion-1',
        'exportado_at',    now(),
        'usuario',         auth.uid(),
        'perfil',          (SELECT to_jsonb(p) FROM perfiles p WHERE id = auth.uid()),
        'deudores',        (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM deudores x),
        'deudas',          (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.fecha_gasto, x.created_at, x.id), '[]') FROM deudas x),
        'pagos',           (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.fecha_pago, x.created_at, x.id), '[]') FROM pagos x),
        'detalle_pagos',   (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM detalle_pagos x),
        'cruces_editados', (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM cruces_editados x),
        'pagos_editados',  (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM pagos_editados x),
        'invitaciones',    (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.codigo), '[]') FROM invitaciones x),
        'vinculos',        (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM vinculos x),
        'propuestas',      (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM propuestas x),
        'acuerdos',        (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM acuerdos x),  -- v2 fase 8
        'avisos',          (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM avisos x),     -- v2 fase 9
        'gastos',          (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.fecha, x.created_at, x.id), '[]') FROM gastos x),            -- v2 fase 9
        'gasto_participantes', (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.gasto_id, x.orden), '[]') FROM gasto_participantes x), -- v2 fase 9B
        'grupos',          (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM grupos x),                 -- v2 fase 9B
        'grupo_miembros',  (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.grupo_id, x.created_at, x.id), '[]') FROM grupo_miembros x), -- v2 fase 9B
        'grupo_pagos',     (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.fecha, x.created_at, x.id), '[]') FROM grupo_pagos x),   -- v2 fase 9B
        'grupo_invitaciones', (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.codigo), '[]') FROM grupo_invitaciones x)); -- v2 fase 9B
END $$;

-- ====================================================================================
-- Permisos
-- ====================================================================================

REVOKE ALL ON FUNCTION public._soy_miembro(uuid)                         FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._mi_miembro(uuid)                          FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._exigir_miembro(uuid)                      FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._tocar_grupo(uuid)                         FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._candado_grupo(uuid)                       FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._filas_gasto(uuid)                         FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._gasto_sin_nadie(uuid)                     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._avisar_gasto(uuid, text, jsonb, jsonb)    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._avisar_pago(public.grupo_pagos, uuid, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._pares_grupo(uuid)                         FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._neto_miembro(uuid, uuid)                  FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._validar_miembros(uuid, jsonb, uuid)       FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._revision_vista()                          FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._grupos_nuevos(timestamptz)                FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.crear_grupo(uuid, text, text, uuid, text, uuid)  FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.agregar_persona(uuid, text, uuid, uuid)    FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.invitar_a_grupo(uuid)                      FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.unirse_a_grupo(text, uuid)                 FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.salir_de_grupo(uuid, uuid)                 FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.archivar_grupo(uuid, boolean, uuid)        FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.rechazar_parte(uuid, text, uuid)           FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.registrar_pago_grupo(uuid, uuid, uuid, uuid, numeric, date, text, uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.confirmar_pago_grupo(uuid, uuid)           FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.rechazar_pago_grupo(uuid, text, uuid)      FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.borrar_pago_grupo(uuid, uuid)              FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.estado_grupo(uuid)                         FROM PUBLIC, anon;
-- Las policies, estado_grupo y cambios_gastos (SECURITY INVOKER) las usan con los permisos
-- de quien llama.
GRANT EXECUTE ON FUNCTION public._soy_miembro(uuid)             TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._mi_miembro(uuid)              TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._exigir_miembro(uuid)          TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._pares_grupo(uuid)             TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._neto_miembro(uuid, uuid)      TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._grupos_nuevos(timestamptz)    TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.crear_grupo(uuid, text, text, uuid, text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.agregar_persona(uuid, text, uuid, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.invitar_a_grupo(uuid)          TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.unirse_a_grupo(text, uuid)     TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.salir_de_grupo(uuid, uuid)     TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.archivar_grupo(uuid, boolean, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rechazar_parte(uuid, text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.registrar_pago_grupo(uuid, uuid, uuid, uuid, numeric, date, text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.confirmar_pago_grupo(uuid, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rechazar_pago_grupo(uuid, text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.borrar_pago_grupo(uuid, uuid)  TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.estado_grupo(uuid)             TO authenticated, service_role;
