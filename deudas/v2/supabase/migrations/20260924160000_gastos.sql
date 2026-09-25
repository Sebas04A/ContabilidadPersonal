-- Fase 9A (deudas/PLAN_MULTIUSUARIO.md §4.8 y §5.4): gastos divididos, primero el "gasto
-- suelto": anotar una cuenta dividida entre varios contactos de mi libreta (y yo), sin
-- crear un grupo. Decisiones 25 a 31 de §3.3, aprobadas por el dueño el 2026-09-24.
--
--   * `gastos` + `gasto_participantes` guardan el gasto como registro propio (§3.2): cuánto
--     PUSO cada uno (`pagado`) y cuánto le TOCA (`parte`). Por ahora lo paga una sola
--     persona; la tabla ya sirve para varios pagadores (9C).
--   * Cada parte de un contacto se vuelve una DEUDA NORMAL de mi libreta con `gasto_id`:
--     `estado_cuenta` no cambia y un contacto vinculado la recibe como cualquier deuda
--     (fase 8: entra sola, con su aviso). Si pagó un contacto, en mi libreta queda solo lo
--     que yo le debo (decisión 31).
--   * `_repartir` divide el monto (decisión 25: centavos truncados y los que sobran, de a
--     uno, primero a quien pagó). La misma función vive en Dart (lib/dominio/reparto.dart)
--     con un test de paridad.
--   * Una deuda de un gasto no se edita suelta: monto, fecha, dirección, contacto y
--     borrado van por editar_gasto/borrar_gasto (`_guardia_gasto`). Si la deuda está
--     acordada con un contacto vinculado, el cambio o el borrado se le PROPONE (decisión 22,
--     que manda sobre el caso 7 de 9.2). El título sí se edita suelto.
--   * Nadie escribe directo en las tablas del gasto: todo va por RPC.
--
-- Los grupos (9B) llegan en 20260924170000_grupos.sql: aquí `gastos.grupo_id` y
-- `gasto_participantes.miembro_id` todavía no tienen FK, y las ramas de grupo de los RPC
-- son funciones que esa migración reemplaza.
--
-- `proponer_cambio` y `exportar_mis_datos` son copia exacta de su última versión
-- (20260924120000 y 20260924150000) más las líneas marcadas «v2 fase 9»; se generaron con
-- un script que exige que cada ancla aparezca una vez. Compruébalo con un diff.

-- ====================================================================================
-- Tablas
-- ====================================================================================

CREATE TABLE public.gastos (
    id          uuid PRIMARY KEY,                -- lo genera el teléfono (idempotencia)
    grupo_id    uuid,                            -- NULL = gasto suelto (FK en 20260924170000)
    -- SET NULL: en un grupo, el gasto sigue siendo de todos aunque quien lo anotó borre su
    -- cuenta. Un gasto suelto sin dueño lo borra `_perfil_sin_gastos`.
    creado_por  uuid DEFAULT auth.uid() REFERENCES public.perfiles ON DELETE SET NULL,
    titulo      text NOT NULL CHECK (btrim(titulo) <> '' AND length(titulo) <= 200),
    monto_total numeric(10,2) NOT NULL CHECK (monto_total > 0),
    fecha       date NOT NULL,
    modo        text NOT NULL DEFAULT 'igual'
                CHECK (modo IN ('igual', 'montos', 'porcentaje', 'partes')),
    estado      text NOT NULL DEFAULT 'activo'
                CHECK (estado IN ('activo', 'en_revision', 'rechazado')),
    idem_key    uuid,                            -- la de crear_gasto
    edit_idem   uuid,                            -- la del último editar_gasto
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_gastos_idem   ON public.gastos (creado_por, idem_key) WHERE idem_key IS NOT NULL;
CREATE INDEX idx_gastos_creador       ON public.gastos (creado_por, updated_at);
CREATE INDEX idx_gastos_grupo         ON public.gastos (grupo_id, updated_at);
COMMENT ON TABLE public.gastos IS 'Gasto dividido (suelto o de un grupo). Solo por RPC.';

CREATE TABLE public.gasto_participantes (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gasto_id   uuid NOT NULL REFERENCES public.gastos ON DELETE CASCADE,
    orden      smallint NOT NULL,                -- el de la lista: decide a quién van los centavos
    miembro_id uuid,                             -- gasto de grupo (FK en 20260924170000)
    -- Gasto suelto: un contacto de la libreta de quien lo anotó. Miembro y deudor NULL =
    -- quien lo anotó. CASCADE: borrar el contacto lo saca del gasto (su deuda ya se fue).
    deudor_id  uuid REFERENCES public.deudores ON DELETE CASCADE,
    pagado     numeric(10,2) NOT NULL DEFAULT 0 CHECK (pagado >= 0),
    parte      numeric(10,2) NOT NULL DEFAULT 0 CHECK (parte >= 0),
    -- Para repartir de nuevo: 1 en 'igual', el % en 'porcentaje', las partes en 'partes' y
    -- el monto fijo en 'montos'. NULL = no participa del reparto (quien pagó sin incluirse).
    peso       numeric CHECK (peso > 0),
    estado     text NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'rechazada')),
    motivo     text,
    deuda_id   uuid REFERENCES public.deudas ON DELETE SET NULL,  -- gasto suelto: la deuda que generó
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (gasto_id, miembro_id, deudor_id),
    CHECK (miembro_id IS NULL OR deudor_id IS NULL),
    CHECK (peso IS NOT NULL OR pagado > 0)
);
CREATE INDEX idx_gasto_part_gasto  ON public.gasto_participantes (gasto_id, orden);
CREATE INDEX idx_gasto_part_deuda  ON public.gasto_participantes (deuda_id);
CREATE INDEX idx_gasto_part_deudor ON public.gasto_participantes (deudor_id);

-- La deuda que generó un gasto suelto. SET NULL: si el gasto se borra y la deuda sigue
-- (estaba acordada y el otro todavía no aceptó el borrado), queda como deuda normal.
ALTER TABLE public.deudas ADD COLUMN gasto_id uuid REFERENCES public.gastos ON DELETE SET NULL;
CREATE INDEX idx_deudas_gasto ON public.deudas (gasto_id) WHERE gasto_id IS NOT NULL;

