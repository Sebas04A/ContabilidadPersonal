-- Fase 7 (parte de la base): exportar mis datos, borrar mi cuenta y límites de uso
-- (migración 20260924140000).
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(25);

INSERT INTO auth.users (id, email, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated'),
  ('c0000000-0000-0000-0000-000000000000', 'c@test.local', 'authenticated', 'authenticated');
INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Ale',   'a0000000-0000-0000-0000-000000000000'),
  ('a2000000-0000-0000-0000-000000000000', 'Otro',  'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Sebas', 'b0000000-0000-0000-0000-000000000000'),
  ('b2000000-0000-0000-0000-000000000000', 'Cami',  'b0000000-0000-0000-0000-000000000000');
INSERT INTO vinculos (id, usuario_a, deudor_a, usuario_b, deudor_b, estado, conciliado_a, conciliado_b) VALUES
  ('f0000000-0000-0000-0000-000000000000',
   'a0000000-0000-0000-0000-000000000000', 'a1000000-0000-0000-0000-000000000000',
   'b0000000-0000-0000-0000-000000000000', 'b1000000-0000-0000-0000-000000000000',
   'activo', true, true);

SET LOCAL ROLE authenticated;

-- Con el vínculo activo, lo que anota cada uno nace propuesta para el otro.
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d1', 'a1000000-0000-0000-0000-000000000000', 'Cena',  20, '2026-09-20', false),
  ('a0000000-0000-0000-0000-0000000000d9', 'a2000000-0000-0000-0000-000000000000', 'Borrar', 1, '2026-09-20', false);
DELETE FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d9';
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('b0000000-0000-0000-0000-0000000000e1', 'b1000000-0000-0000-0000-000000000000', 'Taxi',   5, '2026-09-21', false),
  ('b0000000-0000-0000-0000-0000000000e9', 'b2000000-0000-0000-0000-000000000000', 'Borrar', 1, '2026-09-21', false);
DELETE FROM deudas WHERE id = 'b0000000-0000-0000-0000-0000000000e9';

-- ------------------------------------------------------------------------------------
-- Exportar mis datos
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
CREATE TEMP TABLE t (clave text PRIMARY KEY, valor jsonb);
INSERT INTO t VALUES ('exp', exportar_mis_datos());
SELECT is((SELECT valor->>'formato' FROM t WHERE clave = 'exp'), 'deudas-v2/exportacion-1', 'la exportación dice su formato');
SELECT is((SELECT jsonb_path_query_array(valor, '$.deudores[*].nombre') FROM t WHERE clave = 'exp'),
  '["Ale", "Otro"]'::jsonb, 'trae mis dos contactos y ninguno de B');
SELECT is((SELECT jsonb_path_query_array(valor, '$.deudas[*].titulo') FROM t WHERE clave = 'exp'),
  '["Cena"]'::jsonb, 'trae mis deudas y no las de B');
SELECT is((SELECT jsonb_array_length(valor->'propuestas') FROM t WHERE clave = 'exp'), 2,
  'trae las propuestas en que soy parte: la que mandé y la que me llegó');
SELECT is((SELECT jsonb_array_length(valor->'vinculos') FROM t WHERE clave = 'exp'), 1, 'y mi vínculo');
SELECT is((SELECT valor->'perfil'->>'id' FROM t WHERE clave = 'exp'), 'a0000000-0000-0000-0000-000000000000',
  'y mi perfil');
RESET ROLE;
SET LOCAL ROLE anon;
SELECT throws_ok($$SELECT exportar_mis_datos()$$, '42501', NULL, 'sin sesión no se exporta nada');
SET LOCAL ROLE authenticated;

-- ------------------------------------------------------------------------------------
-- Límite de invitaciones: 20 por día
-- ------------------------------------------------------------------------------------
SELECT lives_ok($o$DO $x$ BEGIN
                    FOR i IN 1..20 LOOP PERFORM crear_invitacion('a2000000-0000-0000-0000-000000000000'); END LOOP;
                  END $x$ $o$, '20 invitaciones en un día, bien');
SELECT throws_ok($$SELECT crear_invitacion('a2000000-0000-0000-0000-000000000000')$$,
  'PT429', NULL, 'la 21 se frena (PostgREST responde 429)');

-- ------------------------------------------------------------------------------------
-- Límite de canje: 10 códigos que no sirven por hora
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO t VALUES ('cod', to_jsonb(crear_invitacion('b2000000-0000-0000-0000-000000000000')));
SELECT set_config('request.jwt.claims', '{"sub":"c0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is(reclamar_invitacion('NOEXISTE00'), NULL::uuid, 'un código que no sirve devuelve NULL');
SELECT lives_ok($o$DO $x$ BEGIN
                    FOR i IN 1..9 LOOP PERFORM reclamar_invitacion('NOEXISTE00'); END LOOP;
                  END $x$ $o$, 'hasta 10 intentos fallidos, sin error');
SELECT throws_ok(format('SELECT reclamar_invitacion(%L)', (SELECT valor->>0 FROM t WHERE clave = 'cod')),
  'PT429', NULL, 'al undécimo se frena, aunque ahora traiga un código bueno');
SELECT throws_ok($$SELECT count(*) FROM intentos_canje$$, '42501', NULL, 'nadie lee los intentos desde fuera');

-- ------------------------------------------------------------------------------------
-- Visor: consultas por IP y minuto
-- ------------------------------------------------------------------------------------
SELECT throws_ok($$SELECT contar_visita_visor('1.2.3.4')$$, '42501', NULL, 'solo la edge (service_role) cuenta visitas');
RESET ROLE;
SET LOCAL ROLE service_role;
SELECT is(contar_visita_visor('1.2.3.4'), 1, 'primera visita de una IP en el minuto');
SELECT is(contar_visita_visor('1.2.3.4'), 2, 'la segunda suma');
SELECT is(contar_visita_visor('5.6.7.8'), 1, 'otra IP cuenta aparte');
RESET ROLE;
SELECT ok(NOT EXISTS (SELECT 1 FROM visitas_visor WHERE ip_hash LIKE '%1.2.3.4%'), 'la IP no se guarda en claro');

-- ------------------------------------------------------------------------------------
-- Borrar la cuenta de A
-- ------------------------------------------------------------------------------------
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is(preparar_baja(), 1, 'preparar la baja rompe el único vínculo vivo');
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'b0000000-0000-0000-0000-0000000000e1'), 'local',
  'lo que B le había propuesto a A vuelve a ser solo de B');
RESET ROLE;

SELECT is((SELECT count(*) FROM borrados WHERE owner_id = 'a0000000-0000-0000-0000-000000000000')::int, 1,
  'antes de borrar la cuenta, A tiene su lápida (el borrado normal sigue dejándola)');
DELETE FROM auth.users WHERE id = 'a0000000-0000-0000-0000-000000000000';
SELECT is((SELECT count(*) FROM deudores WHERE owner_id = 'a0000000-0000-0000-0000-000000000000')::int, 0,
  'la cascada se lleva la libreta de A');
SELECT is((SELECT count(*) FROM borrados WHERE owner_id = 'a0000000-0000-0000-0000-000000000000')::int, 0,
  'y no quedan lápidas de A (ni las viejas ni las de la cascada)');
SELECT is((SELECT count(*) FROM borrados WHERE owner_id = 'b0000000-0000-0000-0000-000000000000')::int, 1,
  'la lápida de B sigue');
SELECT is((SELECT count(*) FROM deudas WHERE owner_id = 'b0000000-0000-0000-0000-000000000000')::int, 1,
  'y la libreta de B está intacta');

SELECT * FROM finish();
ROLLBACK;
