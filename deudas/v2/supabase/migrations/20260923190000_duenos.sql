-- Deudas v2 — fase 1: cada fila tiene dueño y el RLS lo hace cumplir.
--
-- Ver deudas/PLAN_MULTIUSUARIO.md §5.1 y fase 1. Resumen:
--   * `perfiles` (uno por usuario de Auth, creado por trigger al registrarse);
--   * `owner_id` en todas las tablas, con DEFAULT auth.uid() para que los clientes no
--     tengan que mandarlo, y FK COMPUESTAS (x_id, owner_id): nadie puede colgar filas
--     propias de un deudor, pago o deuda ajenos aunque conozca su UUID;
--   * `updated_at` + lápidas en `borrados`, para el pull incremental de Flutter;
--   * RLS "solo lo propio" en todo, y la vista con security_invoker;
--   * `idem_key` único POR DUEÑO (antes global);
--   * chequeo explícito de dueño en los RPC que reciben un deudor_id del cliente.
--
-- Se aplica sobre tablas VACÍAS (db reset + importar.py --owner): por eso las columnas
-- nacen NOT NULL sin backfill.
--
-- La matemática NO cambia: aplicar_cruce y registrar_pago de abajo son copia exacta de
-- 20260923180000_base.sql más las dos líneas marcadas «v2:». Compruébalo con un diff.

-- ====================================================================================
-- Perfiles
-- ====================================================================================