-- Lápidas de lo borrado del gasto, para el pull incremental (`cambios_gastos`). No van en
-- `borrados`: lo de un grupo lo tienen que ver TODOS sus miembros, no un solo dueño.
CREATE TABLE public.borrados_gastos (
    tabla    text        NOT NULL,
    id       uuid        NOT NULL,
    grupo_id uuid,                               -- lo de un grupo
    owner_id uuid,                               -- lo de un gasto suelto
    at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tabla, id)
);
CREATE INDEX idx_borrados_gastos_grupo ON public.borrados_gastos (grupo_id, at);
CREATE INDEX idx_borrados_gastos_owner ON public.borrados_gastos (owner_id, at);

CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.gastos
    FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();
CREATE TRIGGER tocar_updated_at BEFORE UPDATE ON public.gasto_participantes
    FOR EACH ROW EXECUTE FUNCTION public._tocar_updated_at();

-- ====================================================================================
-- RLS: un gasto suelto lo ve solo quien lo anotó (20260924170000 suma los de mis
-- grupos). Nadie escribe directo.
-- ====================================================================================

ALTER TABLE public.gastos ENABLE ROW LEVEL SECURITY;
CREATE POLICY ver ON public.gastos FOR SELECT TO authenticated
    USING (grupo_id IS NULL AND creado_por = (SELECT auth.uid()));
REVOKE ALL ON public.gastos FROM anon, authenticated;
GRANT SELECT ON public.gastos TO authenticated;

-- El subquery pasa por el RLS de `gastos`: veo los participantes de los gastos que veo.
ALTER TABLE public.gasto_participantes ENABLE ROW LEVEL SECURITY;
CREATE POLICY ver ON public.gasto_participantes FOR SELECT TO authenticated
    USING (EXISTS (SELECT 1 FROM public.gastos g WHERE g.id = gasto_id));
REVOKE ALL ON public.gasto_participantes FROM anon, authenticated;
GRANT SELECT ON public.gasto_participantes TO authenticated;

ALTER TABLE public.borrados_gastos ENABLE ROW LEVEL SECURITY;
CREATE POLICY ver ON public.borrados_gastos FOR SELECT TO authenticated
    USING (owner_id = (SELECT auth.uid()));
REVOKE ALL ON public.borrados_gastos FROM anon, authenticated;
GRANT SELECT ON public.borrados_gastos TO authenticated;

-- ====================================================================================
-- Repartir (decisión 25)
-- ====================================================================================

-- Reparte `p_monto` según `p_pesos`: cada parte se trunca al centavo y los centavos que
-- sobran se dan de a uno, primero a la posición `p_primero` (quien pagó, si participa) y
-- después en el orden de la lista. La suma cuadra siempre: $100 entre 3 → 33.34, 33.33,
-- 33.33. Todo en centavos enteros: `div` es la división entera exacta, así el resultado no
-- depende de la precisión de la división (lib/dominio/reparto.dart hace lo mismo con
-- enteros, y el test de paridad lo comprueba).
CREATE FUNCTION public._repartir(p_monto numeric, p_pesos numeric[], p_primero int DEFAULT NULL)
    RETURNS numeric[]
    LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_n      int := COALESCE(array_length(p_pesos, 1), 0);
    v_cent   numeric := round(p_monto * 100);
    v_total  numeric;
    v_partes numeric[];
    v_orden  int[];
    v_resto  numeric;
    i        int;
BEGIN
    IF v_n = 0 THEN
        RAISE EXCEPTION 'No hay entre quiénes repartir' USING ERRCODE = '22023';
    END IF;
    IF p_monto IS NULL OR p_monto <= 0 THEN
        RAISE EXCEPTION 'El monto a repartir tiene que ser mayor que cero' USING ERRCODE = '22023';
    END IF;
    IF EXISTS (SELECT 1 FROM unnest(p_pesos) w WHERE w IS NULL OR w <= 0) THEN
        RAISE EXCEPTION 'Cada parte tiene que ser mayor que cero' USING ERRCODE = '22023';
    END IF;
    v_total := (SELECT sum(w) FROM unnest(p_pesos) w);
    v_partes := array_fill(0::numeric, ARRAY[v_n]);
    FOR i IN 1..v_n LOOP
        v_partes[i] := div(v_cent * p_pesos[i], v_total);
    END LOOP;
    v_resto := v_cent - (SELECT sum(x) FROM unnest(v_partes) x);
    v_orden := CASE WHEN p_primero BETWEEN 1 AND v_n THEN ARRAY[p_primero] ELSE '{}'::int[] END
            || ARRAY(SELECT g FROM generate_series(1, v_n) g
                      WHERE g IS DISTINCT FROM p_primero ORDER BY g);
    i := 1;
    WHILE v_resto > 0 LOOP
        v_partes[v_orden[i]] := v_partes[v_orden[i]] + 1;
        v_resto := v_resto - 1;
        i := i % v_n + 1;
    END LOOP;
    RETURN ARRAY(SELECT round(x / 100, 2) FROM unnest(v_partes) WITH ORDINALITY u(x, o) ORDER BY o);
END $$;

-- ====================================================================================
-- Piezas internas
-- ====================================================================================

-- La llave de los RPC del gasto: deja a `_guardia_gasto` poner `gasto_id` y tocar las
-- deudas de un gasto, y a `proponer_cambio` proponer sobre ellas. Como `deudas.en_rpc`,
-- un cliente no la puede poner y se apaga antes de volver.
CREATE FUNCTION public._en_gasto() RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT COALESCE(current_setting('deudas.en_gasto', true), '') = 'on'
$$;

-- Valida lo que manda el cliente y lo deja normalizado. `p_participantes` es una lista de
-- {miembro_id | deudor_id | (ninguno = yo), pagado, participa, peso, deuda_id, reincluir}:
--   * `pagado`: lo que puso; por ahora exactamente uno pone el total;
--   * `participa` (sí por defecto): no participar solo lo puede quien pagó;
--   * `peso`: el % ('porcentaje'), las partes ('partes') o el monto ('montos'); en
--     'igual' se ignora;
--   * `deuda_id`: el id que el teléfono quiere para la deuda de esa parte (gasto suelto),
--     para mostrarla antes de sincronizar;
--   * `reincluir`: en un grupo, vuelve a incluir a quien había rechazado su parte.
-- Devuelve {titulo, monto, fecha, modo, pagador (posición), filas}. Quién puede estar en
-- la lista (contactos míos, miembros del grupo) lo comprueba quien la llama.
CREATE FUNCTION public._leer_gasto(
    p_titulo text, p_monto numeric, p_fecha date, p_modo text, p_participantes jsonb)
    RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_monto   numeric := round(p_monto, 2);
    v_filas   jsonb := '[]';
    v_e       jsonb;
    v_pagado  numeric;
    v_peso    numeric;
    v_pagador int;
    v_suma    numeric := 0;
    v_pagos   numeric := 0;
    v_claves  text[] := '{}';
    v_clave   text;
    i         int := 0;
