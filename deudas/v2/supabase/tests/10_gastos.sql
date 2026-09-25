-- Fase 9A: gasto suelto (§4.8; decisiones 25 a 31 de §3.3). Los escenarios de 9.2, en
-- orden y sobre la misma libreta: cada uno parte de lo que dejó el anterior, con "mi
-- saldo" (resumen.neto) de cada contacto calculado a mano en los comentarios.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(132);

-- ------------------------------------------------------------------------------------
-- Datos: A (a0…) y B (b0…) vinculados y activos; C (c0…) es un tercero.
--   libreta de A: "Bea" (a1, la del vínculo con B), "Beto" (a2) y "Caro" (a3), personas
--   libreta de B: "Ana" (b1)
--   libreta de C: "Cato" (c1)
-- ------------------------------------------------------------------------------------
INSERT INTO auth.users (id, email, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated'),
  ('c0000000-0000-0000-0000-000000000000', 'c@test.local', 'authenticated', 'authenticated');
INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Bea',  'a0000000-0000-0000-0000-000000000000'),
  ('a2000000-0000-0000-0000-000000000000', 'Beto', 'a0000000-0000-0000-0000-000000000000'),
  ('a3000000-0000-0000-0000-000000000000', 'Caro', 'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Ana',  'b0000000-0000-0000-0000-000000000000'),
  ('c1000000-0000-0000-0000-000000000000', 'Cato', 'c0000000-0000-0000-0000-000000000000');
INSERT INTO vinculos (id, usuario_a, deudor_a, usuario_b, deudor_b, estado, conciliado_a, conciliado_b) VALUES
  ('f0000000-0000-0000-0000-000000000000',
   'a0000000-0000-0000-0000-000000000000', 'a1000000-0000-0000-0000-000000000000',
   'b0000000-0000-0000-0000-000000000000', 'b1000000-0000-0000-0000-000000000000',
   'activo', true, true);

CREATE FUNCTION pg_temp.como(u text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('request.jwt.claims',
        json_build_object('sub', CASE u WHEN 'A' THEN 'a0000000-0000-0000-0000-000000000000'
                                        WHEN 'B' THEN 'b0000000-0000-0000-0000-000000000000'
                                        ELSE 'c0000000-0000-0000-0000-000000000000' END,
                          'role', 'authenticated')::text, true);
END $$;
-- Mi saldo con un contacto (+ me debe, − le debo).
CREATE FUNCTION pg_temp.saldo(deudor text) RETURNS numeric LANGUAGE sql AS $$
    SELECT (estado_cuenta(deudor::uuid) -> 'resumen' ->> 'neto')::numeric
$$;
-- Las deudas de un gasto: "contacto:monto:dirección:estado", en orden de contacto.
CREATE FUNCTION pg_temp.deudas(gasto text) RETURNS text LANGUAGE sql AS $$
    SELECT string_agg(r.nombre || ':' || d.monto || ':' || CASE WHEN d.es_mi_deuda THEN 'debo' ELSE 'me_debe' END
                      || ':' || d.estado_acuerdo, ' ' ORDER BY r.nombre)
      FROM deudas d JOIN deudores r ON r.id = d.deudor_id
     WHERE d.gasto_id = gasto::uuid
$$;
-- Los participantes de un gasto: "quién:pagado:parte:estado", en orden.
CREATE FUNCTION pg_temp.partes(gasto text) RETURNS text LANGUAGE sql AS $$
    SELECT string_agg(COALESCE(r.nombre, 'yo') || ':' || p.pagado || ':' || p.parte || ':' || p.estado,
                      ' ' ORDER BY p.orden)
      FROM gasto_participantes p LEFT JOIN deudores r ON r.id = p.deudor_id
     WHERE p.gasto_id = gasto::uuid
$$;
CREATE FUNCTION pg_temp.ok() RETURNS boolean LANGUAGE sql AS $$
    SELECT (verificar_vinculo('f0000000-0000-0000-0000-000000000000') ->> 'ok')::boolean
$$;

-- ====================================================================================
-- 0. _repartir (decisión 25), la tabla de casos que comparte con lib/dominio/reparto.dart
-- ====================================================================================
SELECT is(_repartir(100, '{1,1,1}', 1), '{33.34,33.33,33.33}'::numeric[], '0. $100 entre 3: el centavo que sobra, a quien pagó');
SELECT is(_repartir(100, '{1,1,1}', 3), '{33.33,33.33,33.34}'::numeric[], '0. …aunque esté último en la lista');
SELECT is(_repartir(100, '{1,1,1}', NULL), '{33.34,33.33,33.33}'::numeric[], '0. sin quien pagó en el reparto: en el orden de la lista');
SELECT is(_repartir(0.05, '{1,1,1}', 2), '{0.02,0.02,0.01}'::numeric[], '0. $0.05 entre 3: primero a quien pagó (2.º) y después en orden (1.º)');
SELECT is(_repartir(100, '{2,1,1}', NULL), '{50.00,25.00,25.00}'::numeric[], '0. partes 2:1:1');
SELECT is(_repartir(10, '{33.33,33.33,33.34}', 1), '{3.34,3.33,3.33}'::numeric[], '0. porcentajes con decimales');
SELECT is(_repartir(42.42, '{1}', 1), '{42.42}'::numeric[], '0. un solo participante: todo');
SELECT is(_repartir(0.01, '{1,1}', 2), '{0.00,0.01}'::numeric[], '0. un centavo entre dos');
SELECT throws_ok($$SELECT _repartir(10, '{1,0}')$$, '22023', NULL, '0. un peso en cero no se reparte');
SELECT throws_ok($$SELECT _repartir(10, '{}')$$, '22023', NULL, '0. sin nadie no se reparte');
-- Repartir de nuevo tras un rechazo (§4.8): con pesos, entre los que quedan; en 'montos',
-- lo absorbe quien pagó (decisión 26). La fila rechazada conserva su parte de antes.
SELECT is(_partes_gasto(90, 'igual', '[{"peso":1},{"peso":1},{"peso":1,"rechazada":true}]', 1),
  '{45.00,45.00,30.00}'::numeric[], '0. igual: $90 entre 3 y uno rechaza → 45 y 45 (la rechazada era 30)');
SELECT is(_partes_gasto(100, 'partes', '[{"peso":2},{"peso":1,"rechazada":true},{"peso":1}]', 1),
  '{66.67,25.00,33.33}'::numeric[], '0. partes 2:1:1 y rechaza el de 1 → 2:1');
SELECT is(_partes_gasto(90, 'montos', '[{"peso":50},{"peso":25},{"peso":15,"rechazada":true}]', 1),
  '{65,25,15}'::numeric[], '0. montos: lo rechazado lo absorbe quien pagó (decisión 26)');
SELECT is(_partes_gasto(90, 'montos', '[{"peso":null},{"peso":60},{"peso":30,"rechazada":true}]', 1),
  '{30,60,30}'::numeric[], '0. montos, quien pagó no participaba: absorbe igual');

SET LOCAL ROLE authenticated;

-- ====================================================================================
-- 1. A pagó $90 entre A, Beto y Caro → dos deudas "me debe $30" con gasto_id; la parte de
--    A queda solo en el gasto. Beto: +30. Caro: +30.
-- ====================================================================================
SELECT pg_temp.como('A');
SELECT is((crear_gasto('9a000000-0000-0000-0000-000000000001', NULL, 'Cena', 90, '2026-07-01', 'igual',
    '[{"pagado":90},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000","deuda_id":"9d000000-0000-0000-0000-000000000001"},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]',
    '9e000000-0000-0000-0000-000000000001') ->> 'repetido')::boolean, false, '1. A anota la cena');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000001'),
  'Beto:30.00:me_debe:local Caro:30.00:me_debe:local', '1. una deuda por contacto, con gasto_id');
SELECT is(pg_temp.partes('9a000000-0000-0000-0000-000000000001'),
  'yo:90.00:30.00:activa Beto:0.00:30.00:activa Caro:0.00:30.00:activa', '1. el gasto guarda lo que puso y le toca a cada uno');
SELECT is((SELECT gasto_id FROM deudas WHERE id = '9d000000-0000-0000-0000-000000000001'),
  '9a000000-0000-0000-0000-000000000001'::uuid, '1. la deuda de Beto lleva el id que mandó el teléfono');
SELECT is((SELECT titulo FROM deudas WHERE id = '9d000000-0000-0000-0000-000000000001'), 'Cena',
  '1. y el título del gasto');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 30.00, '1. estado_cuenta de Beto: +30');