CREATE TABLE public.perfiles (
    id         uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
    nombre     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.perfiles IS 'Un perfil por usuario de Auth. Lo crea el trigger _crear_perfil.';

-- SECURITY DEFINER: corre dentro del alta de Auth, donde el rol no tiene permisos sobre
-- public. El nombre sale de los metadatos del registro o, si no hay, del email.
CREATE FUNCTION public._crear_perfil() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO public.perfiles (id, nombre)
    VALUES (NEW.id, COALESCE(NULLIF(NEW.raw_user_meta_data ->> 'nombre', ''),
                             split_part(COALESCE(NEW.email, 'usuario'), '@', 1)));
    RETURN NEW;
END $$;

CREATE TRIGGER crear_perfil AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public._crear_perfil();

-- ====================================================================================
-- Dueño en cada tabla
-- ====================================================================================

ALTER TABLE public.deudores
    ADD COLUMN owner_id     uuid NOT NULL DEFAULT auth.uid() REFERENCES public.perfiles ON DELETE CASCADE,
    ADD COLUMN token_expira timestamptz,
    ADD COLUMN moneda       text NOT NULL DEFAULT 'USD',
    ADD COLUMN updated_at   timestamptz NOT NULL DEFAULT now(),
    ADD CONSTRAINT deudores_id_owner UNIQUE (id, owner_id);
COMMENT ON COLUMN public.deudores.token_expira IS 'NULL = el enlace del visor no expira (como siempre).';

ALTER TABLE public.deudas
    ADD COLUMN owner_id   uuid NOT NULL DEFAULT auth.uid(),
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
    ADD CONSTRAINT deudas_id_owner UNIQUE (id, owner_id),
    DROP CONSTRAINT deudas_deudor_id_fkey,
    ADD CONSTRAINT deudas_deudor_owner_fkey
        FOREIGN KEY (deudor_id, owner_id) REFERENCES public.deudores (id, owner_id) ON DELETE CASCADE;

ALTER TABLE public.pagos
    ADD COLUMN owner_id   uuid NOT NULL DEFAULT auth.uid(),
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
    ADD CONSTRAINT pagos_id_owner UNIQUE (id, owner_id),
    DROP CONSTRAINT pagos_deudor_id_fkey,
    ADD CONSTRAINT pagos_deudor_owner_fkey
        FOREIGN KEY (deudor_id, owner_id) REFERENCES public.deudores (id, owner_id) ON DELETE CASCADE;

-- Las dos puntas de un detalle tienen que ser del mismo dueño.
ALTER TABLE public.detalle_pagos
    ADD COLUMN owner_id   uuid NOT NULL DEFAULT auth.uid(),
    ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
    DROP CONSTRAINT detalle_pagos_pago_id_fkey,
    DROP CONSTRAINT detalle_pagos_deuda_id_fkey,
    ADD CONSTRAINT detalle_pagos_pago_owner_fkey
        FOREIGN KEY (pago_id, owner_id) REFERENCES public.pagos (id, owner_id) ON DELETE CASCADE,
    ADD CONSTRAINT detalle_pagos_deuda_owner_fkey
        FOREIGN KEY (deuda_id, owner_id) REFERENCES public.deudas (id, owner_id) ON DELETE CASCADE;

ALTER TABLE public.cruces_editados
    ADD COLUMN owner_id uuid NOT NULL DEFAULT auth.uid(),
    DROP CONSTRAINT cruces_editados_deudor_id_fkey,
    ADD CONSTRAINT cruces_editados_deudor_owner_fkey
        FOREIGN KEY (deudor_id, owner_id) REFERENCES public.deudores (id, owner_id) ON DELETE CASCADE;

ALTER TABLE public.pagos_editados
    ADD COLUMN owner_id uuid NOT NULL DEFAULT auth.uid(),
    DROP CONSTRAINT pagos_editados_deudor_id_fkey,
    ADD CONSTRAINT pagos_editados_deudor_owner_fkey
        FOREIGN KEY (deudor_id, owner_id) REFERENCES public.deudores (id, owner_id) ON DELETE CASCADE;

-- Índices para el RLS y el pull incremental.
CREATE INDEX idx_deudores_owner ON public.deudores (owner_id, updated_at);
CREATE INDEX idx_deudas_owner   ON public.deudas (owner_id, updated_at);
CREATE INDEX idx_pagos_owner    ON public.pagos (owner_id, updated_at);
CREATE INDEX idx_detalle_owner  ON public.detalle_pagos (owner_id, updated_at);
CREATE INDEX idx_cruces_editados_owner ON public.cruces_editados (owner_id);
CREATE INDEX idx_pagos_editados_owner  ON public.pagos_editados (owner_id);

-- Idempotencia por dueño: con la clave global, un usuario podía chocar (o sondear) las
-- claves de otro. Las funciones buscan `WHERE idem_key = …` y el RLS ya las limita a lo
-- propio, así que el alcance real siempre fue "por dueño".
DROP INDEX public.idx_pagos_idem_key;
DROP INDEX public.idx_cruces_editados_idem;
DROP INDEX public.idx_pagos_editados_idem;
CREATE UNIQUE INDEX idx_pagos_idem_key       ON public.pagos (owner_id, idem_key)           WHERE idem_key IS NOT NULL;
CREATE UNIQUE INDEX idx_cruces_editados_idem ON public.cruces_editados (owner_id, idem_key) WHERE idem_key IS NOT NULL;
CREATE UNIQUE INDEX idx_pagos_editados_idem  ON public.pagos_editados (owner_id, idem_key)  WHERE idem_key IS NOT NULL;

-- ====================================================================================
-- updated_at y lápidas (pull incremental)
-- ====================================================================================

CREATE FUNCTION public._tocar_updated_at() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.deudores      FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();
CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.deudas        FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();
CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.pagos         FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();
CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.detalle_pagos FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();

-- Un pull por `updated_at` no ve lo que se borró: cada DELETE deja su lápida.
CREATE TABLE public.borrados (
    tabla    text        NOT NULL,
    id       uuid        NOT NULL,
    owner_id uuid        NOT NULL,
    at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tabla, id)
);
CREATE INDEX idx_borrados_owner ON public.borrados (owner_id, at);
COMMENT ON TABLE public.borrados IS 'Lápidas de filas borradas, para que el pull incremental de los clientes se entere.';

-- SECURITY DEFINER: los usuarios solo pueden LEER sus lápidas, nunca escribirlas.
CREATE FUNCTION public._lapida() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    INSERT INTO public.borrados (tabla, id, owner_id)
    VALUES (TG_TABLE_NAME, OLD.id, OLD.owner_id)
    ON CONFLICT (tabla, id) DO UPDATE SET at = now();
    RETURN OLD;