BEGIN
    IF btrim(COALESCE(p_titulo, '')) = '' OR length(p_titulo) > 200 THEN
        RAISE EXCEPTION 'El gasto necesita un título (hasta 200 caracteres)' USING ERRCODE = '22023';
    END IF;
    IF v_monto IS NULL OR v_monto <= 0 OR v_monto >= 100000000 THEN
        RAISE EXCEPTION 'El monto del gasto tiene que ser mayor que cero' USING ERRCODE = '22023';
    END IF;
    IF p_fecha IS NULL THEN
        RAISE EXCEPTION 'Falta la fecha del gasto' USING ERRCODE = '22023';
    END IF;
    IF p_modo IS NULL OR p_modo NOT IN ('igual', 'montos', 'porcentaje', 'partes') THEN
        RAISE EXCEPTION 'Modo de reparto desconocido: %', p_modo USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(p_participantes) IS DISTINCT FROM 'array' OR jsonb_array_length(p_participantes) = 0 THEN
        RAISE EXCEPTION 'Faltan los participantes del gasto' USING ERRCODE = '22023';
    END IF;
    IF jsonb_array_length(p_participantes) > 50 THEN
        RAISE EXCEPTION 'Un gasto se divide entre 50 personas como mucho' USING ERRCODE = '22023';
    END IF;

    FOR v_e IN SELECT e FROM jsonb_array_elements(p_participantes) WITH ORDINALITY x(e, o) ORDER BY o LOOP
        i := i + 1;
        IF jsonb_typeof(v_e) <> 'object' OR (v_e ? 'miembro_id' AND v_e ? 'deudor_id') THEN
            RAISE EXCEPTION 'Participante inválido: %', v_e USING ERRCODE = '22023';
        END IF;
        v_clave := COALESCE(v_e ->> 'miembro_id', v_e ->> 'deudor_id', 'yo');
        IF v_clave = ANY (v_claves) THEN
            RAISE EXCEPTION 'Una persona aparece dos veces en el gasto' USING ERRCODE = '22023';
        END IF;
        v_claves := v_claves || v_clave;

        v_pagado := round(COALESCE((v_e ->> 'pagado')::numeric, 0), 2);
        IF v_pagado < 0 THEN
            RAISE EXCEPTION 'Lo que puso cada uno no puede ser negativo' USING ERRCODE = '22023';
        END IF;
        IF COALESCE((v_e ->> 'participa')::boolean, true) THEN
            v_peso := CASE p_modo WHEN 'igual' THEN 1
                                  WHEN 'montos' THEN round((v_e ->> 'peso')::numeric, 2)
                                  ELSE round((v_e ->> 'peso')::numeric, 4) END;
            IF v_peso IS NULL OR v_peso <= 0 THEN
                RAISE EXCEPTION 'A cada participante le falta su %', CASE p_modo
                    WHEN 'montos' THEN 'monto' WHEN 'porcentaje' THEN 'porcentaje' ELSE 'número de partes' END
                    USING ERRCODE = '22023';
            END IF;
            v_suma := v_suma + v_peso;
        ELSE
            v_peso := NULL;
        END IF;
        IF v_pagado > 0 THEN
            IF v_pagador IS NOT NULL THEN
                RAISE EXCEPTION 'Por ahora un gasto lo paga una sola persona' USING ERRCODE = '22023';
            END IF;
            v_pagador := i;
        END IF;
        v_pagos := v_pagos + v_pagado;
        v_filas := v_filas || jsonb_build_object(
            'miembro_id', v_e -> 'miembro_id',
            'deudor_id',  v_e -> 'deudor_id',
            'deuda_id',   v_e -> 'deuda_id',
            'pagado',     v_pagado,
            'peso',       v_peso,
            'reincluir',  COALESCE((v_e ->> 'reincluir')::boolean, false));
    END LOOP;

    IF v_pagador IS NULL OR v_pagos <> v_monto THEN
        RAISE EXCEPTION 'Quien pagó tiene que haber puesto el total del gasto ($%)', v_monto
            USING ERRCODE = '22023';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_filas) WITH ORDINALITY x(f, o)
                WHERE f -> 'peso' = 'null' AND o <> v_pagador) THEN
        RAISE EXCEPTION 'Solo quien pagó puede quedar fuera del reparto' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM jsonb_array_elements(v_filas) WITH ORDINALITY x(f, o)
                    WHERE f -> 'peso' <> 'null' AND o <> v_pagador) THEN
        RAISE EXCEPTION 'Un gasto dividido necesita al menos a otra persona además de quien pagó'
            USING ERRCODE = '22023';
    END IF;
    IF p_modo = 'montos' AND v_suma <> v_monto THEN
        RAISE EXCEPTION 'Los montos suman $% y el gasto es de $%', v_suma, v_monto USING ERRCODE = '22023';
    END IF;
    IF p_modo = 'porcentaje' AND v_suma <> 100 THEN
        RAISE EXCEPTION 'Los porcentajes suman % y tienen que sumar 100', v_suma USING ERRCODE = '22023';
    END IF;

    RETURN jsonb_build_object('titulo', btrim(p_titulo), 'monto', v_monto, 'fecha', p_fecha,
                              'modo', p_modo, 'pagador', v_pagador, 'filas', v_filas);
END $$;

