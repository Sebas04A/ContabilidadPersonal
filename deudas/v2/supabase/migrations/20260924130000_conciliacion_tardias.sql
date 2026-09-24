-- Hueco de la fase 5 (deudas/PLAN_MULTIUSUARIO.md, notas de la fase 6): filas anotadas
-- entre las dos confirmaciones de la conciliación.
--
-- Mientras el vínculo está `conciliando`, lo nuevo nace `local` (`_nace_propuesta` solo
-- propone con el vínculo `activo`). Quien confirma primero manda como propuesta todo lo
-- que tenía; si después anota algo más y el otro confirma, esa fila se quedaba `local`
-- para siempre: el otro nunca la veía y ninguna conciliación la volvía a mirar.
--
-- Arreglo: al pasar el vínculo a `activo`, lo `local` que le quede al OTRO (quien confirmó
-- primero) se le propone a quien cierra, como habría pasado si el vínculo ya estuviera
-- activo cuando lo anotó. Lo de quien cierra ya salió en esta misma llamada. Como son
-- filas anotadas con el vínculo vivo, viajan con su título (decisión 10 de §3.3), igual
-- que las de `_nace_propuesta_post`.
--
-- De paso, la clave de idempotencia de las propuestas de la conciliación pasa a incluir el
-- vínculo. Con `_idem_derivada(fila, 'conciliacion')` a secas, vincularse, desvincularse y
-- volver a vincularse fallaba (23505) al confirmar: desvincular devuelve la fila a `local`
-- pero la propuesta anulada conserva la clave, y la segunda conciliación la repetía.
--
-- confirmar_conciliacion es copia exacta de 20260924120000_propuestas.sql más las líneas
-- marcadas «v2 tardías». Compruébalo con un diff.

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
    v_tardias    int := 0;   -- v2 tardías
    v_fila       jsonb;      -- v2 tardías
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
                public._idem_derivada(f.id, 'conciliacion|' || p_vinculo_id));   -- v2 tardías
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

    -- v2 tardías: el vínculo quedó activo y al otro le queda algo `local` → lo anotó después
    -- de confirmar. Se me propone con la dirección de SU libreta (la propuesta es suya).
    IF v_estado = 'activo' THEN                                                  -- v2 tardías
        FOR f IN SELECT * FROM public._filas_conciliables(c.su_deudor, c.otro, false) LOOP   -- v2 tardías
            IF f.entidad = 'deuda' THEN                                          -- v2 tardías
                UPDATE public.deudas SET estado_acuerdo = 'propuesta' WHERE id = f.id -- v2 tardías
                RETURNING to_jsonb(deudas.*) INTO v_fila;                        -- v2 tardías
            ELSE                                                                 -- v2 tardías
                UPDATE public.pagos SET estado_acuerdo = 'propuesta' WHERE id = f.id  -- v2 tardías
                RETURNING to_jsonb(pagos.*) INTO v_fila;                         -- v2 tardías
            END IF;                                                              -- v2 tardías
            INSERT INTO public.propuestas                                        -- v2 tardías
                (vinculo_id, de_usuario, para_usuario, entidad, tipo, fila_origen, payload, idem_key) -- v2 tardías
            VALUES (p_vinculo_id, c.otro, auth.uid(), f.entidad, 'crear', f.id,  -- v2 tardías
                    public._payload_de(f.entidad, v_fila),                       -- v2 tardías
                    public._idem_derivada(f.id, 'tardia|' || p_vinculo_id));     -- v2 tardías
            v_tardias := v_tardias + 1;                                          -- v2 tardías
        END LOOP;                                                                -- v2 tardías
    END IF;                                                                      -- v2 tardías

    PERFORM set_config('deudas.en_rpc', 'off', true);   -- v2 fase 6
    RETURN jsonb_build_object('estado', v_estado, 'acordadas', v_acordadas, 'propuestas', v_propuestas)
        -- v2 tardías: la clave solo aparece si hubo algo, así la respuesta de siempre no cambia.
        || CASE WHEN v_tardias > 0 THEN jsonb_build_object('tardias', v_tardias) ELSE '{}' END;
END $$;

-- ====================================================================================
-- Volver a vincularse
-- ====================================================================================

-- Al romperse un vínculo, lo acordado queda `acordada` (decisión 11 de §3.3) y cada uno
-- lo edita libremente (decisión 12: la guardia solo mira vínculos vivos). Pero si el mismo
-- contacto se vuelve a vincular, esas filas quedaban `acordada` sin acuerdo en el vínculo
-- nuevo: la guardia las bloqueaba, `proponer_cambio` no encontraba su pareja y
-- `verificar_vinculo` daba descuadre. Además pudieron cambiar mientras no había vínculo.
--
-- Por eso, al nacer un vínculo, todo lo acordado de sus dos deudores (que por fuerza viene
-- de vínculos rotos: un deudor no puede tener dos vivos) vuelve a `local` y pasa por la
-- conciliación nueva, que lo empareja como a cualquier historial. Los acuerdos viejos se
-- borran: `acuerdos` es único por fila en todos los vínculos, y el nuevo par chocaría.
-- Lo rechazado sigue rechazado.
CREATE FUNCTION public._soltar_acuerdos_viejos(p_deudor uuid) RETURNS void
    LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    DELETE FROM acuerdos ac USING vinculos v
     WHERE v.id = ac.vinculo_id AND v.estado = 'roto'
       AND p_deudor IN (v.deudor_a, v.deudor_b);
    UPDATE deudas SET estado_acuerdo = 'local'
     WHERE deudor_id = p_deudor AND estado_acuerdo = 'acordada';
    UPDATE pagos SET estado_acuerdo = 'local'
     WHERE deudor_id = p_deudor AND estado_acuerdo = 'acordada';
END $$;

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
    -- v2 tardías: lo acordado en un vínculo roto vuelve a conciliarse en este.
    PERFORM set_config('deudas.en_rpc', 'on', true);                             -- v2 tardías
    PERFORM public._soltar_acuerdos_viejos(v_inv.deudor_id);                     -- v2 tardías
    PERFORM public._soltar_acuerdos_viejos(v_deudor);                            -- v2 tardías
    PERFORM set_config('deudas.en_rpc', 'off', true);                            -- v2 tardías
    RETURN v_vinculo;
END $$;


REVOKE ALL ON FUNCTION public._soltar_acuerdos_viejos(uuid) FROM PUBLIC, anon, authenticated;
