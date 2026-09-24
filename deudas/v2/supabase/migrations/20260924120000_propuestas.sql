-- Fase 6 (deudas/PLAN_MULTIUSUARIO.md §4.1–§4.5 y §5.3): propuestas continuas.
--
-- Con el vínculo `activo`, cada deuda o pago nuevo nace `propuesta` y le llega al otro;
-- cada cambio a algo `acordada` pasa por aceptar o rechazar:
--   * triggers: `_nace_propuesta` (BEFORE INSERT) decide el estado, `_nace_propuesta_post`
--     (AFTER INSERT) crea la propuesta, `_guardia_acordada` (BEFORE UPDATE/DELETE) impide
--     tocar directo lo acordado;
--   * RPC: aceptar_propuesta, rechazar_propuesta, anular_propuesta, proponer_cambio y
--     verificar_vinculo; desvincular ahora anula lo pendiente;
--   * estado_cuenta: lo `rechazada` deja de contar y, SOLO con vínculo vivo, cada deuda
--     trae su `estado_acuerdo` y el resumen `saldo_acordado` y `pendiente_acuerdo`. Sin
--     vínculo la salida es byte a byte la de antes (§4.1): lo comprueba
--     scripts/v2/comparar_linea_base.py.
--
-- La matemática no cambia. estado_cuenta, registrar_pago y _editar_cruce_aplicar son copia
-- exacta de las migraciones anteriores más las líneas marcadas «v2 fase 6». Compruébalo
-- con un diff.
--
-- La variable de sesión `deudas.en_rpc` ('on' solo dentro de los RPC de este archivo)
-- deja pasar a los triggers: los RPC escriben estados y campos del acuerdo que un cliente
-- no puede tocar. Un cliente no la puede poner: PostgREST no ejecuta SET arbitrarios ni
-- expone pg_catalog.set_config. Los RPC la apagan antes de volver (en una misma
-- transacción de prueba, un 'on' olvidado desactivaría las guardias de lo que siga).

-- ====================================================================================
-- Columnas nuevas
-- ====================================================================================

-- Idempotencia de la RESOLUCIÓN: aceptar dos veces con la misma clave devuelve la misma
-- respuesta; `idem_key` (de 20260924110000) es la de la creación.
ALTER TABLE public.propuestas
    ADD COLUMN resuelta_idem uuid,
    ADD COLUMN resultado     jsonb;

-- ====================================================================================
-- Piezas internas
-- ====================================================================================

CREATE FUNCTION public._en_rpc() RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT COALESCE(current_setting('deudas.en_rpc', true), '') = 'on'
$$;

-- Lo que viaja en una propuesta, SIEMPRE desde el punto de vista de quien propone (§5.3):
-- monto, fecha, dirección y el texto con que la anotó. El texto sí viaja: quien recibe
-- tiene que saber qué le proponen ("Cena", no solo "$20"). Después cada uno edita el suyo
-- en su libreta (§4.3). La conciliación (fase 5) no manda títulos del historial.
CREATE FUNCTION public._payload_de(p_entidad text, p_fila jsonb) RETURNS jsonb
    LANGUAGE sql IMMUTABLE AS $$
    SELECT jsonb_strip_nulls(CASE WHEN p_entidad = 'deuda' THEN
        jsonb_build_object('monto',  (p_fila ->> 'monto')::numeric,
                           'fecha',  p_fila ->> 'fecha_gasto',
                           'es_mia', (p_fila ->> 'es_mi_deuda')::boolean,
                           'titulo', p_fila ->> 'titulo')
    ELSE
        jsonb_build_object('monto',  (p_fila ->> 'monto_total')::numeric,
                           'fecha',  p_fila ->> 'fecha_pago',
                           'es_mia', (p_fila ->> 'es_mi_pago')::boolean,
                           'nota',   p_fila ->> 'nota')
    END)
$$;

-- Neto bruto de las filas de un deudor en un estado, punto de vista del dueño (+ te deben,
-- − tú debes): deudas y pagos físicos por su monto completo; los cruces no mueven el neto.
-- Con filas acordadas, las dos libretas dan lo mismo con el signo cambiado (invariante de
-- §4.1): son las mismas filas con la dirección invertida.
CREATE FUNCTION public._neto_por_estado(p_deudor_id uuid, p_estado text) RETURNS numeric
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT ROUND(
          COALESCE((SELECT SUM(CASE WHEN es_mi_deuda THEN -monto
                                    WHEN NOT es_mi_deuda THEN monto END)
                      FROM public.deudas
                     WHERE deudor_id = p_deudor_id AND estado_acuerdo = p_estado), 0)
        + COALESCE((SELECT SUM(CASE WHEN es_mi_pago THEN monto_total
                                    WHEN NOT es_mi_pago THEN -monto_total END)
                      FROM public.pagos
                     WHERE deudor_id = p_deudor_id AND estado_acuerdo = p_estado
                       AND NOT COALESCE(es_compensacion, false)), 0), 2)
$$;

-- Candados de los dos deudores de un vínculo, en orden fijo: los mismos que toman
-- registrar_pago y aplicar_cruce (uno cada uno), así nadie se traba con nadie.
CREATE FUNCTION public._bloquear_vinculo(p_vinculo public.vinculos) RETURNS void
    LANGUAGE plpgsql AS $$
DECLARE
    d uuid;
BEGIN
    FOR d IN SELECT x FROM unnest(ARRAY[p_vinculo.deudor_a, p_vinculo.deudor_b]) x ORDER BY x::text LOOP
        PERFORM pg_advisory_xact_lock(hashtext(d::text));
    END LOOP;
END $$;

-- Saca una deuda de todos los cruces en los que está. Hace falta ANTES de borrar sus
-- detalles: si no, uno de los dos pagos virtuales queda con sobrante y el cruce deja de
-- cuadrar (§4.2). Usa el recorte de editar_cruce sin la regla de "solo la última
-- operación": la deuda puede estar en un cruce viejo.
CREATE FUNCTION public._sacar_de_cruces(p_deuda_id uuid) RETURNS int
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_cruce uuid;
    v_n     int := 0;
BEGIN
    IF EXISTS (SELECT 1 FROM detalle_pagos dp JOIN pagos p ON p.id = dp.pago_id
                WHERE dp.deuda_id = p_deuda_id AND COALESCE(p.es_compensacion, false)
                  AND p.cruce_id IS NULL) THEN
        RAISE EXCEPTION 'La deuda % está en un cruce sin cruce_id (anterior a la columna)', p_deuda_id;
    END IF;
    FOR v_cruce IN SELECT DISTINCT p.cruce_id
                     FROM detalle_pagos dp JOIN pagos p ON p.id = dp.pago_id
                    WHERE dp.deuda_id = p_deuda_id AND COALESCE(p.es_compensacion, false) LOOP
        PERFORM set_config('deudas.recorte_libre', 'on', true);
        PERFORM _editar_cruce_aplicar(v_cruce, ARRAY[p_deuda_id]);
        PERFORM set_config('deudas.recorte_libre', 'off', true);
        v_n := v_n + 1;
    END LOOP;
    RETURN v_n;
END $$;

-- Deja lo asignado a una deuda en `p_tope` como máximo (NULL = soltarlo todo). Primero
-- suelta dinero de pagos reales, del más reciente al más antiguo: ese dinero queda como
-- saldo a favor de quien pagó, que estado_cuenta abona solo a las deudas pendientes (§2).
-- Si todavía sobra, la deuda sale de sus cruces.
CREATE FUNCTION public._soltar_deuda(p_deuda_id uuid, p_tope numeric) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_exceso numeric;
    r        record;