-- La parte de cada fila (`p_filas` de _leer_gasto, con `rechazada` en las que rechazaron).
-- Sin rechazos es el reparto de siempre. Con rechazos (§4.8, solo en grupos):
--   * 'montos': no hay proporción para repartir de nuevo, así que lo rechazado lo absorbe
--     quien pagó (decisión 26);
--   * los demás modos: se reparte de nuevo con los pesos, entre las partes activas.
-- Una fila rechazada conserva la parte que tenía antes, como información ("tu parte era
-- $30"): no cuenta en ningún saldo.
CREATE FUNCTION public._partes_gasto(p_monto numeric, p_modo text, p_filas jsonb, p_pagador int)
    RETURNS numeric[]
    LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_n      int := jsonb_array_length(p_filas);
    v_partes numeric[] := array_fill(0::numeric, ARRAY[v_n]);
    v_idx    int[];
    v_pesos  numeric[];
    v_rep    numeric[];
    v_absorb numeric := 0;
    k        int;
BEGIN
    IF p_modo = 'montos' THEN
        FOR k IN 1..v_n LOOP
            v_partes[k] := COALESCE((p_filas -> (k - 1) ->> 'peso')::numeric, 0);
            IF COALESCE((p_filas -> (k - 1) ->> 'rechazada')::boolean, false) THEN
                v_absorb := v_absorb + v_partes[k];
            END IF;
        END LOOP;
        v_partes[p_pagador] := v_partes[p_pagador] + v_absorb;
        RETURN v_partes;
    END IF;

    -- Con todos los que participan (la parte "de antes" de quien rechazó)…
    SELECT array_agg(o::int ORDER BY o), array_agg((f ->> 'peso')::numeric ORDER BY o)
      INTO v_idx, v_pesos
      FROM jsonb_array_elements(p_filas) WITH ORDINALITY x(f, o)
     WHERE f -> 'peso' <> 'null';
    v_rep := _repartir(p_monto, v_pesos, array_position(v_idx, p_pagador));
    FOR k IN 1..array_length(v_idx, 1) LOOP
        v_partes[v_idx[k]] := v_rep[k];
    END LOOP;

    -- …y, si alguien rechazó, de nuevo entre los que quedan.
    SELECT array_agg(o::int ORDER BY o), array_agg((f ->> 'peso')::numeric ORDER BY o)
      INTO v_idx, v_pesos
      FROM jsonb_array_elements(p_filas) WITH ORDINALITY x(f, o)
     WHERE f -> 'peso' <> 'null' AND NOT COALESCE((f ->> 'rechazada')::boolean, false);
    IF v_idx IS NOT NULL AND array_length(v_idx, 1) < (SELECT count(*) FROM jsonb_array_elements(p_filas) f
                                                        WHERE f -> 'peso' <> 'null') THEN
        v_rep := _repartir(p_monto, v_pesos, array_position(v_idx, p_pagador));
        FOR k IN 1..array_length(v_idx, 1) LOOP
            v_partes[v_idx[k]] := v_rep[k];
        END LOOP;
    END IF;
    RETURN v_partes;
END $$;

-- El gasto con sus participantes en orden, como lo devuelven los RPC.
CREATE FUNCTION public._gasto_json(p_id uuid) RETURNS jsonb
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT to_jsonb(g) || jsonb_build_object('participantes',
               (SELECT COALESCE(jsonb_agg(to_jsonb(p) ORDER BY p.orden), '[]')
                  FROM gasto_participantes p WHERE p.gasto_id = g.id))
      FROM gastos g WHERE g.id = p_id
$$;

-- Candados de varios deudores y de las otras puntas de sus vínculos vivos, en un solo orden
-- global (el de _bloquear_vinculo). Un gasto suelto toca varias libretas a la vez (cada
-- contacto vinculado recibe su espejo); tomarlos en otro orden podía trabarse con alguien
-- que anota al mismo tiempo (fase 8, §10).
CREATE FUNCTION public._candados_deudores(p_deudores uuid[]) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    d uuid;
BEGIN
    FOR d IN SELECT x FROM (
                 SELECT unnest(p_deudores) x
                 UNION
                 SELECT unnest(ARRAY[v.deudor_a, v.deudor_b])
                   FROM vinculos v
                  WHERE v.estado <> 'roto'
                    AND (v.deudor_a = ANY (p_deudores) OR v.deudor_b = ANY (p_deudores))) s
              WHERE x IS NOT NULL
              ORDER BY x::text LOOP
        PERFORM pg_advisory_xact_lock(hashtext(d::text));
    END LOOP;
END $$;

-- Las deudas que tendría que haber en mi libreta por un gasto suelto, por contacto:
--   * pagué yo → cada contacto que participa me debe su parte;
--   * pagó un contacto → yo le debo mi parte, y nada más (decisión 31).
-- Filas {deudor_id, es_mi_deuda, monto, fila (posición del participante), deuda_id}.
CREATE FUNCTION public._deudas_de_gasto(p_leido jsonb, p_partes numeric[]) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_filas   jsonb := p_leido -> 'filas';
    v_pagador int := (p_leido ->> 'pagador')::int;
    v_quien   jsonb := v_filas -> (v_pagador - 1) -> 'deudor_id';   -- null = pagué yo
    v_res     jsonb := '[]';
    k         int;
BEGIN
    FOR k IN 1..jsonb_array_length(v_filas) LOOP
        CONTINUE WHEN p_partes[k] <= 0;
        IF v_quien = 'null' AND v_filas -> (k - 1) -> 'deudor_id' <> 'null' THEN
            v_res := v_res || jsonb_build_object(
                'deudor_id', v_filas -> (k - 1) -> 'deudor_id', 'es_mi_deuda', false,
                'monto', p_partes[k], 'fila', k, 'deuda_id', v_filas -> (k - 1) -> 'deuda_id');
        ELSIF v_quien <> 'null' AND v_filas -> (k - 1) -> 'deudor_id' = 'null' THEN
            v_res := v_res || jsonb_build_object(
                'deudor_id', v_quien, 'es_mi_deuda', true,
                'monto', p_partes[k], 'fila', k, 'deuda_id', v_filas -> (k - 1) -> 'deuda_id');
        END IF;
    END LOOP;
    RETURN v_res;
END $$;

-- Comprueba que todos los contactos del gasto suelto son míos y que, si pagó un contacto,
-- yo participo (si no, no hay nada que anotar en mi libreta, decisión 31).
CREATE FUNCTION public._validar_gasto_suelto(p_leido jsonb) RETURNS void
    LANGUAGE plpgsql STABLE SET search_path = public AS $$
DECLARE
    v_filas   jsonb := p_leido -> 'filas';
    v_pagador int := (p_leido ->> 'pagador')::int;
BEGIN
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_filas) f WHERE f -> 'miembro_id' <> 'null') THEN
        RAISE EXCEPTION 'Un gasto suelto se divide entre contactos de tu libreta, no entre miembros de un grupo'
            USING ERRCODE = '22023';
    END IF;
    IF EXISTS (SELECT 1 FROM jsonb_array_elements(v_filas) f
                WHERE f -> 'deudor_id' <> 'null'
                  AND NOT EXISTS (SELECT 1 FROM deudores d
                                   WHERE d.id = (f ->> 'deudor_id')::uuid AND d.owner_id = auth.uid())) THEN
        RAISE EXCEPTION 'Uno de los contactos no existe o no es tuyo' USING ERRCODE = '42501';
    END IF;
    IF v_filas -> (v_pagador - 1) -> 'deudor_id' <> 'null'
       AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements(v_filas) f
                        WHERE f -> 'deudor_id' = 'null' AND f -> 'peso' <> 'null') THEN
        RAISE EXCEPTION 'Si pagó un contacto y tú no participas, no hay nada que anotar en tu libreta'
            USING ERRCODE = '22023';
    END IF;
