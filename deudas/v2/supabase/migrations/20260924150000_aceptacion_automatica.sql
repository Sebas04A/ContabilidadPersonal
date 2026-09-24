-- Fase 8 (deudas/PLAN_MULTIUSUARIO.md §4.7 y §5.4): aceptación automática y avisos.
--
-- Con el vínculo `activo`, lo nuevo que anota uno ENTRA de una vez en la libreta del otro
-- y cuenta en los dos saldos; el otro recibe un aviso y lo puede rechazar cuando quiera.
-- Lo que necesita respuesta sigue siendo propuesta (decisiones 21 a 24 de §3.3, revisadas
-- por el dueño el 2026-09-24):
--   * deudas (en cualquier dirección) y pagos que anota QUIEN RECIBE la plata → entran
--     solos, con un aviso;
--   * pagos que anota quien la ENTREGA → propuesta: el que recibe confirma o dice "no lo
--     recibí" (§3.2: si no, cualquiera se marcaría "pagado" solo);
--   * más de 50 filas nuevas de una persona en un vínculo en 24 horas → propuesta (tope
--     contra abusos, decisión 24);
--   * cambiar o borrar algo acordado sigue siendo propuesta (proponer_cambio, decisión 22);
--   * la conciliación inicial no cambia (decisión 23).
--
-- Mecánica: `_nace_propuesta_post` sigue creando la propuesta y, si entra sola, la acepta
-- en la misma transacción EN NOMBRE DEL OTRO: `_llegada` pone su id en
-- `request.jwt.claim.sub` (lo primero que mira auth.uid()) y llama a aceptar_propuesta con
-- p_crear_nueva, que ya sabe crear el espejo, repartir un pago y atar el acuerdo. La
-- matemática y las reglas son las de la fase 6, sin copias. La invariante (acordado de A
-- = −acordado de B) se cumple desde el primer momento: las dos filas nacen juntas.
--
-- Avisos (`avisos`): los escriben los triggers y los RPC, nunca la app. deuda_nueva y
-- pago_nuevo (entró algo; si en la libreta del que recibe había algo parecido, trae los
-- candidatos para `fusionar_espejo`), pago_por_confirmar y propuesta (espera respuesta),
-- cambio y borrado (proponer_cambio), confirmado y rechazo (el otro respondió) y
-- desvinculado. Las notificaciones push (7.1) se colgarán del INSERT en esta tabla.
--
-- RPC nuevos: rechazar_fila (rechazar, cuando sea, algo que anotó el otro), fusionar_espejo
-- ("es la misma que ya tenía") y marcar_vistos.
--
-- registrar_pago, _nace_propuesta_post y exportar_mis_datos son copia exacta de su última
-- versión (20260924120000 y 20260924140000) más las líneas marcadas «v2 fase 8»; se
-- generaron con un script que exige que cada ancla aparezca una vez. Compruébalo con un
-- diff.

-- ====================================================================================
-- Avisos
-- ====================================================================================

CREATE TABLE public.avisos (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id   uuid NOT NULL REFERENCES public.perfiles ON DELETE CASCADE,  -- para quién
    tipo         text NOT NULL CHECK (tipo IN (
                     'deuda_nueva', 'pago_nuevo', 'pago_por_confirmar', 'propuesta',
                     'cambio', 'borrado', 'confirmado', 'rechazo', 'desvinculado',
                     -- fase 9 (§4.8)
                     'gasto_nuevo', 'gasto_en_revision', 'gasto_rechazado',
                     'pago_grupo_por_confirmar')),
    de_usuario   uuid,           -- quién lo causó (sin FK: su cuenta se puede borrar)
    entidad      text CHECK (entidad IN ('deuda', 'pago')),
    fila_id      uuid,           -- la fila de MI libreta, si la hay
    vinculo_id   uuid REFERENCES public.vinculos ON DELETE CASCADE,
    propuesta_id uuid REFERENCES public.propuestas ON DELETE CASCADE,
    grupo_id     uuid,           -- fase 9
    gasto_id     uuid,           -- fase 9
    -- En el punto de vista de quien lo recibe: monto, fecha, es_mia (yo debo / yo pagué),
    -- texto, y según el tipo candidatos, antes o motivo.
    datos        jsonb NOT NULL DEFAULT '{}',
    created_at   timestamptz NOT NULL DEFAULT now(),
    visto_at     timestamptz
);
CREATE INDEX idx_avisos_usuario   ON public.avisos (usuario_id, created_at);
CREATE INDEX idx_avisos_sin_ver   ON public.avisos (usuario_id) WHERE visto_at IS NULL;
CREATE INDEX idx_avisos_propuesta ON public.avisos (propuesta_id);
CREATE INDEX idx_avisos_fila      ON public.avisos (fila_id);

