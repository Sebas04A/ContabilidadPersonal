-- Fase 7 (deudas/PLAN_MULTIUSUARIO.md §8, fase 7): lo que hace falta para abrir la app
-- a cualquiera, en la parte que vive en la base.
--
--   * 7.2 "Exportar mis datos": `exportar_mis_datos()`, toda mi libreta en un JSON.
--   * 7.2 "Borrar mi cuenta": `preparar_baja()` rompe mis vínculos (lo pendiente vuelve a
--     su dueño, como en desvincular) y la edge `borrar_cuenta` borra el usuario de Auth con
--     la service_role; la cascada se lleva la libreta. Una cuenta que se borra ya no deja
--     lápidas en `borrados` (y se limpian las que tenía): nadie va a sincronizarlas.
--   * 7.3 Límites de uso: 20 invitaciones por día, 10 códigos inválidos por hora y
--     60 consultas por minuto al visor por IP.
--
-- `reclamar_invitacion` con un código que no sirve ahora DEVUELVE NULL en vez de lanzar
-- 22023: un error desharía el registro del intento fallido, y sin ese registro no hay
-- límite. La respuesta sigue siendo la misma para cualquier motivo (no existe, vencido,
-- usado, propio), así que tampoco se puede sondear qué códigos existen.
--
-- `_lapida`, `crear_invitacion` y `reclamar_invitacion` son copia exacta de su migración
-- anterior (20260923190000, 20260924100000 y 20260924130000) más las líneas marcadas
-- «v2 fase 7». Compruébalo con un diff.

-- ====================================================================================
-- Borrar mi cuenta (7.2)
-- ====================================================================================

CREATE OR REPLACE FUNCTION public._lapida() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    -- Se está borrando la cuenta (el perfil ya no está): no queda nadie que sincronice. -- v2 fase 7
    IF NOT EXISTS (SELECT 1 FROM public.perfiles WHERE id = OLD.owner_id) THEN        -- v2 fase 7
        RETURN OLD;                                                                   -- v2 fase 7
    END IF;                                                                           -- v2 fase 7
    INSERT INTO public.borrados (tabla, id, owner_id)
    VALUES (TG_TABLE_NAME, OLD.id, OLD.owner_id)
    ON CONFLICT (tabla, id) DO UPDATE SET at = now();
    RETURN OLD;
END $$;


-- Las lápidas que ya tenía la cuenta, al borrarse su perfil (en la cascada de auth.users).
-- SECURITY DEFINER: `borrados` no se escribe directo.
CREATE FUNCTION public._perfil_sin_lapidas() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM public.borrados WHERE owner_id = OLD.id;
    RETURN NULL;
END $$;

CREATE TRIGGER perfil_sin_lapidas AFTER DELETE ON public.perfiles
    FOR EACH ROW EXECUTE FUNCTION public._perfil_sin_lapidas();

-- Las que dejaron las cuentas de prueba borradas antes de esta migración.
DELETE FROM public.borrados b
 WHERE NOT EXISTS (SELECT 1 FROM public.perfiles p WHERE p.id = b.owner_id);

-- Paso previo a borrar la cuenta: romper cada vínculo vivo con `desvincular`, que devuelve
-- lo pendiente a su dueño y deja lo acordado como está (decisión 11 de §3.3). Si no, la
-- cascada borraría el vínculo y sus propuestas de golpe, y las filas del otro que me
-- esperaban quedarían `propuesta` para siempre. Lo llama la edge `borrar_cuenta` con la
-- sesión del usuario; se puede repetir sin daño.
CREATE FUNCTION public.preparar_baja() RETURNS int
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_id uuid;
    v_n  int := 0;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    FOR v_id IN SELECT id FROM vinculos
                 WHERE estado <> 'roto' AND auth.uid() IN (usuario_a, usuario_b)
                 ORDER BY id LOOP
        PERFORM desvincular(v_id);
        v_n := v_n + 1;
    END LOOP;
    RETURN v_n;
END $$;

-- ====================================================================================
-- Exportar mis datos (7.2)
-- ====================================================================================

-- Toda mi libreta, tal cual está en el servidor. SECURITY INVOKER: el RLS ya limita cada
-- tabla a lo mío (y `vinculos`, `propuestas` y `acuerdos` a aquello en que soy parte).
-- Cada lista va en orden fijo, así dos exportaciones iguales dan el mismo archivo.
CREATE FUNCTION public.exportar_mis_datos() RETURNS jsonb
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
        'acuerdos',        (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM acuerdos x));
END $$;

-- ====================================================================================
-- Límites de uso (7.3)
-- ====================================================================================