SELECT is(pg_temp.saldo('a3000000-0000-0000-0000-000000000000'), 30.00, '1. estado_cuenta de Caro: +30');

-- ====================================================================================
-- 2. Pagó Beto $30 entre A, Beto y Caro → una sola deuda: A le debe $10 a Beto. Lo de
--    Caro con Beto queda solo en el gasto (decisión 31). Beto: 30 − 10 = +20.
-- ====================================================================================
SELECT lives_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-000000000002', NULL, 'Taxi', 30, '2026-07-02', 'igual',
    '[{},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000","pagado":30},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]')$$, '2. A anota el taxi que pagó Beto');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000002'), 'Beto:10.00:debo:local',
  '2. en la libreta de A solo queda lo que A le debe a Beto');
SELECT is(pg_temp.partes('9a000000-0000-0000-0000-000000000002'),
  'yo:0.00:10.00:activa Beto:30.00:10.00:activa Caro:0.00:10.00:activa', '2. la parte de Caro queda en el gasto, como información');
SELECT is((SELECT deuda_id IS NOT NULL FROM gasto_participantes
            WHERE gasto_id = '9a000000-0000-0000-0000-000000000002' AND orden = 1), true,
  '2. la deuda cuelga de la fila de A (es su parte)');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 20.00, '2. Beto: +30 − 10 = +20');