BEGIN
    IF p_tope IS NULL THEN
        PERFORM _sacar_de_cruces(p_deuda_id);
        DELETE FROM detalle_pagos WHERE deuda_id = p_deuda_id;
        RETURN;
    END IF;

    SELECT COALESCE(SUM(monto_asignado), 0) - p_tope INTO v_exceso
      FROM detalle_pagos WHERE deuda_id = p_deuda_id;
    FOR r IN SELECT dp.id, dp.monto_asignado
               FROM detalle_pagos dp JOIN pagos p ON p.id = dp.pago_id
              WHERE dp.deuda_id = p_deuda_id AND NOT COALESCE(p.es_compensacion, false)
              ORDER BY p.fecha_pago DESC, p.created_at DESC, p.id DESC LOOP
        EXIT WHEN v_exceso <= 0.001;
        IF r.monto_asignado <= v_exceso + 0.001 THEN
            DELETE FROM detalle_pagos WHERE id = r.id;
        ELSE
            UPDATE detalle_pagos SET monto_asignado = monto_asignado - v_exceso WHERE id = r.id;
        END IF;
        v_exceso := v_exceso - LEAST(r.monto_asignado, v_exceso);
    END LOOP;

    IF v_exceso > 0.001 THEN
        PERFORM _sacar_de_cruces(p_deuda_id);
    END IF;
END $$;

-- Lo mismo para un pago real: su reparto no puede pasar de `p_tope` (NULL = soltarlo
-- todo). Suelta de las deudas más recientes primero (el FIFO al revés); lo soltado queda
-- como sobrante del pago, o sea, saldo a favor de quien pagó.
CREATE FUNCTION public._soltar_pago(p_pago_id uuid, p_tope numeric) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_exceso numeric;
    r        record;
BEGIN
    IF p_tope IS NULL THEN
        DELETE FROM detalle_pagos WHERE pago_id = p_pago_id;
        RETURN;
    END IF;
    SELECT COALESCE(SUM(monto_asignado), 0) - p_tope INTO v_exceso
      FROM detalle_pagos WHERE pago_id = p_pago_id;
    FOR r IN SELECT dp.id, dp.monto_asignado
               FROM detalle_pagos dp JOIN deudas d ON d.id = dp.deuda_id
              WHERE dp.pago_id = p_pago_id
              ORDER BY d.fecha_gasto DESC, d.created_at DESC, d.id DESC LOOP
        EXIT WHEN v_exceso <= 0.001;
        IF r.monto_asignado <= v_exceso + 0.001 THEN
            DELETE FROM detalle_pagos WHERE id = r.id;
        ELSE
            UPDATE detalle_pagos SET monto_asignado = monto_asignado - v_exceso WHERE id = r.id;
        END IF;
        v_exceso := v_exceso - LEAST(r.monto_asignado, v_exceso);
    END LOOP;
END $$;

-- §4.2: una fila deja de contar (rechazada, o anulada por quien la propuso). Primero se
-- sacan sus cruces, después se borran sus detalles y al final se marca.
CREATE FUNCTION public._descontar_fila(p_entidad text, p_id uuid) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF p_entidad = 'deuda' THEN
        PERFORM _soltar_deuda(p_id, NULL);
        UPDATE deudas SET estado_acuerdo = 'rechazada' WHERE id = p_id;
    ELSE
        PERFORM _soltar_pago(p_id, NULL);
        UPDATE pagos SET estado_acuerdo = 'rechazada' WHERE id = p_id;
    END IF;
END $$;

-- Fila de deudas o pagos como jsonb (NULL si no existe), bloqueada para el resto de la
-- transacción.
CREATE FUNCTION public._fila(p_entidad text, p_id uuid) RETURNS jsonb
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v jsonb;
BEGIN
    IF p_entidad = 'deuda' THEN
        SELECT to_jsonb(d) INTO v FROM deudas d WHERE id = p_id FOR UPDATE;
    ELSE
        SELECT to_jsonb(p) INTO v FROM pagos p WHERE id = p_id FOR UPDATE;
    END IF;
    RETURN v;
END $$;

-- La propuesta, su vínculo y los candados de los dos deudores. Solo para sus dos partes.
CREATE FUNCTION public._tomar_propuesta(
    p_id uuid, OUT prop public.propuestas, OUT vinc public.vinculos)
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    SELECT * INTO prop FROM propuestas
     WHERE id = p_id AND auth.uid() IN (de_usuario, para_usuario);
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La propuesta % no existe o no es tuya', p_id USING ERRCODE = '42501';
    END IF;
    SELECT * INTO vinc FROM vinculos WHERE id = prop.vinculo_id;
    PERFORM _bloquear_vinculo(vinc);
    -- Releer tras el candado: la otra parte pudo resolverla mientras esperábamos.
    SELECT * INTO prop FROM propuestas WHERE id = p_id FOR UPDATE;
END $$;

-- ====================================================================================
-- Triggers
-- ====================================================================================

-- BEFORE INSERT en deudas y pagos. El estado y el origen los decide el servidor: lo que
-- mande el cliente se ignora. Con el vínculo `activo`, una fila nueva que no es un cruce
-- nace `propuesta` (§4.1). Las filas espejo las crean los RPC (con `deudas.en_rpc`).
CREATE FUNCTION public._nace_propuesta() RETURNS trigger
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF _en_rpc() THEN
        RETURN NEW;
    END IF;
    NEW.origen_id := NULL;
    NEW.estado_acuerdo := 'local';
    IF TG_TABLE_NAME = 'pagos' THEN
        IF COALESCE((to_jsonb(NEW) ->> 'es_compensacion')::boolean, false) THEN
            RETURN NEW;  -- los cruces son derivados: siempre locales
        END IF;
    END IF;
    IF (_vinculo_de(NEW.deudor_id)).estado = 'activo' THEN
        NEW.estado_acuerdo := 'propuesta';
    END IF;
    RETURN NEW;
END $$;

-- AFTER INSERT: la fila quedó `propuesta` → la propuesta para el otro. SECURITY DEFINER:
-- `propuestas` no se escribe directo. La clave de idempotencia sale de la fila, así un
-- reintento del sync no la duplica.
CREATE FUNCTION public._nace_propuesta_post() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v       public.vinculos;
    v_ent   text := CASE TG_TABLE_NAME WHEN 'deudas' THEN 'deuda' ELSE 'pago' END;
BEGIN
    IF NEW.estado_acuerdo <> 'propuesta' OR _en_rpc() THEN
        RETURN NULL;
    END IF;
    v := _vinculo_de(NEW.deudor_id);
    INSERT INTO propuestas (vinculo_id, de_usuario, para_usuario, entidad, tipo,
                            fila_origen, payload, idem_key)
    VALUES (v.id, NEW.owner_id,
            CASE WHEN v.usuario_a = NEW.owner_id THEN v.usuario_b ELSE v.usuario_a END,
            v_ent, 'crear', NEW.id, _payload_de(v_ent, to_jsonb(NEW)),
            _idem_derivada(NEW.id, 'crear'))
    ON CONFLICT (idem_key) DO NOTHING;
    RETURN NULL;
END $$;

-- AFTER UPDATE: quien propuso corrige su fila antes de que el otro responda → la propuesta
-- pendiente se pone al día. Así el otro acepta lo que ve.
CREATE FUNCTION public._propuesta_al_dia() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_ent text := CASE TG_TABLE_NAME WHEN 'deudas' THEN 'deuda' ELSE 'pago' END;
BEGIN
    IF NEW.estado_acuerdo = 'propuesta'
       AND _payload_de(v_ent, to_jsonb(NEW)) IS DISTINCT FROM _payload_de(v_ent, to_jsonb(OLD)) THEN
        UPDATE propuestas
           SET payload = _payload_de(v_ent, to_jsonb(NEW))
         WHERE fila_origen = NEW.id AND tipo = 'crear' AND estado = 'pendiente';
    END IF;
    RETURN NULL;