ALTER TABLE public.avisos ENABLE ROW LEVEL SECURITY;
CREATE POLICY propio_leer ON public.avisos FOR SELECT TO authenticated
    USING (usuario_id = (SELECT auth.uid()));
REVOKE ALL ON public.avisos FROM anon, authenticated;
GRANT SELECT ON public.avisos TO authenticated;

-- ====================================================================================
-- Piezas internas
-- ====================================================================================

-- Actuar como otro usuario dentro de un trigger o RPC SECURITY DEFINER: auth.uid() mira
-- primero `request.jwt.claim.sub`. Devuelve el valor anterior, para restaurarlo con otra
-- llamada. Es local a la transacción (un error lo deshace solo) y ningún cliente la puede
-- llamar.
CREATE FUNCTION public._suplantar(p_sub text) RETURNS text
    LANGUAGE plpgsql AS $$
DECLARE
    v_antes text := COALESCE(current_setting('request.jwt.claim.sub', true), '');
BEGIN
    PERFORM set_config('request.jwt.claim.sub', COALESCE(p_sub, ''), true);
    RETURN v_antes;
END $$;

-- Los candados de los dos deudores del vínculo vivo de un deudor, en orden fijo (los de
-- _bloquear_vinculo), si lo tiene. Para registrar_pago, que es SECURITY INVOKER.
CREATE FUNCTION public._candado_vinculo(p_deudor_id uuid) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v public.vinculos := _vinculo_de(p_deudor_id);
    d uuid;
BEGIN
    IF v.id IS NULL THEN
        RETURN;
    END IF;
    FOR d IN SELECT x FROM unnest(ARRAY[v.deudor_a, v.deudor_b]) x ORDER BY x::text LOOP
        PERFORM pg_advisory_xact_lock(hashtext(d::text));
    END LOOP;
END $$;

-- Filas nuevas que anotó `p_usuario` en el vínculo en las últimas 24 horas: las que
-- nacieron por el trigger (con su clave `crear`), hayan entrado solas o no. Las de la
-- conciliación no cuentan: son el historial, no el día a día.
CREATE FUNCTION public._nacidas_hoy(p_vinculo uuid, p_usuario uuid) RETURNS int
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT count(*)::int FROM propuestas
     WHERE vinculo_id = p_vinculo AND de_usuario = p_usuario AND tipo = 'crear'
       AND idem_key = _idem_derivada(fila_origen, 'crear')
       AND created_at > now() - interval '24 hours'
$$;

-- El tope de la decisión 24: filas nuevas por persona y vínculo en 24 horas que entran
-- solas. `deudas.tope_diario` lo cambia (un cliente no puede poner esa variable, igual que
-- `deudas.en_rpc`): sirve de freno de emergencia (`ALTER DATABASE postgres SET
-- deudas.tope_diario = 0` apaga la aceptación automática sin migrar nada) y a los tests
-- de la fase 6, que prueban el camino de la propuesta.
CREATE FUNCTION public._tope_diario() RETURNS int
    LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(current_setting('deudas.tope_diario', true), '')::int, 50)
$$;

-- ¿Es una propuesta de la conciliación (fase 5)? Esas no se avisan una por una: se
-- revisan en su pantalla (decisión 23). Nunca NULL: un cambio propuesto sin idem_key no
-- tiene clave, y un NULL aquí se tragaba su aviso.
CREATE FUNCTION public._es_de_conciliacion(p public.propuestas) RETURNS boolean
    LANGUAGE sql IMMUTABLE SET search_path = public AS $$
    SELECT COALESCE(p.idem_key IN (_idem_derivada(p.fila_origen, 'conciliacion|' || p.vinculo_id),
                                   _idem_derivada(p.fila_origen, 'conciliacion')), false)