SELECT is(pg_temp.saldo('a3000000-0000-0000-0000-000000000000'), 30.00, '2. Caro no cambia');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000ff', NULL, 'Nada', 30, '2026-07-02', 'igual',
    '[{"participa":false},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000","pagado":30},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]')$$, '22023', NULL,
  '2. pagó Beto y A no participa: no hay nada que anotar en su libreta');

-- ====================================================================================
-- 3. Sin incluirme: A pagó $90 de un regalo para Beto y Caro → $45 cada uno.
--    Beto: 20 + 45 = +65. Caro: 30 + 45 = +75.
-- ====================================================================================
SELECT lives_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-000000000003', NULL, 'Regalo', 90, '2026-07-03', 'igual',
    '[{"pagado":90,"participa":false},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000"},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]')$$, '3. A anota el regalo sin incluirse');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000003'),
  'Beto:45.00:me_debe:local Caro:45.00:me_debe:local', '3. $45 cada uno');
SELECT is(pg_temp.partes('9a000000-0000-0000-0000-000000000003'),
  'yo:90.00:0.00:activa Beto:0.00:45.00:activa Caro:0.00:45.00:activa', '3. la parte de A es 0');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 65.00, '3. Beto: +65');
SELECT is(pg_temp.saldo('a3000000-0000-0000-0000-000000000000'), 75.00, '3. Caro: +75');

-- ====================================================================================
-- 4. Editar: la cena pasa a $96 → $32 cada uno. Caro paga $30 (FIFO: a la cena, la más
--    vieja). La cena baja a $60 → la parte de Caro ($20) queda por debajo de lo pagado y
--    suelta el exceso (decisión 16): los $10 quedan como saldo a favor.
--    Beto: 65 + 2 = 67 → 67 − 12 = +55. Caro: 75 + 2 = 77 → − 30 = 47 → − 12 = +35.
-- ====================================================================================
SELECT is((editar_gasto('9a000000-0000-0000-0000-000000000001', 'Cena', 96, '2026-07-01', 'igual',
    '[{"pagado":96},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000"},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]') ->> 'esperan_respuesta')::int, 0,
  '4. A cambia el total a $96: nada espera respuesta (nadie vinculado)');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000001'),
  'Beto:32.00:me_debe:local Caro:32.00:me_debe:local', '4. las deudas pasan a $32');
SELECT is((SELECT id FROM deudas WHERE gasto_id = '9a000000-0000-0000-0000-000000000001'
            AND deudor_id = 'a2000000-0000-0000-0000-000000000000'),
  '9d000000-0000-0000-0000-000000000001'::uuid, '4. son las mismas deudas, cambiadas (no otras)');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 67.00, '4. Beto: +67');
SELECT lives_ok($$SELECT registrar_pago('a3000000-0000-0000-0000-000000000000', 30, false, '2026-07-10')$$,
  '4. Caro le paga $30 a A');
SELECT is((SELECT sum(dp.monto_asignado) FROM detalle_pagos dp JOIN deudas d ON d.id = dp.deuda_id
            WHERE d.gasto_id = '9a000000-0000-0000-0000-000000000001'
              AND d.deudor_id = 'a3000000-0000-0000-0000-000000000000'), 30.00,
  '4. el pago va entero a la cena (FIFO)');
