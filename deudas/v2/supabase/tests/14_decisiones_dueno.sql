-- Decisiones del dueño del 2026-09-25 (20260925100000_decisiones_dueno.sql): 17 (varios
-- cambios pendientes), 14 (fechas a ±2 días), 12 (desvincular deja todo como con una
-- Persona) y 32 (enlace de grupo de 5 días). La 34 está en 13_grupos_sin_nadie.sql.
-- Las aserciones marcadas «control negativo» fallan con las versiones anteriores.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(28);

-- A (a0…) y B (b0…) vinculados y activos. Libreta de A: "Bea" (a1); de B: "Ana" (b1).
INSERT INTO auth.users (id, email, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated');
INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Bea', 'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Ana', 'b0000000-0000-0000-0000-000000000000');
INSERT INTO vinculos (id, usuario_a, deudor_a, usuario_b, deudor_b, estado, conciliado_a, conciliado_b) VALUES
  ('f0000000-0000-0000-0000-000000000000',
   'a0000000-0000-0000-0000-000000000000', 'a1000000-0000-0000-0000-000000000000',
   'b0000000-0000-0000-0000-000000000000', 'b1000000-0000-0000-0000-000000000000',
   'activo', true, true);

CREATE TEMP TABLE t (clave text PRIMARY KEY, valor text);
GRANT ALL ON t TO authenticated;

CREATE FUNCTION pg_temp.como(u text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('request.jwt.claims',
        json_build_object('sub', CASE u WHEN 'A' THEN 'a0000000-0000-0000-0000-000000000000'
                                        ELSE 'b0000000-0000-0000-0000-000000000000' END,
                          'role', 'authenticated')::text, true);
END $$;
CREATE FUNCTION pg_temp.v(k text) RETURNS uuid LANGUAGE sql AS $$
    SELECT valor::uuid FROM t WHERE clave = k
$$;
-- Propuestas pendientes de cambio o borrado sobre la deuda d1 (de A) y su espejo (de B).
CREATE FUNCTION pg_temp.pendientes_d1() RETURNS int LANGUAGE sql AS $$
    SELECT count(*)::int FROM propuestas
     WHERE fila_origen IN (pg_temp.v('d1'), pg_temp.v('d1_b')) AND tipo IN ('editar', 'borrar')
       AND estado = 'pendiente'
$$;
CREATE FUNCTION pg_temp.neto(deudor text) RETURNS numeric LANGUAGE sql AS $$
    SELECT (estado_cuenta(deudor::uuid) -> 'resumen' ->> 'neto')::numeric
$$;

-- ------------------------------------------------------------------------------------
-- 17. Varios cambios pendientes sobre el mismo acuerdo
-- ------------------------------------------------------------------------------------
SET LOCAL ROLE authenticated;
SELECT pg_temp.como('A');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
VALUES ('a0000000-0000-0000-0000-0000000000d1', 'a1000000-0000-0000-0000-000000000000', 'Cena', 20, '2026-07-01', false);
INSERT INTO t VALUES ('d1', 'a0000000-0000-0000-0000-0000000000d1');
RESET ROLE;
INSERT INTO t SELECT 'd1_b', id::text FROM deudas WHERE origen_id = pg_temp.v('d1');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = pg_temp.v('d1')), 'acordada',
  '17. preparado: la deuda de A entró sola en B y está acordada');

SET LOCAL ROLE authenticated;
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT proponer_cambio('deuda', pg_temp.v('d1'), 'editar',
                    '{"monto": 25, "fecha": "2026-07-01", "es_mia": false}')$$,
  '17. A propone $25');
SELECT lives_ok($$SELECT proponer_cambio('deuda', pg_temp.v('d1'), 'editar',
                    '{"monto": 30, "fecha": "2026-07-01", "es_mia": false}')$$,
  '17. control negativo: A propone $30 con el de $25 todavía pendiente (antes 23505)');
SELECT is(pg_temp.pendientes_d1(), 2, '17. los dos cambios conviven');
SELECT lives_ok($$SELECT proponer_cambio('deuda', pg_temp.v('d1'), 'editar',
                    '{"monto": 30, "fecha": "2026-07-01", "es_mia": false}')$$,
  '17. A vuelve a proponer exactamente $30');