$$;

-- Lo que una propuesta le cuenta a `p_para`, en SU punto de vista: el payload viene en el
-- de quien propone (§5.3), así que para el otro se invierte la dirección.
CREATE FUNCTION public._datos_propuesta(p public.propuestas, p_para uuid) RETURNS jsonb
    LANGUAGE sql STABLE AS $$
    SELECT jsonb_strip_nulls(jsonb_build_object(
        'tipo',   p.tipo,
        'monto',  p.payload -> 'monto',
        'fecha',  p.payload -> 'fecha',
        'es_mia', (p.payload ->> 'es_mia')::boolean = (p_para = p.de_usuario),
        'texto',  COALESCE(p.payload ->> 'titulo', p.payload ->> 'nota'),
        'antes',  CASE WHEN p.payload ? 'antes' THEN jsonb_build_object(
                      'monto',  p.payload -> 'antes' -> 'monto',
                      'fecha',  p.payload -> 'antes' -> 'fecha',
                      'es_mia', (p.payload -> 'antes' ->> 'es_mia')::boolean = (p_para = p.de_usuario))
                  END,
        'motivo', p.motivo))
$$;

-- Filas de la libreta de quien recibe (auth.uid(), ya suplantado) que podrían ser la misma
-- que acaba de llegar. Como `_candidatos_espejo` (misma entidad, dirección invertida,
-- mismo monto al centavo, fecha a ±3 días, sin cruces), pero también las `acordada`: con
-- todo entrando solo, lo más probable es que los dos anotaran lo mismo y lo del otro ya
-- hubiera entrado.
CREATE FUNCTION public._candidatos_duplicado(p_entidad text, p_origen jsonb, p_mi_deudor uuid)
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
           AND abs(d.fecha_gasto - (p_origen ->> 'fecha_gasto')::date) <= 3
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
           AND abs(p.fecha_pago - (p_origen ->> 'fecha_pago')::date) <= 3
      ) c
$$;

-- Una fila nueva llegó con el vínculo activo y su propuesta acaba de nacer (la llama
-- _nace_propuesta_post). Decide si entra sola (§4.7) y avisa al otro.
CREATE FUNCTION public._llegada(p_prop uuid) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_prop   public.propuestas;
    v_vinc   public.vinculos;
    v_origen jsonb;
    v_deudor uuid;          -- el deudor del vínculo en la libreta de quien recibe
    v_auto   boolean;
    v_previo text;
    v_cands  jsonb := '[]';
    v_res    jsonb;
    v_tipo   text;
BEGIN
    SELECT * INTO v_prop FROM propuestas WHERE id = p_prop;
    SELECT * INTO v_vinc FROM vinculos WHERE id = v_prop.vinculo_id;
    v_origen := _fila(v_prop.entidad, v_prop.fila_origen);
    v_deudor := CASE WHEN v_vinc.usuario_a = v_prop.para_usuario
                     THEN v_vinc.deudor_a ELSE v_vinc.deudor_b END;
    -- Entra sola: una deuda, o un pago que anota quien recibe la plata. Siempre bajo el
    -- tope (esta fila ya cuenta en él).
    v_auto := (v_prop.entidad = 'deuda'
               OR (NOT (v_origen ->> 'es_mi_pago')::boolean
                   AND (v_origen ->> 'monto_total')::numeric > 0.01))
          AND _nacidas_hoy(v_vinc.id, v_prop.de_usuario) <= _tope_diario();

    IF v_auto THEN
        -- Como quien recibe: sus candidatos y su aceptación.
        v_previo := _suplantar(v_prop.para_usuario::text);
        v_cands := _candidatos_duplicado(v_prop.entidad, v_origen, v_deudor);
        PERFORM set_config('deudas.sin_aviso', 'on', true);
        v_res := aceptar_propuesta(p_prop, NULL, true, NULL);
        PERFORM set_config('deudas.sin_aviso', 'off', true);
        PERFORM _suplantar(v_previo);
        v_tipo := CASE v_prop.entidad WHEN 'deuda' THEN 'deuda_nueva' ELSE 'pago_nuevo' END;
    ELSE
        v_tipo := CASE WHEN v_prop.entidad = 'pago' AND (v_origen ->> 'es_mi_pago')::boolean
                       THEN 'pago_por_confirmar' ELSE 'propuesta' END;
    END IF;

    INSERT INTO avisos (usuario_id, tipo, de_usuario, entidad, fila_id, vinculo_id,
                        propuesta_id, datos)
    VALUES (v_prop.para_usuario, v_tipo, v_prop.de_usuario, v_prop.entidad,
            (v_res ->> 'fila_espejo')::uuid, v_vinc.id, p_prop,
            _datos_propuesta(v_prop, v_prop.para_usuario)
            || CASE WHEN jsonb_array_length(v_cands) > 0
                    THEN jsonb_build_object('candidatos', v_cands) ELSE '{}' END);