SELECT is(pg_temp.saldo('a3000000-0000-0000-0000-000000000000'), 47.00, '4. Caro: 77 − 30 = +47');
SELECT lives_ok($$SELECT editar_gasto('9a000000-0000-0000-0000-000000000001', 'Cena', 60, '2026-07-01', 'igual',
    '[{"pagado":60},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000"},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]')$$, '4. A baja la cena a $60');
SELECT is((SELECT sum(dp.monto_asignado) FROM detalle_pagos dp JOIN deudas d ON d.id = dp.deuda_id
            WHERE d.gasto_id = '9a000000-0000-0000-0000-000000000001'
              AND d.deudor_id = 'a3000000-0000-0000-0000-000000000000'), 20.00,
  '4. la deuda de Caro ($20) suelta los $10 que le sobran (decisión 16)');
SELECT is(pg_temp.saldo('a3000000-0000-0000-0000-000000000000'), 35.00, '4. Caro: 20 + 45 − 30 = +35');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 55.00, '4. Beto: 20 + 45 − 10 = +55');
SELECT is((estado_cuenta('a3000000-0000-0000-0000-000000000000') -> 'resumen' ->> 'total_te_deben')::numeric, 35.00,
  '4. los $10 sueltos abonan solos lo que Caro todavía debe (saldo a favor)');
-- Editar la lista: Caro sale de la cena y entra Bea (vinculada; ver 6). Mismo título.
SELECT lives_ok($$SELECT editar_gasto('9a000000-0000-0000-0000-000000000001', 'Cena', 60, '2026-07-01', 'igual',
    '[{"pagado":60},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '4. A saca a Caro de la cena');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000001'), 'Beto:30.00:me_debe:local',
  '4. la deuda de Caro se va y la de Beto pasa a $30');
SELECT is(pg_temp.saldo('a3000000-0000-0000-0000-000000000000'), 15.00,
  '4. Caro: 45 − 30 = +15 (su pago queda, abonando el regalo)');
SELECT is(pg_temp.partes('9a000000-0000-0000-0000-000000000001'),
  'yo:60.00:30.00:activa Beto:0.00:30.00:activa', '4. el gasto queda con dos participantes');

-- ====================================================================================
-- 5. La deuda de un gasto no se cambia suelta; el título sí.
-- ====================================================================================
SELECT throws_ok($$UPDATE deudas SET monto = 99 WHERE id = '9d000000-0000-0000-0000-000000000001'$$,
  '42501', NULL, '5. UPDATE directo del monto → 42501');
SELECT throws_ok($$UPDATE deudas SET es_mi_deuda = true WHERE id = '9d000000-0000-0000-0000-000000000001'$$,
  '42501', NULL, '5. ni la dirección');
SELECT throws_ok($$DELETE FROM deudas WHERE id = '9d000000-0000-0000-0000-000000000001'$$,
  '42501', NULL, '5. ni se borra suelta');
SELECT lives_ok($$UPDATE deudas SET titulo = 'Cena en lo de Beto' WHERE id = '9d000000-0000-0000-0000-000000000001'$$,
  '5. el título sí');
UPDATE deudas SET gasto_id = NULL WHERE id = '9d000000-0000-0000-0000-000000000001';
SELECT is((SELECT gasto_id FROM deudas WHERE id = '9d000000-0000-0000-0000-000000000001'),
  '9a000000-0000-0000-0000-000000000001'::uuid, '5. gasto_id no se puede soltar a mano (se conserva)');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda, gasto_id) VALUES
  ('9d000000-0000-0000-0000-0000000000aa', 'a2000000-0000-0000-0000-000000000000', 'Colada', 5, '2026-07-04', false,
   '9a000000-0000-0000-0000-000000000003');
SELECT is((SELECT gasto_id FROM deudas WHERE id = '9d000000-0000-0000-0000-0000000000aa'), NULL,
  '5. ni colgarle una deuda a un gasto: se ignora');
SELECT lives_ok($$DELETE FROM deudas WHERE id = '9d000000-0000-0000-0000-0000000000aa'$$, '5. (y esa se borra normal)');