SELECT is(pg_temp.pendientes_d1(), 2, '17. el idéntico reemplaza al anterior: siguen siendo 2');
RESET ROLE;
SELECT is((SELECT count(*)::int FROM avisos
            WHERE usuario_id = 'b0000000-0000-0000-0000-000000000000' AND datos ? 'mismo_que_el_tuyo'),
  0, '36. si A reemplaza uno suyo, a B no se le dice "lo mismo que el tuyo"');
SET LOCAL ROLE authenticated;

-- B propone lo mismo desde su libreta (para B la deuda es suya: es_mia = true).
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT proponer_cambio('deuda', pg_temp.v('d1_b'), 'editar',
                    '{"monto": 30, "fecha": "2026-07-01", "es_mia": true}')$$,
  '17. B propone lo mismo que A, visto desde su libreta');
RESET ROLE;
SELECT is((SELECT array_agg(de_usuario::text || ':' || (payload ->> 'monto') ORDER BY de_usuario)
             FROM propuestas
            WHERE fila_origen IN (pg_temp.v('d1'), pg_temp.v('d1_b')) AND tipo = 'editar'
              AND estado = 'pendiente'),
  ARRAY['a0000000-0000-0000-0000-000000000000:25.00', 'b0000000-0000-0000-0000-000000000000:30.00'],
  '17. queda el más nuevo aunque venga del otro: el $25 de A y el $30 de B');
SELECT is((SELECT (a.datos ->> 'mismo_que_el_tuyo')::boolean FROM avisos a JOIN propuestas p ON p.id = a.propuesta_id
            WHERE a.usuario_id = 'a0000000-0000-0000-0000-000000000000' AND p.de_usuario = 'b0000000-0000-0000-0000-000000000000'
              AND p.estado = 'pendiente'),
  true, '36. control negativo: a A el aviso del cambio de B le dice que es lo mismo que el suyo');
INSERT INTO t SELECT 'p_b', id::text FROM propuestas
 WHERE fila_origen = pg_temp.v('d1_b') AND estado = 'pendiente';

SET LOCAL ROLE authenticated;
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT aceptar_propuesta(pg_temp.v('p_b'))$$, '17. A acepta el de B');
RESET ROLE;
SELECT is((SELECT array_agg(monto ORDER BY owner_id) FROM deudas WHERE id IN (pg_temp.v('d1'), pg_temp.v('d1_b'))),
  ARRAY[30, 30]::numeric[], '17. las dos filas quedan en $30');
SELECT is(pg_temp.pendientes_d1(), 0, '17. control negativo: aceptar uno anuló el de $25');
SELECT ok((verificar_vinculo('f0000000-0000-0000-0000-000000000000') ->> 'ok')::boolean,
  '17. el vínculo sigue cuadrado');

-- ------------------------------------------------------------------------------------
-- 14. "¿Es la misma?" a ±2 días
-- ------------------------------------------------------------------------------------
-- Dos deudas de B sin acordar: $41 a 2 días y $42 a 3 días del 10 de agosto.
SELECT set_config('deudas.en_rpc', 'on', true);
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda, owner_id, estado_acuerdo) VALUES
  ('b0000000-0000-0000-0000-0000000000e1', 'b1000000-0000-0000-0000-000000000000', 'x', 41, '2026-08-12', true,
   'b0000000-0000-0000-0000-000000000000', 'local'),
  ('b0000000-0000-0000-0000-0000000000e2', 'b1000000-0000-0000-0000-000000000000', 'y', 42, '2026-08-13', true,
   'b0000000-0000-0000-0000-000000000000', 'local');
SELECT set_config('deudas.en_rpc', 'off', true);
SELECT pg_temp.como('B');
SELECT is(jsonb_array_length(_candidatos_espejo('deuda',
            '{"es_mi_deuda": false, "monto": 41, "fecha_gasto": "2026-08-10"}', 'b1000000-0000-0000-0000-000000000000')), 1,
  '14. al aceptar: a 2 días es candidata');