END $$;

-- AFTER DELETE: si la fila se va (la borró quien la propuso, o se borró el contacto), sus
-- propuestas pendientes no tienen qué aceptar.
CREATE FUNCTION public._propuesta_sin_fila() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    UPDATE propuestas
       SET estado = 'anulada', resuelta_at = now()
     WHERE fila_origen = OLD.id AND estado = 'pendiente';
    RETURN NULL;
END $$;

-- BEFORE UPDATE OR DELETE en deudas y pagos (§4.3):
--   * `estado_acuerdo` y `origen_id` solo los cambian los RPC: en un UPDATE directo se
--     conservan (un Flutter con datos viejos no puede "desacordar" nada);
--   * mientras el vínculo esté vivo, lo `acordada` no se borra directo ni cambia sus campos
--     del acuerdo (42501): eso se propone con proponer_cambio. `titulo` y `nota` son
--     privados de cada libreta y se editan libremente.
-- Se deja pasar el borrado en cascada (se borra el contacto o la cuenta: pg_trigger_depth()
-- > 1) y todo lo de una fila cuyo vínculo ya se rompió: cada uno vuelve a mandar en su
-- libreta.
CREATE FUNCTION public._guardia_acordada() RETURNS trigger
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_campos text[] := CASE TG_TABLE_NAME
        WHEN 'deudas' THEN ARRAY['monto', 'fecha_gasto', 'es_mi_deuda', 'deudor_id']
        ELSE ARRAY['monto_total', 'fecha_pago', 'es_mi_pago', 'deudor_id', 'es_compensacion'] END;
BEGIN
    IF _en_rpc() THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        NEW.estado_acuerdo := OLD.estado_acuerdo;
        NEW.origen_id := OLD.origen_id;
    END IF;
    IF OLD.estado_acuerdo <> 'acordada' OR pg_trigger_depth() > 1
       OR (_vinculo_de(OLD.deudor_id)).id IS NULL THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Esta fila está acordada con la otra persona: para borrarla, propón el cambio'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(v_campos) k
                WHERE to_jsonb(OLD) -> k IS DISTINCT FROM to_jsonb(NEW) -> k) THEN
        RAISE EXCEPTION 'Esta fila está acordada con la otra persona: para cambiar monto, fecha o dirección, propón el cambio'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END $$;

-- BEFORE INSERT OR UPDATE en detalle_pagos:
--   * dentro de los RPC, el dueño de un detalle es el de su pago. Al rechazar, quien
--     rechaza recorta un cruce de la libreta del OTRO, y `_editar_cruce_aplicar` inserta
--     con el DEFAULT auth.uid(), que sería el dueño equivocado;
--   * nada de repartir dinero hacia o desde una fila rechazada. Pasa si un teléfono sin
--     conexión repartió un pago sobre una deuda que el otro rechazó mientras tanto: el
--     detalle no entra, y ese dinero queda como saldo a favor, que es lo correcto.
CREATE FUNCTION public._detalle_antes() RETURNS trigger
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF _en_rpc() THEN
        SELECT owner_id INTO NEW.owner_id FROM pagos WHERE id = NEW.pago_id;
    END IF;
    IF EXISTS (SELECT 1 FROM deudas WHERE id = NEW.deuda_id AND estado_acuerdo = 'rechazada')
       OR EXISTS (SELECT 1 FROM pagos WHERE id = NEW.pago_id AND estado_acuerdo = 'rechazada') THEN
        RAISE EXCEPTION 'No se puede repartir dinero sobre una fila rechazada' USING ERRCODE = '22023';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER nace_propuesta BEFORE INSERT ON public.deudas
    FOR EACH ROW EXECUTE FUNCTION public._nace_propuesta();
CREATE TRIGGER nace_propuesta BEFORE INSERT ON public.pagos
    FOR EACH ROW EXECUTE FUNCTION public._nace_propuesta();
CREATE TRIGGER nace_propuesta_post AFTER INSERT ON public.deudas
    FOR EACH ROW EXECUTE FUNCTION public._nace_propuesta_post();
CREATE TRIGGER nace_propuesta_post AFTER INSERT ON public.pagos
    FOR EACH ROW EXECUTE FUNCTION public._nace_propuesta_post();
CREATE TRIGGER propuesta_al_dia AFTER UPDATE ON public.deudas
    FOR EACH ROW EXECUTE FUNCTION public._propuesta_al_dia();
CREATE TRIGGER propuesta_al_dia AFTER UPDATE ON public.pagos
    FOR EACH ROW EXECUTE FUNCTION public._propuesta_al_dia();
CREATE TRIGGER propuesta_sin_fila AFTER DELETE ON public.deudas
    FOR EACH ROW EXECUTE FUNCTION public._propuesta_sin_fila();
CREATE TRIGGER propuesta_sin_fila AFTER DELETE ON public.pagos
    FOR EACH ROW EXECUTE FUNCTION public._propuesta_sin_fila();
CREATE TRIGGER guardia_acordada BEFORE UPDATE OR DELETE ON public.deudas
    FOR EACH ROW EXECUTE FUNCTION public._guardia_acordada();
CREATE TRIGGER guardia_acordada BEFORE UPDATE OR DELETE ON public.pagos
    FOR EACH ROW EXECUTE FUNCTION public._guardia_acordada();
CREATE TRIGGER detalle_antes BEFORE INSERT OR UPDATE ON public.detalle_pagos
    FOR EACH ROW EXECUTE FUNCTION public._detalle_antes();

-- ====================================================================================
-- Funciones existentes, con el filtro de lo rechazado
-- ====================================================================================

CREATE OR REPLACE FUNCTION "public"."estado_cuenta"("p_deudor_id" "uuid", "p_pov" "text" DEFAULT 'owner'::"text", "p_pago" "jsonb" DEFAULT NULL::"jsonb") RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    AS $$
WITH
pago_planeado AS (
    SELECT COALESCE((p_pago ->> 'monto')::NUMERIC, 0)          AS monto,
           COALESCE((p_pago ->> 'es_mi_pago')::BOOLEAN, FALSE) AS es_mi_pago,
           ARRAY(SELECT jsonb_array_elements_text(
                     CASE WHEN jsonb_typeof(p_pago -> 'deudas_ids') = 'array'
                          THEN p_pago -> 'deudas_ids' ELSE '[]'::JSONB END))::UUID[]
                                                               AS deudas_ids
),

base_hoy AS (
    SELECT d.id,
           d.titulo,
           d.fecha_gasto,
           d.created_at,
           d.es_mi_deuda,
           d.estado_acuerdo,                                           -- v2 fase 6
           d.monto::NUMERIC                                            AS monto_original,
           COALESCE(SUM(dp.monto_asignado), 0)::NUMERIC                AS monto_pagado,
           GREATEST(d.monto - COALESCE(SUM(dp.monto_asignado), 0), 0)::NUMERIC
                                                                       AS saldo_pendiente
    FROM deudas d
    LEFT JOIN detalle_pagos dp ON dp.deuda_id = d.id
    WHERE d.deudor_id = p_deudor_id
      AND d.estado_acuerdo <> 'rechazada'   -- v2 fase 6: lo rechazado no cuenta (§4.1)
    GROUP BY d.id
),