-- ====================================================================================
-- 6. Bea vinculada: su parte sigue §4.7 (entra sola en la libreta de B, con su aviso).
--    Pizza $60 entre A y Bea → Bea +30 en A; −30 en B.
-- ====================================================================================
SELECT lives_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-000000000006', NULL, 'Pizza', 60, '2026-07-06', 'igual',
    '[{"pagado":60},
      {"deudor_id":"a1000000-0000-0000-0000-000000000000","deuda_id":"9d000000-0000-0000-0000-000000000006"}]')$$,
  '6. A anota la pizza con Bea');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000006'), 'Bea:30.00:me_debe:acordada',
  '6. la deuda de Bea entra acordada (fase 8)');
SELECT ok(pg_temp.ok(), '6. verificar_vinculo ok');
SELECT throws_ok($$SELECT proponer_cambio('deuda', '9d000000-0000-0000-0000-000000000006', 'editar', '{"monto": 1}')$$,
  '22023', NULL, '6. A no la cambia con proponer_cambio suelto: va por el gasto');
SELECT pg_temp.como('B');
SELECT is((SELECT row(titulo, monto, es_mi_deuda, estado_acuerdo, gasto_id IS NULL)::text FROM deudas
            WHERE origen_id = '9d000000-0000-0000-0000-000000000006'),
  '(Pizza,30.00,t,acordada,t)', '6. en B está el espejo, sin gasto (el gasto es de A)');
SELECT is((SELECT count(*)::int FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'deuda_nueva'), 1,
  '6. B tiene su aviso deuda_nueva');
SELECT is(pg_temp.saldo('b1000000-0000-0000-0000-000000000000'), -30.00, '6. B: −30');
SELECT throws_ok(format('SELECT proponer_cambio(%L, %L, %L, %L)', 'deuda',
    (SELECT id FROM deudas WHERE origen_id = '9d000000-0000-0000-0000-000000000006'), 'editar', '{"monto": 1}'),
  '22023', NULL, '6. B tampoco le propone cambios: si no la reconoce, la rechaza');
SELECT is((SELECT count(*)::int FROM gastos), 0, '6. B no ve el gasto de A');
SELECT is((SELECT count(*)::int FROM gasto_participantes), 0, '6. ni sus participantes');
-- A cambia el total: con Bea se PROPONE (decisión 22).
SELECT pg_temp.como('A');
SELECT is((editar_gasto('9a000000-0000-0000-0000-000000000006', 'Pizza', 80, '2026-07-06', 'igual',
    '[{"pagado":80},{"deudor_id":"a1000000-0000-0000-0000-000000000000"}]') ->> 'esperan_respuesta')::int, 1,
  '6. A sube la pizza a $80: la parte de Bea espera respuesta');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000006'), 'Bea:30.00:me_debe:acordada',
  '6. hasta que B acepte, la deuda sigue en $30');
SELECT is(pg_temp.partes('9a000000-0000-0000-0000-000000000006'),
  'yo:80.00:40.00:activa Bea:0.00:40.00:activa', '6. el gasto ya dice $40');
SELECT lives_ok($$SELECT editar_gasto('9a000000-0000-0000-0000-000000000006', 'Pizza', 100, '2026-07-06', 'igual',
    '[{"pagado":100},{"deudor_id":"a1000000-0000-0000-0000-000000000000"}]')$$,
  '6. A la vuelve a cambiar, a $100, antes de que B responda');
SELECT is((SELECT count(*)::int FROM propuestas WHERE fila_origen = '9d000000-0000-0000-0000-000000000006'
            AND estado = 'pendiente'), 1, '6. queda un solo cambio pendiente (el de antes se anuló)');
SELECT is((SELECT payload ->> 'monto' FROM propuestas WHERE fila_origen = '9d000000-0000-0000-0000-000000000006'
            AND estado = 'pendiente'), '50.00', '6. el de $50');
SELECT pg_temp.como('B');
SELECT is((SELECT count(*)::int FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'cambio'), 1,
  '6. B tiene un solo aviso de cambio (el anulado se fue)');
SELECT lives_ok(format('SELECT aceptar_propuesta(%L)', (SELECT id FROM propuestas
    WHERE fila_origen = '9d000000-0000-0000-0000-000000000006' AND estado = 'pendiente')), '6. B acepta');
SELECT is(pg_temp.saldo('b1000000-0000-0000-0000-000000000000'), -50.00, '6. B: −50');
SELECT pg_temp.como('A');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000006'), 'Bea:50.00:me_debe:acordada',
  '6. en A la deuda de Bea es $50');
