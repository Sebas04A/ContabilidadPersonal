-- Test: Rechazar filas con cruce (incluso con cruces malformados o legados)
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(11);

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

SET LOCAL ROLE authenticated;

-- Caso 1: B anota una deuda por 20 (entra sola como acordada a la libreta de A con origen_id)
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
VALUES ('b0000000-0000-0000-0000-0000000000d1', 'b1000000-0000-0000-0000-000000000000', 'Cena B', 20, '2026-06-01', false);

-- A anota una deuda por 20 (entra sola a la libreta de B)
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
VALUES ('a0000000-0000-0000-0000-0000000000d1', 'a1000000-0000-0000-0000-000000000000', 'Taxi A', 20, '2026-06-01', false);

-- A aplica un cruce en su libreta
SELECT lives_ok($$SELECT aplicar_cruce('a1000000-0000-0000-0000-000000000000')$$, '1. Cruce aplicado correctamente');

-- En la libreta de A, la deuda que vino de B está acordada
SELECT is((SELECT estado_acuerdo FROM deudas WHERE origen_id = 'b0000000-0000-0000-0000-0000000000d1'), 'acordada',
  '2. La deuda de B en libreta de A está acordada');

-- Simular la inconsistencia de datos: ambos pagos virtuales del cruce con es_mi_pago = false
RESET ROLE;
UPDATE pagos SET es_mi_pago = false WHERE cruce_id IS NOT NULL;
SET LOCAL ROLE authenticated;

-- A rechaza la deuda que anotó B (con cruce y pagos virtuales inconsistentes)
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT lives_ok(format($$SELECT rechazar_fila('deuda', %L::uuid, 'no reconozco la cena')$$,
  (SELECT id FROM deudas WHERE origen_id = 'b0000000-0000-0000-0000-0000000000d1')),
  '3. A puede rechazar la deuda con cruce y pagos virtuales malformados');

-- La deuda queda rechazada
SELECT is((SELECT estado_acuerdo FROM deudas WHERE origen_id = 'b0000000-0000-0000-0000-0000000000d1'), 'rechazada',
  '4. La deuda pasa a estado rechazada');

-- La deuda propia de A queda liberada del cruce
SELECT is((SELECT count(*) FROM detalle_pagos WHERE deuda_id = 'a0000000-0000-0000-0000-0000000000d1'), 0::bigint,
  '5. La deuda de A ya no tiene detalles de pago asociados');

RESET ROLE;
INSERT INTO pagos (id, deudor_id, monto_total, es_compensacion, cruce_id, owner_id, fecha_pago)
VALUES ('e0000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000000', 10, true, NULL,
        'a0000000-0000-0000-0000-000000000000', CURRENT_DATE);
INSERT INTO detalle_pagos (pago_id, deuda_id, monto_asignado, owner_id)
VALUES ('e0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-0000000000d1', 10,
        'a0000000-0000-0000-0000-000000000000');
-- Un pago de compensación huérfano (sin cruce_id ni detalle) de OTRO usuario: sacar la
-- deuda de A de sus cruces viejos no puede tocarlo.
INSERT INTO pagos (id, deudor_id, monto_total, es_compensacion, cruce_id, owner_id, fecha_pago)
VALUES ('e0000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000000', 7, true, NULL,
        'b0000000-0000-0000-0000-000000000000', CURRENT_DATE);

SELECT lives_ok($$SELECT _sacar_de_cruces('a0000000-0000-0000-0000-0000000000d1')$$,
  '6. _sacar_de_cruces no falla ante pagos de compensación legados sin cruce_id');

SELECT is((SELECT count(*) FROM pagos WHERE id = 'e0000000-0000-0000-0000-000000000001'), 0::bigint,
  '7. El pago legado de A, que quedó sin detalle, se borra');
SELECT is((SELECT count(*) FROM pagos WHERE id = 'e0000000-0000-0000-0000-000000000002'), 1::bigint,
  '8. El pago de compensación huérfano de B sigue ahí (el borrado se limita a lo que se tocó)');

-- _editar_cruce_aplicar se puede llamar por la API: tiene que correr con los permisos de
-- quien llama, para que el RLS le esconda los cruces ajenos.
SELECT is((SELECT prosecdef FROM pg_proc WHERE oid = '_editar_cruce_aplicar(uuid, uuid[])'::regprocedure),
  false, '9. _editar_cruce_aplicar es SECURITY INVOKER');

-- A arma un cruce nuevo (le debe $5 a Bea; Bea le debe los $20 del taxi).
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
VALUES ('a0000000-0000-0000-0000-0000000000d2', 'a1000000-0000-0000-0000-000000000000', 'Café A', 5, '2026-06-02', true);
SELECT aplicar_cruce('a1000000-0000-0000-0000-000000000000');

RESET ROLE;
CREATE TEMP TABLE cruce_a AS
  SELECT DISTINCT cruce_id AS id FROM pagos
   WHERE owner_id = 'a0000000-0000-0000-0000-000000000000' AND cruce_id IS NOT NULL;
GRANT SELECT ON cruce_a TO authenticated;

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT throws_like(format($$SELECT _editar_cruce_aplicar(%L::uuid, NULL)$$, (SELECT id FROM cruce_a)),
  '%No existe el cruce%', '10. B no puede recortar el cruce de A llamando a _editar_cruce_aplicar');

RESET ROLE;
SELECT is((SELECT count(*) FROM pagos WHERE cruce_id = (SELECT id FROM cruce_a)), 2::bigint,
  '11. El cruce de A sigue entero');

SELECT * FROM finish();
ROLLBACK;