END $$;

CREATE TRIGGER lapida AFTER DELETE ON public.deudores      FOR EACH ROW EXECUTE FUNCTION public._lapida();
CREATE TRIGGER lapida AFTER DELETE ON public.deudas        FOR EACH ROW EXECUTE FUNCTION public._lapida();
CREATE TRIGGER lapida AFTER DELETE ON public.pagos         FOR EACH ROW EXECUTE FUNCTION public._lapida();
CREATE TRIGGER lapida AFTER DELETE ON public.detalle_pagos FOR EACH ROW EXECUTE FUNCTION public._lapida();

-- ====================================================================================
-- RLS: cada uno ve y toca solo lo suyo
-- ====================================================================================

-- (SELECT auth.uid()) y no auth.uid(): Postgres lo evalúa una vez por consulta, no por fila.
CREATE POLICY propio ON public.deudores      FOR ALL TO authenticated
    USING (owner_id = (SELECT auth.uid())) WITH CHECK (owner_id = (SELECT auth.uid()));
CREATE POLICY propio ON public.deudas        FOR ALL TO authenticated
    USING (owner_id = (SELECT auth.uid())) WITH CHECK (owner_id = (SELECT auth.uid()));
CREATE POLICY propio ON public.pagos         FOR ALL TO authenticated
    USING (owner_id = (SELECT auth.uid())) WITH CHECK (owner_id = (SELECT auth.uid()));
CREATE POLICY propio ON public.detalle_pagos FOR ALL TO authenticated
    USING (owner_id = (SELECT auth.uid())) WITH CHECK (owner_id = (SELECT auth.uid()));

-- Bitácoras: las escriben editar_cruce/editar_pago (SECURITY INVOKER) y nunca se editan.
CREATE POLICY propio_leer     ON public.cruces_editados FOR SELECT TO authenticated
    USING (owner_id = (SELECT auth.uid()));
CREATE POLICY propio_insertar ON public.cruces_editados FOR INSERT TO authenticated
    WITH CHECK (owner_id = (SELECT auth.uid()));
CREATE POLICY propio_leer     ON public.pagos_editados  FOR SELECT TO authenticated
    USING (owner_id = (SELECT auth.uid()));
CREATE POLICY propio_insertar ON public.pagos_editados  FOR INSERT TO authenticated
    WITH CHECK (owner_id = (SELECT auth.uid()));
REVOKE UPDATE, DELETE, TRUNCATE ON public.cruces_editados, public.pagos_editados FROM authenticated;

ALTER TABLE public.borrados ENABLE ROW LEVEL SECURITY;
CREATE POLICY propio_leer ON public.borrados FOR SELECT TO authenticated
    USING (owner_id = (SELECT auth.uid()));
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.borrados FROM authenticated;

ALTER TABLE public.perfiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY propio_leer ON public.perfiles FOR SELECT TO authenticated
    USING (id = (SELECT auth.uid()));
CREATE POLICY propio_nombre ON public.perfiles FOR UPDATE TO authenticated
    USING (id = (SELECT auth.uid())) WITH CHECK (id = (SELECT auth.uid()));
REVOKE INSERT, DELETE, TRUNCATE ON public.perfiles FROM authenticated;
REVOKE UPDATE ON public.perfiles FROM authenticated;
GRANT UPDATE (nombre) ON public.perfiles TO authenticated;

-- Sin esto la vista corre como su dueño (postgres), se salta el RLS y muestra las deudas
-- de TODOS los usuarios.
ALTER VIEW public.vista_estado_deudas SET (security_invoker = true);

-- ====================================================================================
-- RPC
-- ====================================================================================

