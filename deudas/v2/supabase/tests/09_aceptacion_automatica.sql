-- Fase 8: aceptación automática y avisos (§4.7; decisiones 21 a 24 de §3.3). Los
-- escenarios de 8.3, en orden y sobre la misma pareja vinculada: cada uno parte del saldo
-- que dejó el anterior y termina con verificar_vinculo().ok y "mi saldo" (resumen.neto)
-- de los dos, calculado a mano en los comentarios. Cambiar o borrar algo acordado sigue
-- siendo propuesta (decisión 22): los escenarios 8 y 9 lo comprueban con sus avisos.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(167);

-- ------------------------------------------------------------------------------------
-- Datos: A (a0…) y B (b0…) vinculados y activos; C (c0…) es un tercero.
--   libreta de A: deudor "Bea" (a1, el del vínculo) y "Otro" (a2, sin vínculo)
--   libreta de B: deudor "Ana" (b1)
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
-- El deudor del vínculo de quien está actuando.
CREATE FUNCTION pg_temp.mio() RETURNS uuid LANGUAGE sql AS $$
    SELECT CASE WHEN auth.uid() = 'a0000000-0000-0000-0000-000000000000'
                THEN 'a1000000-0000-0000-0000-000000000000'::uuid
                ELSE 'b1000000-0000-0000-0000-000000000000'::uuid END
$$;
CREATE FUNCTION pg_temp.neto() RETURNS numeric LANGUAGE sql AS $$
    SELECT (estado_cuenta(pg_temp.mio()) -> 'resumen' ->> 'neto')::numeric
$$;
CREATE FUNCTION pg_temp.acordado() RETURNS numeric LANGUAGE sql AS $$
    SELECT (estado_cuenta(pg_temp.mio()) -> 'resumen' ->> 'saldo_acordado')::numeric
$$;
CREATE FUNCTION pg_temp.pendiente() RETURNS numeric LANGUAGE sql AS $$
    SELECT (estado_cuenta(pg_temp.mio()) -> 'resumen' ->> 'pendiente_acuerdo')::numeric
$$;
CREATE FUNCTION pg_temp.ok() RETURNS boolean LANGUAGE sql AS $$
    SELECT (verificar_vinculo('f0000000-0000-0000-0000-000000000000') ->> 'ok')::boolean
$$;
-- En la libreta de quien actúa: la fila que es el espejo de una fila del otro.
CREATE FUNCTION pg_temp.espejo(origen text) RETURNS uuid LANGUAGE sql AS $$
    SELECT id FROM deudas WHERE origen_id = origen::uuid
    UNION ALL
    SELECT id FROM pagos WHERE origen_id = origen::uuid
$$;
CREATE FUNCTION pg_temp.estado(fila text) RETURNS text LANGUAGE sql AS $$
    SELECT estado_acuerdo FROM deudas WHERE id = fila::uuid
    UNION ALL
    SELECT estado_acuerdo FROM pagos WHERE id = fila::uuid
$$;
-- La propuesta pendiente de una fila (la ven las dos partes).
CREATE FUNCTION pg_temp.prop(fila text) RETURNS uuid LANGUAGE sql AS $$
    SELECT id FROM propuestas WHERE fila_origen = fila::uuid AND estado = 'pendiente'
$$;
-- Mis avisos sin ver de un tipo.
CREATE FUNCTION pg_temp.sin_ver(tipo_ text) RETURNS int LANGUAGE sql AS $$
    SELECT count(*)::int FROM avisos
     WHERE usuario_id = auth.uid() AND tipo = tipo_ AND visto_at IS NULL
$$;
-- Mi aviso de un tipo sobre una fila de mi libreta.
CREATE FUNCTION pg_temp.aviso(tipo_ text, fila uuid) RETURNS jsonb LANGUAGE sql AS $$
    SELECT to_jsonb(a) FROM avisos a
     WHERE usuario_id = auth.uid() AND tipo = tipo_ AND fila_id = fila
$$;
-- En la libreta de quien actúa: ningún pago virtual con sobrante ni nada repartido de más
-- o sobre una fila rechazada.
CREATE FUNCTION pg_temp.cuadra() RETURNS boolean LANGUAGE sql AS $$
    SELECT NOT EXISTS (
        SELECT 1 FROM pagos p LEFT JOIN detalle_pagos dp ON dp.pago_id = p.id
         WHERE p.deudor_id = pg_temp.mio() AND p.es_compensacion
         GROUP BY p.id, p.monto_total
        HAVING abs(p.monto_total - COALESCE(sum(dp.monto_asignado), 0)) > 0.001)
    AND NOT EXISTS (
        SELECT 1 FROM deudas d JOIN detalle_pagos dp ON dp.deuda_id = d.id
         WHERE d.deudor_id = pg_temp.mio()
         GROUP BY d.id, d.monto, d.estado_acuerdo
        HAVING sum(dp.monto_asignado) > d.monto + 0.001 OR d.estado_acuerdo = 'rechazada')
    AND NOT EXISTS (
        SELECT 1 FROM pagos p JOIN detalle_pagos dp ON dp.pago_id = p.id
         WHERE p.deudor_id = pg_temp.mio()
         GROUP BY p.id, p.monto_total, p.estado_acuerdo
        HAVING sum(dp.monto_asignado) > p.monto_total + 0.001 OR p.estado_acuerdo = 'rechazada')