favor_hoy AS (
    SELECT COALESCE(SUM(sobrante) FILTER (WHERE es_mi_pago), 0)     AS favor_owner_ini,
           COALESCE(SUM(sobrante) FILTER (WHERE NOT es_mi_pago), 0) AS favor_debtor_ini
    FROM (
        SELECT p.es_mi_pago,
               p.monto_total - COALESCE(SUM(dp.monto_asignado), 0) AS sobrante
        FROM pagos p
        LEFT JOIN detalle_pagos dp ON dp.pago_id = p.id
        WHERE p.deudor_id = p_deudor_id
          AND NOT COALESCE(p.es_compensacion, FALSE)
          AND p.estado_acuerdo <> 'rechazada'   -- v2 fase 6
        GROUP BY p.id, p.es_mi_pago, p.monto_total
    ) s
    WHERE sobrante > 0.01
),

saldo_hoy AS (
    SELECT a.id, a.fecha_gasto, a.created_at, a.es_mi_deuda,
           ROUND(a.saldo_pendiente - CASE
               WHEN a.saldo_pendiente > 0.01
                    AND (a.credito_ini - a.consumido_antes) > 0.01
               THEN LEAST(a.saldo_pendiente, a.credito_ini - a.consumido_antes)
               ELSE 0
           END, 2) AS saldo_real
    FROM (
        SELECT b.*,
               CASE WHEN b.es_mi_deuda THEN f.favor_owner_ini ELSE f.favor_debtor_ini END
                   AS credito_ini,
               COALESCE(
                   SUM(b.saldo_pendiente) FILTER (WHERE b.saldo_pendiente > 0.01)
                       OVER (PARTITION BY b.es_mi_deuda
                             ORDER BY b.fecha_gasto, b.created_at, b.id
                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
                   0) AS consumido_antes
        FROM base_hoy b
        CROSS JOIN favor_hoy f
    ) a
),

reparto AS (
    SELECT e.id,
           ROUND(CASE WHEN pp.monto - e.repartido_antes > 0.01
                      THEN LEAST(e.saldo_real, pp.monto - e.repartido_antes)
                      ELSE 0 END, 2) AS pago
    FROM (
        SELECT s.id, s.saldo_real,
               COALESCE(SUM(s.saldo_real)
                            OVER (ORDER BY s.fecha_gasto, s.created_at, s.id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
                        0) AS repartido_antes
        FROM saldo_hoy s
        CROSS JOIN pago_planeado pp
        WHERE s.id = ANY(pp.deudas_ids)
          AND s.es_mi_deuda = pp.es_mi_pago
          AND s.saldo_real > 0.01
    ) e
    CROSS JOIN pago_planeado pp
),
reparto_total AS (
    SELECT pp.monto,
           pp.es_mi_pago,
           COALESCE((SELECT SUM(pago) FROM reparto), 0)          AS asignado,
           pp.monto - COALESCE((SELECT SUM(pago) FROM reparto), 0) AS sobrante
    FROM pago_planeado pp
),

base AS (
    SELECT b.id, b.titulo, b.fecha_gasto, b.created_at, b.es_mi_deuda, b.monto_original,
           b.estado_acuerdo,                                           -- v2 fase 6
           b.monto_pagado + COALESCE(r.pago, 0)                        AS monto_pagado,
           GREATEST(b.saldo_pendiente - COALESCE(r.pago, 0), 0)        AS saldo_pendiente,
           COALESCE(r.pago, 0)                                         AS pago_planeado
    FROM base_hoy b
    LEFT JOIN reparto r ON r.id = b.id
),

favor AS (
    SELECT f.favor_owner_ini
             + CASE WHEN rt.es_mi_pago AND rt.sobrante > 0.01 THEN rt.sobrante ELSE 0 END
               AS favor_owner_ini,
           f.favor_debtor_ini
             + CASE WHEN NOT rt.es_mi_pago AND rt.sobrante > 0.01 THEN rt.sobrante ELSE 0 END
               AS favor_debtor_ini
    FROM favor_hoy f
    CROSS JOIN reparto_total rt
),

abono_pos AS (
    SELECT b.*,
           CASE WHEN b.es_mi_deuda THEN f.favor_owner_ini ELSE f.favor_debtor_ini END
               AS credito_ini,
           COALESCE(
               SUM(b.saldo_pendiente) FILTER (WHERE b.saldo_pendiente > 0.01)
                   OVER (PARTITION BY b.es_mi_deuda
                         ORDER BY b.fecha_gasto, b.created_at, b.id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
               0) AS consumido_antes
    FROM base b
    CROSS JOIN favor f
),
calc AS (
    SELECT a.id, a.titulo, a.fecha_gasto, a.created_at, a.es_mi_deuda, a.estado_acuerdo,  -- v2 fase 6
           a.monto_original, a.monto_pagado, a.saldo_pendiente, a.pago_planeado,
           abono.v                                           AS abono_saldo_favor,
           ROUND(a.saldo_pendiente - abono.v, 2)             AS saldo_real
    FROM abono_pos a
    CROSS JOIN LATERAL (
        SELECT CASE
                   WHEN a.saldo_pendiente > 0.01
                        AND (a.credito_ini - a.consumido_antes) > 0.01
                   THEN LEAST(a.saldo_pendiente, a.credito_ini - a.consumido_antes)
                   ELSE 0
               END AS v
    ) abono
),
tot AS (
    SELECT COALESCE(SUM(saldo_real)        FILTER (WHERE NOT es_mi_deuda), 0) AS te_deben,
           COALESCE(SUM(saldo_real)        FILTER (WHERE es_mi_deuda),     0) AS tu_debes,
           COALESCE(SUM(abono_saldo_favor) FILTER (WHERE es_mi_deuda),     0) AS usado_owner,
           COALESCE(SUM(abono_saldo_favor) FILTER (WHERE NOT es_mi_deuda), 0) AS usado_debtor,
           COALESCE(SUM(monto_original), 0)                                   AS total_original,
           COALESCE(SUM(monto_pagado), 0)                                     AS total_pagado,
           COUNT(*)                                                           AS n,
           COUNT(*) FILTER (WHERE saldo_real <= 0.01)                         AS n_pagadas,
           COUNT(*) FILTER (WHERE saldo_real >  0.01)                         AS n_pendientes
    FROM calc
),
cruzable AS (
    SELECT ROUND(LEAST(t.te_deben, t.tu_debes), 2) AS monto FROM tot t
),

cruce_pos AS (
    SELECT c.*,
           cz.monto AS cruzable,
           COALESCE(
               SUM(c.saldo_real) FILTER (WHERE c.saldo_real > 0.01)
                   OVER (PARTITION BY c.es_mi_deuda
                         ORDER BY c.fecha_gasto, c.created_at, c.id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
               0) AS cruzado_antes
    FROM calc c
    CROSS JOIN cruzable cz
),
final AS (
    SELECT p.id, p.titulo, p.fecha_gasto, p.created_at, p.es_mi_deuda, p.estado_acuerdo,  -- v2 fase 6
           p.monto_original, p.monto_pagado, p.saldo_pendiente, p.pago_planeado,
           p.abono_saldo_favor, p.saldo_real,
           CASE
               WHEN p.cruzable > 0.01
                    AND p.saldo_real > 0.01
                    AND (p.cruzable - p.cruzado_antes) > 0.01
               THEN LEAST(p.saldo_real, p.cruzable - p.cruzado_antes)
               ELSE 0
           END AS cruce_sugerido
    FROM cruce_pos p
),

-- v2 fase 6: con vínculo vivo (§4.1), el saldo acordado y lo que espera respuesta. Sin
-- vínculo no se calcula ni se agrega nada: la salida es la de siempre.
acuerdo AS (
    SELECT v.vinculado,
           CASE WHEN v.vinculado THEN _neto_por_estado(p_deudor_id, 'acordada')  END AS acordado,
           CASE WHEN v.vinculado THEN _neto_por_estado(p_deudor_id, 'propuesta') END AS pendiente
    FROM (SELECT (_vinculo_de(p_deudor_id)).id IS NOT NULL AS vinculado) v
)

SELECT jsonb_build_object(
    'deudas', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'id', id,
            'titulo', titulo,
            'fecha_gasto', fecha_gasto,
            -- El desempate del FIFO: la app lo necesita para calcular igual sin red.
            'creado', created_at,
            'monto_original', ROUND(monto_original, 2),
            'monto_pagado', ROUND(monto_pagado, 2),
            'saldo_pendiente', ROUND(saldo_pendiente, 2),
            'abono_saldo_favor', ROUND(abono_saldo_favor, 2),
            'saldo_real', ROUND(saldo_real, 2),
            'cruce_sugerido', ROUND(cruce_sugerido, 2),
            -- El POV del deudor ve las deudas al revés que el dueño.
            'es_tu_deuda', CASE WHEN p_pov = 'owner' THEN es_mi_deuda ELSE NOT es_mi_deuda END,
            'estado', CASE
                WHEN saldo_real <= 0.01 THEN 'PAGADA'
                WHEN monto_pagado > 0.01 OR abono_saldo_favor > 0.01 THEN 'PARCIAL'
                ELSE 'PENDIENTE' END
        )
        -- Solo con pago planeado, para que sin él la salida no cambie ni en una clave.
        || CASE WHEN p_pago IS NOT NULL
                THEN jsonb_build_object('pago_planeado', ROUND(pago_planeado, 2))
                ELSE '{}'::JSONB END
        -- v2 fase 6
        || CASE WHEN (SELECT vinculado FROM acuerdo)
                THEN jsonb_build_object('estado_acuerdo', estado_acuerdo)
                ELSE '{}'::JSONB END
        ORDER BY fecha_gasto DESC, created_at DESC, id)
        FROM final), '[]'::JSONB),

    'resumen', jsonb_build_object(
        'total_original',  ROUND(t.total_original, 2),
        'total_pagado',    ROUND(t.total_pagado, 2),
        'total_pendiente', ROUND(t.te_deben + t.tu_debes, 2),
        'total_te_deben',  CASE WHEN p_pov = 'owner' THEN t.te_deben ELSE t.tu_debes END,
        'total_tu_debes',  CASE WHEN p_pov = 'owner' THEN t.tu_debes ELSE t.te_deben END,
        -- El crédito que no abonó ninguna deuda es deuda pura: lo que el deudor pagó de
        -- más se lo debes, lo que pagaste de más te lo debe. Sobre el crédito RESTANTE.
        'neto', (CASE WHEN p_pov = 'owner' THEN 1 ELSE -1 END) * ROUND(
                    t.te_deben - t.tu_debes
                    - (f.favor_debtor_ini - t.usado_debtor)
                    + (f.favor_owner_ini  - t.usado_owner), 2),
        'saldo_favor', CASE WHEN p_pov = 'owner'
                            THEN ROUND(f.favor_debtor_ini - t.usado_debtor, 2)
                            ELSE ROUND(f.favor_owner_ini  - t.usado_owner,  2) END,
        'saldo_favor_owner', CASE WHEN p_pov = 'owner'
                            THEN ROUND(f.favor_owner_ini  - t.usado_owner,  2)
                            ELSE ROUND(f.favor_debtor_ini - t.usado_debtor, 2) END,
        'monto_ideal_a_cruzar', cz.monto,
        'count', t.n,
        'count_pagadas', t.n_pagadas,
        'count_pendientes', t.n_pendientes
    )
    || CASE WHEN p_pago IS NOT NULL
            THEN jsonb_build_object('pago_planeado', jsonb_build_object(
                     'monto',      ROUND(rt.monto, 2),
                     'es_mi_pago', rt.es_mi_pago,
                     'asignado',   ROUND(rt.asignado, 2),
                     'sobrante',   ROUND(rt.sobrante, 2)))
            ELSE '{}'::JSONB END
    -- v2 fase 6
    || CASE WHEN a.vinculado
            THEN jsonb_build_object(
                     'saldo_acordado',    (CASE WHEN p_pov = 'owner' THEN 1 ELSE -1 END) * a.acordado,
                     'pendiente_acuerdo', (CASE WHEN p_pov = 'owner' THEN 1 ELSE -1 END) * a.pendiente)
            ELSE '{}'::JSONB END,

    'cruce_sugerido', jsonb_build_object(
        'monto', cz.monto,
        'lados', jsonb_build_object(
            'te_deben', jsonb_build_object(
                'total', COALESCE((
                    SELECT ROUND(SUM(cruce_sugerido), 2) FROM final
                    WHERE es_mi_deuda = (p_pov <> 'owner') AND cruce_sugerido > 0.01), 0),
                'items', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'deuda_id', id,
                        'titulo', titulo,
                        'fecha_gasto', fecha_gasto,
                        'es_tu_deuda', FALSE,
                        'monto_original', ROUND(monto_original, 2),
                        'saldo_antes', ROUND(saldo_real, 2),
                        'aplicado', ROUND(cruce_sugerido, 2),
                        'pagado_acumulado', ROUND(monto_original - saldo_real + cruce_sugerido, 2),
                        'saldo_despues', ROUND(saldo_real - cruce_sugerido, 2),
                        'cerrada', (saldo_real - cruce_sugerido) <= 0.01,
                        'abono_saldo_favor', ROUND(abono_saldo_favor, 2)
                    ) ORDER BY fecha_gasto, created_at, id)
                    FROM final
                    WHERE es_mi_deuda = (p_pov <> 'owner') AND cruce_sugerido > 0.01), '[]'::JSONB)
            ),
            'tu_debes', jsonb_build_object(
                'total', COALESCE((
                    SELECT ROUND(SUM(cruce_sugerido), 2) FROM final
                    WHERE es_mi_deuda = (p_pov =  'owner') AND cruce_sugerido > 0.01), 0),
                'items', COALESCE((
                    SELECT jsonb_agg(jsonb_build_object(
                        'deuda_id', id,
                        'titulo', titulo,
                        'fecha_gasto', fecha_gasto,
                        'es_tu_deuda', TRUE,
                        'monto_original', ROUND(monto_original, 2),
                        'saldo_antes', ROUND(saldo_real, 2),
                        'aplicado', ROUND(cruce_sugerido, 2),
                        'pagado_acumulado', ROUND(monto_original - saldo_real + cruce_sugerido, 2),
                        'saldo_despues', ROUND(saldo_real - cruce_sugerido, 2),
                        'cerrada', (saldo_real - cruce_sugerido) <= 0.01,
                        'abono_saldo_favor', ROUND(abono_saldo_favor, 2)
                    ) ORDER BY fecha_gasto, created_at, id)
                    FROM final
                    WHERE es_mi_deuda = (p_pov =  'owner') AND cruce_sugerido > 0.01), '[]'::JSONB)
            )
        )
    )
)
FROM tot t, favor f, cruzable cz, reparto_total rt, acuerdo a;  -- v2 fase 6: acuerdo
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
              AND d.estado_acuerdo <> 'rechazada'   -- v2 fase 6: a lo rechazado no se le paga
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

