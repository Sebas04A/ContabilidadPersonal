-- Hueco de la fase 5: lo anotado entre las dos confirmaciones de la conciliación, y
-- volver a vincularse después de desvincularse (migración 20260924130000).
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(21);

INSERT INTO auth.users (id, email, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated');
INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Ale',   'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Sebas', 'b0000000-0000-0000-0000-000000000000');
INSERT INTO vinculos (id, usuario_a, deudor_a, usuario_b, deudor_b) VALUES
  ('f0000000-0000-0000-0000-000000000000',
   'a0000000-0000-0000-0000-000000000000', 'a1000000-0000-0000-0000-000000000000',
   'b0000000-0000-0000-0000-000000000000', 'b1000000-0000-0000-0000-000000000000');
-- Historial previo, sin pares: A anotó que Ale le debe $10; B, que le debe $5 a Sebas.
INSERT INTO deudas (id, deudor_id, owner_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d1', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Antes',  10, '2026-09-01', false),
  ('b0000000-0000-0000-0000-0000000000e1', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 'Previa',  5, '2026-09-02', true);

SET LOCAL ROLE authenticated;

-- ------------------------------------------------------------------------------------
-- A confirma primero y sigue anotando mientras B no confirma
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is(confirmar_conciliacion('f0000000-0000-0000-0000-000000000000'),
  '{"estado": "conciliando", "acordadas": 0, "propuestas": 1}'::jsonb,
  'A confirma: "Antes" va propuesta y el vínculo sigue conciliando');

INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d2', 'a1000000-0000-0000-0000-000000000000', 'Taxi', 8, '2026-09-20', false);
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago, es_compensacion, nota) VALUES
  ('a0000000-0000-0000-0000-0000000000f2', 'a1000000-0000-0000-0000-000000000000', 3, '2026-09-21', true, false, 'Transferencia');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d2'), 'local',
  'lo anotado entre las dos confirmaciones nace local (el vínculo no está activo)');

-- ------------------------------------------------------------------------------------
-- B cierra la conciliación: lo tardío de A se le propone
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is(confirmar_conciliacion('f0000000-0000-0000-0000-000000000000'),
  '{"estado": "activo", "acordadas": 0, "propuestas": 1, "tardias": 2}'::jsonb,
  'B confirma: "Previa" va propuesta, el vínculo pasa a activo y las 2 filas tardías de A se proponen');
SELECT is((SELECT count(*) FROM propuestas WHERE para_usuario = auth.uid() AND estado = 'pendiente')::int, 3,
  'B tiene 3 propuestas de A: la del historial y las 2 tardías');
SELECT is((SELECT payload FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000d2'),
  '{"monto": 8, "fecha": "2026-09-20", "es_mia": false, "titulo": "Taxi"}'::jsonb,
  'la deuda tardía viaja en el punto de vista de A y con su título (se anotó con el vínculo vivo)');
SELECT is((SELECT payload FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000f2'),
  '{"monto": 3, "fecha": "2026-09-21", "es_mia": true, "nota": "Transferencia"}'::jsonb,
  'el pago tardío también');
SELECT is((SELECT de_usuario FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000d2'),
  'a0000000-0000-0000-0000-000000000000'::uuid, 'la propuesta tardía es de A, no de quien cerró');

SELECT is(aceptar_propuesta((SELECT id FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000d2'))->>'resultado',
  'aceptada', 'B acepta el taxi');
SELECT is((SELECT titulo || '|' || es_mi_deuda FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d2'),
  'Taxi|true', 'la fila espejo nace con el título y la dirección invertida');
SELECT ok((verificar_vinculo('f0000000-0000-0000-0000-000000000000')->>'ok')::boolean,
  'el vínculo cuadra');

-- ------------------------------------------------------------------------------------
-- A ve lo suyo
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is((SELECT string_agg(estado_acuerdo, ',' ORDER BY id) FROM deudas), 'propuesta,acordada',
  'en A: "Antes" sigue esperando respuesta y el taxi quedó acordado');
SELECT is((SELECT estado_acuerdo FROM pagos WHERE id = 'a0000000-0000-0000-0000-0000000000f2'), 'propuesta',
  'el pago tardío espera respuesta');

-- ------------------------------------------------------------------------------------
-- Desvincularse y volver a vincularse: la segunda conciliación no choca con la primera
-- ------------------------------------------------------------------------------------
SELECT lives_ok($$SELECT desvincular('f0000000-0000-0000-0000-000000000000')$$, 'A se desvincula');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d1'), 'local',
  'lo pendiente vuelve a local');

-- Se vuelven a vincular por el flujo real (invitación + canje).
CREATE TEMP TABLE t (clave text PRIMARY KEY, valor jsonb);
RESET ROLE;
GRANT ALL ON t TO authenticated;
SET LOCAL ROLE authenticated;
INSERT INTO t VALUES ('codigo', to_jsonb(crear_invitacion('a1000000-0000-0000-0000-000000000000')));
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO t VALUES ('vinculo', to_jsonb(reclamar_invitacion(
  (SELECT valor->>0 FROM t WHERE clave = 'codigo'), 'b1000000-0000-0000-0000-000000000000')));
-- Desde la decisión 12 (2026-09-25) el espejo ya no recuerda quién lo anotó: se busca por
-- título, que nació con él.
SELECT is((SELECT estado_acuerdo FROM deudas
            WHERE deudor_id = 'b1000000-0000-0000-0000-000000000000' AND titulo = 'Taxi'), 'local',
  'lo acordado en el vínculo roto vuelve a local para conciliarse de nuevo');

SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO t VALUES ('cand', candidatos_conciliacion((SELECT (valor->>0)::uuid FROM t WHERE clave = 'vinculo')));
SELECT is((SELECT jsonb_path_query_array(valor, '$.pares[*].mia') FROM t WHERE clave = 'cand'),
  '["a0000000-0000-0000-0000-0000000000d2"]'::jsonb, 'el taxi acordado antes se vuelve a emparejar solo');
SELECT is(confirmar_conciliacion((SELECT (valor->>0)::uuid FROM t WHERE clave = 'vinculo'),
                                 (SELECT jsonb_agg(p - 'puntaje' - 'dudoso') FROM t, jsonb_array_elements(valor->'pares') p WHERE clave = 'cand')),
  '{"estado": "conciliando", "acordadas": 1, "propuestas": 2}'::jsonb,
  'A vuelve a proponer "Antes" y el pago sin chocar con las propuestas anuladas del vínculo anterior');

SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is(confirmar_conciliacion((SELECT (valor->>0)::uuid FROM t WHERE clave = 'vinculo'))->>'estado', 'activo',
  'B también vuelve a conciliar y el vínculo queda activo');
SELECT ok((verificar_vinculo((SELECT (valor->>0)::uuid FROM t WHERE clave = 'vinculo'))->>'ok')::boolean,
  'el vínculo nuevo cuadra');
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT lives_ok($$SELECT proponer_cambio('deuda', 'a0000000-0000-0000-0000-0000000000d2', 'editar', '{"monto": 9}')$$,
  'y el taxi se puede volver a cambiar por propuesta (antes quedaba congelado)');
RESET ROLE;
SELECT is((SELECT count(*) FROM acuerdos WHERE vinculo_id = 'f0000000-0000-0000-0000-000000000000')::int, 0,
  'el acuerdo del vínculo roto se borró');

SELECT * FROM finish();
ROLLBACK;
