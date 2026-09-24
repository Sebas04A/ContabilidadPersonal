-- Fase 4 (deudas/PLAN_MULTIUSUARIO.md §4.4 y §5.2): invitaciones y vínculos.
--
-- Una Persona de mi libreta (un deudor) pasa a estar vinculada con su Usuario real:
--   * `crear_invitacion(deudor)` da un código de un solo uso que se comparte por WhatsApp;
--   * el otro lo canjea con `reclamar_invitacion(código, deudor_existente?)`, que crea el
--     vínculo en estado 'conciliando' (las fases 5 y 6 le dan uso);
--   * cualquiera de los dos lo rompe con `desvincular`.
--
-- Reglas: nadie se vincula consigo mismo; un deudor tiene como máximo un vínculo no roto;
-- un par de usuarios, también. Las garantizan los índices únicos parciales, así que dos
-- canjes simultáneos no pueden colarse entre las validaciones.

-- ====================================================================================
-- Tablas
-- ====================================================================================

CREATE TABLE public.invitaciones (
    codigo     text PRIMARY KEY,
    deudor_id  uuid NOT NULL,
    owner_id   uuid NOT NULL DEFAULT auth.uid(),
    expira     timestamptz NOT NULL DEFAULT now() + interval '7 days',
    usada_por  uuid REFERENCES public.perfiles ON DELETE SET NULL,
    usada_at   timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (deudor_id, owner_id) REFERENCES public.deudores (id, owner_id) ON DELETE CASCADE
);
CREATE INDEX idx_invitaciones_deudor ON public.invitaciones (deudor_id);
COMMENT ON TABLE public.invitaciones IS 'Códigos de un solo uso para vincular un deudor con su usuario real. Solo por RPC.';