SELECT ok(pg_temp.ok(), '6. verificar_vinculo ok');
-- B rechaza su parte → el gasto de A lo muestra; no se reparte de nuevo (se absorbe).
SELECT pg_temp.como('B');
SELECT lives_ok(format('SELECT rechazar_fila(%L, %L, %L)', 'deuda',
    (SELECT id FROM deudas WHERE origen_id = '9d000000-0000-0000-0000-000000000006'), 'No comí pizza'),
  '6. B rechaza su parte');
SELECT pg_temp.como('A');
SELECT is(pg_temp.partes('9a000000-0000-0000-0000-000000000006'),
  'yo:100.00:50.00:activa Bea:0.00:50.00:rechazada', '6. en el gasto de A la parte de Bea sale rechazada');
SELECT is(pg_temp.saldo('a1000000-0000-0000-0000-000000000000'), 0.00, '6. y deja de contar: Bea 0');
SELECT ok(pg_temp.ok(), '6. verificar_vinculo ok');

-- ====================================================================================
-- 7. Borrar el gasto: lo que no está acordado se va; lo acordado con Bea se le propone
--    borrar (decisión 22) y la deuda queda como deuda normal hasta que acepte.
-- ====================================================================================
SELECT lives_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-000000000007', NULL, 'Cine', 30, '2026-07-07', 'igual',
    '[{"pagado":30},
      {"deudor_id":"a1000000-0000-0000-0000-000000000000","deuda_id":"9d000000-0000-0000-0000-000000000007"},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '7. A anota el cine con Bea y Beto');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 75.00, '7. Beto: 65 + 10 = +75');
SELECT is((borrar_gasto('9a000000-0000-0000-0000-000000000007') ->> 'esperan_respuesta')::int, 1,
  '7. A borra el cine: la parte de Bea espera respuesta');
SELECT is((SELECT count(*)::int FROM gastos WHERE id = '9a000000-0000-0000-0000-000000000007'), 0, '7. el gasto se fue');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 65.00, '7. la deuda de Beto se fue: +65');
SELECT is((SELECT row(estado_acuerdo, gasto_id IS NULL)::text FROM deudas WHERE id = '9d000000-0000-0000-0000-000000000007'),
  '(acordada,t)', '7. la de Bea queda, sin gasto, hasta que B acepte el borrado');
SELECT is((SELECT count(*)::int FROM borrados_gastos WHERE id = '9a000000-0000-0000-0000-000000000007'), 1,
  '7. deja su lápida para el pull');
SELECT is((borrar_gasto('9a000000-0000-0000-0000-000000000007') ->> 'repetido')::boolean, true,
  '7. repetirlo no hace nada');
SELECT pg_temp.como('B');
SELECT lives_ok(format('SELECT aceptar_propuesta(%L)', (SELECT id FROM propuestas
    WHERE fila_origen = '9d000000-0000-0000-0000-000000000007' AND estado = 'pendiente' AND tipo = 'borrar')),
  '7. B acepta el borrado');
SELECT pg_temp.como('A');
SELECT is((SELECT count(*)::int FROM deudas WHERE id = '9d000000-0000-0000-0000-000000000007'), 0,
  '7. y la deuda se va de las dos libretas');
SELECT ok(pg_temp.ok(), '7. verificar_vinculo ok');
-- El taxi (pagó Beto): borrarlo se lleva la deuda de A con Beto. Beto: 65 + 10 = +75.
SELECT lives_ok($$SELECT borrar_gasto('9a000000-0000-0000-0000-000000000002')$$, '7. A borra el taxi');
SELECT is(pg_temp.saldo('a2000000-0000-0000-0000-000000000000'), 75.00, '7. ya no le debe $10 a Beto: +75');

-- ====================================================================================
-- 8. Idempotencia y RLS.
-- ====================================================================================
SELECT is((crear_gasto('9a000000-0000-0000-0000-000000000001', NULL, 'Cena', 90, '2026-07-01', 'igual',
    '[{"pagado":90},{"deudor_id":"a2000000-0000-0000-0000-000000000000"}]') ->> 'repetido')::boolean, true,
  '8. el sync reintenta crear la cena: devuelve la misma, sin tocarla');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000001'), 'Beto:30.00:me_debe:local', '8. …que sigue igual');
SELECT is((crear_gasto('9a000000-0000-0000-0000-0000000000f1', NULL, 'Otra', 10, '2026-07-01', 'igual',
    '[{"pagado":10},{"deudor_id":"a2000000-0000-0000-0000-000000000000"}]',
    '9e000000-0000-0000-0000-000000000001') ->> 'id'), '9a000000-0000-0000-0000-000000000001',
  '8. con la misma idem_key y otro id, también devuelve la cena');
