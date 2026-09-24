-- Fase 4: invitaciones y vínculos (§4.4, §5.2).
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(27);

INSERT INTO auth.users (id, email, aud, role, raw_user_meta_data) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated', '{"nombre":"Sebas"}'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated', '{"nombre":"Ale"}'),
  ('c0000000-0000-0000-0000-000000000000', 'c@test.local', 'authenticated', 'authenticated', '{"nombre":"Caro"}');
INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Ale',          'a0000000-0000-0000-0000-000000000000'),
  ('a2000000-0000-0000-0000-000000000000', 'Caro',         'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Sebas (viejo)', 'b0000000-0000-0000-0000-000000000000'),
  ('c1000000-0000-0000-0000-000000000000', 'Sebas',        'c0000000-0000-0000-0000-000000000000'),
  ('c2000000-0000-0000-0000-000000000000', 'Ale',          'c0000000-0000-0000-0000-000000000000');

CREATE TEMP TABLE t (clave text PRIMARY KEY, valor text);
GRANT ALL ON t TO authenticated;

SET LOCAL ROLE authenticated;

-- ------------------------------------------------------------------------------------
-- A invita a B; B canjea creando un contacto nuevo
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);

INSERT INTO t VALUES ('viejo', crear_invitacion('a1000000-0000-0000-0000-000000000000'));
INSERT INTO t VALUES ('cod1',  crear_invitacion('a1000000-0000-0000-0000-000000000000'));
SELECT matches((SELECT valor FROM t WHERE clave = 'cod1'), '^[A-HJ-NP-Z2-9]{10}$',
  'el código tiene 10 caracteres sin 0/O/1/I');
SELECT is((SELECT count(*) FROM invitaciones WHERE expira > now())::int, 1,
  'la invitación nueva anula la anterior sin usar');