END $$;

-- Deja una deuda de un gasto suelto como dice `p_d` ({es_mi_deuda, monto}) con esta fecha
-- y título. Lo acordado con un contacto vinculado se le PROPONE (decisión 22): mis cambios
-- anteriores que él todavía no respondió se reemplazan por este. Lo demás se cambia
-- directo, soltando el reparto que ya no cabe (decisión 16). Lo rechazado no cuenta: solo
-- se deja al día para que el gasto muestre lo mismo.
CREATE FUNCTION public._ajustar_deuda_gasto(
    p_deuda public.deudas, p_d jsonb, p_fecha date, p_titulo text, p_idem uuid) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_mia   boolean := (p_d ->> 'es_mi_deuda')::boolean;
    v_monto numeric := (p_d ->> 'monto')::numeric;
    v_prop  uuid;
BEGIN
    IF p_deuda.titulo IS DISTINCT FROM p_titulo THEN
        UPDATE deudas SET titulo = p_titulo WHERE id = p_deuda.id;
    END IF;
    IF (p_deuda.es_mi_deuda, p_deuda.monto, p_deuda.fecha_gasto) = (v_mia, v_monto, p_fecha) THEN
        RETURN;
    END IF;
    IF p_deuda.estado_acuerdo = 'acordada' AND (_vinculo_de(p_deuda.deudor_id)).id IS NOT NULL THEN
        FOR v_prop IN SELECT id FROM propuestas
                       WHERE fila_origen = p_deuda.id AND estado = 'pendiente'
                         AND de_usuario = auth.uid() ORDER BY id LOOP
            PERFORM anular_propuesta(v_prop);
        END LOOP;
        PERFORM proponer_cambio('deuda', p_deuda.id, 'editar',
                                jsonb_build_object('monto', v_monto, 'fecha', p_fecha, 'es_mia', v_mia),
                                _idem_derivada(p_idem, 'gasto|' || p_deuda.id));
        RETURN;
    END IF;
    IF p_deuda.estado_acuerdo <> 'rechazada' THEN
        IF p_deuda.es_mi_deuda IS DISTINCT FROM v_mia THEN
            PERFORM _soltar_deuda(p_deuda.id, NULL);
        ELSIF v_monto < p_deuda.monto THEN
            PERFORM _soltar_deuda(p_deuda.id, v_monto);
        END IF;
    END IF;
    UPDATE deudas SET es_mi_deuda = v_mia, monto = v_monto, fecha_gasto = p_fecha WHERE id = p_deuda.id;
END $$;

-- Saca una deuda de su gasto suelto: si está acordada con un contacto vinculado, se le
-- propone borrarla (decisión 22); si no, se va, soltando antes sus cruces (§4.2).
-- Devuelve true si quedó esperando respuesta.
CREATE FUNCTION public._quitar_deuda_gasto(p_deuda public.deudas, p_idem uuid) RETURNS boolean
    LANGUAGE plpgsql SET search_path = public AS $$
DECLARE
    v_prop uuid;
BEGIN
    IF p_deuda.estado_acuerdo = 'acordada' AND (_vinculo_de(p_deuda.deudor_id)).id IS NOT NULL THEN
        FOR v_prop IN SELECT id FROM propuestas
                       WHERE fila_origen = p_deuda.id AND estado = 'pendiente'
                         AND de_usuario = auth.uid() ORDER BY id LOOP
            PERFORM anular_propuesta(v_prop);
        END LOOP;
        IF NOT EXISTS (SELECT 1 FROM propuestas WHERE fila_origen = p_deuda.id
                          AND estado = 'pendiente' AND tipo = 'borrar') THEN
            PERFORM proponer_cambio('deuda', p_deuda.id, 'borrar', '{}',
                                    _idem_derivada(p_idem, 'gasto|' || p_deuda.id));
        END IF;
        RETURN true;
    END IF;
    PERFORM _soltar_deuda(p_deuda.id, NULL);
    DELETE FROM deudas WHERE id = p_deuda.id;
    RETURN false;
END $$;

-- ====================================================================================
-- Triggers
-- ====================================================================================

-- BEFORE INSERT OR UPDATE OR DELETE en deudas. `gasto_id` solo lo ponen los RPC del gasto,
-- y una deuda de un gasto no se cambia suelta (§4.8): monto, fecha, dirección y contacto
-- salen del gasto, y se borra borrando o editando el gasto. El título es libre. Pasan los
-- RPC del gasto (`deudas.en_gasto`), los de las propuestas (`deudas.en_rpc`: rechazos,
-- cambios del gasto que el otro aceptó) y el borrado en cascada (se borra el contacto o la
-- cuenta: pg_trigger_depth() > 1).
CREATE FUNCTION public._guardia_gasto() RETURNS trigger
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF _en_gasto() THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF TG_OP = 'INSERT' THEN
        NEW.gasto_id := NULL;
        RETURN NEW;
    END IF;
    IF _en_rpc() OR OLD.gasto_id IS NULL OR pg_trigger_depth() > 1 THEN
        IF TG_OP = 'UPDATE' AND NOT _en_rpc() THEN
            NEW.gasto_id := OLD.gasto_id;
        END IF;
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Esta deuda es parte de un gasto dividido: bórrala desde el gasto'
            USING ERRCODE = '42501';
    END IF;
    NEW.gasto_id := OLD.gasto_id;
    IF (OLD.monto, OLD.fecha_gasto, OLD.es_mi_deuda, OLD.deudor_id)
       IS DISTINCT FROM (NEW.monto, NEW.fecha_gasto, NEW.es_mi_deuda, NEW.deudor_id) THEN
        RAISE EXCEPTION 'Esta deuda es parte de un gasto dividido: cambia monto, fecha o persona desde el gasto'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END $$;