$$;

SET LOCAL ROLE authenticated;

-- ====================================================================================
-- 1. A anota "Bea me debe $20" → entra sola: acordada en A, espejo acordado en B, aviso.
--    A: +20. B: −20.
-- ====================================================================================
SELECT pg_temp.como('A');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d1', 'a1000000-0000-0000-0000-000000000000', 'Préstamo', 20, '2026-06-01', false);
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000d1'), 'acordada',
  '1. la deuda nueva de A entra acordada, sin esperar a B');
SELECT is(pg_temp.acordado(), 20.00, '1. saldo acordado de A: +20');
SELECT is(pg_temp.pendiente(), 0.00, '1. y nada esperando respuesta');
SELECT is(pg_temp.neto(), 20.00, '1. mi saldo de A: +20');
SELECT is((SELECT count(*) FROM acuerdos WHERE fila_a = 'a0000000-0000-0000-0000-0000000000d1')::int, 1,
  '1. un acuerdo la ata a su espejo');
SELECT is((SELECT estado FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000d1'), 'aceptada',
  '1. la propuesta queda en el historial, ya aceptada');
SELECT pg_temp.como('B');
SELECT is((SELECT row(titulo, monto, es_mi_deuda, estado_acuerdo)::text FROM deudas
            WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d1'),
  '(Préstamo,20.00,t,acordada)', '1. en B ya está el espejo: B debe, acordado y con el título');
SELECT is(pg_temp.acordado(), -20.00, '1. saldo acordado de B: −20');
SELECT is(pg_temp.neto(), -20.00, '1. mi saldo de B: −20');
SELECT is((SELECT row(tipo, fila_id = pg_temp.espejo('a0000000-0000-0000-0000-0000000000d1'),
                      (datos ->> 'monto')::numeric, datos ->> 'es_mia', datos ->> 'texto',
                      datos ? 'candidatos', de_usuario)::text
             FROM avisos WHERE usuario_id = auth.uid()),
  '(deuda_nueva,t,20.00,true,Préstamo,f,a0000000-0000-0000-0000-000000000000)',
  '1. B tiene un aviso deuda_nueva sobre su fila, en su punto de vista (él debe), sin candidatos');
SELECT ok(pg_temp.ok(), '1. verificar_vinculo ok');

-- ====================================================================================
-- 2. B anota "le debo $10 a Ana" → lo mismo desde el otro lado.
--    A: 20 + 10 = 30. B: −30.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('b0000000-0000-0000-0000-0000000000e2', 'b1000000-0000-0000-0000-000000000000', 'Taxi', 10, '2026-06-05', true);
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000e2'), 'acordada', '2. la deuda de B entra acordada');
SELECT is(pg_temp.acordado(), -30.00, '2. saldo acordado de B: −30');
SELECT is(pg_temp.neto(), -30.00, '2. mi saldo de B: −30');
SELECT pg_temp.como('A');
SELECT is((SELECT row(titulo, es_mi_deuda, estado_acuerdo)::text FROM deudas
            WHERE origen_id = 'b0000000-0000-0000-0000-0000000000e2'),
  '(Taxi,f,acordada)', '2. espejo en A: Bea le debe');
SELECT is(pg_temp.acordado(), 30.00, '2. saldo acordado de A: +30');
SELECT is(pg_temp.neto(), 30.00, '2. mi saldo de A: +30');
SELECT is(pg_temp.sin_ver('deuda_nueva'), 1, '2. A tiene su aviso deuda_nueva');
SELECT ok(pg_temp.ok(), '2. verificar_vinculo ok');

-- ====================================================================================
-- 3. A anota que Bea le pagó $8 (lo anota quien RECIBE) → entra solo; en B se reparte
--    como un pago automático suyo: a la deuda más antigua, el espejo del préstamo.
--    A: 30 − 8 = 22. B: −22.
-- ====================================================================================
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago) VALUES
  ('a0000000-0000-0000-0000-0000000000f3', 'a1000000-0000-0000-0000-000000000000', 8, '2026-06-10', false);
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000f3'), 'acordada', '3. el pago que anota quien recibe entra solo');
SELECT is(pg_temp.acordado(), 22.00, '3. saldo acordado de A: 22');
SELECT is(pg_temp.neto(), 22.00, '3. mi saldo de A: 22');
SELECT pg_temp.como('B');
SELECT is((SELECT row(p.monto_total, p.es_mi_pago, p.estado_acuerdo, sum(dp.monto_asignado))::text
             FROM pagos p JOIN detalle_pagos dp ON dp.pago_id = p.id
            WHERE p.origen_id = 'a0000000-0000-0000-0000-0000000000f3'
            GROUP BY p.id),
  '(8.00,t,acordada,8.00)', '3. en B: pago de B, acordado y repartido entero');
SELECT is((SELECT dp.deuda_id FROM detalle_pagos dp JOIN pagos p ON p.id = dp.pago_id
            WHERE p.origen_id = 'a0000000-0000-0000-0000-0000000000f3'),
  pg_temp.espejo('a0000000-0000-0000-0000-0000000000d1'), '3. a la deuda más antigua (FIFO): el préstamo');
SELECT is(pg_temp.acordado(), -22.00, '3. saldo acordado de B: −22');
SELECT is(pg_temp.neto(), -22.00, '3. mi saldo de B: −22');
SELECT is(pg_temp.sin_ver('pago_nuevo'), 1, '3. B tiene su aviso pago_nuevo');
SELECT ok(pg_temp.ok(), '3. verificar_vinculo ok');

-- ====================================================================================
-- 4. B anota un pago de $5 que ENTREGÓ → espera a que A lo confirme. A confirma.
--    Mientras: B −22 + 5 = −17 en su saldo, −22 acordado. Después: A 17, B −17.
--    Luego B anota otro de $3 y A dice "no lo recibí" → rechazado, no cuenta.
-- ====================================================================================
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago) VALUES
  ('b0000000-0000-0000-0000-0000000000f4', 'b1000000-0000-0000-0000-000000000000', 5, '2026-06-12', true);
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000f4'), 'propuesta',
  '4. un pago que anota quien entrega nace propuesta');
