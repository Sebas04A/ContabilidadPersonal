-- Fase 6: propuestas continuas (§4.1–§4.5, §5.3). Los 12 escenarios de 6.3, en orden y
-- sobre la misma pareja vinculada, así cada uno parte del saldo que dejó el anterior.
-- Cada escenario termina con verificar_vinculo().ok y con "mi saldo" (resumen.neto) de
-- los dos. Los números esperados están calculados a mano en los comentarios.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(96);

-- ------------------------------------------------------------------------------------
-- Datos: A (a0…) y B (b0…) vinculados y activos; C (c0…) es un tercero.
--   libreta de A: deudor "Bea" (a1, el del vínculo) y "Otro" (a2, sin vínculo)
--   libreta de B: deudor "Ana" (b1)
-- Lo cargado como postgres nace `local` (sin sesión no hay vínculo que mirar).
-- ------------------------------------------------------------------------------------
INSERT INTO auth.users (id, email, aud, role) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated'),
  ('c0000000-0000-0000-0000-000000000000', 'c@test.local', 'authenticated', 'authenticated');
INSERT INTO deudores (id, nombre, owner_id) VALUES
  ('a1000000-0000-0000-0000-000000000000', 'Bea',  'a0000000-0000-0000-0000-000000000000'),
  ('a2000000-0000-0000-0000-000000000000', 'Otro', 'a0000000-0000-0000-0000-000000000000'),
  ('b1000000-0000-0000-0000-000000000000', 'Ana',  'b0000000-0000-0000-0000-000000000000');
INSERT INTO vinculos (id, usuario_a, deudor_a, usuario_b, deudor_b, estado, conciliado_a, conciliado_b) VALUES
  ('f0000000-0000-0000-0000-000000000000',
   'a0000000-0000-0000-0000-000000000000', 'a1000000-0000-0000-0000-000000000000',
   'b0000000-0000-0000-0000-000000000000', 'b1000000-0000-0000-0000-000000000000',
   'activo', true, true);