-- AFTER UPDATE OF estado_acuerdo en deudas: el contacto vinculado rechazó su parte de un
-- gasto suelto (rechazar_fila, o no aceptó la propuesta) → el gasto lo muestra. No se
-- reparte de nuevo: sus deudas con los demás contactos están acordadas con ellos, y
-- cambiarlas es proponérselo. Lo rechazado lo absorbe quien pagó, como en la decisión 26;
-- para cobrárselo a otro, se edita el gasto.
CREATE FUNCTION public._gasto_parte_rechazada() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    UPDATE gasto_participantes SET estado = 'rechazada' WHERE deuda_id = NEW.id AND estado <> 'rechazada';
    UPDATE gastos SET updated_at = now() WHERE id = NEW.gasto_id;
    RETURN NULL;
END $$;

-- Lápidas de lo borrado del gasto. Una cuenta que se está borrando no deja (como _lapida).
CREATE FUNCTION public._lapida_gasto() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    -- Por jsonb: las tablas no tienen las mismas columnas (grupo_pagos no tiene creado_por).
    v_grupo uuid := (to_jsonb(OLD) ->> 'grupo_id')::uuid;
    v_owner uuid := CASE WHEN TG_TABLE_NAME = 'gastos' AND v_grupo IS NULL
                         THEN (to_jsonb(OLD) ->> 'creado_por')::uuid END;
BEGIN
    IF v_grupo IS NULL AND (v_owner IS NULL OR NOT EXISTS (SELECT 1 FROM perfiles WHERE id = v_owner)) THEN
        RETURN OLD;
    END IF;
    INSERT INTO borrados_gastos (tabla, id, grupo_id, owner_id)
    VALUES (TG_TABLE_NAME, OLD.id, v_grupo, v_owner)
    ON CONFLICT (tabla, id) DO UPDATE SET at = now();
    RETURN OLD;
END $$;

-- Al borrarse una cuenta, sus gastos sueltos quedaron sin dueño (SET NULL): se van. Corre
-- después de las cascadas (los triggers de las FK se llaman "RI_…" y van antes), cuando
-- sus deudas ya se fueron con sus contactos.
CREATE FUNCTION public._perfil_sin_gastos() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM gastos WHERE grupo_id IS NULL AND creado_por IS NULL;
    DELETE FROM borrados_gastos WHERE owner_id = OLD.id;
    RETURN NULL;
END $$;

CREATE TRIGGER guardia_gasto BEFORE INSERT OR UPDATE OR DELETE ON public.deudas
    FOR EACH ROW EXECUTE FUNCTION public._guardia_gasto();
CREATE TRIGGER gasto_parte_rechazada AFTER UPDATE OF estado_acuerdo ON public.deudas
    FOR EACH ROW WHEN (NEW.gasto_id IS NOT NULL AND NEW.estado_acuerdo = 'rechazada'
                       AND OLD.estado_acuerdo <> 'rechazada')
    EXECUTE FUNCTION public._gasto_parte_rechazada();
CREATE TRIGGER lapida AFTER DELETE ON public.gastos
    FOR EACH ROW EXECUTE FUNCTION public._lapida_gasto();
CREATE TRIGGER perfil_sin_gastos AFTER DELETE ON public.perfiles
    FOR EACH ROW EXECUTE FUNCTION public._perfil_sin_gastos();

-- ====================================================================================
-- Ramas de grupo (las reemplaza 20260924170000_grupos.sql)
-- ====================================================================================

CREATE FUNCTION public._crear_gasto_grupo(
    p_id uuid, p_grupo_id uuid, p_leido jsonb, p_idem_key uuid) RETURNS jsonb
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Los grupos todavía no están disponibles' USING ERRCODE = '0A000';
END $$;

CREATE FUNCTION public._editar_gasto_grupo(p_gasto public.gastos, p_leido jsonb, p_idem_key uuid)
    RETURNS jsonb
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Los grupos todavía no están disponibles' USING ERRCODE = '0A000';
END $$;

CREATE FUNCTION public._borrar_gasto_grupo(p_gasto public.gastos) RETURNS jsonb
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Los grupos todavía no están disponibles' USING ERRCODE = '0A000';
END $$;

-- ====================================================================================
-- RPC
-- ====================================================================================

-- Anota un gasto dividido. `p_id` lo genera el teléfono: repetirlo (el sync reintenta)
-- devuelve el mismo gasto sin tocar nada. Con `p_grupo_id` NULL es un gasto suelto: cada
-- parte de un contacto es una deuda normal de mi libreta (ver _deudas_de_gasto), que a un
-- contacto vinculado le llega como cualquier deuda (fase 8). SECURITY DEFINER: las tablas
-- del gasto no se escriben directo; las deudas llevan mi owner_id (DEFAULT auth.uid()).
CREATE FUNCTION public.crear_gasto(
    p_id uuid, p_grupo_id uuid, p_titulo text, p_monto numeric, p_fecha date,
    p_modo text, p_participantes jsonb, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid    uuid := auth.uid();
    v_prev   public.gastos;
    v_leido  jsonb;
    v_partes numeric[];
    v_deudas jsonb;
    v_d      jsonb;
    v_deuda  uuid;
    v_f      jsonb;
    k        int;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    IF p_id IS NULL THEN
        RAISE EXCEPTION 'Falta el id del gasto' USING ERRCODE = '22023';
    END IF;
    SELECT * INTO v_prev FROM gastos
     WHERE id = p_id OR (p_idem_key IS NOT NULL AND creado_por = v_uid AND idem_key = p_idem_key)
     LIMIT 1;
    IF FOUND THEN
        IF v_prev.creado_por = v_uid THEN
            RETURN _gasto_json(v_prev.id) || jsonb_build_object('repetido', true);
        END IF;
        RAISE EXCEPTION 'El gasto % ya existe y no es tuyo', p_id USING ERRCODE = '42501';
    END IF;

    v_leido := _leer_gasto(p_titulo, p_monto, p_fecha, p_modo, p_participantes);
    IF p_grupo_id IS NOT NULL THEN
        RETURN _crear_gasto_grupo(p_id, p_grupo_id, v_leido, p_idem_key);
    END IF;

    PERFORM _validar_gasto_suelto(v_leido);
    v_partes := _partes_gasto((v_leido ->> 'monto')::numeric, p_modo, v_leido -> 'filas',
                              (v_leido ->> 'pagador')::int);
    v_deudas := _deudas_de_gasto(v_leido, v_partes);
    PERFORM _candados_deudores(ARRAY(SELECT (d ->> 'deudor_id')::uuid FROM jsonb_array_elements(v_deudas) d));

    PERFORM set_config('deudas.en_gasto', 'on', true);
    INSERT INTO gastos (id, grupo_id, creado_por, titulo, monto_total, fecha, modo, idem_key)
    VALUES (p_id, NULL, v_uid, v_leido ->> 'titulo', (v_leido ->> 'monto')::numeric, p_fecha,
            p_modo, p_idem_key);
    FOR k IN 1..jsonb_array_length(v_leido -> 'filas') LOOP
        v_f := v_leido -> 'filas' -> (k - 1);
        v_deuda := NULL;
        SELECT d INTO v_d FROM jsonb_array_elements(v_deudas) d WHERE (d ->> 'fila')::int = k;
        IF v_d IS NOT NULL THEN
            INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda, gasto_id, synced)
            VALUES (COALESCE((v_d ->> 'deuda_id')::uuid, gen_random_uuid()), (v_d ->> 'deudor_id')::uuid,
                    v_leido ->> 'titulo', (v_d ->> 'monto')::numeric, p_fecha,
                    (v_d ->> 'es_mi_deuda')::boolean, p_id, true)
            RETURNING id INTO v_deuda;
        END IF;
        v_d := NULL;
        INSERT INTO gasto_participantes (gasto_id, orden, deudor_id, pagado, parte, peso, deuda_id)
        VALUES (p_id, k, (v_f ->> 'deudor_id')::uuid, (v_f ->> 'pagado')::numeric, v_partes[k],
                (v_f ->> 'peso')::numeric, v_deuda);
    END LOOP;
    PERFORM set_config('deudas.en_gasto', 'off', true);
    RETURN _gasto_json(p_id) || jsonb_build_object('repetido', false);