SELECT is(pg_temp.neto(), -17.00, '4. cuenta en mi saldo de B (−22 + 5)');
SELECT is(pg_temp.acordado(), -22.00, '4. pero no en el acordado');
SELECT pg_temp.como('A');
SELECT is(pg_temp.espejo('b0000000-0000-0000-0000-0000000000f4'), NULL, '4. en A todavía no hay nada');
SELECT is((SELECT tipo FROM avisos WHERE usuario_id = auth.uid()
            AND propuesta_id = pg_temp.prop('b0000000-0000-0000-0000-0000000000f4')),
  'pago_por_confirmar', '4. A tiene un aviso pago_por_confirmar');
SELECT is(pg_temp.acordado(), 22.00, '4. y su saldo no se movió');
INSERT INTO t VALUES ('r4', aceptar_propuesta(pg_temp.prop('b0000000-0000-0000-0000-0000000000f4')));
SELECT is((SELECT valor ->> 'resultado' FROM t WHERE clave = 'r4'), 'aceptada', '4. A confirma');
SELECT is(pg_temp.acordado(), 17.00, '4. saldo acordado de A: 17');
SELECT is(pg_temp.neto(), 17.00, '4. mi saldo de A: 17');
SELECT is(pg_temp.sin_ver('pago_por_confirmar'), 0, '4. su aviso queda visto al responder');
SELECT pg_temp.como('B');
SELECT is(pg_temp.acordado(), -17.00, '4. saldo acordado de B: −17');
SELECT is(pg_temp.neto(), -17.00, '4. mi saldo de B: −17');
SELECT is(pg_temp.aviso('confirmado', 'b0000000-0000-0000-0000-0000000000f4') ->> 'de_usuario',
  'a0000000-0000-0000-0000-000000000000', '4. a B le llega "confirmado" de A, sobre su pago');
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago) VALUES
  ('b0000000-0000-0000-0000-0000000000f5', 'b1000000-0000-0000-0000-000000000000', 3, '2026-06-13', true);
SELECT pg_temp.como('A');
SELECT lives_ok(format('SELECT rechazar_propuesta(%L, %L)',
                       pg_temp.prop('b0000000-0000-0000-0000-0000000000f5'), 'No me llegó'),
  '4. A dice "no lo recibí"');
SELECT pg_temp.como('B');
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000f5'), 'rechazada', '4. el pago de B queda rechazado');
SELECT is(pg_temp.aviso('rechazo', 'b0000000-0000-0000-0000-0000000000f5') -> 'datos' ->> 'motivo', 'No me llegó',
  '4. a B le llega el rechazo con el motivo');
SELECT is(pg_temp.neto(), -17.00, '4. y no cuenta: B sigue en −17');
SELECT ok(pg_temp.ok(), '4. verificar_vinculo ok');

-- ====================================================================================
-- 5. B rechaza el préstamo (el espejo de d1), que ya tenía repartido el pago de $8 → las
--    dos filas rechazadas; lo repartido pasa a saldo a favor de B.
--    A: Bea le debe 10 y le pagó 8 + 5 → −3. B: +3.
-- ====================================================================================
INSERT INTO t VALUES ('r5', rechazar_fila('deuda', pg_temp.espejo('a0000000-0000-0000-0000-0000000000d1'),
                                          'Eso no fue un préstamo'));
SELECT is((SELECT valor ->> 'resultado' FROM t WHERE clave = 'r5'), 'rechazada', '5. B rechaza');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d1'), 'rechazada',
  '5. el espejo de B queda rechazado');
SELECT is((SELECT count(*) FROM detalle_pagos
            WHERE deuda_id = pg_temp.espejo('a0000000-0000-0000-0000-0000000000d1'))::int, 0,
  '5. el pago de $8 ya no está repartido sobre lo rechazado');
SELECT is(pg_temp.neto(), 3.00, '5. mi saldo de B: +3 (pagó 13 y solo debía 10)');
SELECT is(pg_temp.acordado(), 3.00, '5. saldo acordado de B: +3');
SELECT ok(pg_temp.cuadra(), '5. la libreta de B cuadra');
SELECT is(pg_temp.sin_ver('deuda_nueva'), 0, '5. rechazarlo deja visto su aviso');
SELECT is((rechazar_fila('deuda', pg_temp.espejo('a0000000-0000-0000-0000-0000000000d1')) ->> 'repetido'), 'true',
  '5. repetirlo no hace nada');