-- Falla con 42501 si el deudor no es del usuario que llama. Solo hace falta en los RPC
-- que reciben un deudor_id del cliente (aplicar_cruce, registrar_pago): los que reciben
-- un cruce_id o un pago_id (editar_cruce, _editar_cruce_aplicar, editar_pago) ya no ven
-- filas ajenas por el RLS y responden "no existe". estado_cuenta es LANGUAGE sql: con un
-- deudor ajeno devuelve un estado vacío.
CREATE FUNCTION public._exigir_deudor_propio(p_deudor_id uuid) RETURNS void
    LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.deudores
                    WHERE id = p_deudor_id AND owner_id = auth.uid()) THEN
        RAISE EXCEPTION 'El deudor % no existe o no es tuyo', p_deudor_id
            USING ERRCODE = '42501';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION "public"."aplicar_cruce"("p_deudor_id" "uuid", "p_fecha" "date" DEFAULT CURRENT_DATE, "p_idem_key" "uuid" DEFAULT NULL::"uuid", "p_con_estado" boolean DEFAULT true) RETURNS "jsonb"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    v_estado     JSONB;
    v_monto      NUMERIC;
    v_cruce_id   UUID;
    v_pago_mias  UUID;
    v_pago_suyas UUID;
    v_idem_a     UUID := _idem_derivada(p_idem_key, 'cruce_mias');
    v_idem_b     UUID := _idem_derivada(p_idem_key, 'cruce_suyas');
    v_existente  UUID;
    it           JSONB;
BEGIN
    -- v2: el deudor tiene que ser del usuario que llama (PLAN_MULTIUSUARIO §5.1).
    PERFORM _exigir_deudor_propio(p_deudor_id);
    -- Serializa las operaciones sobre un mismo deudor: dos pagos simultáneos no pueden
    -- cruzar las mismas deudas dos veces.
    PERFORM pg_advisory_xact_lock(hashtext(p_deudor_id::TEXT));

    -- Idempotencia: si esta misma operación ya se aplicó, no se repite.
    IF v_idem_a IS NOT NULL THEN
        SELECT cruce_id INTO v_existente FROM pagos WHERE idem_key = v_idem_a;
        IF v_existente IS NOT NULL THEN
            RETURN jsonb_build_object('cruce_id', v_existente, 'aplicado', 0,
                                      'repetido', TRUE,
                                      'estado', CASE WHEN p_con_estado
                                                     THEN estado_cuenta(p_deudor_id)
                                                     ELSE NULL END);
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
                              'repetido', FALSE,
                              'estado', CASE WHEN p_con_estado
                                             THEN estado_cuenta(p_deudor_id)
                                             ELSE NULL END);
END;
$$;

CREATE OR REPLACE FUNCTION "public"."registrar_pago"("p_deudor_id" "uuid", "p_monto" numeric, "p_es_mi_pago" boolean DEFAULT false, "p_fecha" "date" DEFAULT CURRENT_DATE, "p_idem_key" "uuid" DEFAULT NULL::"uuid", "p_deudas_ids" "uuid"[] DEFAULT NULL::"uuid"[]) RETURNS "jsonb"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    v_cruce     JSONB;
    v_plan      JSONB;
    v_pago_id   UUID;
    v_restante  NUMERIC := p_monto;
    v_asignar   NUMERIC;
    v_existente UUID;
    r           RECORD;