END $$;

-- Las dos filas de un acuerdo dejan de contar (§4.2, en las dos libretas) y se desatan. El
-- motivo le llega a quien anotó la otra fila por su propuesta de 'crear', que pasa a
-- `rechazada`: la app ya lee los motivos de ahí, y el trigger de avisos le avisa. Si no la
-- hay (un par de la conciliación), el aviso se escribe directo.
CREATE FUNCTION public._rechazar_par(p_entidad text, p_mia uuid, p_otra uuid, p_motivo text)
    RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_ac   public.acuerdos;
    v_mia  jsonb := _fila(p_entidad, p_mia);
    v_otra jsonb := _fila(p_entidad, p_otra);
BEGIN
    SELECT * INTO v_ac FROM acuerdos WHERE entidad = p_entidad AND p_mia IN (fila_a, fila_b);
    PERFORM _descontar_fila(p_entidad, p_mia);
    PERFORM _descontar_fila(p_entidad, p_otra);
    DELETE FROM acuerdos WHERE id = v_ac.id;
    -- Un cambio que esperaba respuesta sobre estas filas ya no tiene sentido.
    UPDATE propuestas SET estado = 'anulada', resuelta_at = now()
     WHERE fila_origen IN (p_mia, p_otra) AND estado = 'pendiente';
    UPDATE propuestas
       SET estado = 'rechazada', motivo = NULLIF(btrim(p_motivo), ''), resuelta_at = now()
     WHERE fila_origen = p_otra AND tipo = 'crear' AND estado = 'aceptada';
    IF NOT FOUND THEN
        INSERT INTO avisos (usuario_id, tipo, de_usuario, entidad, fila_id, vinculo_id, datos)
        VALUES ((v_otra ->> 'owner_id')::uuid, 'rechazo', (v_mia ->> 'owner_id')::uuid,
                p_entidad, p_otra, v_ac.vinculo_id,
                (_payload_de(p_entidad, v_otra) - 'titulo' - 'nota')
                || jsonb_strip_nulls(jsonb_build_object(
                       'tipo',   'crear',
                       'texto',  COALESCE(v_otra ->> 'titulo', v_otra ->> 'nota'),
                       'motivo', NULLIF(btrim(p_motivo), ''))));
    END IF;
END $$;

-- ====================================================================================
-- Triggers de avisos
-- ====================================================================================