SELECT is(jsonb_array_length(_candidatos_espejo('deuda',
            '{"es_mi_deuda": false, "monto": 42, "fecha_gasto": "2026-08-10"}', 'b1000000-0000-0000-0000-000000000000')), 0,
  '14. control negativo: al aceptar, a 3 días ya no');
SELECT is(jsonb_array_length(_candidatos_duplicado('deuda',
            '{"es_mi_deuda": false, "monto": 41, "fecha_gasto": "2026-08-10"}', 'b1000000-0000-0000-0000-000000000000')), 1,
  '14. posible duplicado: a 2 días sí');
SELECT is(jsonb_array_length(_candidatos_duplicado('deuda',
            '{"es_mi_deuda": false, "monto": 42, "fecha_gasto": "2026-08-10"}', 'b1000000-0000-0000-0000-000000000000')), 0,
  '14. control negativo: posible duplicado, a 3 días ya no');
SELECT ok(pg_get_functiondef('fusionar_espejo(text, uuid, uuid, uuid)'::regprocedure) !~ '<= 3',
  '14. control negativo: fusionar_espejo ya no acepta 3 días');
SELECT ok(pg_get_functiondef('candidatos_conciliacion(uuid)'::regprocedure) !~ '<= 3',
  '14. control negativo: la conciliación tampoco');
DELETE FROM deudas WHERE id IN ('b0000000-0000-0000-0000-0000000000e1', 'b0000000-0000-0000-0000-0000000000e2');

-- ------------------------------------------------------------------------------------
-- 12. Desvincular: todo queda como con una Persona sin app, sin mover el saldo
-- ------------------------------------------------------------------------------------
-- Una deuda que B rechaza: no cuenta antes y no tiene que empezar a contar después.
SET LOCAL ROLE authenticated;
SELECT pg_temp.como('A');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
VALUES ('a0000000-0000-0000-0000-0000000000d2', 'a1000000-0000-0000-0000-000000000000', 'Taxi', 7, '2026-07-02', false);
SELECT pg_temp.como('B');
SELECT rechazar_fila('deuda', (SELECT id FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d2'), 'no fue');
SELECT pg_temp.como('A');
INSERT INTO t VALUES ('neto_a', pg_temp.neto('a1000000-0000-0000-0000-000000000000')::text);
SELECT pg_temp.como('B');
INSERT INTO t VALUES ('neto_b', pg_temp.neto('b1000000-0000-0000-0000-000000000000')::text);
RESET ROLE;
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d2'), 'rechazada',
  '12. preparado: la de $7 quedó rechazada en A');

SET LOCAL ROLE authenticated;
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT desvincular('f0000000-0000-0000-0000-000000000000')$$, '12. A se desvincula');
RESET ROLE;
SELECT is((SELECT array_agg(estado_acuerdo || ':' || (origen_id IS NULL) ORDER BY owner_id)
             FROM deudas WHERE id IN (pg_temp.v('d1'), pg_temp.v('d1_b'))),
  ARRAY['local:true', 'local:true'],
  '12. control negativo: lo acordado vuelve a local y se olvida quién lo anotó, en las dos libretas');
SELECT is((SELECT count(*)::int FROM acuerdos WHERE vinculo_id = 'f0000000-0000-0000-0000-000000000000'), 0,
  '12. control negativo: los acuerdos del vínculo se borran');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d2'), 'rechazada',
  '12. lo rechazado sigue rechazado');
SELECT pg_temp.como('A');
SELECT is(pg_temp.neto('a1000000-0000-0000-0000-000000000000'), (SELECT valor::numeric FROM t WHERE clave = 'neto_a'),
  '12. el saldo de A no cambia');
SELECT pg_temp.como('B');
SELECT is(pg_temp.neto('b1000000-0000-0000-0000-000000000000'), (SELECT valor::numeric FROM t WHERE clave = 'neto_b'),
  '12. el saldo de B no cambia');

-- ------------------------------------------------------------------------------------
-- 32. El enlace de un grupo vence a los 5 días
-- ------------------------------------------------------------------------------------
SELECT is((SELECT column_default FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'grupo_invitaciones' AND column_name = 'expira'),
  '(now() + ''5 days''::interval)', '32. control negativo: el enlace de grupo nace con 5 días');

SELECT * FROM finish();
ROLLBACK;
