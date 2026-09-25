-- Fase 9: borrar un grupo entero y los grupos que se quedan sin nadie con app
-- (20260924190000_grupos_sin_nadie.sql).
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(14);

-- Ana (A) y Beto (B) tienen la app; Dani es una persona sin app.
INSERT INTO auth.users (id, email, aud, role, raw_user_meta_data) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated', '{"nombre":"Ana"}'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated', '{"nombre":"Beto"}');

CREATE FUNCTION pg_temp.como(u text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('request.jwt.claims',
        json_build_object('sub', CASE u WHEN 'A' THEN 'a0000000-0000-0000-0000-000000000000'
                                        ELSE 'b0000000-0000-0000-0000-000000000000' END,
                          'role', 'authenticated')::text, true);
END $$;
CREATE FUNCTION pg_temp.m(g text, nombre_ text) RETURNS uuid LANGUAGE sql AS $$
    SELECT id FROM grupo_miembros WHERE grupo_id = g::uuid AND nombre = nombre_
$$;
CREATE FUNCTION pg_temp.cuantos(g text) RETURNS text LANGUAGE sql AS $$
    SELECT (SELECT count(*) FROM grupos WHERE id = g::uuid) || ' grupo, '
        || (SELECT count(*) FROM grupo_miembros WHERE grupo_id = g::uuid) || ' miembros, '
        || (SELECT count(*) FROM gastos WHERE grupo_id = g::uuid) || ' gastos, '
        || (SELECT count(*) FROM grupo_pagos WHERE grupo_id = g::uuid) || ' pagos, '
        || (SELECT count(*) FROM borrados_gastos WHERE grupo_id = g::uuid) || ' lápidas'
$$;

-- Dos grupos iguales: Ana, Beto y Dani; Ana paga $30 entre los tres, Dani le paga $5 y Ana
-- borra un pago (deja una lápida). El 1 es el de siempre; el 2 se borra entero.
SET LOCAL ROLE authenticated;
DO $x$
DECLARE
    g text;
    v_codigo text;
BEGIN
    FOREACH g IN ARRAY ARRAY['91000000-0000-0000-0000-000000000001', '91000000-0000-0000-0000-000000000002'] LOOP
        PERFORM pg_temp.como('A');
        PERFORM crear_grupo(g::uuid, 'Viaje ' || right(g, 1));
        PERFORM agregar_persona(g::uuid, 'Dani');
        v_codigo := invitar_a_grupo(g::uuid);
        PERFORM pg_temp.como('B');
        PERFORM unirse_a_grupo(v_codigo);
        PERFORM pg_temp.como('A');
        PERFORM crear_gasto(gen_random_uuid(), g::uuid, 'Cena', 30, '2026-09-01', 'igual',
            jsonb_build_array(jsonb_build_object('miembro_id', pg_temp.m(g, 'Ana'), 'pagado', 30),
                              jsonb_build_object('miembro_id', pg_temp.m(g, 'Beto')),
                              jsonb_build_object('miembro_id', pg_temp.m(g, 'Dani'))));
        PERFORM registrar_pago_grupo(gen_random_uuid(), g::uuid, pg_temp.m(g, 'Dani'), pg_temp.m(g, 'Ana'), 5, '2026-09-02');
        PERFORM borrar_pago_grupo((registrar_pago_grupo(gen_random_uuid(), g::uuid, pg_temp.m(g, 'Dani'),
                                   pg_temp.m(g, 'Ana'), 1, '2026-09-02') ->> 'id')::uuid);
    END LOOP;
END $x$;
RESET ROLE;

SELECT is(pg_temp.cuantos('91000000-0000-0000-0000-000000000002'), '1 grupo, 3 miembros, 1 gastos, 1 pagos, 1 lápidas',
  'preparado: el grupo 2 tiene su gasto, su pago y la lápida del pago borrado');

-- ------------------------------------------------------------------------------------
-- 1. Borrar un grupo entero (antes: 23503 por gasto_participantes → grupo_miembros).
-- ------------------------------------------------------------------------------------
SELECT lives_ok($$DELETE FROM grupos WHERE id = '91000000-0000-0000-0000-000000000002'$$,
  '1. un grupo con gastos y pagos se puede borrar entero');
SELECT lives_ok($$SET CONSTRAINTS ALL IMMEDIATE$$, '1. y las FK diferidas quedan bien');
SELECT is(pg_temp.cuantos('91000000-0000-0000-0000-000000000002'), '0 grupo, 0 miembros, 0 gastos, 0 pagos, 3 lápidas',
  '1. se van sus miembros, gastos y pagos (quedan las lápidas: la del pago borrado antes, la del gasto y la del pago)');
SELECT is(pg_temp.cuantos('91000000-0000-0000-0000-000000000001'), '1 grupo, 3 miembros, 1 gastos, 1 pagos, 1 lápidas',
  '1. el otro grupo no se toca');
SET CONSTRAINTS ALL DEFERRED;

-- Control negativo: borrar SOLO un miembro que un gasto nombra sigue fallando.
SELECT throws_ok($$SET CONSTRAINTS ALL IMMEDIATE; DELETE FROM grupo_miembros
                    WHERE id = pg_temp.m('91000000-0000-0000-0000-000000000001', 'Dani')$$,
  '23503', NULL, '1. control negativo: un miembro que un gasto nombra no se borra suelto');
SET CONSTRAINTS ALL DEFERRED;
SELECT throws_ok($$DELETE FROM grupo_pagos WHERE grupo_id = '91000000-0000-0000-0000-000000000001';
                    DELETE FROM gasto_participantes p USING gastos g
                     WHERE g.id = p.gasto_id AND g.grupo_id = '91000000-0000-0000-0000-000000000001'
                       AND p.miembro_id <> pg_temp.m('91000000-0000-0000-0000-000000000001', 'Dani');
                    DELETE FROM grupo_miembros WHERE id = pg_temp.m('91000000-0000-0000-0000-000000000001', 'Dani');
                    SET CONSTRAINTS ALL IMMEDIATE$$,
  '23503', NULL, '1. control negativo: diferida, igual se comprueba al final');
SELECT is(pg_temp.cuantos('91000000-0000-0000-0000-000000000001'), '1 grupo, 3 miembros, 1 gastos, 1 pagos, 1 lápidas',
  '1. y lo que intentó no quedó');
SET CONSTRAINTS ALL DEFERRED;

-- ------------------------------------------------------------------------------------
-- 2. Borrar cuentas: el grupo se va cuando no queda ninguna cuenta con app en él.
-- ------------------------------------------------------------------------------------
DELETE FROM auth.users WHERE id = 'a0000000-0000-0000-0000-000000000000';
SELECT is(pg_temp.cuantos('91000000-0000-0000-0000-000000000001'), '1 grupo, 3 miembros, 1 gastos, 1 pagos, 1 lápidas',
  '2. control negativo: se borra Ana pero queda Beto → el grupo sigue entero');
SELECT is((SELECT usuario_id IS NULL FROM grupo_miembros WHERE id = pg_temp.m('91000000-0000-0000-0000-000000000001', 'Ana')),
  true, '2. Ana queda como persona sin app');
SELECT is((SELECT count(*)::int FROM borrados_gastos WHERE grupo_id = '91000000-0000-0000-0000-000000000002'), 0,
  '2. las lápidas del grupo 2, que ya no existe, se limpian con cualquier cuenta que se borre');

DELETE FROM auth.users WHERE id = 'b0000000-0000-0000-0000-000000000000';
SELECT is(pg_temp.cuantos('91000000-0000-0000-0000-000000000001'), '0 grupo, 0 miembros, 0 gastos, 0 pagos, 0 lápidas',
  '2. se borra Beto, la última cuenta → el grupo se va con todo y sus lápidas');
SELECT is((SELECT count(*)::int FROM borrados_gastos WHERE grupo_id IS NOT NULL), 0,
  '2. y las lápidas de grupos que ya no existen');
SELECT lives_ok($$SET CONSTRAINTS ALL IMMEDIATE$$, '2. sin FK rotas');

SELECT * FROM finish();
ROLLBACK;