-- AFTER INSERT OR UPDATE OF estado en propuestas:
--   * nace un cambio o un borrado de algo acordado → aviso al otro (`cambio`/`borrado`);
--     las de 'crear' las avisa _llegada, que sabe si entraron solas;
--   * se responde → aviso a quien propuso (`confirmado`/`rechazo`) y lo pendiente de
--     quien respondió queda visto. Una aceptación de la conciliación no se avisa (serían
--     cientos de una vez); un rechazo sí;
--   * se anula → se va lo que no se vio: ya no hay nada que responder.
-- `deudas.sin_aviso` lo apaga: lo pone _llegada mientras acepta en nombre del otro (ese
-- aviso es el de deuda_nueva o pago_nuevo) y fusionar_espejo.
CREATE FUNCTION public._aviso_propuesta() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_fila uuid;
BEGIN
    IF COALESCE(current_setting('deudas.sin_aviso', true), '') = 'on' THEN
        RETURN NULL;
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.tipo IN ('editar', 'borrar') THEN
            SELECT CASE WHEN fila_a = NEW.fila_origen THEN fila_b ELSE fila_a END INTO v_fila
              FROM acuerdos
             WHERE vinculo_id = NEW.vinculo_id AND entidad = NEW.entidad
               AND NEW.fila_origen IN (fila_a, fila_b);
            INSERT INTO avisos (usuario_id, tipo, de_usuario, entidad, fila_id, vinculo_id,
                                propuesta_id, datos)
            VALUES (NEW.para_usuario, CASE NEW.tipo WHEN 'editar' THEN 'cambio' ELSE 'borrado' END,
                    NEW.de_usuario, NEW.entidad, v_fila, NEW.vinculo_id, NEW.id,
                    _datos_propuesta(NEW, NEW.para_usuario));
        END IF;
        RETURN NULL;
    END IF;

    IF NEW.estado = OLD.estado THEN
        RETURN NULL;
    END IF;
    IF NEW.estado = 'anulada' THEN
        DELETE FROM avisos WHERE propuesta_id = NEW.id AND visto_at IS NULL;
    ELSIF NEW.estado IN ('aceptada', 'rechazada') THEN
        UPDATE avisos SET visto_at = now()
         WHERE propuesta_id = NEW.id AND usuario_id = NEW.para_usuario AND visto_at IS NULL;
        IF NEW.estado = 'rechazada'
           OR (OLD.estado = 'pendiente' AND NOT _es_de_conciliacion(NEW)) THEN
            INSERT INTO avisos (usuario_id, tipo, de_usuario, entidad, fila_id, vinculo_id,
                                propuesta_id, datos)
            VALUES (NEW.de_usuario,
                    CASE NEW.estado WHEN 'aceptada' THEN 'confirmado' ELSE 'rechazo' END,
                    NEW.para_usuario, NEW.entidad,
                    -- Un borrado aceptado ya no tiene fila.
                    CASE WHEN NEW.tipo = 'borrar' AND NEW.estado = 'aceptada'
                         THEN NULL ELSE NEW.fila_origen END,
                    NEW.vinculo_id, NEW.id, _datos_propuesta(NEW, NEW.de_usuario));
        END IF;
    END IF;
    RETURN NULL;
END $$;

-- AFTER UPDATE OF estado en vinculos: al romperse, aviso a la otra parte (a las dos si lo
-- rompe la service_role). Una cuenta que se está borrando ya no tiene perfil.
CREATE FUNCTION public._aviso_vinculo() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF NEW.estado = 'roto' AND OLD.estado <> 'roto' THEN
        INSERT INTO avisos (usuario_id, tipo, de_usuario, vinculo_id)
        SELECT u, 'desvinculado', auth.uid(), NEW.id
          FROM unnest(ARRAY[NEW.usuario_a, NEW.usuario_b]) u
         WHERE u IS DISTINCT FROM auth.uid()
           AND EXISTS (SELECT 1 FROM perfiles WHERE id = u)
         ORDER BY u;
    END IF;
    RETURN NULL;
END $$;

CREATE TRIGGER aviso_propuesta AFTER INSERT OR UPDATE OF estado ON public.propuestas
    FOR EACH ROW EXECUTE FUNCTION public._aviso_propuesta();
CREATE TRIGGER aviso_vinculo AFTER UPDATE OF estado ON public.vinculos
    FOR EACH ROW EXECUTE FUNCTION public._aviso_vinculo();

-- ====================================================================================
-- Funciones existentes (copia exacta + «v2 fase 8»)
-- ====================================================================================

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
    -- v2 fase 8: con vínculo vivo, primero los candados de los dos deudores, en orden   -- v2 fase 8
    -- fijo. Un pago que anota quien recibe crea su espejo en la libreta del otro (y los   -- v2 fase 8
    -- toma ahí); tomarlos después del propio podía trabar a los dos (40P01).             -- v2 fase 8
    PERFORM _candado_vinculo(p_deudor_id);                                              -- v2 fase 8
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


CREATE OR REPLACE FUNCTION public._nace_propuesta_post() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v       public.vinculos;
    v_ent   text := CASE TG_TABLE_NAME WHEN 'deudas' THEN 'deuda' ELSE 'pago' END;
    v_prop  uuid;   -- v2 fase 8
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
    -- v2 fase 8: entra de una vez en la libreta del otro, o espera respuesta (§4.7).   -- v2 fase 8
    SELECT id INTO v_prop FROM propuestas                                              -- v2 fase 8
     WHERE idem_key = _idem_derivada(NEW.id, 'crear') AND estado = 'pendiente';        -- v2 fase 8
    IF v_prop IS NOT NULL THEN                                                         -- v2 fase 8
        PERFORM _llegada(v_prop);                                                      -- v2 fase 8
    END IF;                                                                            -- v2 fase 8
    RETURN NULL;