CREATE OR REPLACE FUNCTION "public"."_editar_cruce_aplicar"("p_cruce_id" "uuid", "p_excluir" "uuid"[]) RETURNS "jsonb"
    LANGUAGE "plpgsql"
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
    -- v2 fase 6: `deudas.recorte_libre` la salta. La pone solo _sacar_de_cruces, que al
    -- rechazar o editar algo acordado tiene que recortar cruces viejos (§4.2).
    IF COALESCE(current_setting('deudas.recorte_libre', true), '') <> 'on'
       AND EXISTS (SELECT 1 FROM pagos
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
               d.created_at,
               ROUND(SUM(dp.monto_asignado), 2)       AS antes,
               (p_excluir IS NULL OR d.id = ANY(p_excluir)) AS excluida
          FROM pagos p
          JOIN detalle_pagos dp ON dp.pago_id = p.id
          JOIN deudas d         ON d.id = dp.deuda_id
         WHERE p.cruce_id = p_cruce_id
         GROUP BY p.es_mi_pago, d.id, d.titulo, d.fecha_gasto, d.created_at
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
                            OVER (PARTITION BY i.lado ORDER BY i.fecha_gasto, i.created_at, i.deuda_id
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
           ) ORDER BY lado DESC, fecha_gasto, created_at, deuda_id), '[]'::JSONB)
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