END $$;

-- Cambia un gasto: título, monto, fecha, modo y participantes, todo junto (la lista
-- completa, como en crear_gasto). Se reparte de nuevo y cada deuda del gasto suelto se
-- deja al día (_ajustar_deuda_gasto): lo acordado se propone, lo demás cambia directo.
-- Repetirlo con la misma `p_idem_key` no hace nada. Solo quien lo anotó.
CREATE FUNCTION public.editar_gasto(
    p_gasto_id uuid, p_titulo text, p_monto numeric, p_fecha date, p_modo text,
    p_participantes jsonb, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid     uuid := auth.uid();
    v_g       public.gastos;
    v_leido   jsonb;
    v_partes  numeric[];
    v_deudas  jsonb;
    v_d       jsonb;
    v_e       public.deudas;
    v_usadas  uuid[] := '{}';
    v_por_fila jsonb := '{}';      -- posición del participante → su deuda
    v_deuda   uuid;
    v_f       jsonb;
    v_esperan int := 0;
    k         int;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v_g FROM gastos WHERE id = p_gasto_id FOR UPDATE;
    IF NOT FOUND OR (v_g.grupo_id IS NULL AND v_g.creado_por IS DISTINCT FROM v_uid) THEN
        RAISE EXCEPTION 'El gasto % no existe o no es tuyo', p_gasto_id USING ERRCODE = '42501';
    END IF;
    IF p_idem_key IS NOT NULL AND v_g.edit_idem = p_idem_key THEN
        RETURN _gasto_json(v_g.id) || jsonb_build_object('repetido', true);
    END IF;
    v_leido := _leer_gasto(p_titulo, p_monto, p_fecha, p_modo, p_participantes);
    IF v_g.grupo_id IS NOT NULL THEN
        RETURN _editar_gasto_grupo(v_g, v_leido, p_idem_key);
    END IF;

    PERFORM _validar_gasto_suelto(v_leido);
    v_partes := _partes_gasto((v_leido ->> 'monto')::numeric, p_modo, v_leido -> 'filas',
                              (v_leido ->> 'pagador')::int);
    v_deudas := _deudas_de_gasto(v_leido, v_partes);
    PERFORM _candados_deudores(ARRAY(
        SELECT (d ->> 'deudor_id')::uuid FROM jsonb_array_elements(v_deudas) d
        UNION SELECT deudor_id FROM deudas WHERE gasto_id = v_g.id));

    PERFORM set_config('deudas.en_gasto', 'on', true);
    -- Lo que ya había, por contacto: se ajusta o se quita.
    FOR v_e IN SELECT * FROM deudas WHERE gasto_id = v_g.id AND owner_id = v_uid
                ORDER BY created_at, id FOR UPDATE LOOP
        SELECT d INTO v_d FROM jsonb_array_elements(v_deudas) d
         WHERE (d ->> 'deudor_id')::uuid = v_e.deudor_id AND NOT (v_e.deudor_id = ANY (v_usadas));
        IF v_d IS NULL THEN
            IF _quitar_deuda_gasto(v_e, p_idem_key) THEN
                v_esperan := v_esperan + 1;
            END IF;
        ELSE
            PERFORM _ajustar_deuda_gasto(v_e, v_d, p_fecha, v_leido ->> 'titulo', p_idem_key);
            v_usadas := v_usadas || v_e.deudor_id;
            v_por_fila := v_por_fila || jsonb_build_object(v_d ->> 'fila', v_e.id);
            IF EXISTS (SELECT 1 FROM propuestas WHERE fila_origen = v_e.id AND estado = 'pendiente'
                          AND tipo = 'editar') THEN
                v_esperan := v_esperan + 1;
            END IF;
        END IF;
        v_d := NULL;
    END LOOP;
    -- Lo nuevo.
    FOR v_d IN SELECT d FROM jsonb_array_elements(v_deudas) d
                WHERE NOT ((d ->> 'deudor_id')::uuid = ANY (v_usadas)) LOOP
        INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda, gasto_id, synced)
        VALUES (COALESCE((v_d ->> 'deuda_id')::uuid, gen_random_uuid()), (v_d ->> 'deudor_id')::uuid,
                v_leido ->> 'titulo', (v_d ->> 'monto')::numeric, p_fecha,
                (v_d ->> 'es_mi_deuda')::boolean, v_g.id, true)
        RETURNING id INTO v_deuda;
        v_por_fila := v_por_fila || jsonb_build_object(v_d ->> 'fila', v_deuda);
    END LOOP;

    DELETE FROM gasto_participantes WHERE gasto_id = v_g.id;
    FOR k IN 1..jsonb_array_length(v_leido -> 'filas') LOOP
        v_f := v_leido -> 'filas' -> (k - 1);
        v_deuda := (v_por_fila ->> k::text)::uuid;
        INSERT INTO gasto_participantes (gasto_id, orden, deudor_id, pagado, parte, peso, deuda_id, estado)
        VALUES (v_g.id, k, (v_f ->> 'deudor_id')::uuid, (v_f ->> 'pagado')::numeric, v_partes[k],
                (v_f ->> 'peso')::numeric, v_deuda,
                CASE WHEN EXISTS (SELECT 1 FROM deudas WHERE id = v_deuda AND estado_acuerdo = 'rechazada')
                     THEN 'rechazada' ELSE 'activa' END);
    END LOOP;
    UPDATE gastos
       SET titulo = v_leido ->> 'titulo', monto_total = (v_leido ->> 'monto')::numeric,
           fecha = p_fecha, modo = p_modo, edit_idem = p_idem_key
     WHERE id = v_g.id;
    PERFORM set_config('deudas.en_gasto', 'off', true);
    RETURN _gasto_json(v_g.id) || jsonb_build_object('repetido', false, 'esperan_respuesta', v_esperan);