-- Códigos de invitación que no sirvieron, para frenar a quien los prueba al azar. Solo los
-- escribe `reclamar_invitacion` (SECURITY DEFINER); nadie los lee desde fuera.
CREATE TABLE public.intentos_canje (
    usuario uuid        NOT NULL REFERENCES public.perfiles ON DELETE CASCADE,
    at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_intentos_canje ON public.intentos_canje (usuario, at);
ALTER TABLE public.intentos_canje ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.intentos_canje FROM anon, authenticated;

-- Anota el intento fallido y devuelve NULL, la respuesta de un código que no sirve. De paso
-- borra los intentos viejos de ese usuario, que ya no cuentan para nada.
CREATE FUNCTION public._canje_fallido(p_usuario uuid) RETURNS uuid
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    DELETE FROM intentos_canje WHERE usuario = p_usuario AND at < now() - interval '1 day';
    INSERT INTO intentos_canje (usuario) VALUES (p_usuario);
    RETURN NULL;
END $$;

-- Consultas al visor por IP y minuto. La IP no se guarda: se guarda su SHA-256, que basta
-- para contar, y las filas se borran a la hora. Solo la usa la edge `visor`
-- (service_role).
CREATE TABLE public.visitas_visor (
    ip_hash text        NOT NULL,
    minuto  timestamptz NOT NULL,
    n       int         NOT NULL DEFAULT 1,
    PRIMARY KEY (ip_hash, minuto)
);
ALTER TABLE public.visitas_visor ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.visitas_visor FROM anon, authenticated;

-- Suma una visita y devuelve cuántas lleva esa IP en este minuto. La limpieza va de vez en
-- cuando (1 de cada 50 llamadas) para no escribir de más en cada consulta.
CREATE FUNCTION public.contar_visita_visor(p_ip text) RETURNS int
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, extensions AS $$
DECLARE
    v_n int;
BEGIN
    INSERT INTO public.visitas_visor (ip_hash, minuto)
    VALUES (encode(extensions.digest(COALESCE(p_ip, ''), 'sha256'), 'hex'), date_trunc('minute', now()))
    ON CONFLICT (ip_hash, minuto) DO UPDATE SET n = public.visitas_visor.n + 1
    RETURNING n INTO v_n;
    IF random() < 0.02 THEN
        DELETE FROM public.visitas_visor WHERE minuto < now() - interval '1 hour';
    END IF;
    RETURN v_n;
END $$;

-- Invitaciones: 20 por día.
CREATE OR REPLACE FUNCTION public.crear_invitacion(p_deudor_id uuid) RETURNS text
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
    -- Límite de uso (7.3). Cuentan también las anuladas: crear otra anula la anterior. -- v2 fase 7
    IF (SELECT count(*) FROM public.invitaciones                                    -- v2 fase 7
         WHERE owner_id = v_uid AND created_at > now() - interval '1 day') >= 20 THEN -- v2 fase 7
        RAISE EXCEPTION 'Llegaste al límite de 20 invitaciones por día. Prueba mañana.' -- v2 fase 7
            USING ERRCODE = 'PT429';                                                -- v2 fase 7
    END IF;                                                                         -- v2 fase 7

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


-- Canje: 10 códigos que no sirven por hora; con uno así devuelve NULL.
CREATE OR REPLACE FUNCTION public.reclamar_invitacion(p_codigo text, p_deudor_existente uuid DEFAULT NULL)
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
    -- Límite de uso (7.3): 10 códigos que no sirven por hora y por usuario.            -- v2 fase 7
    IF (SELECT count(*) FROM public.intentos_canje                                  -- v2 fase 7
         WHERE usuario = v_uid AND at > now() - interval '1 hour') >= 10 THEN       -- v2 fase 7
        RAISE EXCEPTION 'Demasiados códigos que no sirven. Espera una hora y vuelve a intentarlo.' -- v2 fase 7
            USING ERRCODE = 'PT429';                                                -- v2 fase 7
    END IF;                                                                         -- v2 fase 7

    SELECT * INTO v_inv
      FROM public.invitaciones
     WHERE codigo = upper(btrim(p_codigo))
       FOR UPDATE;
    IF NOT FOUND OR v_inv.expira <= now() OR v_inv.usada_por IS NOT NULL
       OR v_inv.owner_id = v_uid THEN
        RETURN public._canje_fallido(v_uid);                                        -- v2 fase 7
    END IF;

    IF EXISTS (SELECT 1 FROM public.vinculos
                WHERE estado <> 'roto'
                  AND LEAST(usuario_a, usuario_b) = LEAST(v_uid, v_inv.owner_id)
                  AND GREATEST(usuario_a, usuario_b) = GREATEST(v_uid, v_inv.owner_id)) THEN
        RAISE EXCEPTION 'Ya estás vinculado con esta persona' USING ERRCODE = '23505';
    END IF;
    IF EXISTS (SELECT 1 FROM public.vinculos
                WHERE estado <> 'roto' AND v_inv.deudor_id IN (deudor_a, deudor_b)) THEN
        RETURN public._canje_fallido(v_uid);                                        -- v2 fase 7
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
    -- v2 tardías: lo acordado en un vínculo roto vuelve a conciliarse en este.
    PERFORM set_config('deudas.en_rpc', 'on', true);                             -- v2 tardías
    PERFORM public._soltar_acuerdos_viejos(v_inv.deudor_id);                     -- v2 tardías
    PERFORM public._soltar_acuerdos_viejos(v_deudor);                            -- v2 tardías
    PERFORM set_config('deudas.en_rpc', 'off', true);                            -- v2 tardías
    RETURN v_vinculo;
END $$;


-- ====================================================================================
-- Permisos
-- ====================================================================================

REVOKE ALL ON FUNCTION public._perfil_sin_lapidas()     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._canje_fallido(uuid)      FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.preparar_baja()           FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.exportar_mis_datos()      FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.contar_visita_visor(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.preparar_baja()           TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.exportar_mis_datos()      TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.contar_visita_visor(text) TO service_role;