-- La vista gana `estado_acuerdo` al final (CREATE OR REPLACE VIEW solo deja agregar
-- columnas al final). Sigue mostrando lo rechazado: la app lo pinta tachado; quien suma
-- saldos desde la vista lo filtra (contabilidad/debts/reading.py). Mismo cuerpo que en
-- 20260923180000_base.sql, y security_invoker como en 20260923190000_duenos.sql.
CREATE OR REPLACE VIEW public.vista_estado_deudas WITH (security_invoker = true) AS
 SELECT d.id,
    d.titulo,
    d.monto AS monto_original,
    d.fecha_gasto,
    d.deudor_id,
    d.es_mi_deuda,
    COALESCE(sum(dp.monto_asignado), (0)::numeric) AS monto_pagado,
    (d.monto - COALESCE(sum(dp.monto_asignado), (0)::numeric)) AS saldo_pendiente,
        CASE
            WHEN ((d.monto - COALESCE(sum(dp.monto_asignado), (0)::numeric)) <= 0.001) THEN 'PAGADA'::text
            WHEN (COALESCE(sum(dp.monto_asignado), (0)::numeric) > (0)::numeric) THEN 'PARCIAL'::text
            ELSE 'PENDIENTE'::text
        END AS estado,
    d.estado_acuerdo                                            -- v2 fase 6
   FROM (public.deudas d
     LEFT JOIN public.detalle_pagos dp ON ((d.id = dp.deuda_id)))
  GROUP BY d.id;


-- confirmar_conciliacion (fase 5) escribe `estado_acuerdo`: ahora tiene que avisarle a la
-- guardia con `deudas.en_rpc`, como los RPC de abajo.
CREATE OR REPLACE FUNCTION public.confirmar_conciliacion(p_vinculo_id uuid, p_pares jsonb DEFAULT '[]')
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
    PERFORM set_config('deudas.en_rpc', 'on', true);   -- v2 fase 6

    IF (c.soy_a AND (c.vinculo).conciliado_a) OR (NOT c.soy_a AND (c.vinculo).conciliado_b) THEN
        PERFORM set_config('deudas.en_rpc', 'off', true);   -- v2 fase 6
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

    PERFORM set_config('deudas.en_rpc', 'off', true);   -- v2 fase 6
    RETURN jsonb_build_object('estado', v_estado, 'acordadas', v_acordadas, 'propuestas', v_propuestas);
END $$;

-- ====================================================================================
-- RPC
-- ====================================================================================

-- Filas de MI libreta que podrían ser la misma que la propuesta (capa 4 de §4.5): mismo
-- deudor del vínculo, dirección invertida, mismo monto al centavo, fecha a ±3 días, sin
-- acordar ni rechazar. Una `propuesta` mía también cuenta: los dos anotaron lo mismo a la
-- vez y cada uno se lo mandó al otro.
CREATE FUNCTION public._candidatos_espejo(p_entidad text, p_origen jsonb, p_mi_deudor uuid)
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
           AND abs(d.fecha_gasto - (p_origen ->> 'fecha_gasto')::date) <= 3
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
           AND abs(p.fecha_pago - (p_origen ->> 'fecha_pago')::date) <= 3
      ) c
$$;