END $$;

-- Borra un gasto. En un gasto suelto, sus deudas se van; las acordadas con un contacto
-- vinculado se le proponen borrar (decisión 22) y, si no acepta, quedan como deudas
-- normales. Repetirlo no hace nada. Solo quien lo anotó.
CREATE FUNCTION public.borrar_gasto(p_gasto_id uuid, p_idem_key uuid DEFAULT NULL) RETURNS jsonb
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid     uuid := auth.uid();
    v_g       public.gastos;
    v_e       public.deudas;
    v_esperan int := 0;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Hay que iniciar sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO v_g FROM gastos WHERE id = p_gasto_id FOR UPDATE;
    IF NOT FOUND THEN
        IF EXISTS (SELECT 1 FROM borrados_gastos WHERE tabla = 'gastos' AND id = p_gasto_id
                      AND (owner_id = v_uid OR grupo_id IS NOT NULL)) THEN
            RETURN jsonb_build_object('resultado', 'borrado', 'gasto_id', p_gasto_id, 'repetido', true);
        END IF;
        RAISE EXCEPTION 'El gasto % no existe o no es tuyo', p_gasto_id USING ERRCODE = '42501';
    END IF;
    IF v_g.grupo_id IS NOT NULL THEN
        RETURN _borrar_gasto_grupo(v_g);
    END IF;
    IF v_g.creado_por IS DISTINCT FROM v_uid THEN
        RAISE EXCEPTION 'El gasto % no existe o no es tuyo', p_gasto_id USING ERRCODE = '42501';
    END IF;

    PERFORM _candados_deudores(ARRAY(SELECT deudor_id FROM deudas WHERE gasto_id = v_g.id));
    PERFORM set_config('deudas.en_gasto', 'on', true);
    FOR v_e IN SELECT * FROM deudas WHERE gasto_id = v_g.id AND owner_id = v_uid
                ORDER BY created_at, id FOR UPDATE LOOP
        IF _quitar_deuda_gasto(v_e, p_idem_key) THEN
            v_esperan := v_esperan + 1;
        END IF;
    END LOOP;
    DELETE FROM gastos WHERE id = v_g.id;
    PERFORM set_config('deudas.en_gasto', 'off', true);
    RETURN jsonb_build_object('resultado', 'borrado', 'gasto_id', p_gasto_id,
                              'esperan_respuesta', v_esperan, 'repetido', false);
END $$;

-- Lo que cambió en mis gastos desde `p_desde` (NULL = todo), para el pull incremental de
-- la app: cada gasto con TODOS sus participantes (cambian juntos) y las lápidas.
-- SECURITY INVOKER: el RLS limita todo a lo que veo. 20260924170000 le suma los grupos.
CREATE FUNCTION public.cambios_gastos(p_desde timestamptz DEFAULT NULL) RETURNS jsonb
    LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT jsonb_build_object(
        'gastos', (SELECT COALESCE(jsonb_agg(_gasto_json(g.id) ORDER BY g.updated_at, g.id), '[]')
                     FROM gastos g
                    WHERE p_desde IS NULL OR g.updated_at > p_desde),
        'borrados', (SELECT COALESCE(jsonb_agg(jsonb_build_object('tabla', b.tabla, 'id', b.id, 'at', b.at)
                                               ORDER BY b.at, b.id), '[]')
                       FROM borrados_gastos b
                      WHERE p_desde IS NULL OR b.at > p_desde))
$$;

-- ====================================================================================
-- Funciones existentes (copia exacta + «v2 fase 9»)
-- ====================================================================================

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
        'gasto_participantes', (SELECT COALESCE(jsonb_agg(to_jsonb(x) ORDER BY x.gasto_id, x.orden), '[]') FROM gasto_participantes x)); -- v2 fase 9
END $$;

-- ====================================================================================
-- Permisos
-- ====================================================================================

REVOKE ALL ON FUNCTION public._repartir(numeric, numeric[], int)                 FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._en_gasto()                                        FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._leer_gasto(text, numeric, date, text, jsonb)      FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._partes_gasto(numeric, text, jsonb, int)           FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._gasto_json(uuid)                                  FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public._candados_deudores(uuid[])                         FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._deudas_de_gasto(jsonb, numeric[])                 FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._validar_gasto_suelto(jsonb)                       FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._ajustar_deuda_gasto(public.deudas, jsonb, date, text, uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._quitar_deuda_gasto(public.deudas, uuid)           FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._guardia_gasto()                                   FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._gasto_parte_rechazada()                           FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._lapida_gasto()                                    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._perfil_sin_gastos()                               FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._crear_gasto_grupo(uuid, uuid, jsonb, uuid)        FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._editar_gasto_grupo(public.gastos, jsonb, uuid)    FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public._borrar_gasto_grupo(public.gastos)                 FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.crear_gasto(uuid, uuid, text, numeric, date, text, jsonb, uuid) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.editar_gasto(uuid, text, numeric, date, text, jsonb, uuid)      FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.borrar_gasto(uuid, uuid)                           FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.cambios_gastos(timestamptz)                        FROM PUBLIC, anon;
-- _guardia_gasto (trigger de deudas) y cambios_gastos (SECURITY INVOKER) las usan con los
-- permisos de quien llama; _repartir sirve también para una vista previa.
GRANT EXECUTE ON FUNCTION public._repartir(numeric, numeric[], int) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._en_gasto()                        TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public._gasto_json(uuid)                  TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.crear_gasto(uuid, uuid, text, numeric, date, text, jsonb, uuid) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.editar_gasto(uuid, text, numeric, date, text, jsonb, uuid)      TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.borrar_gasto(uuid, uuid)           TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.cambios_gastos(timestamptz)        TO authenticated, service_role;
