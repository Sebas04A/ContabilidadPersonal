-- Fase 1: cada usuario ve y toca solo lo suyo; anon no toca nada.
-- Se corre con `supabase test db` (pgTAP). Todo dentro de una transacción que se revierte.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(26);

-- ------------------------------------------------------------------------------------
-- Datos: dos usuarios, A y B, cada uno con un deudor, deudas y un pago repartido.
-- (Se cargan como postgres, que no pasa por el RLS.)
-- ------------------------------------------------------------------------------------
INSERT INTO auth.users (id, email, raw_user_meta_data, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', '{"nombre":"Ana"}', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', '{}',               'authenticated', 'authenticated');

INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Deudor de A', 'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Deudor de B', 'b0000000-0000-0000-0000-000000000000');
INSERT INTO deudas (id, deudor_id, titulo, monto, es_mi_deuda, owner_id) VALUES
  ('a2000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000000', 'Cena A',  20, false, 'a0000000-0000-0000-0000-000000000000'),
  ('b2000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000000', 'Cena B',  30, false, 'b0000000-0000-0000-0000-000000000000'),
  ('b2000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000000', 'Taxi B',  10, true,  'b0000000-0000-0000-0000-000000000000');
INSERT INTO pagos (id, deudor_id, monto_total, owner_id) VALUES
  ('b3000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000000', 5, 'b0000000-0000-0000-0000-000000000000');
INSERT INTO detalle_pagos (pago_id, deuda_id, monto_asignado, owner_id) VALUES
  ('b3000000-0000-0000-0000-000000000001', 'b2000000-0000-0000-0000-000000000001', 5, 'b0000000-0000-0000-0000-000000000000');

-- ------------------------------------------------------------------------------------
-- Perfiles: el trigger de alta los crea
-- ------------------------------------------------------------------------------------
SELECT is((SELECT nombre FROM perfiles WHERE id = 'a0000000-0000-0000-0000-000000000000'), 'Ana',
          'el perfil toma el nombre de los metadatos');
SELECT is((SELECT nombre FROM perfiles WHERE id = 'b0000000-0000-0000-0000-000000000000'), 'b',
          'sin nombre en los metadatos, el perfil usa el email');

-- ------------------------------------------------------------------------------------
-- Actuando como A
-- ------------------------------------------------------------------------------------
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);

SELECT is((SELECT count(*) FROM deudores)::int,        1, 'A ve solo su deudor');
SELECT is((SELECT count(*) FROM deudas)::int,          1, 'A ve solo sus deudas');
SELECT is((SELECT count(*) FROM pagos)::int,           0, 'A no ve los pagos de B');
SELECT is((SELECT count(*) FROM detalle_pagos)::int,   0, 'A no ve los detalles de B');
SELECT is((SELECT count(*) FROM vista_estado_deudas)::int, 1, 'la vista respeta el RLS (security_invoker)');
SELECT is((SELECT count(*) FROM perfiles)::int,        1, 'A ve solo su perfil');

-- Escrituras sobre lo ajeno: el RLS las deja en 0 filas, sin error.
UPDATE deudas   SET monto = 999 WHERE id = 'b2000000-0000-0000-0000-000000000001';
DELETE FROM deudas WHERE id = 'b2000000-0000-0000-0000-000000000002';
UPDATE deudores SET nombre = 'hackeado' WHERE id = 'b1000000-0000-0000-0000-000000000000';
UPDATE perfiles SET nombre = 'hackeado' WHERE id = 'b0000000-0000-0000-0000-000000000000';

SELECT throws_ok(
  $$INSERT INTO deudas (deudor_id, titulo, monto) VALUES ('b1000000-0000-0000-0000-000000000000', 'x', 1)$$,
  '23503', NULL, 'A no puede colgar una deuda del deudor de B (FK compuesta)');
SELECT throws_ok(
  $$INSERT INTO deudas (deudor_id, titulo, monto, owner_id)
    VALUES ('b1000000-0000-0000-0000-000000000000', 'x', 1, 'b0000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'A no puede escribir filas a nombre de B (RLS WITH CHECK)');
SELECT throws_ok(
  $$INSERT INTO detalle_pagos (pago_id, deuda_id, monto_asignado)
    VALUES ('b3000000-0000-0000-0000-000000000001', 'a2000000-0000-0000-0000-000000000001', 1)$$,
  '23503', NULL, 'A no puede atar su deuda a un pago de B');
SELECT throws_ok($$INSERT INTO borrados (tabla, id, owner_id)
                  VALUES ('deudas', gen_random_uuid(), 'a0000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'nadie escribe lápidas a mano');
SELECT throws_ok($$UPDATE perfiles SET id = gen_random_uuid() WHERE true$$,
  '42501', NULL, 'del perfil solo se puede cambiar el nombre');

-- Lo propio sí se puede.
SELECT lives_ok($$INSERT INTO deudas (deudor_id, titulo, monto)
                  VALUES ('a1000000-0000-0000-0000-000000000000', 'Nueva', 7)$$,
  'A crea una deuda sin mandar owner_id (DEFAULT auth.uid())');
SELECT is((SELECT owner_id FROM deudas WHERE titulo = 'Nueva'), 'a0000000-0000-0000-0000-000000000000'::uuid,
  'la deuda nueva queda a nombre de A');
SELECT lives_ok($$UPDATE perfiles SET nombre = 'Ana María' WHERE id = 'a0000000-0000-0000-0000-000000000000'$$,
  'A cambia su nombre');
DELETE FROM deudas WHERE titulo = 'Nueva';
SELECT is((SELECT count(*) FROM borrados WHERE tabla = 'deudas')::int, 1,
  'borrar deja una lápida que su dueño ve');

-- ------------------------------------------------------------------------------------
-- Actuando como B: lo suyo sigue intacto y no ve las lápidas de A
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is((SELECT monto FROM deudas WHERE id = 'b2000000-0000-0000-0000-000000000001'), 30.00,
  'el UPDATE de A no tocó la deuda de B');
SELECT is((SELECT count(*) FROM deudas)::int, 2, 'el DELETE de A no borró la deuda de B');
SELECT is((SELECT nombre FROM deudores)::text, 'Deudor de B', 'el UPDATE de A no tocó el deudor de B');
SELECT is((SELECT nombre FROM perfiles)::text, 'b', 'A no pudo renombrar a B');
SELECT is((SELECT count(*) FROM borrados)::int, 0, 'B no ve las lápidas de A');

-- ------------------------------------------------------------------------------------
-- anon: nada
-- ------------------------------------------------------------------------------------
SET LOCAL ROLE anon;
SELECT set_config('request.jwt.claims', '{"role":"anon"}', true);
SELECT throws_ok($$SELECT * FROM deudores$$,           '42501', NULL, 'anon no lee deudores');
SELECT throws_ok($$SELECT * FROM vista_estado_deudas$$, '42501', NULL, 'anon no lee la vista');
SELECT throws_ok($$SELECT estado_cuenta('b1000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'anon no ejecuta estado_cuenta');
SELECT throws_ok($$SELECT registrar_pago('b1000000-0000-0000-0000-000000000000', 1)$$,
  '42501', NULL, 'anon no ejecuta registrar_pago');

SELECT * FROM finish();
ROLLBACK;