SELECT throws_ok($$SELECT rechazar_fila('deuda', 'b0000000-0000-0000-0000-0000000000e2')$$, '22023', NULL,
  '5. lo que anotó uno mismo no se rechaza: se propone borrarlo');
SELECT throws_ok($$SELECT rechazar_fila('deuda', 'a0000000-0000-0000-0000-0000000000d1')$$, '42501', NULL,
  '5. ni se rechaza una fila de la libreta del otro');
SELECT pg_temp.como('A');
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000d1'), 'rechazada', '5. en A también queda rechazada');
SELECT is(pg_temp.neto(), -3.00, '5. mi saldo de A: −3');
SELECT is(pg_temp.acordado(), -3.00, '5. saldo acordado de A: −3');
SELECT is(pg_temp.aviso('rechazo', 'a0000000-0000-0000-0000-0000000000d1') -> 'datos' ->> 'motivo',
  'Eso no fue un préstamo', '5. a A le llega el rechazo con el motivo, sobre su fila');
SELECT is((SELECT motivo FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000d1'),
  'Eso no fue un préstamo', '5. el motivo queda en la propuesta de la fila (de ahí lo lee la app)');
SELECT ok(pg_temp.cuadra(), '5. la libreta de A cuadra');
SELECT ok(pg_temp.ok(), '5. verificar_vinculo ok');

-- ====================================================================================
-- 6. Rechazar una deuda que entró en un cruce de la OTRA libreta.
--    A anota "le debo $6" y "Bea me debe $9". En A: Bea debe 10 + 9, le pagó 13 (saldo a
--    favor que abona el Taxi y 3 del Súper) → te deben 6, debes 6 → A cruza $6.
--    B rechaza las Entradas (espejo de d6) → el cruce de A se deshace entero.
--    Antes del rechazo: A −3 − 6 + 9 = 0. Después: A +6, B −6.
-- ====================================================================================
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d6', 'a1000000-0000-0000-0000-000000000000', 'Entradas', 6, '2026-06-15', true),
  ('a0000000-0000-0000-0000-0000000000d9', 'a1000000-0000-0000-0000-000000000000', 'Súper',    9, '2026-06-16', false);
SELECT is(pg_temp.neto(), 0.00, '6. mi saldo de A: 0');
SELECT lives_ok($$SELECT aplicar_cruce('a1000000-0000-0000-0000-000000000000')$$, '6. A cruza');
SELECT is((SELECT count(*) FROM pagos WHERE deudor_id = pg_temp.mio() AND es_compensacion)::int, 2,
  '6. dos pagos virtuales');
SELECT is((SELECT sum(monto_total) FROM pagos WHERE deudor_id = pg_temp.mio() AND es_compensacion), 12.00,
  '6. de $6 cada uno');
SELECT pg_temp.como('B');
SELECT lives_ok(format('SELECT rechazar_fila(%L, %L, %L)', 'deuda',
                       pg_temp.espejo('a0000000-0000-0000-0000-0000000000d6'), 'Esas las pagué yo'),
  '6. B rechaza las Entradas');
SELECT is(pg_temp.neto(), -6.00, '6. mi saldo de B: −6');
SELECT ok(pg_temp.cuadra(), '6. la libreta de B cuadra');
SELECT pg_temp.como('A');
SELECT is((SELECT count(*) FROM pagos WHERE deudor_id = pg_temp.mio() AND es_compensacion)::int, 0,
  '6. el cruce de A se deshizo: ya no hay qué cruzar');
SELECT ok(pg_temp.cuadra(), '6. ningún pago virtual con sobrante en A');
SELECT is(pg_temp.neto(), 6.00, '6. mi saldo de A: +6');
SELECT ok(pg_temp.ok(), '6. verificar_vinculo ok');

-- ====================================================================================
-- 7. Duplicados que llegan igual (decisión 21: sin conexión, el aviso previo de la app
--    no alcanzó).
--    7a. B anota "Pizza, le debo 7" (entra: A 13, B −13); A, sin verla, anota "pizza, me
--        debe 7" un día después (entra: A 20, B −20). B dice "es la misma": como la suya
--        ya estaba acordada, el par nuevo sobra → A 13, B −13.
-- ====================================================================================
SELECT pg_temp.como('B');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('b0000000-0000-0000-0000-0000000000e7', 'b1000000-0000-0000-0000-000000000000', 'Pizza', 7, '2026-07-01', true);
SELECT pg_temp.como('A');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d7', 'a1000000-0000-0000-0000-000000000000', 'pizza', 7, '2026-07-02', false);
SELECT is(pg_temp.neto(), 20.00, '7a. sin fusionar, en A cuenta dos veces');
SELECT pg_temp.como('B');
SELECT is(pg_temp.neto(), -20.00, '7a. y en B también');
SELECT is(jsonb_path_query_array(pg_temp.aviso('deuda_nueva', pg_temp.espejo('a0000000-0000-0000-0000-0000000000d7')),
                                 '$.datos.candidatos[*].id'),
  '["b0000000-0000-0000-0000-0000000000e7"]'::jsonb, '7a. el aviso trae la Pizza de B como candidata');
INSERT INTO t VALUES ('r7a', fusionar_espejo('deuda', pg_temp.espejo('a0000000-0000-0000-0000-0000000000d7'),
                                             'b0000000-0000-0000-0000-0000000000e7'));
SELECT is((SELECT valor ->> 'modo' FROM t WHERE clave = 'r7a'), 'sobraba', '7a. B dice "es la misma": el par nuevo sobra');
SELECT is((SELECT estado_acuerdo FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d7'), 'rechazada',
  '7a. el espejo queda rechazado');
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000e7'), 'acordada', '7a. la Pizza de B sigue acordada');
SELECT is(pg_temp.neto(), -13.00, '7a. mi saldo de B: −13, sin duplicar');
SELECT is((fusionar_espejo('deuda', pg_temp.espejo('a0000000-0000-0000-0000-0000000000d7'),
                           'b0000000-0000-0000-0000-0000000000e7') ->> 'repetido'), 'true',
  '7a. repetirlo no hace nada');
SELECT throws_ok($$SELECT fusionar_espejo('deuda', 'a0000000-0000-0000-0000-0000000000d9',
                                                   'b0000000-0000-0000-0000-0000000000e7')$$,
  '42501', NULL, '7a. no se fusiona una fila de la libreta del otro');
SELECT pg_temp.como('A');
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000d7'), 'rechazada', '7a. en A la repetida queda rechazada');
SELECT is(pg_temp.aviso('rechazo', 'a0000000-0000-0000-0000-0000000000d7') -> 'datos' ->> 'motivo',
  'Ya estaba anotada', '7a. y a A le llega "ya estaba anotada"');
SELECT is(pg_temp.neto(), 13.00, '7a. mi saldo de A: 13');
SELECT ok(pg_temp.ok(), '7a. verificar_vinculo ok');

-- ====================================================================================
--    7b. B anota un pago de $2 que entregó (espera a A: B −11 en su saldo, −13 acordado).
--        A, sin verlo, anota que Bea le pagó $2 → entra (A 11) y en B cuenta dos veces
--        (−9). B dice "es la misma": su pago ocupa el lugar del espejo → B −11 acordado.
-- ====================================================================================
SELECT pg_temp.como('B');
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago) VALUES
  ('b0000000-0000-0000-0000-0000000000f7', 'b1000000-0000-0000-0000-000000000000', 2, '2026-07-05', true);
SELECT pg_temp.como('A');
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago) VALUES
  ('a0000000-0000-0000-0000-0000000000f7', 'a1000000-0000-0000-0000-000000000000', 2, '2026-07-05', false);