SELECT is((editar_gasto('9a000000-0000-0000-0000-000000000003', 'Regalo', 100, '2026-07-03', 'igual',
    '[{"pagado":100,"participa":false},{"deudor_id":"a2000000-0000-0000-0000-000000000000"},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]',
    '9e000000-0000-0000-0000-000000000031') ->> 'repetido')::boolean, false, '8. A edita el regalo a $100');
SELECT is((editar_gasto('9a000000-0000-0000-0000-000000000003', 'Regalo', 200, '2026-07-03', 'igual',
    '[{"pagado":200,"participa":false},{"deudor_id":"a2000000-0000-0000-0000-000000000000"},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000"}]',
    '9e000000-0000-0000-0000-000000000031') ->> 'repetido')::boolean, true, '8. la misma edición repetida no hace nada');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-000000000003'),
  'Beto:50.00:me_debe:local Caro:50.00:me_debe:local', '8. el regalo quedó en $100');
SELECT pg_temp.como('C');
SELECT is((SELECT count(*)::int FROM gastos), 0, '8. C no ve los gastos de A');
SELECT is((SELECT count(*)::int FROM gasto_participantes), 0, '8. ni sus participantes');
SELECT is((SELECT count(*)::int FROM borrados_gastos), 0, '8. ni sus lápidas');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-000000000001', NULL, 'Cena', 10, '2026-07-01', 'igual',
    '[{"pagado":10},{"deudor_id":"c1000000-0000-0000-0000-000000000000"}]')$$, '42501', NULL,
  '8. C no puede reusar el id de un gasto ajeno');
SELECT throws_ok($$SELECT editar_gasto('9a000000-0000-0000-0000-000000000001', 'Cena', 10, '2026-07-01', 'igual',
    '[{"pagado":10},{"deudor_id":"c1000000-0000-0000-0000-000000000000"}]')$$, '42501', NULL,
  '8. ni editar el de A');
SELECT throws_ok($$SELECT borrar_gasto('9a000000-0000-0000-0000-000000000001')$$, '42501', NULL, '8. ni borrarlo');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000c1', NULL, 'Robo', 10, '2026-07-01', 'igual',
    '[{"pagado":10},{"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '42501', NULL,
  '8. ni meter en un gasto a un contacto de A');
SELECT throws_ok($$INSERT INTO gastos (id, titulo, monto_total, fecha) VALUES
    ('9a000000-0000-0000-0000-0000000000c2', 'Directo', 10, '2026-07-01')$$, '42501', NULL,
  '8. nadie inserta directo en gastos');
SELECT throws_ok($$INSERT INTO gasto_participantes (gasto_id, orden) VALUES
    ('9a000000-0000-0000-0000-000000000001', 9)$$, '42501', NULL, '8. ni en sus participantes');
SELECT pg_temp.como('A');
SELECT throws_ok($$UPDATE gastos SET monto_total = 1 WHERE id = '9a000000-0000-0000-0000-000000000001'$$,
  '42501', NULL, '8. ni A cambia su gasto directo');
SELECT throws_ok($$DELETE FROM gasto_participantes WHERE gasto_id = '9a000000-0000-0000-0000-000000000001'$$,
  '42501', NULL, '8. ni borra participantes directo');