-- Acepta una propuesta dirigida a mí. SECURITY DEFINER: marca la fila del otro (solo su
-- `estado_acuerdo`, o los campos del acuerdo si es un cambio que él propuso).
--
-- tipo 'crear':
--   * sin `p_enlazar_con` ni `p_crear_nueva`, si en mi libreta hay filas que podrían ser la
--     misma, no hace nada y devuelve {"resultado": "hay_candidatos", "candidatos": […]};
--   * `p_enlazar_con` = una fila mía (del deudor del vínculo, sin acordar, mismo monto y
--     dirección invertida) → esa fila queda `acordada` y no se crea otra;
--   * si no, se crea la fila espejo en mi libreta, con la dirección invertida. Un pago
--     espejo se reparte como cualquier pago automático (registrar_pago: cruce y FIFO).
-- tipo 'editar' / 'borrar': el cambio se aplica a las dos filas del acuerdo.
--
-- Idempotente: repetir con la misma `p_idem_key` devuelve la misma respuesta; con otra
-- clave, una propuesta ya resuelta es un error.
CREATE FUNCTION public.aceptar_propuesta(
    p_id uuid, p_enlazar_con uuid DEFAULT NULL, p_crear_nueva boolean DEFAULT false,
    p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid       uuid := auth.uid();
    t           record;
    v_prop      public.propuestas;
    v_vinc      public.vinculos;
    v_mi_deudor uuid;
    v_origen    jsonb;
    v_espejo    uuid;
    v_enlazada  boolean := false;
    v_cands     jsonb;
    v_res       jsonb;
    v_titulo    text;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO t FROM _tomar_propuesta(p_id);
    v_prop := t.prop;
    v_vinc := t.vinc;
    IF v_prop.para_usuario <> v_uid THEN
        RAISE EXCEPTION 'Solo quien recibe la propuesta puede aceptarla' USING ERRCODE = '42501';
    END IF;
    IF v_prop.estado <> 'pendiente' THEN
        IF p_idem_key IS NOT NULL AND v_prop.resuelta_idem = p_idem_key THEN
            RETURN v_prop.resultado;
        END IF;
        RAISE EXCEPTION 'La propuesta ya está resuelta (%)', v_prop.estado USING ERRCODE = '22023';
    END IF;
    IF v_vinc.estado = 'roto' THEN
        RAISE EXCEPTION 'El vínculo está roto' USING ERRCODE = '22023';
    END IF;
    v_mi_deudor := CASE WHEN v_vinc.usuario_a = v_uid THEN v_vinc.deudor_a ELSE v_vinc.deudor_b END;

    PERFORM set_config('deudas.en_rpc', 'on', true);

    IF v_prop.tipo = 'crear' THEN
        v_origen := _fila(v_prop.entidad, v_prop.fila_origen);
        IF v_origen IS NULL OR v_origen ->> 'estado_acuerdo' <> 'propuesta' THEN
            RAISE EXCEPTION 'La fila propuesta ya no está pendiente' USING ERRCODE = '22023';
        END IF;

        IF p_enlazar_con IS NULL AND NOT COALESCE(p_crear_nueva, false) THEN
            v_cands := _candidatos_espejo(v_prop.entidad, v_origen, v_mi_deudor);
            IF jsonb_array_length(v_cands) > 0 THEN
                PERFORM set_config('deudas.en_rpc', 'off', true);
                RETURN jsonb_build_object('resultado', 'hay_candidatos',
                                          'propuesta_id', p_id, 'candidatos', v_cands);
            END IF;
        END IF;

        IF p_enlazar_con IS NOT NULL THEN
            -- Capa 4: es una fila que ya tenía. Se valida de nuevo: el cliente no es de fiar.
            IF v_prop.entidad = 'deuda' THEN
                PERFORM 1 FROM deudas d
                 WHERE d.id = p_enlazar_con AND d.owner_id = v_uid AND d.deudor_id = v_mi_deudor
                   AND d.estado_acuerdo IN ('local', 'propuesta')
                   AND d.monto = (v_origen ->> 'monto')::numeric
                   AND d.es_mi_deuda = NOT (v_origen ->> 'es_mi_deuda')::boolean
                   FOR UPDATE;
            ELSE
                PERFORM 1 FROM pagos p
                 WHERE p.id = p_enlazar_con AND p.owner_id = v_uid AND p.deudor_id = v_mi_deudor
                   AND p.estado_acuerdo IN ('local', 'propuesta')
                   AND NOT COALESCE(p.es_compensacion, false)
                   AND p.monto_total = (v_origen ->> 'monto_total')::numeric
                   AND p.es_mi_pago = NOT (v_origen ->> 'es_mi_pago')::boolean
                   FOR UPDATE;
            END IF;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'No se puede enlazar con esa fila (no es tuya, ya está acordada o no cuadra en monto o dirección)'
                    USING ERRCODE = '22023';
            END IF;
            v_espejo := p_enlazar_con;
            v_enlazada := true;
            IF v_prop.entidad = 'deuda' THEN
                UPDATE deudas SET estado_acuerdo = 'acordada',
                                  origen_id = COALESCE(origen_id, v_prop.fila_origen)
                 WHERE id = v_espejo;
            ELSE
                UPDATE pagos SET estado_acuerdo = 'acordada',
                                 origen_id = COALESCE(origen_id, v_prop.fila_origen)
                 WHERE id = v_espejo;
            END IF;
            -- Si era una propuesta mía para el otro, este enlace también la resuelve.
            UPDATE propuestas
               SET estado = 'aceptada', fila_espejo = v_prop.fila_origen, resuelta_at = now()
             WHERE fila_origen = v_espejo AND tipo = 'crear' AND estado = 'pendiente';

        ELSIF v_prop.entidad = 'deuda' THEN
            -- Fila espejo nueva. `created_at` es el de ahora (el orden entre libretas no se
            -- compara, §10) y `origen_id` es la capa 2 de §4.5: una segunda aceptación
            -- chocaría con UNIQUE (owner_id, origen_id).
            SELECT COALESCE(NULLIF(btrim(v_prop.payload ->> 'titulo'), ''),
                            'Anotada por ' || nombre)
              INTO v_titulo FROM perfiles WHERE id = v_prop.de_usuario;
            INSERT INTO deudas (deudor_id, owner_id, titulo, monto, fecha_gasto, es_mi_deuda,
                                estado_acuerdo, origen_id, synced)
            VALUES (v_mi_deudor, v_uid, COALESCE(v_titulo, 'Propuesta aceptada'),
                    (v_origen ->> 'monto')::numeric, (v_origen ->> 'fecha_gasto')::date,
                    NOT (v_origen ->> 'es_mi_deuda')::boolean, 'acordada', v_prop.fila_origen, true)
            RETURNING id INTO v_espejo;
        ELSE
            -- Pago espejo: se registra como cualquier pago automático de mi libreta.
            v_res := registrar_pago(v_mi_deudor, (v_origen ->> 'monto_total')::numeric,
                                    NOT (v_origen ->> 'es_mi_pago')::boolean,
                                    (v_origen ->> 'fecha_pago')::date,
                                    _idem_derivada(p_id, 'espejo'));
            v_espejo := (v_res ->> 'pago_id')::uuid;
            IF v_espejo IS NULL THEN
                RAISE EXCEPTION 'El pago propuesto no tiene monto' USING ERRCODE = '22023';
            END IF;
            UPDATE pagos SET estado_acuerdo = 'acordada', origen_id = v_prop.fila_origen,
                             nota = NULLIF(btrim(v_prop.payload ->> 'nota'), '')
             WHERE id = v_espejo;
        END IF;

        IF v_prop.entidad = 'deuda' THEN
            UPDATE deudas SET estado_acuerdo = 'acordada' WHERE id = v_prop.fila_origen;
        ELSE
            UPDATE pagos SET estado_acuerdo = 'acordada' WHERE id = v_prop.fila_origen;
        END IF;
        INSERT INTO acuerdos (vinculo_id, entidad, fila_a, fila_b)
        VALUES (v_vinc.id, v_prop.entidad,
                CASE WHEN v_vinc.usuario_a = v_prop.de_usuario THEN v_prop.fila_origen ELSE v_espejo END,
                CASE WHEN v_vinc.usuario_a = v_prop.de_usuario THEN v_espejo ELSE v_prop.fila_origen END);
    ELSE
        v_espejo := _aplicar_cambio(v_prop);
    END IF;

    v_res := jsonb_build_object('resultado', 'aceptada', 'propuesta_id', p_id,
                                'tipo', v_prop.tipo, 'fila_espejo', v_espejo,
                                'enlazada', v_enlazada);
    UPDATE propuestas
       SET estado = 'aceptada', fila_espejo = v_espejo, resuelta_at = now(),
           resuelta_idem = p_idem_key, resultado = v_res
     WHERE id = p_id;

    PERFORM set_config('deudas.en_rpc', 'off', true);
    RETURN v_res;
END $$;

-- Aplica a las dos filas de un acuerdo una propuesta 'editar' o 'borrar' ya aceptada.
-- Devuelve la fila de quien acepta. Los campos del acuerdo cambian a la vez en las dos
-- libretas; el reparto de cada una se ajusta por su cuenta (§3.3, punto 4):
--   * dirección cambiada → la fila suelta todo su reparto (y sale de sus cruces);
--   * monto menor que lo ya repartido → suelta solo el exceso;
--   * borrar → sale de sus cruces y se borra (sus detalles se van en cascada).
-- Lo soltado queda como saldo a favor y estado_cuenta lo abona solo.
CREATE FUNCTION public._aplicar_cambio(p_prop public.propuestas) RETURNS uuid
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
    RETURN v_otra;
END $$;

-- Rechaza una propuesta dirigida a mí. SECURITY DEFINER: si era 'crear', la fila del otro
-- deja de contar (§4.2: se sacan sus cruces, se borra su reparto y queda `rechazada`). Si
-- era 'editar' o 'borrar', no se toca ninguna fila.
CREATE FUNCTION public.rechazar_propuesta(
    p_id uuid, p_motivo text DEFAULT NULL, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    t      record;
    v_prop public.propuestas;
    v_res  jsonb;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO t FROM _tomar_propuesta(p_id);
    v_prop := t.prop;
    IF v_prop.para_usuario <> auth.uid() THEN
        RAISE EXCEPTION 'Solo quien recibe la propuesta puede rechazarla' USING ERRCODE = '42501';
    END IF;
    IF v_prop.estado <> 'pendiente' THEN
        IF p_idem_key IS NOT NULL AND v_prop.resuelta_idem = p_idem_key THEN
            RETURN v_prop.resultado;
        END IF;
        RAISE EXCEPTION 'La propuesta ya está resuelta (%)', v_prop.estado USING ERRCODE = '22023';
    END IF;
    IF length(p_motivo) > 500 THEN
        RAISE EXCEPTION 'El motivo no puede pasar de 500 caracteres' USING ERRCODE = '22023';
    END IF;

    PERFORM set_config('deudas.en_rpc', 'on', true);
    IF v_prop.tipo = 'crear' THEN
        PERFORM _descontar_fila(v_prop.entidad, v_prop.fila_origen);
    END IF;
    v_res := jsonb_build_object('resultado', 'rechazada', 'propuesta_id', p_id, 'tipo', v_prop.tipo);
    UPDATE propuestas
       SET estado = 'rechazada', motivo = NULLIF(btrim(p_motivo), ''), resuelta_at = now(),
           resuelta_idem = p_idem_key, resultado = v_res
     WHERE id = p_id;
    PERFORM set_config('deudas.en_rpc', 'off', true);
    RETURN v_res;
END $$;

-- Quien propuso se arrepiente mientras sigue pendiente. Si era 'crear', su propia fila
-- queda `rechazada` (§4.2): el otro nunca la aceptó, así que no vale. SECURITY DEFINER
-- porque `propuestas` no se escribe directo.
CREATE FUNCTION public.anular_propuesta(p_id uuid) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    t      record;
    v_prop public.propuestas;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO t FROM _tomar_propuesta(p_id);
    v_prop := t.prop;
    IF v_prop.de_usuario <> auth.uid() THEN
        RAISE EXCEPTION 'Solo quien hizo la propuesta puede anularla' USING ERRCODE = '42501';
    END IF;
    IF v_prop.estado = 'anulada' THEN
        RETURN jsonb_build_object('resultado', 'anulada', 'propuesta_id', p_id, 'repetido', true);
    END IF;
    IF v_prop.estado <> 'pendiente' THEN
        RAISE EXCEPTION 'La propuesta ya está resuelta (%)', v_prop.estado USING ERRCODE = '22023';
    END IF;

    PERFORM set_config('deudas.en_rpc', 'on', true);
    IF v_prop.tipo = 'crear' THEN
        PERFORM _descontar_fila(v_prop.entidad, v_prop.fila_origen);
    END IF;
    UPDATE propuestas SET estado = 'anulada', resuelta_at = now() WHERE id = p_id;
    PERFORM set_config('deudas.en_rpc', 'off', true);
    RETURN jsonb_build_object('resultado', 'anulada', 'propuesta_id', p_id, 'repetido', false);
END $$;

-- Propone cambiar o borrar una fila acordada propia (§4.3). Mientras el otro no acepta,
-- las dos filas siguen igual. `p_payload` (solo para 'editar') trae lo que cambia, en MI
-- punto de vista: cualquiera de {monto, fecha, es_mia}; lo que falte queda como está. Una
-- sola propuesta pendiente por acuerdo, venga de quien venga.
CREATE FUNCTION public.proponer_cambio(
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
    IF EXISTS (SELECT 1 FROM propuestas
                WHERE fila_origen IN (p_fila, v_otra) AND estado = 'pendiente') THEN
        RAISE EXCEPTION 'Ya hay un cambio pendiente sobre esta fila' USING ERRCODE = '23505';
    END IF;

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

-- La invariante de §4.1: lo acordado de A con B es exactamente lo acordado de B con A con
-- el signo cambiado, y cada acuerdo ata una fila acordada de cada lado. SECURITY DEFINER:
-- lee las dos libretas (solo sumas). La llaman las dos partes, o la service_role (la
-- revisión diaria, 6.7).
CREATE FUNCTION public.verificar_vinculo(p_vinculo_id uuid) RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v       public.vinculos;
    v_neto_a numeric;
    v_neto_b numeric;
    v_huerfanos int;
BEGIN
    SELECT * INTO v FROM vinculos WHERE id = p_vinculo_id;
    IF NOT FOUND OR (auth.uid() IS NOT NULL AND auth.uid() NOT IN (v.usuario_a, v.usuario_b)) THEN
        RAISE EXCEPTION 'El vínculo % no existe o no es tuyo', p_vinculo_id USING ERRCODE = '42501';
    END IF;
    v_neto_a := _neto_por_estado(v.deudor_a, 'acordada');
    v_neto_b := _neto_por_estado(v.deudor_b, 'acordada');
    -- Filas acordadas sin acuerdo, o acuerdos sin sus dos filas acordadas.
    SELECT (SELECT count(*) FROM deudas WHERE deudor_id IN (v.deudor_a, v.deudor_b) AND estado_acuerdo = 'acordada')
         + (SELECT count(*) FROM pagos  WHERE deudor_id IN (v.deudor_a, v.deudor_b) AND estado_acuerdo = 'acordada')
         - 2 * (SELECT count(*) FROM acuerdos ac
                 WHERE ac.vinculo_id = v.id
                   AND EXISTS (SELECT 1 FROM deudas d WHERE d.id = ac.fila_a AND d.deudor_id = v.deudor_a AND d.estado_acuerdo = 'acordada'
                               UNION ALL
                               SELECT 1 FROM pagos p WHERE p.id = ac.fila_a AND p.deudor_id = v.deudor_a AND p.estado_acuerdo = 'acordada')
                   AND EXISTS (SELECT 1 FROM deudas d WHERE d.id = ac.fila_b AND d.deudor_id = v.deudor_b AND d.estado_acuerdo = 'acordada'
                               UNION ALL
                               SELECT 1 FROM pagos p WHERE p.id = ac.fila_b AND p.deudor_id = v.deudor_b AND p.estado_acuerdo = 'acordada'))
      INTO v_huerfanos;
    RETURN jsonb_build_object('vinculo_id', v.id, 'estado', v.estado,
                              'neto_a', v_neto_a, 'neto_b', v_neto_b,
                              'filas_sin_pareja', v_huerfanos,
                              'ok', v_neto_a = -v_neto_b AND v_huerfanos = 0);
END $$;

-- desvincular (fase 4) + §4.4 paso 6: las propuestas pendientes se anulan y las filas que
-- esperaban respuesta vuelven a ser solo de su libreta (`local`): siguen contando en mi
-- saldo, como antes de proponerlas. Lo acordado queda como está.
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
    UPDATE public.vinculos SET estado = 'roto', roto_at = now()
     WHERE id = p_vinculo_id AND estado <> 'roto';
    PERFORM set_config('deudas.en_rpc', 'off', true);
END $$;

-- ====================================================================================
-- Permisos
-- ====================================================================================

REVOKE ALL ON FUNCTION public._en_rpc()                                 FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._payload_de(text, jsonb)                  FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._neto_por_estado(uuid, text)              FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._bloquear_vinculo(public.vinculos)        FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._sacar_de_cruces(uuid)                    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._soltar_deuda(uuid, numeric)              FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._soltar_pago(uuid, numeric)               FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._descontar_fila(text, uuid)               FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._fila(text, uuid)                         FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._tomar_propuesta(uuid)                    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._candidatos_espejo(text, jsonb, uuid)     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._aplicar_cambio(public.propuestas)        FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._nace_propuesta()                         FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._nace_propuesta_post()                    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._propuesta_al_dia()                       FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._propuesta_sin_fila()                     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._guardia_acordada()                       FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._detalle_antes()                         FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.aceptar_propuesta(uuid, uuid, boolean, uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.rechazar_propuesta(uuid, text, uuid)      FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.anular_propuesta(uuid)                    FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.proponer_cambio(text, uuid, text, jsonb, uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.verificar_vinculo(uuid)                   FROM PUBLIC, anon;
-- estado_cuenta (SECURITY INVOKER) las usa con los permisos de quien llama.
GRANT EXECUTE ON FUNCTION public._en_rpc()                    TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._payload_de(text, jsonb)     TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._neto_por_estado(uuid, text) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.aceptar_propuesta(uuid, uuid, boolean, uuid)     TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rechazar_propuesta(uuid, text, uuid)             TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.anular_propuesta(uuid)                           TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.proponer_cambio(text, uuid, text, jsonb, uuid)   TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.verificar_vinculo(uuid)                          TO authenticated, service_role;
