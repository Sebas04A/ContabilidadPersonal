-- Fase 5: conciliación inicial (§4.6).
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(20);

INSERT INTO auth.users (id, email, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated'),
  ('c0000000-0000-0000-0000-000000000000', 'c@test.local', 'authenticated', 'authenticated');
INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Ale',   'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Sebas', 'b0000000-0000-0000-0000-000000000000');
INSERT INTO vinculos (id, usuario_a, deudor_a, usuario_b, deudor_b) VALUES
  ('f0000000-0000-0000-0000-000000000000',
   'a0000000-0000-0000-0000-000000000000', 'a1000000-0000-0000-0000-000000000000',
   'b0000000-0000-0000-0000-000000000000', 'b1000000-0000-0000-0000-000000000000');

-- Las dos libretas anotaron lo mismo con ruido: fechas corridas, títulos distintos, dos
-- deudas de $20 con fechas pegadas (los títulos las desempatan) y una de más en cada lado.
INSERT INTO deudas (id, deudor_id, owner_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d1', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Uber 28 ag',  12.50, '2026-08-28', false),
  ('a0000000-0000-0000-0000-0000000000d2', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Cena',        40,    '2026-09-01', true),
  ('a0000000-0000-0000-0000-0000000000d3', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Pizza',       20,    '2026-09-05', false),
  ('a0000000-0000-0000-0000-0000000000d4', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Pizza extra', 20,    '2026-09-06', false),
  ('a0000000-0000-0000-0000-0000000000d5', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Solo A',       7,    '2026-09-07', false),
  ('b0000000-0000-0000-0000-0000000000d1', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 'uber',        12.50, '2026-08-30', true),
  ('b0000000-0000-0000-0000-0000000000d2', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 'cena cumple', 40,    '2026-09-02', false),
  ('b0000000-0000-0000-0000-0000000000d4', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 'pizza extra', 20,    '2026-09-06', true),
  ('b0000000-0000-0000-0000-0000000000d3', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 'pizza',       20,    '2026-09-05', true),
  ('b0000000-0000-0000-0000-0000000000d6', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 'Solo B',       9,    '2026-09-08', true);
INSERT INTO pagos (id, deudor_id, owner_id, monto_total, fecha_pago, es_mi_pago, es_compensacion, cruce_id) VALUES
  ('a0000000-0000-0000-0000-00000000000f', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 10, '2026-09-10', false, false, NULL),
  ('b0000000-0000-0000-0000-00000000000f', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 10, '2026-09-11', true,  false, NULL),
  -- Un cruce de A: nunca se concilia.
  ('a0000000-0000-0000-0000-0000000000c1', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000',  5, '2026-09-12', true,  true, 'a0000000-0000-0000-0000-0000000000cc'),
  ('a0000000-0000-0000-0000-0000000000c2', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000',  5, '2026-09-12', false, true, 'a0000000-0000-0000-0000-0000000000cc');

CREATE TEMP TABLE t (clave text PRIMARY KEY, valor jsonb);
GRANT ALL ON t TO authenticated;
SET LOCAL ROLE authenticated;

-- ------------------------------------------------------------------------------------
-- Candidatos vistos por A
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO t VALUES ('saldo_antes', (estado_cuenta('a1000000-0000-0000-0000-000000000000'))->'resumen');
INSERT INTO t VALUES ('cand', candidatos_conciliacion('f0000000-0000-0000-0000-000000000000'));

SELECT is(jsonb_array_length((SELECT valor->'pares' FROM t WHERE clave = 'cand')), 5,
  'empareja las 4 deudas comunes y el pago');
SELECT is((SELECT p->>'suya' FROM t, jsonb_array_elements(valor->'pares') p
            WHERE clave = 'cand' AND p->>'mia' = 'a0000000-0000-0000-0000-0000000000d3'),
  'b0000000-0000-0000-0000-0000000000d3', 'las dos pizzas de $20 no se cruzan: el título desempata');
SELECT ok(NOT EXISTS (SELECT 1 FROM t, jsonb_array_elements(valor->'pares') p
                       WHERE clave = 'cand' AND (p->>'dudoso')::boolean),
  'ningún par de este juego es dudoso');
SELECT is(jsonb_array_length((SELECT valor->'mias' FROM t WHERE clave = 'cand')), 6,
  'mis filas conciliables: 5 deudas y 1 pago (los cruces no cuentan)');
SELECT ok(NOT EXISTS (SELECT 1 FROM t, jsonb_array_elements(valor->'suyas') s
                       WHERE clave = 'cand' AND s ? 'titulo'),
  'de las filas del otro no se ven los títulos');

SELECT set_config('request.jwt.claims', '{"sub":"c0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT throws_ok($$SELECT candidatos_conciliacion('f0000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'un tercero no ve la conciliación');
SELECT throws_ok($$SELECT confirmar_conciliacion('f0000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, 'ni la confirma');

-- ------------------------------------------------------------------------------------
-- A confirma los pares propuestos
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"a0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
INSERT INTO t VALUES ('conf_a', confirmar_conciliacion('f0000000-0000-0000-0000-000000000000',
  (SELECT jsonb_agg(p - 'puntaje' - 'dudoso') FROM t, jsonb_array_elements(valor->'pares') p WHERE clave = 'cand')));
SELECT is((SELECT valor FROM t WHERE clave = 'conf_a'),
  '{"estado": "conciliando", "acordadas": 5, "propuestas": 1}'::jsonb,
  '5 pares acordados, "Solo A" propuesto, y B todavía tiene lo suyo por conciliar');
SELECT is((SELECT count(*) FROM deudas WHERE estado_acuerdo = 'acordada')::int, 4,
  'A ve sus 4 deudas acordadas');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d5'), 'propuesta',
  'la deuda sin par de A queda propuesta');
SELECT is((SELECT estado_acuerdo FROM pagos WHERE id = 'a0000000-0000-0000-0000-0000000000c1'), 'local',
  'el cruce sigue local');
-- Fase 6: con vínculo vivo el resumen trae además saldo_acordado y pendiente_acuerdo, que
-- sí cambian al conciliar. Lo demás no se mueve.
SELECT is(((estado_cuenta('a1000000-0000-0000-0000-000000000000'))->'resumen') - 'saldo_acordado' - 'pendiente_acuerdo',
  (SELECT valor - 'saldo_acordado' - 'pendiente_acuerdo' FROM t WHERE clave = 'saldo_antes'),
  'el saldo de A no se mueve un centavo');

INSERT INTO t VALUES ('conf_a2', confirmar_conciliacion('f0000000-0000-0000-0000-000000000000',
  (SELECT jsonb_agg(p - 'puntaje' - 'dudoso') FROM t, jsonb_array_elements(valor->'pares') p WHERE clave = 'cand')));
SELECT is((SELECT (valor->>'acordadas')::int + (valor->>'propuestas')::int FROM t WHERE clave = 'conf_a2'), 0,
  'confirmar dos veces no hace nada');

-- ------------------------------------------------------------------------------------
-- B
-- ------------------------------------------------------------------------------------
SELECT set_config('request.jwt.claims', '{"sub":"b0000000-0000-0000-0000-000000000000","role":"authenticated"}', true);
SELECT is((SELECT count(*) FROM deudas WHERE estado_acuerdo = 'acordada')::int, 4,
  'B también ve acordadas sus 4 deudas');
SELECT is((SELECT count(*) FROM propuestas WHERE para_usuario = auth.uid() AND estado = 'pendiente')::int, 1,
  'y tiene 1 propuesta pendiente de A');
SELECT is((SELECT payload FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000d5'),
  '{"monto": 7.00, "fecha": "2026-09-07", "es_mia": false}'::jsonb, 'el payload va en el punto de vista de A');
SELECT throws_ok($$SELECT confirmar_conciliacion('f0000000-0000-0000-0000-000000000000',
                    '[{"entidad":"deuda","mia":"b0000000-0000-0000-0000-0000000000d6","suya":"a0000000-0000-0000-0000-0000000000d5"}]')$$,
  '22023', NULL, 'un par que no cuadra (monto, o fila ya no local) se rechaza');
SELECT is(confirmar_conciliacion('f0000000-0000-0000-0000-000000000000'),
  '{"estado": "activo", "acordadas": 0, "propuestas": 1}'::jsonb,
  'B confirma sin pares: "Solo B" va propuesto y el vínculo pasa a activo');

RESET ROLE;
SELECT is((SELECT count(*) FROM acuerdos)::int, 5, 'hay 5 acuerdos');
SELECT ok((SELECT count(DISTINCT (entidad, fila_a)) = count(*) AND count(DISTINCT (entidad, fila_b)) = count(*)
             FROM acuerdos), 'ninguna fila está en dos acuerdos');

SELECT * FROM finish();
ROLLBACK;