SELECT is(pg_temp.neto(), 11.00, '7b. mi saldo de A: 11');
SELECT pg_temp.como('B');
SELECT is(pg_temp.neto(), -9.00, '7b. sin fusionar, en B el pago cuenta dos veces');
SELECT is(jsonb_path_query_array(pg_temp.aviso('pago_nuevo', pg_temp.espejo('a0000000-0000-0000-0000-0000000000f7')),
                                 '$.datos.candidatos[*].id'),
  '["b0000000-0000-0000-0000-0000000000f7"]'::jsonb, '7b. el aviso trae el pago de B como candidato');
INSERT INTO t VALUES ('r7b', fusionar_espejo('pago', pg_temp.espejo('a0000000-0000-0000-0000-0000000000f7'),
                                             'b0000000-0000-0000-0000-0000000000f7'));
SELECT is((SELECT valor ->> 'modo' FROM t WHERE clave = 'r7b'), 'enlazada', '7b. B dice "es la misma": se enlazan');
SELECT is(pg_temp.espejo('a0000000-0000-0000-0000-0000000000f7'), 'b0000000-0000-0000-0000-0000000000f7'::uuid,
  '7b. el pago de B ocupa el lugar del espejo, que se borró');
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000f7'), 'acordada', '7b. y queda acordado');
SELECT is((SELECT estado FROM propuestas WHERE fila_origen = 'b0000000-0000-0000-0000-0000000000f7'), 'aceptada',
  '7b. su propuesta quedó resuelta por el enlace');
SELECT is(pg_temp.neto(), -11.00, '7b. mi saldo de B: −11');
SELECT is(pg_temp.acordado(), -11.00, '7b. saldo acordado de B: −11');
SELECT is(pg_temp.pendiente(), 0.00, '7b. nada esperando respuesta');
SELECT is(pg_temp.sin_ver('confirmado'), 1, '7b. sin un "confirmado" nuevo: el enlace lo hizo B');
SELECT ok(pg_temp.cuadra(), '7b. la libreta de B cuadra');
SELECT pg_temp.como('A');
SELECT is(pg_temp.sin_ver('pago_por_confirmar'), 0, '7b. A ya no tiene nada que confirmar');
SELECT is(pg_temp.acordado(), 11.00, '7b. saldo acordado de A: 11');
SELECT ok(pg_temp.ok(), '7b. verificar_vinculo ok');