END $$;


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
        'avisos',          (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.created_at, x.id), '[]') FROM avisos x));    -- v2 fase 8
END $$;


-- ====================================================================================
-- RPC
-- ====================================================================================

-- Rechazar algo que la otra persona anotó y entró solo a mi libreta (§4.7), en cualquier
-- momento: las dos filas pasan a `rechazada` (§4.2 en las dos libretas: cruces, reparto,
-- saldo a favor) y el otro recibe el aviso con el motivo. Solo sobre filas que anotó el
-- otro (`origen_id`): lo que anoté yo se cambia o se borra proponiéndolo (decisión 22), y
-- lo emparejado en la conciliación ya lo aceptaron los dos. Repetirlo no hace nada.
-- `p_idem_key` es para la cola sin conexión de la app: rechazar ya es idempotente.
CREATE FUNCTION public.rechazar_fila(
    p_entidad text, p_fila uuid, p_motivo text DEFAULT NULL, p_idem_key uuid DEFAULT NULL)
    RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid  uuid := auth.uid();
    v_fila jsonb;
    v_vinc public.vinculos;
    v_otra uuid;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    IF p_entidad IS NULL OR p_entidad NOT IN ('deuda', 'pago') THEN
        RAISE EXCEPTION 'Entidad desconocida: %', p_entidad USING ERRCODE = '22023';
    END IF;
    IF length(p_motivo) > 500 THEN
        RAISE EXCEPTION 'El motivo no puede pasar de 500 caracteres' USING ERRCODE = '22023';
    END IF;
    v_fila := CASE WHEN p_entidad = 'deuda'
                   THEN (SELECT to_jsonb(d) FROM deudas d WHERE id = p_fila AND owner_id = v_uid)
                   ELSE (SELECT to_jsonb(p) FROM pagos p WHERE id = p_fila AND owner_id = v_uid) END;
    IF v_fila IS NULL THEN
        RAISE EXCEPTION 'La fila % no existe o no es tuya', p_fila USING ERRCODE = '42501';
    END IF;
    v_vinc := _vinculo_de((v_fila ->> 'deudor_id')::uuid);
    IF v_vinc.id IS NOT NULL THEN
        PERFORM _bloquear_vinculo(v_vinc);
        v_fila := _fila(p_entidad, p_fila);   -- releer tras el candado
    END IF;
    IF v_fila ->> 'estado_acuerdo' = 'rechazada' THEN
        RETURN jsonb_build_object('resultado', 'rechazada', 'fila', p_fila, 'repetido', true);
    END IF;
    IF v_vinc.id IS NULL THEN
        RAISE EXCEPTION 'El contacto ya no está vinculado: esta fila se edita directo'
            USING ERRCODE = '22023';
    END IF;
    IF v_fila ->> 'estado_acuerdo' <> 'acordada' OR v_fila ->> 'origen_id' IS NULL THEN
        RAISE EXCEPTION 'Solo se rechaza lo que anotó la otra persona; lo tuyo se cambia o se borra proponiéndolo'
            USING ERRCODE = '22023';
    END IF;
    SELECT CASE WHEN fila_a = p_fila THEN fila_b ELSE fila_a END INTO v_otra
      FROM acuerdos
     WHERE vinculo_id = v_vinc.id AND entidad = p_entidad AND p_fila IN (fila_a, fila_b);
    IF v_otra IS NULL THEN
        RAISE EXCEPTION 'La fila ya no está acordada' USING ERRCODE = '22023';
    END IF;

    PERFORM set_config('deudas.en_rpc', 'on', true);
    PERFORM _rechazar_par(p_entidad, p_fila, v_otra, p_motivo);
    UPDATE avisos SET visto_at = now()
     WHERE usuario_id = v_uid AND fila_id = p_fila AND visto_at IS NULL;
    PERFORM set_config('deudas.en_rpc', 'off', true);
    RETURN jsonb_build_object('resultado', 'rechazada', 'fila', p_fila, 'repetido', false);