INSERT INTO deudas (id, deudor_id, owner_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  -- A le debe $4 a Bea, de antes del vínculo
  ('a0000000-0000-0000-0000-0000000000a1', 'a1000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Almuerzo', 4,  '2026-05-01', true),
  ('a0000000-0000-0000-0000-0000000000a2', 'a2000000-0000-0000-0000-000000000000', 'a0000000-0000-0000-0000-000000000000', 'Suelto',  10,  '2026-05-01', false),
  -- B ya había anotado que le debe $20 a Ana por una cena (escenario 6)
  ('b0000000-0000-0000-0000-0000000000c0', 'b1000000-0000-0000-0000-000000000000', 'b0000000-0000-0000-0000-000000000000', 'Cena',     20,  '2026-06-10', true);

CREATE TEMP TABLE t (clave text PRIMARY KEY, valor jsonb);
GRANT ALL ON t TO authenticated;

CREATE FUNCTION pg_temp.como(u text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('request.jwt.claims',
        json_build_object('sub', CASE u WHEN 'A' THEN 'a0000000-0000-0000-0000-000000000000'
                                        WHEN 'B' THEN 'b0000000-0000-0000-0000-000000000000'
                                        ELSE 'c0000000-0000-0000-0000-000000000000' END,
                          'role', 'authenticated')::text, true);
END $$;
-- "Mi saldo" y el saldo acordado de quien está actuando, con su deudor del vínculo.
CREATE FUNCTION pg_temp.neto() RETURNS numeric LANGUAGE sql AS $$
    SELECT (estado_cuenta(CASE WHEN auth.uid() = 'a0000000-0000-0000-0000-000000000000'
                               THEN 'a1000000-0000-0000-0000-000000000000'::uuid
                               ELSE 'b1000000-0000-0000-0000-000000000000'::uuid END)
            -> 'resumen' ->> 'neto')::numeric
$$;
CREATE FUNCTION pg_temp.acordado() RETURNS numeric LANGUAGE sql AS $$
    SELECT (estado_cuenta(CASE WHEN auth.uid() = 'a0000000-0000-0000-0000-000000000000'
                               THEN 'a1000000-0000-0000-0000-000000000000'::uuid
                               ELSE 'b1000000-0000-0000-0000-000000000000'::uuid END)
            -> 'resumen' ->> 'saldo_acordado')::numeric
$$;
CREATE FUNCTION pg_temp.ok() RETURNS boolean LANGUAGE sql AS $$
    SELECT (verificar_vinculo('f0000000-0000-0000-0000-000000000000') ->> 'ok')::boolean
$$;
-- La propuesta pendiente de una fila (la ven las dos partes).
CREATE FUNCTION pg_temp.prop(fila text) RETURNS uuid LANGUAGE sql AS $$
    SELECT id FROM propuestas WHERE fila_origen = fila::uuid AND estado = 'pendiente'
$$;

-- Fase 8: estos tests prueban el camino de la PROPUESTA (la bandeja de la fase 6). Desde
-- 20260924150000 lo nuevo entra solo, salvo lo que pasa el tope diario (decisión 24):
-- con el tope en 0, todo nace propuesta como antes. La aceptación automática se prueba
-- en 09_aceptacion_automatica.sql.
SELECT set_config('deudas.tope_diario', '0', true);

SET LOCAL ROLE authenticated;

-- ====================================================================================
-- 1. A anota "Bea me debe $20" → propuesta → B acepta → espejo acordado.
--    A: −4 +20 = 16. B: −20 (Cena) −20 (espejo) = −40. Acordado: A +20, B −20.
-- ====================================================================================
SELECT pg_temp.como('A');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d1', 'a1000000-0000-0000-0000-000000000000', 'Préstamo', 20, '2026-03-01', false);
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d1'), 'propuesta',
  '1. con el vínculo activo, la deuda nueva de A nace propuesta');
SELECT is((estado_cuenta('a1000000-0000-0000-0000-000000000000') -> 'resumen' ->> 'pendiente_acuerdo')::numeric, 20.00,
  '1. y cuenta en el saldo de A como pendiente de acuerdo');

SELECT pg_temp.como('B');
SELECT is((SELECT payload FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000d1'),
  '{"monto": 20.00, "fecha": "2026-03-01", "es_mia": false, "titulo": "Préstamo"}'::jsonb,
  '1. B la tiene pendiente, en el punto de vista de A y con el título');
INSERT INTO t VALUES ('r1', aceptar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000d1')));
SELECT is((SELECT valor ->> 'resultado' FROM t WHERE clave = 'r1'), 'aceptada', '1. B acepta');
SELECT is((SELECT row(titulo, monto, es_mi_deuda, estado_acuerdo)::text FROM deudas
            WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d1'),
  '(Préstamo,20.00,t,acordada)', '1. espejo en B: la dirección invertida (B debe), acordada');
SELECT is(pg_temp.acordado(), -20.00, '1. saldo acordado de B: −20');
SELECT is(pg_temp.neto(), -40.00, '1. mi saldo de B: −40 (la cena que ya tenía + el espejo)');
SELECT pg_temp.como('A');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d1'), 'acordada',
  '1. la fila de A queda acordada');
SELECT is(pg_temp.acordado(), 20.00, '1. saldo acordado de A: +20');
SELECT is(pg_temp.neto(), 16.00, '1. mi saldo de A: 16');
SELECT ok(pg_temp.ok(), '1. verificar_vinculo ok');

-- ====================================================================================
-- 2. Igual con un pago: A anota que Bea le pagó $8 → B acepta → en B se reparte como un
--    pago automático suyo (va a la deuda espejo, la más antigua).
--    A: 16 −8 = 8. B: −40 +8 = −32. Acordado: A 12, B −12.
-- ====================================================================================
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago) VALUES
  ('a0000000-0000-0000-0000-0000000000f2', 'a1000000-0000-0000-0000-000000000000', 8, '2026-03-05', false);
SELECT pg_temp.como('B');
INSERT INTO t VALUES ('r2', aceptar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000f2')));
SELECT is((SELECT row(p.monto_total, p.es_mi_pago, p.estado_acuerdo, sum(dp.monto_asignado))::text
             FROM pagos p JOIN detalle_pagos dp ON dp.pago_id = p.id
            WHERE p.origen_id = 'a0000000-0000-0000-0000-0000000000f2'
            GROUP BY p.id),
  '(8.00,t,acordada,8.00)', '2. pago espejo en B: lo entregó B, acordado y repartido entero');
SELECT is((SELECT d.origen_id FROM detalle_pagos dp JOIN pagos p ON p.id = dp.pago_id JOIN deudas d ON d.id = dp.deuda_id
            WHERE p.origen_id = 'a0000000-0000-0000-0000-0000000000f2'),
  'a0000000-0000-0000-0000-0000000000d1'::uuid, '2. y abona la deuda espejo del préstamo (FIFO)');
SELECT is(pg_temp.acordado(), -12.00, '2. saldo acordado de B: −12');
SELECT is(pg_temp.neto(), -32.00, '2. mi saldo de B: −32');
SELECT pg_temp.como('A');
SELECT is(pg_temp.acordado(), 12.00, '2. saldo acordado de A: +12');
SELECT is(pg_temp.neto(), 8.00, '2. mi saldo de A: 8');
SELECT ok(pg_temp.ok(), '2. verificar_vinculo ok');

-- ====================================================================================
-- 3. B rechaza una deuda → en A queda rechazada y no cuenta en ningún saldo.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d3', 'a1000000-0000-0000-0000-000000000000', 'Taxi', 5, '2026-03-10', false);
SELECT is(pg_temp.neto(), 13.00, '3. antes de la respuesta, la propuesta cuenta en mi saldo (8 + 5)');
SELECT pg_temp.como('B');
SELECT is((rechazar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000d3'), '  no fue así ')) ->> 'resultado',
  'rechazada', '3. B rechaza');
SELECT is(pg_temp.neto(), -32.00, '3. B no cambia');
SELECT pg_temp.como('A');
SELECT is((SELECT row(d.estado_acuerdo, p.motivo)::text FROM deudas d JOIN propuestas p ON p.fila_origen = d.id
            WHERE d.id = 'a0000000-0000-0000-0000-0000000000d3'),
  '(rechazada,"no fue así")', '3. en A la fila queda rechazada, con el motivo');
SELECT is(pg_temp.neto(), 8.00, '3. y deja de contar en el saldo de A');
SELECT ok(NOT EXISTS (SELECT 1 FROM jsonb_array_elements(estado_cuenta('a1000000-0000-0000-0000-000000000000') -> 'deudas') d
                       WHERE d ->> 'id' = 'a0000000-0000-0000-0000-0000000000d3'),
  '3. ni aparece en el estado de cuenta');
SELECT ok(pg_temp.ok(), '3. verificar_vinculo ok');

-- ====================================================================================
-- 4. A le cobra $5 a Bea (registrar_pago) sobre "Cine $20", que todavía es propuesta; B
--    rechaza el cine → esos $5 quedan como saldo a favor de Bea en la libreta de A.
--    Antes de cobrar, el pago automático cruza primero: el Almuerzo ($4, A debe) contra el
--    Cine (el más antiguo). Al rechazar, ese cruce se deshace entero.
--    A: 8 +20 −5 = 23 → sin el cine: 3.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d4', 'a1000000-0000-0000-0000-000000000000', 'Cine', 20, '2026-01-01', false);
INSERT INTO t VALUES ('pago4', registrar_pago('a1000000-0000-0000-0000-000000000000', 5, false, '2026-03-12'));
SELECT is((SELECT sum(monto_asignado) FROM detalle_pagos WHERE deuda_id = 'a0000000-0000-0000-0000-0000000000d4'), 9.00,
  '4. al cine le tocan $4 del cruce y los $5 del cobro');
SELECT is((SELECT estado_acuerdo FROM pagos WHERE id = (SELECT (valor ->> 'pago_id')::uuid FROM t WHERE clave = 'pago4')),
  'propuesta', '4. el cobro también es una propuesta para B');
SELECT is(pg_temp.neto(), 23.00, '4. mi saldo de A antes del rechazo: 23');
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT rechazar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000d4'))$$,
  '4. B rechaza el cine');
SELECT pg_temp.como('A');
SELECT is((SELECT COALESCE(sum(dp.monto_asignado), 0) FROM detalle_pagos dp
            WHERE dp.pago_id = (SELECT (valor ->> 'pago_id')::uuid FROM t WHERE clave = 'pago4')), 0.00,
  '4. los $5 ya no están repartidos: son saldo a favor de Bea');
SELECT is((SELECT count(*) FROM pagos WHERE es_compensacion)::int, 0,
  '4. el cruce que tocaba el cine se deshizo (y no quedó un lado solo)');
SELECT is(pg_temp.neto(), 3.00, '4. mi saldo de A: 3 (préstamo 20 − almuerzo 4 − pagos 8 y 5)');
SELECT is((estado_cuenta('a1000000-0000-0000-0000-000000000000') -> 'resumen' ->> 'pendiente_acuerdo')::numeric, -5.00,
  '4. el cobro sigue pendiente de acuerdo');
SELECT ok(pg_temp.ok(), '4. verificar_vinculo ok');

-- ====================================================================================
-- 5. Una deuda propuesta entra en un cruce y B la rechaza → el cruce se recorta y los dos
--    pagos virtuales siguen cuadrando.
--    Cruce: A debe Almuerzo 4 + Regalo 6; le deben el préstamo, con saldo real 7 (20 − 13
--    de saldo a favor). Cruce de 7 = Almuerzo 4 + Regalo 3. Sin el regalo: cruce de 4.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d5', 'a1000000-0000-0000-0000-000000000000', 'Regalo', 6, '2026-05-02', true);
INSERT INTO t VALUES ('cruce5', aplicar_cruce('a1000000-0000-0000-0000-000000000000', '2026-05-03'));
SELECT is((SELECT (valor ->> 'aplicado')::numeric FROM t WHERE clave = 'cruce5'), 7.00, '5. A cruza $7');
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT rechazar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000d5'))$$,
  '5. B rechaza el regalo');
SELECT pg_temp.como('A');
SELECT is((SELECT array_agg(monto_total ORDER BY es_mi_pago) FROM pagos
            WHERE cruce_id = (SELECT (valor ->> 'cruce_id')::uuid FROM t WHERE clave = 'cruce5')),
  ARRAY[4.00, 4.00]::numeric[], '5. el cruce quedó en $4 por lado');
SELECT ok(NOT EXISTS (SELECT 1 FROM pagos p WHERE p.es_compensacion
                        AND p.monto_total <> (SELECT sum(monto_asignado) FROM detalle_pagos WHERE pago_id = p.id)),
  '5. ningún pago virtual tiene sobrante');
SELECT is((SELECT count(*) FROM detalle_pagos WHERE deuda_id = 'a0000000-0000-0000-0000-0000000000d5')::int, 0,
  '5. el regalo no conserva nada repartido');
SELECT is(pg_temp.neto(), 3.00, '5. mi saldo de A: 3 (el cruce no mueve el neto)');
SELECT ok(pg_temp.ok(), '5. verificar_vinculo ok');

-- ====================================================================================
-- 6. B ya tenía "Cena $20" (local). A propone su "Cena" → aceptar sin más devuelve el
--    candidato → B enlaza: no se crea otra fila.
--    A: 3 +20 = 23. B: −32 (sin cambio). Acordado: A 32, B −32.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d6', 'a1000000-0000-0000-0000-000000000000', 'Cena cumple', 20, '2026-06-11', false);
SELECT pg_temp.como('B');
INSERT INTO t VALUES ('r6', aceptar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000d6')));
SELECT is((SELECT valor ->> 'resultado' FROM t WHERE clave = 'r6'), 'hay_candidatos',
  '6. aceptar sin más avisa que hay candidatos');
SELECT is((SELECT jsonb_path_query_array(valor, '$.candidatos[*].id') FROM t WHERE clave = 'r6'),
  '["b0000000-0000-0000-0000-0000000000c0"]'::jsonb, '6. el candidato es su cena');
SELECT is((SELECT count(*) FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d6')::int, 0,
  '6. todavía no se creó nada');
SELECT is((aceptar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000d6'),
                             'b0000000-0000-0000-0000-0000000000c0')) ->> 'enlazada', 'true',
  '6. B la enlaza con su cena');
SELECT is((SELECT count(*) FROM deudas)::int, 2, '6. B sigue con 2 deudas (cena y préstamo): ninguna nueva');
SELECT is((SELECT row(estado_acuerdo, origen_id)::text FROM deudas WHERE id = 'b0000000-0000-0000-0000-0000000000c0'),
  '(acordada,a0000000-0000-0000-0000-0000000000d6)', '6. su cena queda acordada y atada a la de A');
SELECT is(pg_temp.neto(), -32.00, '6. mi saldo de B no cambia: la cena ya contaba');
SELECT is(pg_temp.acordado(), -32.00, '6. saldo acordado de B: −32');
SELECT pg_temp.como('A');
SELECT is(pg_temp.neto(), 23.00, '6. mi saldo de A: 23');
SELECT is(pg_temp.acordado(), 32.00, '6. saldo acordado de A: +32');
SELECT ok(pg_temp.ok(), '6. verificar_vinculo ok');

-- ====================================================================================
-- 7. Doble aceptación: misma clave → misma respuesta y un solo espejo; otra clave → error.
--    A: 23 +3 = 26. B: −35.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d7', 'a1000000-0000-0000-0000-000000000000', 'Pan', 3, '2026-07-01', false);
SELECT pg_temp.como('B');
INSERT INTO t VALUES ('p7', to_jsonb(pg_temp.prop('a0000000-0000-0000-0000-0000000000d7')));
INSERT INTO t VALUES ('r7', aceptar_propuesta((SELECT valor #>> '{}' FROM t WHERE clave = 'p7')::uuid,
                                              NULL, false, '70000000-0000-0000-0000-000000000001'));
SELECT is(aceptar_propuesta((SELECT valor #>> '{}' FROM t WHERE clave = 'p7')::uuid,
                            NULL, false, '70000000-0000-0000-0000-000000000001'),
  (SELECT valor FROM t WHERE clave = 'r7'), '7. repetir con la misma clave da la misma respuesta');
SELECT is((SELECT count(*) FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d7')::int, 1,
  '7. y hay una sola fila espejo');
SELECT throws_ok(format($$SELECT aceptar_propuesta(%L, NULL, false, '70000000-0000-0000-0000-000000000002')$$,
                        (SELECT valor #>> '{}' FROM t WHERE clave = 'p7')),
  '22023', NULL, '7. con otra clave: "ya resuelta"');
SELECT is(pg_temp.neto(), -35.00, '7. mi saldo de B: −35');
SELECT pg_temp.como('A');
SELECT is(pg_temp.neto(), 26.00, '7. mi saldo de A: 26');
SELECT ok(pg_temp.ok(), '7. verificar_vinculo ok');

-- ====================================================================================
-- 8. proponer_cambio del pan: 3 → 5. B rechaza → siguen en 3. B acepta → las dos en 5.
--    A: 28, B: −37. Además, bajar el préstamo a $6 (B ya le había abonado $8): en B se
--    suelta el exceso ($2 del pago espejo quedan como saldo a favor de B).
--    A: 28 −14 = 14. B: −37 +14 = −23. Acordado: A 23, B −23.
-- ====================================================================================
INSERT INTO t VALUES ('c8a', proponer_cambio('deuda', 'a0000000-0000-0000-0000-0000000000d7', 'editar', '{"monto": 5}'));
SELECT throws_ok($$SELECT proponer_cambio('deuda', 'a0000000-0000-0000-0000-0000000000d7', 'editar', '{"monto": 6}')$$,
  '23505', NULL, '8. una sola propuesta de cambio pendiente por fila');
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT rechazar_propuesta((SELECT (valor ->> 'propuesta_id')::uuid FROM t WHERE clave = 'c8a'))$$,
  '8. B rechaza el cambio');
SELECT is((SELECT array_agg(monto ORDER BY owner_id) FROM deudas
            WHERE 'a0000000-0000-0000-0000-0000000000d7' IN (id, origen_id)), ARRAY[3.00]::numeric[],
  '8. su fila sigue en 3');
SELECT pg_temp.como('A');
SELECT is((SELECT monto FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d7'), 3.00, '8. y la de A también');
INSERT INTO t VALUES ('c8b', proponer_cambio('deuda', 'a0000000-0000-0000-0000-0000000000d7', 'editar', '{"monto": 5}'));
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT aceptar_propuesta((SELECT (valor ->> 'propuesta_id')::uuid FROM t WHERE clave = 'c8b'))$$,
  '8. B acepta el cambio');
SELECT is((SELECT monto FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d7'), 5.00, '8. su fila pasa a 5');
SELECT pg_temp.como('A');
SELECT is((SELECT monto FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d7'), 5.00, '8. y la de A también');
SELECT is(pg_temp.neto(), 28.00, '8. mi saldo de A: 28');

INSERT INTO t VALUES ('c8c', proponer_cambio('deuda', 'a0000000-0000-0000-0000-0000000000d1', 'editar', '{"monto": 6}'));
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT aceptar_propuesta((SELECT (valor ->> 'propuesta_id')::uuid FROM t WHERE clave = 'c8c'))$$,
  '8. B acepta bajar el préstamo a $6');
SELECT is((SELECT sum(dp.monto_asignado) FROM detalle_pagos dp JOIN deudas d ON d.id = dp.deuda_id
            WHERE d.origen_id = 'a0000000-0000-0000-0000-0000000000d1'), 6.00,
  '8. en B, el préstamo tiene repartido solo lo que vale');
SELECT is(pg_temp.neto(), -23.00, '8. mi saldo de B: −23 (los $2 sueltos abonan su cena)');
SELECT is(pg_temp.acordado(), -23.00, '8. saldo acordado de B: −23');
SELECT pg_temp.como('A');
SELECT is(pg_temp.neto(), 14.00, '8. mi saldo de A: 14');
SELECT is(pg_temp.acordado(), 23.00, '8. saldo acordado de A: +23');
SELECT ok(pg_temp.ok(), '8. verificar_vinculo ok');

-- ====================================================================================
-- 9. La guardia: lo acordado no se toca directo, salvo el título.
-- ====================================================================================
SELECT throws_ok($$UPDATE deudas SET monto = 99 WHERE id = 'a0000000-0000-0000-0000-0000000000d1'$$,
  '42501', NULL, '9. cambiar el monto de algo acordado → 42501');
SELECT throws_ok($$DELETE FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d1'$$,
  '42501', NULL, '9. borrarlo → 42501');
SELECT lives_ok($$UPDATE deudas SET titulo = 'Préstamo de mayo', estado_acuerdo = 'local'
                   WHERE id = 'a0000000-0000-0000-0000-0000000000d1'$$,
  '9. el título sí se edita');
SELECT is((SELECT row(titulo, estado_acuerdo)::text FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d1'),
  '("Préstamo de mayo",acordada)', '9. el título cambió; el estado lo ignora (solo lo mueve el servidor)');
INSERT INTO deudas (id, deudor_id, titulo, monto, es_mi_deuda, estado_acuerdo, origen_id) VALUES
  ('a0000000-0000-0000-0000-0000000000d9', 'a1000000-0000-0000-0000-000000000000', 'Trampa', 1, false,
   'acordada', 'b0000000-0000-0000-0000-0000000000c0');
SELECT is((SELECT row(estado_acuerdo, origen_id)::text FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d9'),
  '(propuesta,)', '9. un cliente no puede insertar algo ya acordado ni hacerse pasar por espejo');
SELECT throws_ok($$INSERT INTO detalle_pagos (pago_id, deuda_id, monto_asignado)
                   VALUES ('a0000000-0000-0000-0000-0000000000f2', 'a0000000-0000-0000-0000-0000000000d4', 1)$$,
  '22023', NULL, '9. no se reparte dinero sobre una fila rechazada');

-- ====================================================================================
-- 10. A anula la "Trampa" mientras está pendiente → rechazada en A; B ya no la ve.
-- ====================================================================================
INSERT INTO t VALUES ('p10', to_jsonb(pg_temp.prop('a0000000-0000-0000-0000-0000000000d9')));
SELECT is((anular_propuesta((SELECT valor #>> '{}' FROM t WHERE clave = 'p10')::uuid)) ->> 'resultado', 'anulada',
  '10. A la anula');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d9'), 'rechazada',
  '10. en A queda rechazada');
SELECT is(pg_temp.neto(), 14.00, '10. y no cuenta: mi saldo de A sigue en 14');
SELECT pg_temp.como('B');
SELECT is((SELECT estado FROM propuestas WHERE id = (SELECT valor #>> '{}' FROM t WHERE clave = 'p10')::uuid), 'anulada',
  '10. B ya no la tiene pendiente');
SELECT ok(pg_temp.ok(), '10. verificar_vinculo ok');

-- ====================================================================================
-- 12. Nadie acepta lo que no le mandaron.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('b0000000-0000-0000-0000-0000000000d2', 'b1000000-0000-0000-0000-000000000000', 'Café', 2, '2026-08-01', true);
SELECT throws_ok(format('SELECT aceptar_propuesta(%L)', pg_temp.prop('b0000000-0000-0000-0000-0000000000d2')),
  '42501', NULL, '12. B no acepta su propia propuesta (es para A)');
INSERT INTO t VALUES ('p12', to_jsonb(pg_temp.prop('b0000000-0000-0000-0000-0000000000d2')));
SELECT pg_temp.como('C');
SELECT throws_ok(format('SELECT aceptar_propuesta(%L)', (SELECT valor #>> '{}' FROM t WHERE clave = 'p12')),
  '42501', NULL, '12. un tercero tampoco');
SELECT throws_ok($$SELECT verificar_vinculo('f0000000-0000-0000-0000-000000000000')$$,
  '42501', NULL, '12. ni verifica un vínculo ajeno');

-- ====================================================================================
-- 11. B se desvincula con dos propuestas pendientes (el cobro de A y el café de B):
--     quedan anuladas, sus filas vuelven a `local` y nadie pierde un centavo de su saldo.
-- ====================================================================================
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT desvincular('f0000000-0000-0000-0000-000000000000')$$, '11. B se desvincula');
SELECT is((SELECT count(*) FROM propuestas WHERE estado = 'pendiente')::int, 0, '11. no queda nada pendiente');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE id = 'b0000000-0000-0000-0000-0000000000d2'), 'local',
  '11. el café de B vuelve a ser solo suyo');
SELECT is(pg_temp.neto(), -25.00, '11. mi saldo de B: −23 − 2 del café');
SELECT pg_temp.como('A');
SELECT is((SELECT estado_acuerdo FROM pagos WHERE id = (SELECT (valor ->> 'pago_id')::uuid FROM t WHERE clave = 'pago4')),
  'local', '11. el cobro de A vuelve a ser solo suyo');
SELECT is(pg_temp.neto(), 14.00, '11. mi saldo de A no cambia');
SELECT ok(NOT (estado_cuenta('a1000000-0000-0000-0000-000000000000') -> 'resumen' ? 'saldo_acordado'),
  '11. sin vínculo, el estado de cuenta vuelve a su forma de siempre');
SELECT lives_ok($$UPDATE deudas SET monto = 7 WHERE id = 'a0000000-0000-0000-0000-0000000000d1'$$,
  '11. roto el vínculo, cada uno vuelve a mandar en su libreta');

-- Un deudor que nunca tuvo vínculo no gana ninguna clave (la salida es la de siempre).
SELECT ok(NOT (estado_cuenta('a2000000-0000-0000-0000-000000000000') -> 'resumen' ? 'saldo_acordado')
          AND NOT (estado_cuenta('a2000000-0000-0000-0000-000000000000') -> 'deudas' -> 0 ? 'estado_acuerdo'),
  'sin vínculo: ni saldo acordado ni estado_acuerdo');

SELECT * FROM finish();
ROLLBACK;