-- ====================================================================================
--    7c. Lo mismo con una deuda de B que esperaba respuesta (pasó el tope: B −15 en su
--        saldo, −11 acordado). A anota la misma → entra (A 15; B −19). B dice "es la
--        misma" → su deuda ocupa el lugar del espejo → A 15, B −15.
-- ====================================================================================
SELECT pg_temp.como('B');
SELECT set_config('deudas.tope_diario', '0', true);
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('b0000000-0000-0000-0000-0000000000e6', 'b1000000-0000-0000-0000-000000000000', 'Helado', 4, '2026-07-06', true);
SELECT set_config('deudas.tope_diario', '', true);
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000e6'), 'propuesta', '7c. con el tope lleno, la deuda de B espera');
SELECT pg_temp.como('A');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000d8', 'a1000000-0000-0000-0000-000000000000', 'helado', 4, '2026-07-06', false);
SELECT is(pg_temp.neto(), 15.00, '7c. mi saldo de A: 15');
SELECT pg_temp.como('B');
SELECT is(pg_temp.neto(), -19.00, '7c. sin fusionar, en B cuenta dos veces');
INSERT INTO t VALUES ('r7c', fusionar_espejo('deuda', pg_temp.espejo('a0000000-0000-0000-0000-0000000000d8'),
                                             'b0000000-0000-0000-0000-0000000000e6'));
SELECT is((SELECT valor ->> 'modo' FROM t WHERE clave = 'r7c'), 'enlazada', '7c. se enlazan');
SELECT is(pg_temp.espejo('a0000000-0000-0000-0000-0000000000d8'), 'b0000000-0000-0000-0000-0000000000e6'::uuid,
  '7c. la deuda de B ocupa el lugar del espejo, que se borró');
SELECT is((SELECT count(*) FROM deudas WHERE titulo = 'helado')::int, 0, '7c. en B no queda el espejo');
SELECT is(pg_temp.neto(), -15.00, '7c. mi saldo de B: −15');
SELECT is(pg_temp.acordado(), -15.00, '7c. saldo acordado de B: −15');
SELECT ok(pg_temp.cuadra(), '7c. la libreta de B cuadra');
SELECT pg_temp.como('A');
SELECT is(pg_temp.sin_ver('propuesta'), 0, '7c. A ya no tiene nada que responder');
SELECT is(pg_temp.acordado(), 15.00, '7c. saldo acordado de A: 15');
SELECT ok(pg_temp.ok(), '7c. verificar_vinculo ok');

