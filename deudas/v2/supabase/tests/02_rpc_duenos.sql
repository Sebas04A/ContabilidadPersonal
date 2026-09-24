-- Fase 1: los RPC solo operan sobre lo propio; idempotencia por dueño; rotar_token.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(16);

INSERT INTO auth.users (id, email, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated');
INSERT INTO deudores (id, nombre, owner_id, token) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Deudor de A', 'a0000000-0000-0000-0000-000000000000', 'token-viejo-a'),
  ('b1000000-0000-0000-0000-000000000000', 'Deudor de B', 'b0000000-0000-0000-0000-000000000000', 'token-b');
-- A y B tienen deudas en los dos sentidos, para que haya algo que cruzar.
INSERT INTO deudas (deudor_id, titulo, monto, es_mi_deuda, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Me debe A',  20, false, 'a0000000-0000-0000-0000-000000000000'),
  ('a1000000-0000-0000-0000-000000000000', 'Le debo A',   8, true,  'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Me debe B',  15, false, 'b0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Le debo B',   6, true,  'b0000000-0000-0000-0000-000000000000');

-- ------------------------------------------------------------------------------------
-- B trabaja sobre lo suyo: cruce y un pago con clave de idempotencia
-- ------------------------------------------------------------------------------------
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);

SELECT lives_ok($$SELECT aplicar_cruce('b1000000-0000-0000-0000-000000000000')$$,
  'B cruza las deudas de su deudor');
SELECT is((SELECT count(*) FROM pagos WHERE es_compensacion)::int, 2,
  'el cruce crea sus dos pagos virtuales, a nombre de B');
SELECT lives_ok($$SELECT registrar_pago('b1000000-0000-0000-0000-000000000000', 4, false, CURRENT_DATE,
                                        'c0000000-0000-0000-0000-00000000000c')$$,
  'B registra un pago con idem_key');

-- ------------------------------------------------------------------------------------
-- A contra lo de B
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);

SELECT throws_ok($$SELECT registrar_pago('b1000000-0000-0000-0000-000000000000', 5)$$,
  '42501', NULL, 'A no registra pagos en el deudor de B');
SELECT throws_ok($$SELECT aplicar_cruce('b1000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'A no cruza las deudas de B');
SELECT throws_ok($$SELECT rotar_token('b1000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'A no rota el token de B');
SELECT is(jsonb_array_length(estado_cuenta('b1000000-0000-0000-0000-000000000000') -> 'deudas'), 0,
  'estado_cuenta de un deudor ajeno sale vacío');
-- Los ids de lo de B, sacados como postgres a una tabla temporal que A puede leer.
RESET ROLE;
CREATE TEMP TABLE ids AS
SELECT (SELECT id FROM pagos WHERE idem_key = 'c0000000-0000-0000-0000-00000000000c') AS pago_b,
       (SELECT cruce_id FROM pagos WHERE es_compensacion LIMIT 1)                     AS cruce_b;
GRANT SELECT ON ids TO authenticated;
SET LOCAL ROLE authenticated;
SELECT throws_ok(format('SELECT editar_pago(%L::uuid, CURRENT_DATE, %L)', (SELECT pago_b FROM ids), 'hackeado'),
  NULL, NULL, 'A no edita el pago de B');
SELECT throws_ok(format('SELECT editar_cruce(%L::uuid, NULL, false)', (SELECT cruce_b FROM ids)),
  NULL, NULL, 'A no edita el cruce de B');

-- ------------------------------------------------------------------------------------
-- A sobre lo suyo
-- ------------------------------------------------------------------------------------
SELECT lives_ok($$SELECT registrar_pago('a1000000-0000-0000-0000-000000000000', 5, false, CURRENT_DATE,
                                        'c0000000-0000-0000-0000-00000000000c')$$,
  'A puede usar la MISMA idem_key que B: la idempotencia es por dueño');
SELECT is((SELECT count(*) FROM pagos WHERE idem_key = 'c0000000-0000-0000-0000-00000000000c')::int, 1,
  'y se creó un pago nuevo de A (no se tomó por repetido)');
SELECT is((SELECT (registrar_pago('a1000000-0000-0000-0000-000000000000', 5, false, CURRENT_DATE,
                                  'c0000000-0000-0000-0000-00000000000c') ->> 'repetido')::boolean), true,
  'repetir la llamada de A sí es repetido');
SELECT ok((SELECT count(*) FROM detalle_pagos) > 0,
  'el RPC repartió el pago de A (la FK compuesta exige que los detalles sean de A)');

SELECT isnt(rotar_token('a1000000-0000-0000-0000-000000000000'), 'token-viejo-a',
  'rotar_token devuelve un token nuevo');

-- ------------------------------------------------------------------------------------
-- B: lo suyo intacto
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is((SELECT nota FROM pagos WHERE idem_key = 'c0000000-0000-0000-0000-00000000000c'), NULL::text,
  'la nota del pago de B no cambió');
SELECT is((SELECT count(*) FROM pagos WHERE es_compensacion)::int, 2, 'el cruce de B sigue entero');

SELECT * FROM finish();
ROLLBACK;