CREATE TABLE public.vinculos (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_a    uuid NOT NULL REFERENCES public.perfiles ON DELETE CASCADE,  -- quien invitó
    deudor_a     uuid NOT NULL,
    usuario_b    uuid NOT NULL REFERENCES public.perfiles ON DELETE CASCADE,  -- quien aceptó
    deudor_b     uuid NOT NULL,
    estado       text NOT NULL DEFAULT 'conciliando'
                 CHECK (estado IN ('conciliando', 'activo', 'roto')),
    conciliado_a boolean NOT NULL DEFAULT false,
    conciliado_b boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now(),
    roto_at      timestamptz,
    CHECK (usuario_a <> usuario_b),
    CHECK ((estado = 'roto') = (roto_at IS NOT NULL)),
    -- CASCADE: borrar el deudor (o la cuenta) se lleva el vínculo. Sin él, la app no
    -- podría borrar un contacto vinculado (el FK lo impediría).
    FOREIGN KEY (deudor_a, usuario_a) REFERENCES public.deudores (id, owner_id) ON DELETE CASCADE,
    FOREIGN KEY (deudor_b, usuario_b) REFERENCES public.deudores (id, owner_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX idx_vinculos_deudor_a ON public.vinculos (deudor_a) WHERE estado <> 'roto';
CREATE UNIQUE INDEX idx_vinculos_deudor_b ON public.vinculos (deudor_b) WHERE estado <> 'roto';
CREATE UNIQUE INDEX idx_vinculos_par ON public.vinculos
    (LEAST(usuario_a, usuario_b), GREATEST(usuario_a, usuario_b)) WHERE estado <> 'roto';
CREATE INDEX idx_vinculos_usuario_b ON public.vinculos (usuario_b);
COMMENT ON TABLE public.vinculos IS 'Par deudor↔deudor entre dos libretas. Solo se escribe por RPC.';

-- ====================================================================================
-- RLS: invitaciones las ve solo su dueño; vínculos, sus dos usuarios. Nadie escribe
-- directo: todo pasa por los RPC de abajo.
-- ====================================================================================

ALTER TABLE public.invitaciones ENABLE ROW LEVEL SECURITY;
CREATE POLICY propio_leer ON public.invitaciones FOR SELECT TO authenticated
    USING (owner_id = auth.uid());
REVOKE ALL ON public.invitaciones FROM anon, authenticated;
GRANT SELECT ON public.invitaciones TO authenticated;

ALTER TABLE public.vinculos ENABLE ROW LEVEL SECURITY;
CREATE POLICY partes_leer ON public.vinculos FOR SELECT TO authenticated
    USING (auth.uid() IN (usuario_a, usuario_b));
REVOKE ALL ON public.vinculos FROM anon, authenticated;
GRANT SELECT ON public.vinculos TO authenticated;

-- ====================================================================================
-- Funciones
-- ====================================================================================

-- El vínculo vivo (conciliando o activo) de un deudor, visto por una de sus dos partes.
-- SECURITY DEFINER para que las fases 5 y 6 lo usen desde RPC sin depender del RLS del
-- que llama; por eso mismo filtra por auth.uid().
CREATE FUNCTION public._vinculo_de(p_deudor_id uuid) RETURNS public.vinculos
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT *
      FROM public.vinculos
     WHERE estado <> 'roto'
       AND (deudor_a = p_deudor_id OR deudor_b = p_deudor_id)
       AND auth.uid() IN (usuario_a, usuario_b)
     LIMIT 1
$$;

-- Código de 10 caracteres en base32 sin 0/O/1/I (se dicta y se copia sin confusiones).
-- 32 símbolos: byte % 32 no tiene sesgo. 50 bits aleatorios, de un solo uso y con 7 días
-- de vida: no se puede adivinar uno ajeno.
CREATE FUNCTION public._codigo_invitacion() RETURNS text
    LANGUAGE plpgsql VOLATILE SET search_path = public AS $$
DECLARE
    v_alfabeto constant text := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    v_bytes    bytea := extensions.gen_random_bytes(10);
    v_codigo   text := '';
BEGIN
    FOR i IN 0..9 LOOP
        v_codigo := v_codigo || substr(v_alfabeto, (get_byte(v_bytes, i) % 32) + 1, 1);
    END LOOP;
    RETURN v_codigo;
END $$;

-- SECURITY DEFINER: las invitaciones no se escriben directo (así nadie se fabrica un
-- código a medida ni estira su vencimiento). Valida el dueño antes de tocar nada.
CREATE FUNCTION public.crear_invitacion(p_deudor_id uuid) RETURNS text
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid    uuid := auth.uid();
    v_codigo text;
BEGIN
    IF v_uid IS NULL OR NOT EXISTS (SELECT 1 FROM public.deudores
                                     WHERE id = p_deudor_id AND owner_id = v_uid) THEN
        RAISE EXCEPTION 'El deudor % no existe o no es tuyo', p_deudor_id
            USING ERRCODE = '42501';
    END IF;
    -- `.id` y no la fila: `fila IS NOT NULL` exige que TODOS sus campos lo sean.
    IF (public._vinculo_de(p_deudor_id)).id IS NOT NULL THEN
        RAISE EXCEPTION 'Este contacto ya está vinculado' USING ERRCODE = '23505';
    END IF;

    -- Una sola invitación viva por deudor: la anterior sin usar deja de servir.
    UPDATE public.invitaciones
       SET expira = now()
     WHERE deudor_id = p_deudor_id AND usada_por IS NULL AND expira > now();

    LOOP
        v_codigo := public._codigo_invitacion();
        BEGIN
            INSERT INTO public.invitaciones (codigo, deudor_id, owner_id)
            VALUES (v_codigo, p_deudor_id, v_uid);
            RETURN v_codigo;
        EXCEPTION WHEN unique_violation THEN
            -- Choque de códigos (1 en 2^50): otro intento.
        END;
    END LOOP;
END $$;

-- SECURITY DEFINER: lee una invitación ajena. Todo en una transacción; un código que no
-- sirve (no existe, vencido, usado o propio) da siempre el mismo error, para que no se
-- pueda sondear qué códigos existen.
CREATE FUNCTION public.reclamar_invitacion(p_codigo text, p_deudor_existente uuid DEFAULT NULL)
    RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid     uuid := auth.uid();
    v_inv     public.invitaciones;
    v_deudor  uuid;
    v_vinculo uuid;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;

    SELECT * INTO v_inv
      FROM public.invitaciones
     WHERE codigo = upper(btrim(p_codigo))
       FOR UPDATE;
    IF NOT FOUND OR v_inv.expira <= now() OR v_inv.usada_por IS NOT NULL
       OR v_inv.owner_id = v_uid THEN
        RAISE EXCEPTION 'Código de invitación inválido o vencido' USING ERRCODE = '22023';
    END IF;

    IF EXISTS (SELECT 1 FROM public.vinculos
                WHERE estado <> 'roto'
                  AND LEAST(usuario_a, usuario_b) = LEAST(v_uid, v_inv.owner_id)
                  AND GREATEST(usuario_a, usuario_b) = GREATEST(v_uid, v_inv.owner_id)) THEN
        RAISE EXCEPTION 'Ya estás vinculado con esta persona' USING ERRCODE = '23505';
    END IF;
    IF EXISTS (SELECT 1 FROM public.vinculos
                WHERE estado <> 'roto' AND v_inv.deudor_id IN (deudor_a, deudor_b)) THEN
        RAISE EXCEPTION 'Código de invitación inválido o vencido' USING ERRCODE = '22023';
    END IF;

    IF p_deudor_existente IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM public.deudores
                        WHERE id = p_deudor_existente AND owner_id = v_uid) THEN
            RAISE EXCEPTION 'El deudor % no existe o no es tuyo', p_deudor_existente
                USING ERRCODE = '42501';
        END IF;
        IF EXISTS (SELECT 1 FROM public.vinculos
                    WHERE estado <> 'roto' AND p_deudor_existente IN (deudor_a, deudor_b)) THEN
            RAISE EXCEPTION 'Ese contacto ya está vinculado con otra persona'
                USING ERRCODE = '23505';
        END IF;
        v_deudor := p_deudor_existente;
    ELSE
        -- Contacto nuevo en la libreta de quien acepta, con el nombre de quien invitó.
        INSERT INTO public.deudores (nombre, owner_id)
        SELECT nombre, v_uid FROM public.perfiles WHERE id = v_inv.owner_id
        RETURNING id INTO v_deudor;
    END IF;

    UPDATE public.invitaciones
       SET usada_por = v_uid, usada_at = now()
     WHERE codigo = v_inv.codigo;

    INSERT INTO public.vinculos (usuario_a, deudor_a, usuario_b, deudor_b)
    VALUES (v_inv.owner_id, v_inv.deudor_id, v_uid, v_deudor)
    RETURNING id INTO v_vinculo;
    RETURN v_vinculo;
END $$;

-- SECURITY DEFINER: `vinculos` no se escribe directo. Cualquiera de las dos partes lo
-- rompe; cada uno conserva su libreta intacta (§4.4, paso 6).
CREATE FUNCTION public.desvincular(p_vinculo_id uuid) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    UPDATE public.vinculos
       SET estado = 'roto', roto_at = now()
     WHERE id = p_vinculo_id
       AND estado <> 'roto'
       AND auth.uid() IN (usuario_a, usuario_b);
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El vínculo % no existe o no es tuyo', p_vinculo_id
            USING ERRCODE = '42501';
    END IF;
END $$;

-- ====================================================================================
-- Permisos de ejecución
-- ====================================================================================

REVOKE ALL ON FUNCTION public._vinculo_de(uuid)                FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._codigo_invitacion()             FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.crear_invitacion(uuid)           FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.reclamar_invitacion(text, uuid)  FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.desvincular(uuid)                FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public._vinculo_de(uuid)               TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.crear_invitacion(uuid)          TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.reclamar_invitacion(text, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.desvincular(uuid)               TO authenticated, service_role;