-- ====================================================================================
-- 8. Cambiar algo acordado sigue siendo propuesta (decisión 22): A propone el Súper de 9
--    a 12 → aviso "cambio" a B → B acepta → las dos en 12 y a A le llega "confirmado".
--    A: 15 + 3 = 18. B: −18.
-- ====================================================================================
INSERT INTO t VALUES ('r8', proponer_cambio('deuda', 'a0000000-0000-0000-0000-0000000000d9', 'editar', '{"monto": 12}'));
SELECT is((SELECT monto FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d9'), 9.00,
  '8. mientras B no acepta, nada cambia');
SELECT pg_temp.como('B');
SELECT is((SELECT row((datos -> 'antes' ->> 'monto')::numeric, (datos ->> 'monto')::numeric, datos ->> 'es_mia')::text
             FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'cambio'
              AND fila_id = pg_temp.espejo('a0000000-0000-0000-0000-0000000000d9')),
  '(9.00,12.00,true)', '8. a B le llega el aviso del cambio, sobre su fila y en su punto de vista');
INSERT INTO t VALUES ('r8b', aceptar_propuesta(pg_temp.prop('a0000000-0000-0000-0000-0000000000d9')));
SELECT is((SELECT monto FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d9'), 12.00,
  '8. B acepta: su fila en 12');
SELECT is(pg_temp.neto(), -18.00, '8. mi saldo de B: −18');
SELECT pg_temp.como('A');
SELECT is((SELECT monto FROM deudas WHERE id = 'a0000000-0000-0000-0000-0000000000d9'), 12.00, '8. y la de A también');
SELECT is(pg_temp.aviso('confirmado', 'a0000000-0000-0000-0000-0000000000d9') -> 'datos' ->> 'tipo', 'editar',
  '8. a A le llega que B aceptó el cambio');
SELECT is(pg_temp.neto(), 18.00, '8. mi saldo de A: 18');
SELECT ok(pg_temp.ok(), '8. verificar_vinculo ok');

-- ====================================================================================
-- 9. Borrar algo acordado también: B propone borrar la Pizza → aviso "borrado" a A → A
--    lo rechaza → todo sigue igual y a B le llega el rechazo.
-- ====================================================================================
SELECT pg_temp.como('B');
INSERT INTO t VALUES ('r9', proponer_cambio('deuda', 'b0000000-0000-0000-0000-0000000000e7', 'borrar'));
SELECT pg_temp.como('A');
SELECT isnt(pg_temp.aviso('borrado', pg_temp.espejo('b0000000-0000-0000-0000-0000000000e7')), NULL,
  '9. a A le llega el aviso del borrado, sobre su fila');
SELECT lives_ok(format('SELECT rechazar_propuesta(%L, %L)',
                       pg_temp.prop('b0000000-0000-0000-0000-0000000000e7'), 'Sí la comimos'),
  '9. A lo rechaza');
SELECT is(pg_temp.estado(pg_temp.espejo('b0000000-0000-0000-0000-0000000000e7')::text), 'acordada',
  '9. la Pizza sigue en A');
SELECT is(pg_temp.neto(), 18.00, '9. mi saldo de A no cambia');
SELECT pg_temp.como('B');
SELECT is(pg_temp.aviso('rechazo', 'b0000000-0000-0000-0000-0000000000e7') -> 'datos' ->> 'motivo', 'Sí la comimos',
  '9. a B le llega el rechazo con el motivo');
SELECT ok(pg_temp.ok(), '9. verificar_vinculo ok');

-- ====================================================================================
-- 10. La guardia sigue: nada acordado cambia monto, fecha ni dirección sin RPC.
-- ====================================================================================
SELECT pg_temp.como('A');
SELECT throws_ok($$UPDATE deudas SET monto = 99 WHERE id = 'a0000000-0000-0000-0000-0000000000d9'$$, '42501', NULL,
  '10. UPDATE directo del monto de algo acordado → 42501');
SELECT lives_ok($$UPDATE deudas SET titulo = 'Súper del mes' WHERE id = 'a0000000-0000-0000-0000-0000000000d9'$$,
  '10. el título sí');

-- ====================================================================================
-- 11. El sync reintenta: la misma fila subida otra vez (upsert, como Flutter) no crea otro
--     espejo ni otro aviso. Una fila nueva subida con upsert entra igual.
--     A: 18 + 1.50 = 19.50. B: −19.50.
-- ====================================================================================
SELECT lives_ok($$INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
                  VALUES ('a0000000-0000-0000-0000-0000000000d9', 'a1000000-0000-0000-0000-000000000000',
                          'Súper del mes', 12, '2026-06-16', false)
                  ON CONFLICT (id) DO UPDATE SET titulo = EXCLUDED.titulo$$,
  '11. el sync vuelve a subir una fila acordada');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
VALUES ('a0000000-0000-0000-0000-0000000000d2', 'a1000000-0000-0000-0000-000000000000', 'Café', 1.50, '2026-07-10', false)
ON CONFLICT (id) DO UPDATE SET titulo = EXCLUDED.titulo;
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000d2'), 'acordada', '11. una fila nueva subida con upsert entra sola');
SELECT is(pg_temp.neto(), 19.50, '11. mi saldo de A: 19.50');
SELECT pg_temp.como('B');
SELECT is((SELECT count(*) FROM deudas WHERE origen_id = 'a0000000-0000-0000-0000-0000000000d9')::int, 1,
  '11. sigue habiendo un solo espejo del Súper');
SELECT is((SELECT count(*) FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'deuda_nueva'
            AND fila_id = pg_temp.espejo('a0000000-0000-0000-0000-0000000000d9'))::int, 1,
  '11. y un solo aviso');
SELECT is(pg_temp.neto(), -19.50, '11. mi saldo de B: −19.50');
SELECT ok(pg_temp.ok(), '11. verificar_vinculo ok');

-- ====================================================================================
-- 12. Un deudor sin vínculo: todo `local`, sin propuestas ni avisos.
-- ====================================================================================
SELECT pg_temp.como('A');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000da', 'a2000000-0000-0000-0000-000000000000', 'Suelto', 5, '2026-07-10', false);
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000da'), 'local', '12. sin vínculo nace local');
SELECT is((SELECT count(*) FROM propuestas WHERE fila_origen = 'a0000000-0000-0000-0000-0000000000da')::int, 0,
  '12. sin propuesta');
SELECT is((SELECT count(*) FROM avisos WHERE fila_id = 'a0000000-0000-0000-0000-0000000000da')::int, 0, '12. ni aviso');

-- ====================================================================================
-- 13. Un pago por RPC (registrar_pago) con el vínculo: entra y su espejo también; los
--     candados del vínculo se toman antes que el del deudor. Después, el tope: 50 filas
--     nuevas de A en 24 horas entran solas; la 51 nace propuesta. El de B va aparte.
-- ====================================================================================
INSERT INTO t VALUES ('r13', registrar_pago('a1000000-0000-0000-0000-000000000000', 0.50, false, '2026-07-11'));
SELECT is(pg_temp.estado(t.valor ->> 'pago_id'), 'acordada', '13. el pago por RPC entra solo')
  FROM t WHERE clave = 'r13';
SELECT is(pg_temp.neto(), 19.00, '13. mi saldo de A: 19');
SELECT ok(pg_temp.ok(), '13. verificar_vinculo ok');
RESET ROLE;
INSERT INTO t VALUES ('n', to_jsonb(_nacidas_hoy('f0000000-0000-0000-0000-000000000000',
                                                 'a0000000-0000-0000-0000-000000000000')));
SET LOCAL ROLE authenticated;
INSERT INTO deudas (deudor_id, titulo, monto, fecha_gasto, es_mi_deuda)
SELECT 'a1000000-0000-0000-0000-000000000000', 'Tope ' || g, 1, '2026-08-01', false
  FROM generate_series(1, 50 - (SELECT valor::text::int FROM t WHERE clave = 'n')) g;
SELECT is((SELECT count(*) FROM deudas WHERE titulo LIKE 'Tope %' AND estado_acuerdo = 'acordada')::int,
          50 - (SELECT valor::text::int FROM t WHERE clave = 'n'),
  '13. hasta la 50 del día, todo entra solo');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000db', 'a1000000-0000-0000-0000-000000000000', 'La 51', 1, '2026-08-01', false);
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000db'), 'propuesta', '13. la 51 nace propuesta');
SELECT pg_temp.como('B');
SELECT is(pg_temp.espejo('a0000000-0000-0000-0000-0000000000db'), NULL, '13. y no entra en B');
SELECT is((SELECT tipo FROM avisos WHERE usuario_id = auth.uid()
            AND propuesta_id = pg_temp.prop('a0000000-0000-0000-0000-0000000000db')),
  'propuesta', '13. B tiene un aviso de propuesta por responder');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('b0000000-0000-0000-0000-0000000000eb', 'b1000000-0000-0000-0000-000000000000', 'Chicles', 1, '2026-08-01', true);
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000eb'), 'acordada', '13. el tope es por persona: lo de B sigue entrando');
SELECT ok(pg_temp.ok(), '13. verificar_vinculo ok');

-- ====================================================================================
-- 15. RLS: cada uno ve solo sus avisos y nadie los escribe directo.
-- ====================================================================================
SELECT pg_temp.como('A');
INSERT INTO t SELECT 'aviso_a', to_jsonb(id) FROM avisos WHERE usuario_id = auth.uid() ORDER BY id LIMIT 1;
SELECT pg_temp.como('B');
SELECT is((SELECT count(*) FROM avisos WHERE usuario_id <> auth.uid())::int, 0, '15. B no ve los avisos de A');
SELECT throws_ok($$INSERT INTO avisos (usuario_id, tipo) VALUES (auth.uid(), 'rechazo')$$, '42501', NULL,
  '15. nadie inserta avisos directo');
SELECT throws_ok($$UPDATE avisos SET visto_at = now()$$, '42501', NULL, '15. ni los marca directo');
SELECT throws_ok($$DELETE FROM avisos$$, '42501', NULL, '15. ni los borra');
SELECT is(marcar_vistos(ARRAY[(SELECT (valor #>> '{}')::uuid FROM t WHERE clave = 'aviso_a')]), 0,
  '15. marcar_vistos no toca avisos ajenos');
SELECT cmp_ok(marcar_vistos(), '>', 0, '15. marcar todo como visto');
SELECT is((SELECT count(*) FROM avisos WHERE usuario_id = auth.uid() AND visto_at IS NULL)::int, 0,
  '15. y no queda nada sin ver');
SELECT pg_temp.como('C');
SELECT is((SELECT count(*) FROM avisos)::int, 0, '15. un tercero no ve nada');
RESET ROLE;
SET LOCAL ROLE anon;
SELECT throws_ok($$SELECT marcar_vistos()$$, '42501', NULL, '15. sin sesión, nada');
RESET ROLE;
SET LOCAL ROLE authenticated;

-- ====================================================================================
-- 14. Desvincular con un pago por confirmar: queda anulado (vuelve a ser solo de B) y su
--     aviso desaparece; lo acordado sigue; al otro le llega que se rompió el vínculo.
-- ====================================================================================
SELECT pg_temp.como('B');
INSERT INTO pagos (id, deudor_id, monto_total, fecha_pago, es_mi_pago) VALUES
  ('b0000000-0000-0000-0000-0000000000f9', 'b1000000-0000-0000-0000-000000000000', 4, '2026-08-02', true);
SELECT pg_temp.como('A');
SELECT is(pg_temp.sin_ver('pago_por_confirmar'), 1, '14. A tiene un pago por confirmar');
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT desvincular('f0000000-0000-0000-0000-000000000000')$$, '14. B se desvincula');
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000f9'), 'local', '14. el pago por confirmar vuelve a ser solo de B');
SELECT is(pg_temp.estado('b0000000-0000-0000-0000-0000000000e2'), 'acordada', '14. lo acordado sigue acordado');
SELECT is(pg_temp.sin_ver('desvinculado'), 0, '14. a B no le llega aviso (lo hizo él)');
SELECT throws_ok(format('SELECT rechazar_fila(%L, %L)', 'deuda', pg_temp.espejo('a0000000-0000-0000-0000-0000000000d9')),
  '22023', NULL, '14. sin vínculo ya no se rechaza nada');
SELECT pg_temp.como('A');
SELECT is(pg_temp.sin_ver('pago_por_confirmar'), 0, '14. a A ya no le queda nada que confirmar');
SELECT is(pg_temp.sin_ver('desvinculado'), 1, '14. a A le llega que B se desvinculó');
INSERT INTO deudas (id, deudor_id, titulo, monto, fecha_gasto, es_mi_deuda) VALUES
  ('a0000000-0000-0000-0000-0000000000dc', 'a1000000-0000-0000-0000-000000000000', 'Después', 1, '2026-08-03', false);
SELECT is(pg_temp.estado('a0000000-0000-0000-0000-0000000000dc'), 'local', '14. lo nuevo vuelve a nacer local');

SELECT * FROM finish();
ROLLBACK;