END $$;

-- "Es la misma que ya tenía" (decisión 21, para cuando el aviso previo de la app no
-- alcanzó: sin conexión o sin sync reciente). `p_espejo` es la fila que entró sola a mi
-- libreta; `p_existente`, la mía que era lo mismo (uno de los candidatos del aviso):
--   * si la mía ya estaba acordada (los dos lo anotaron y lo del otro ya había entrado),
--     el par nuevo sobra: sus dos filas pasan a `rechazada` y al otro le llega "ya estaba
--     anotada" (modo 'sobraba');
--   * si la mía era solo mía (`local`) o esperaba respuesta (`propuesta`), ocupa el lugar
--     del espejo: queda acordada con la fila del otro y el espejo se borra soltando su
--     reparto (§4.2). Mi propuesta, si la había, queda aceptada por el enlace (modo
--     'enlazada').
-- Repetirlo devuelve 'repetido'.
CREATE FUNCTION public.fusionar_espejo(
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
            AND abs((v_ex ->> 'fecha_gasto')::date - (v_esp ->> 'fecha_gasto')::date) <= 3;
    ELSE
        v_ok := v_ok
            AND NOT COALESCE((v_ex ->> 'es_compensacion')::boolean, false)
            AND (v_ex ->> 'es_mi_pago')::boolean = (v_esp ->> 'es_mi_pago')::boolean
            AND (v_ex ->> 'monto_total')::numeric = (v_esp ->> 'monto_total')::numeric
            AND abs((v_ex ->> 'fecha_pago')::date - (v_esp ->> 'fecha_pago')::date) <= 3;
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

-- Marca mis avisos como vistos: los de `p_ids`, o todos si es NULL. Devuelve cuántos.
CREATE FUNCTION public.marcar_vistos(p_ids uuid[] DEFAULT NULL) RETURNS int
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_n int;
BEGIN
    IF auth.uid() IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    UPDATE avisos SET visto_at = now()
     WHERE usuario_id = auth.uid() AND visto_at IS NULL
       AND (p_ids IS NULL OR id = ANY (p_ids));
    GET DIAGNOSTICS v_n = ROW_COUNT;
    RETURN v_n;
END $$;

-- ====================================================================================
-- Lo que esperaba respuesta al aplicar esta migración
-- ====================================================================================

-- Lo nacido por el trigger que ahora entraría solo, entra; lo demás recibe su aviso (8.1).
-- En la nube de prueba no hay nada pendiente (comprobado antes de subirla); queda por si
-- esta migración se aplica sobre datos con vínculos.
DO $$
DECLARE
    r record;
BEGIN
    FOR r IN SELECT id FROM public.propuestas
              WHERE estado = 'pendiente' AND tipo = 'crear'
                AND idem_key = public._idem_derivada(fila_origen, 'crear')
              ORDER BY created_at, id LOOP
        PERFORM public._llegada(r.id);
    END LOOP;
END $$;

-- ====================================================================================
-- Permisos
-- ====================================================================================

REVOKE ALL ON FUNCTION public._suplantar(text)                          FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._candado_vinculo(uuid)                    FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._nacidas_hoy(uuid, uuid)                  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._tope_diario()                           FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._es_de_conciliacion(public.propuestas)    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._datos_propuesta(public.propuestas, uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._candidatos_duplicado(text, jsonb, uuid)  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._llegada(uuid)                            FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._rechazar_par(text, uuid, uuid, text)     FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._aviso_propuesta()                        FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._aviso_vinculo()                          FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.rechazar_fila(text, uuid, text, uuid)     FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.fusionar_espejo(text, uuid, uuid, uuid)   FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.marcar_vistos(uuid[])                     FROM PUBLIC, anon;
-- registrar_pago (SECURITY INVOKER) toma los candados con los permisos de quien llama.
GRANT EXECUTE ON FUNCTION public._candado_vinculo(uuid)                   TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.rechazar_fila(text, uuid, text, uuid)    TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.fusionar_espejo(text, uuid, uuid, uuid)  TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.marcar_vistos(uuid[])                    TO authenticated, service_role;