SELECT throws_ok($$SELECT crear_invitacion('b1000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'A no invita con un deudor ajeno');
SELECT throws_ok($$INSERT INTO invitaciones (codigo, deudor_id) VALUES ('AAAAAAAAAA', 'a1000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'nadie escribe invitaciones directo');
SELECT is(reclamar_invitacion((SELECT valor FROM t WHERE clave = 'cod1')), NULL::uuid,
  'A no reclama su propia invitación');

SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);

SELECT is((SELECT count(*) FROM invitaciones)::int, 0, 'B no ve las invitaciones de A');
SELECT is(reclamar_invitacion('NOEXISTE22'), NULL::uuid,
  'código inexistente → NULL, la misma respuesta para todo');
SELECT is(reclamar_invitacion((SELECT valor FROM t WHERE clave = 'viejo')), NULL::uuid,
  'código anulado → NULL, la misma respuesta para todo');

INSERT INTO t VALUES ('v1', reclamar_invitacion(lower((SELECT valor FROM t WHERE clave = 'cod1')) || ' ')::text);
SELECT is((SELECT estado FROM vinculos WHERE id = (SELECT valor FROM t WHERE clave = 'v1')::uuid), 'conciliando',
  'B canjea (sin importar mayúsculas ni espacios) y el vínculo nace conciliando');
SELECT is((SELECT nombre FROM deudores d JOIN vinculos v ON v.deudor_b = d.id
            WHERE v.id = (SELECT valor FROM t WHERE clave = 'v1')::uuid), 'Sebas',
  'se crea en la libreta de B un contacto con el nombre del perfil de A');
SELECT is((SELECT count(*) FROM deudores)::int, 2, 'B ve sus dos contactos (el viejo y el nuevo)');
SELECT throws_ok($$UPDATE vinculos SET estado = 'activo'$$,
  '42501', NULL, 'nadie actualiza vínculos directo');
SELECT throws_ok($$INSERT INTO vinculos (usuario_a, deudor_a, usuario_b, deudor_b)
                   VALUES ('a0000000-0000-0000-0000-000000000000', 'a2000000-0000-0000-0000-000000000000',
                           'b0000000-0000-0000-0000-000000000000', 'b1000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'nadie inserta vínculos directo');

-- ------------------------------------------------------------------------------------
-- Usada, segundo vínculo del par, deudor ya vinculado
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"c0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is(reclamar_invitacion((SELECT valor FROM t WHERE clave = 'cod1')), NULL::uuid,
  'código ya usado → NULL, la misma respuesta para todo');

SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT throws_ok($$SELECT crear_invitacion('a1000000-0000-0000-0000-000000000000')$$,
  '23505', NULL, 'no se invita con un deudor ya vinculado');
INSERT INTO t VALUES ('cod2', crear_invitacion('a2000000-0000-0000-0000-000000000000'));

SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT throws_ok(format('SELECT reclamar_invitacion(%L)', (SELECT valor FROM t WHERE clave = 'cod2')),
  '23505', 'Ya estás vinculado con esta persona', 'segundo vínculo del mismo par → error');

-- ------------------------------------------------------------------------------------
-- C canjea eligiendo un contacto que ya tenía
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"c0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT throws_ok(format('SELECT reclamar_invitacion(%L, %L)', (SELECT valor FROM t WHERE clave = 'cod2'),
                        'b1000000-0000-0000-0000-000000000000'),
  '42501', NULL, 'C no puede elegir un contacto ajeno');
INSERT INTO t VALUES ('v2', reclamar_invitacion((SELECT valor FROM t WHERE clave = 'cod2'),
                                                 'c1000000-0000-0000-0000-000000000000')::text);
SELECT is((SELECT deudor_b FROM vinculos WHERE id = (SELECT valor FROM t WHERE clave = 'v2')::uuid),
  'c1000000-0000-0000-0000-000000000000'::uuid, 'C vincula su contacto existente');
SELECT is((SELECT count(*) FROM deudores)::int, 2, 'y no se le crea ninguno nuevo');
SELECT is((SELECT count(*) FROM vinculos)::int, 1, 'C solo ve su vínculo, no el de A con B');
SELECT is((public._vinculo_de('c1000000-0000-0000-0000-000000000000')).id,
  (SELECT valor FROM t WHERE clave = 'v2')::uuid, '_vinculo_de encuentra el vínculo vivo');
SELECT ok((public._vinculo_de('a1000000-0000-0000-0000-000000000000')).id IS NULL,
  '_vinculo_de no revela vínculos ajenos');

-- ------------------------------------------------------------------------------------
-- Desvincular y volver a invitar
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"c0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT throws_ok(format('SELECT desvincular(%L)', (SELECT valor FROM t WHERE clave = 'v1')),
  '42501', NULL, 'C no rompe un vínculo ajeno');

SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT lives_ok(format('SELECT desvincular(%L)', (SELECT valor FROM t WHERE clave = 'v1')),
  'B (el invitado) desvincula');
SELECT is((SELECT estado FROM vinculos WHERE id = (SELECT valor FROM t WHERE clave = 'v1')::uuid), 'roto',
  'el vínculo queda roto');

SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO t VALUES ('cod3', crear_invitacion('a1000000-0000-0000-0000-000000000000'));
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT lives_ok(format('SELECT reclamar_invitacion(%L, %L)', (SELECT valor FROM t WHERE clave = 'cod3'),
                       'b1000000-0000-0000-0000-000000000000'),
  'tras romperlo se puede volver a invitar y vincular');

-- Vencida: se fuerza como postgres.
RESET ROLE;
UPDATE invitaciones SET expira = now() - interval '1 second'
 WHERE codigo = (SELECT valor FROM t WHERE clave = 'viejo');
SET LOCAL ROLE authenticated;
SELECT is(reclamar_invitacion((SELECT valor FROM t WHERE clave = 'viejo')), NULL::uuid,
  'código expirado → NULL, la misma respuesta para todo');

SELECT * FROM finish();
ROLLBACK;