-- ====================================================================================
-- 9. Validaciones (lo que manda el cliente no es de fiar) y lo que lee la app.
-- ====================================================================================
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e1', NULL, 'X', 90, '2026-07-01', 'montos',
    '[{"pagado":90,"peso":40},{"deudor_id":"a2000000-0000-0000-0000-000000000000","peso":40}]')$$, '22023', NULL,
  '9. montos que no suman el total');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e2', NULL, 'X', 90, '2026-07-01', 'porcentaje',
    '[{"pagado":90,"peso":50},{"deudor_id":"a2000000-0000-0000-0000-000000000000","peso":40}]')$$, '22023', NULL,
  '9. porcentajes que no suman 100');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e3', NULL, 'X', 90, '2026-07-01', 'igual',
    '[{"pagado":45},{"deudor_id":"a2000000-0000-0000-0000-000000000000","pagado":45}]')$$, '22023', NULL,
  '9. dos que pagan (por ahora uno solo)');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e4', NULL, 'X', 90, '2026-07-01', 'igual',
    '[{"pagado":80},{"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '22023', NULL,
  '9. lo pagado no es el total');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e5', NULL, 'X', 90, '2026-07-01', 'igual',
    '[{"pagado":90},{"deudor_id":"a2000000-0000-0000-0000-000000000000"},
      {"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '22023', NULL,
  '9. la misma persona dos veces');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e6', NULL, 'X', 90, '2026-07-01', 'igual',
    '[{"pagado":90}]')$$, '22023', NULL, '9. nadie más que quien pagó');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e7', NULL, 'X', 90, '2026-07-01', 'igual',
    '[{"pagado":90},{"deudor_id":"a2000000-0000-0000-0000-000000000000","participa":false}]')$$, '22023', NULL,
  '9. solo quien pagó puede quedar fuera');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e8', NULL, '  ', 90, '2026-07-01', 'igual',
    '[{"pagado":90},{"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '22023', NULL, '9. sin título');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000e9', NULL, 'X', 0, '2026-07-01', 'igual',
    '[{"pagado":0},{"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '22023', NULL, '9. monto cero');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000ea', NULL, 'X', 90, '2026-07-01', 'raro',
    '[{"pagado":90},{"deudor_id":"a2000000-0000-0000-0000-000000000000"}]')$$, '22023', NULL, '9. modo desconocido');
SELECT is((SELECT count(*)::int FROM gastos WHERE id::text LIKE '9a000000-0000-0000-0000-0000000000e%'), 0,
  '9. ninguno de esos quedó a medias');
SELECT lives_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000eb', NULL, 'Mercado', 100, '2026-07-08', 'partes',
    '[{"pagado":100,"peso":2},{"deudor_id":"a2000000-0000-0000-0000-000000000000","peso":1},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000","peso":1}]')$$, '9. partes 2:1:1');
SELECT is(pg_temp.deudas('9a000000-0000-0000-0000-0000000000eb'),
  'Beto:25.00:me_debe:local Caro:25.00:me_debe:local', '9. A pone 2 partes: $50; Beto y Caro $25');
SELECT lives_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000ec', NULL, 'Luz', 100, '2026-07-08', 'porcentaje',
    '[{"pagado":100,"peso":33.33},{"deudor_id":"a2000000-0000-0000-0000-000000000000","peso":33.33},
      {"deudor_id":"a3000000-0000-0000-0000-000000000000","peso":33.34}]')$$, '9. porcentajes');
SELECT is(pg_temp.partes('9a000000-0000-0000-0000-0000000000ec'),
  'yo:100.00:33.33:activa Beto:0.00:33.33:activa Caro:0.00:33.34:activa', '9. 33.33 / 33.33 / 33.34');
SELECT throws_ok($$SELECT crear_gasto('9a000000-0000-0000-0000-0000000000ed', 'aa000000-0000-0000-0000-000000000000',
    'X', 90, '2026-07-01', 'igual', '[{"pagado":90},{"miembro_id":"ab000000-0000-0000-0000-000000000000"}]')$$,
  NULL, NULL, '9. un gasto con grupo no pasa por la rama del gasto suelto');
-- cambios_gastos: lo que baja la app (cada gasto con sus participantes y las lápidas).
SELECT is((SELECT jsonb_array_length(cambios_gastos() -> 'gastos')), 5,
  '9. cambios_gastos trae los 5 gastos de A (cena, regalo, pizza, mercado, luz)');
SELECT is((SELECT jsonb_array_length(g -> 'participantes') FROM jsonb_array_elements(cambios_gastos() -> 'gastos') g
            WHERE g ->> 'id' = '9a000000-0000-0000-0000-0000000000ec'), 3, '9. con sus participantes');
SELECT is((SELECT count(*)::int FROM jsonb_array_elements(cambios_gastos() -> 'borrados')), 2,
  '9. y las lápidas del cine y el taxi');
SELECT is((SELECT jsonb_array_length(cambios_gastos(now() + interval '1 minute') -> 'gastos')), 0,
  '9. desde después, nada');
SELECT is((SELECT jsonb_array_length(exportar_mis_datos() -> 'gastos')), 5, '9. exportar_mis_datos trae los gastos');

-- Regresión: un gasto no toca estado_cuenta más allá de sus deudas. Lo comprueba
-- scripts/v2/comparar_linea_base.py (22/22) y comparar_edges.py (55/55) sobre los datos
-- reales.

SELECT * FROM finish();
ROLLBACK;