BEGIN
    -- v2: el deudor tiene que ser del usuario que llama (PLAN_MULTIUSUARIO §5.1).
    PERFORM _exigir_deudor_propio(p_deudor_id);
    PERFORM pg_advisory_xact_lock(hashtext(p_deudor_id::TEXT));

    IF p_idem_key IS NOT NULL THEN
        SELECT id INTO v_existente FROM pagos WHERE idem_key = p_idem_key;
        IF v_existente IS NOT NULL THEN
            RETURN jsonb_build_object('pago_id', v_existente, 'repetido', TRUE,
                                      'estado', estado_cuenta(p_deudor_id));
        END IF;
    END IF;

    -- Sin dinero no hay reparto: solo se cruza lo que se pueda.
    IF p_monto IS NULL OR p_monto <= 0.01 THEN
        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);
        RETURN jsonb_build_object('pago_id', NULL, 'cruce', v_cruce - 'estado',
                                  'repetido', FALSE, 'estado', estado_cuenta(p_deudor_id));
    END IF;

    v_pago_id := gen_random_uuid();

    IF p_deudas_ids IS NULL THEN
        -- Automático: el cruce va antes del dinero físico, que no tiene sentido pasarse
        -- billetes por deudas que se anulan entre sí; luego el pago FIFO sobre el lado de
        -- quien paga. Igual que siempre.
        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);

        INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                          es_mi_pago, idem_key, synced)
        VALUES (v_pago_id, p_deudor_id, p_monto, p_fecha, FALSE, p_es_mi_pago,
                p_idem_key, TRUE);

        FOR r IN
            SELECT d.id,
                   d.monto - COALESCE(SUM(dp.monto_asignado), 0) AS saldo
            FROM deudas d
            LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
            WHERE d.deudor_id = p_deudor_id
              AND d.es_mi_deuda = p_es_mi_pago
            GROUP BY d.id
            HAVING d.monto - COALESCE(SUM(dp.monto_asignado), 0) > 0.01
            ORDER BY d.fecha_gasto, d.created_at, d.id
        LOOP
            EXIT WHEN v_restante <= 0.01;
            v_asignar := LEAST(r.saldo, v_restante);
            INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
            VALUES (v_pago_id, r.id, v_asignar, TRUE);
            v_restante := v_restante - v_asignar;
        END LOOP;
    ELSE
        -- Deudas elegidas a mano: primero el pago, solo sobre ellas, y después el cruce
        -- sobre lo que quedó. El reparto es el mismo que la app vio: lo calcula
        -- `estado_cuenta` con este pago planeado.
        v_plan := estado_cuenta(p_deudor_id, 'owner', jsonb_build_object(
                      'monto', p_monto,
                      'es_mi_pago', p_es_mi_pago,
                      'deudas_ids', to_jsonb(p_deudas_ids)));

        INSERT INTO pagos(id, deudor_id, monto_total, fecha_pago, es_compensacion,
                          es_mi_pago, idem_key, synced)
        VALUES (v_pago_id, p_deudor_id, p_monto, p_fecha, FALSE, p_es_mi_pago,
                p_idem_key, TRUE);

        FOR r IN
            SELECT (d ->> 'id')::UUID AS id, (d ->> 'pago_planeado')::NUMERIC AS pago
            FROM jsonb_array_elements(v_plan -> 'deudas') d
            WHERE (d ->> 'pago_planeado')::NUMERIC > 0
        LOOP
            INSERT INTO detalle_pagos(pago_id, deuda_id, monto_asignado, synced)
            VALUES (v_pago_id, r.id, r.pago, TRUE);
            v_restante := v_restante - r.pago;
        END LOOP;

        v_cruce := aplicar_cruce(p_deudor_id, p_fecha, p_idem_key, FALSE);
    END IF;

    -- Lo que no se asignó queda como saldo a favor de quien pagó (no se fuerza).
    RETURN jsonb_build_object('pago_id', v_pago_id,
                              'cruce', v_cruce - 'estado',
                              'sobrante', ROUND(v_restante, 2),
                              'repetido', FALSE,
                              'estado', estado_cuenta(p_deudor_id));
END;
$$;

-- Nuevo token del visor: el enlace viejo deja de funcionar al instante.
CREATE FUNCTION public.rotar_token(p_deudor_id uuid) RETURNS text
    LANGUAGE plpgsql AS $$
DECLARE
    v_token text;
BEGIN
    UPDATE public.deudores
       SET token = gen_random_uuid()::text
     WHERE id = p_deudor_id AND owner_id = auth.uid()
    RETURNING token INTO v_token;
    IF v_token IS NULL THEN
        RAISE EXCEPTION 'El deudor % no existe o no es tuyo', p_deudor_id
            USING ERRCODE = '42501';
    END IF;
    RETURN v_token;
END $$;

-- ====================================================================================
-- Permisos de ejecución: nada para anon (ya revocado en la base) ni para PUBLIC.
-- ====================================================================================

REVOKE ALL ON FUNCTION public._crear_perfil()              FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._lapida()                    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._tocar_updated_at()          FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._exigir_deudor_propio(uuid)  FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.rotar_token(uuid)            FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public._exigir_deudor_propio(uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rotar_token(uuid)           TO authenticated, service_role;
