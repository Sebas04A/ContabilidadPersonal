-- Fase 9B: grupos compartidos (§4.8; decisiones de §3.2 y 25 a 31 de §3.3). Los
-- escenarios de 9.4, en orden y sobre el mismo grupo: cada uno parte de lo que dejó el
-- anterior, con los saldos por par (29) calculados a mano en los comentarios.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(159);

-- ------------------------------------------------------------------------------------
-- Datos: Ana (A), Beto (B) y Caro (C) tienen la app; Eva (E) es una usuaria ajena. Dani
-- es una persona sin app que Ana agrega al grupo. Ningún vínculo: no hace falta (§3.2).
-- ------------------------------------------------------------------------------------
INSERT INTO auth.users (id, email, aud, role, raw_user_meta_data) VALUES
  ('a0000000-0000-0000-0000-000000000000', 'a@test.local', 'authenticated', 'authenticated', '{"nombre":"Ana"}'),
  ('b0000000-0000-0000-0000-000000000000', 'b@test.local', 'authenticated', 'authenticated', '{"nombre":"Beto"}'),
  ('c0000000-0000-0000-0000-000000000000', 'c@test.local', 'authenticated', 'authenticated', '{"nombre":"Caro"}'),
  ('e0000000-0000-0000-0000-000000000000', 'e@test.local', 'authenticated', 'authenticated', '{"nombre":"Eva"}');

CREATE TEMP TABLE t (clave text PRIMARY KEY, valor text);
GRANT ALL ON t TO authenticated;

CREATE FUNCTION pg_temp.como(u text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    PERFORM set_config('request.jwt.claims',
        json_build_object('sub', CASE u WHEN 'A' THEN 'a0000000-0000-0000-0000-000000000000'
                                        WHEN 'B' THEN 'b0000000-0000-0000-0000-000000000000'
                                        WHEN 'C' THEN 'c0000000-0000-0000-0000-000000000000'
                                        ELSE 'e0000000-0000-0000-0000-000000000000' END,
                          'role', 'authenticated')::text, true);
END $$;
-- El grupo del viaje (g1) y el de la casa (g2).
CREATE FUNCTION pg_temp.g(n int DEFAULT 1) RETURNS uuid LANGUAGE sql AS $$
    SELECT ('91000000-0000-0000-0000-00000000000' || n)::uuid
$$;
-- El miembro de un grupo por su nombre (lo lee quien actúa, que tiene que ser miembro).
CREATE FUNCTION pg_temp.m(nombre_ text, n int DEFAULT 1) RETURNS uuid LANGUAGE sql AS $$
    SELECT id FROM grupo_miembros WHERE grupo_id = pg_temp.g(n) AND nombre = nombre_
$$;
-- Una fila de participantes: {miembro_id, pagado, peso, …extra}.
CREATE FUNCTION pg_temp.p(nombre_ text, pagado numeric DEFAULT 0, peso numeric DEFAULT NULL,
                          extra jsonb DEFAULT '{}', n int DEFAULT 1) RETURNS jsonb LANGUAGE sql AS $$
    SELECT jsonb_build_object('miembro_id', pg_temp.m(nombre_, n), 'pagado', pagado)
        || CASE WHEN peso IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('peso', peso) END || extra
$$;
-- Los saldos por par: "Debe>A:monto", en orden de nombre.
CREATE FUNCTION pg_temp.pares(n int DEFAULT 1) RETURNS text LANGUAGE sql AS $$
    SELECT COALESCE(string_agg(md.nombre || '>' || ma.nombre || ':' || p.monto, ' ' ORDER BY md.nombre, ma.nombre), '')
      FROM _pares_grupo(pg_temp.g(n)) p
      JOIN grupo_miembros md ON md.id = p.debe
      JOIN grupo_miembros ma ON ma.id = p.a
$$;
CREATE FUNCTION pg_temp.neto(nombre_ text, n int DEFAULT 1) RETURNS numeric LANGUAGE sql AS $$
    SELECT (m ->> 'neto')::numeric FROM jsonb_array_elements(estado_grupo(pg_temp.g(n)) -> 'miembros') m
     WHERE m ->> 'nombre' = nombre_
$$;
-- Los participantes de un gasto: "nombre:parte:estado", en orden.
CREATE FUNCTION pg_temp.partes(gasto text) RETURNS text LANGUAGE sql AS $$
    SELECT string_agg(m.nombre || ':' || p.parte || ':' || p.estado, ' ' ORDER BY p.orden)
      FROM gasto_participantes p JOIN grupo_miembros m ON m.id = p.miembro_id
     WHERE p.gasto_id = gasto::uuid
$$;
CREATE FUNCTION pg_temp.estado(gasto text) RETURNS text LANGUAGE sql AS $$
    SELECT estado FROM gastos WHERE id = gasto::uuid
$$;
-- Mis avisos sin ver de un tipo.
CREATE FUNCTION pg_temp.sin_ver(tipo_ text) RETURNS int LANGUAGE sql AS $$
    SELECT count(*)::int FROM avisos WHERE usuario_id = auth.uid() AND tipo = tipo_ AND visto_at IS NULL
$$;
CREATE FUNCTION pg_temp.aviso(tipo_ text, gasto text) RETURNS jsonb LANGUAGE sql AS $$
    SELECT datos FROM avisos WHERE usuario_id = auth.uid() AND tipo = tipo_ AND gasto_id = gasto::uuid
     ORDER BY created_at DESC LIMIT 1
$$;

SET LOCAL ROLE authenticated;

-- ====================================================================================
-- 1. Ana crea el grupo del viaje; Beto y Caro entran con el MISMO enlace; Ana agrega a
--    Dani (sin app). Ana paga $90 entre Ana, Beto y Caro.
--    Pares: Beto>Ana 30, Caro>Ana 30.
-- ====================================================================================
SELECT pg_temp.como('A');
SELECT is((crear_grupo(pg_temp.g(1), 'Viaje a la costa', 'viaje', '92000000-0000-0000-0000-0000000000a1')
           ->> 'mi_miembro_id'), '92000000-0000-0000-0000-0000000000a1', '1. Ana crea el grupo y es su primer miembro');
INSERT INTO t VALUES ('codigo', invitar_a_grupo(pg_temp.g(1)));
SELECT is(length((SELECT valor FROM t WHERE clave = 'codigo')), 10, '1. Ana saca un enlace de 10 caracteres');
SELECT pg_temp.como('B');
SELECT is(unirse_a_grupo((SELECT valor FROM t WHERE clave = 'codigo')), pg_temp.g(1), '1. Beto entra con el enlace');
SELECT pg_temp.como('C');
SELECT is(unirse_a_grupo(lower((SELECT valor FROM t WHERE clave = 'codigo'))), pg_temp.g(1),
  '1. Caro entra con el mismo enlace (sirve para varios; mayúsculas no importan)');
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT agregar_persona(pg_temp.g(1), 'Dani', '92000000-0000-0000-0000-0000000000d1')$$,
  '1. Ana agrega a Dani, sin app');
SELECT is((SELECT string_agg(nombre || ':' || (usuario_id IS NOT NULL), ' ' ORDER BY created_at, nombre)
             FROM grupo_miembros WHERE grupo_id = pg_temp.g(1)),
  'Ana:true Beto:true Caro:true Dani:false', '1. los cuatro miembros, con el nombre de su perfil');
SELECT lives_ok($$SELECT crear_gasto('93000000-0000-0000-0000-000000000001', pg_temp.g(1), 'Hotel', 90, '2026-08-01',
    'igual', jsonb_build_array(pg_temp.p('Ana', 90), pg_temp.p('Beto'), pg_temp.p('Caro')))$$, '1. Ana anota el hotel');
SELECT is(pg_temp.partes('93000000-0000-0000-0000-000000000001'),
  'Ana:30.00:activa Beto:30.00:activa Caro:30.00:activa', '1. $30 cada uno');
SELECT is(pg_temp.pares(), 'Beto>Ana:30.00 Caro>Ana:30.00', '1. Beto y Caro le deben $30 a Ana');
SELECT is(pg_temp.neto('Ana'), 60.00, '1. neto de Ana: +60');
SELECT is((SELECT count(*)::int FROM deudas), 0, '1. nada pasa a la libreta de Ana (queda en el grupo)');
SELECT is(pg_temp.sin_ver('gasto_nuevo'), 0, '1. Ana no se avisa a sí misma');
SELECT pg_temp.como('B');
SELECT is((SELECT row(datos ->> 'titulo', (datos ->> 'mi_parte')::numeric, datos ->> 'quien', datos ->> 'grupo')::text
             FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'gasto_nuevo'),
  '(Hotel,30.00,Ana,"Viaje a la costa")', '1. Beto recibe gasto_nuevo con su parte');
SELECT is(pg_temp.neto('Beto'), -30.00, '1. Beto ve su neto: −30');
SELECT pg_temp.como('C');
SELECT is(pg_temp.sin_ver('gasto_nuevo'), 1, '1. Caro también');

-- ====================================================================================
-- 2. Otro grupo con Ana y Beto (la casa): saldos independientes.
-- ====================================================================================
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT crear_grupo(pg_temp.g(2), 'Casa', 'casa')$$, '2. Ana crea el grupo de la casa');
INSERT INTO t VALUES ('codigo2', invitar_a_grupo(pg_temp.g(2)));
SELECT pg_temp.como('B');
SELECT is(unirse_a_grupo((SELECT valor FROM t WHERE clave = 'codigo2')), pg_temp.g(2), '2. Beto entra');
SELECT lives_ok($$SELECT crear_gasto('93000000-0000-0000-0000-000000000021', pg_temp.g(2), 'Luz', 20, '2026-08-01',
    'igual', jsonb_build_array(pg_temp.p('Ana', 0, NULL, '{}', 2), pg_temp.p('Beto', 20, NULL, '{}', 2)))$$,
  '2. Beto paga la luz entre los dos');
SELECT is(pg_temp.pares(2), 'Ana>Beto:10.00', '2. en la casa, Ana le debe $10 a Beto');
SELECT is(pg_temp.pares(1), 'Beto>Ana:30.00 Caro>Ana:30.00', '2. el viaje no cambia');

-- ====================================================================================
-- 3. Caro rechaza su parte del hotel → rechazada solo para ella; se reparte de nuevo
--    entre Ana y Beto ($45) y queda en revisión. Pares: Beto>Ana 45.
-- ====================================================================================
SELECT pg_temp.como('C');
SELECT lives_ok($$SELECT rechazar_parte('93000000-0000-0000-0000-000000000001', 'No fui al hotel')$$,
  '3. Caro rechaza su parte');
SELECT is(pg_temp.partes('93000000-0000-0000-0000-000000000001'),
  'Ana:45.00:activa Beto:45.00:activa Caro:30.00:rechazada', '3. $45 para Ana y Beto; la de Caro queda como era, rechazada');
SELECT is(pg_temp.estado('93000000-0000-0000-0000-000000000001'), 'en_revision', '3. el gasto queda en revisión');
SELECT is(pg_temp.pares(), 'Beto>Ana:45.00', '3. Beto le debe $45 a Ana; Caro, nada');
SELECT is(pg_temp.neto('Caro'), 0.00, '3. el neto de Caro por ese gasto es 0');
SELECT is((rechazar_parte('93000000-0000-0000-0000-000000000001') ->> 'repetido')::boolean, true,
  '3. rechazarlo otra vez no hace nada');
SELECT pg_temp.como('B');
SELECT is((SELECT row((datos ->> 'parte_antes')::numeric, (datos ->> 'parte_nueva')::numeric, datos ->> 'motivo',
                      datos ->> 'quien')::text
             FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'gasto_en_revision'),
  '(30.00,45.00,"No fui al hotel",Caro)', '3. a Beto le llega: tu parte pasó de $30 a $45, con el motivo');
SELECT lives_ok($$SELECT marcar_vistos()$$, '3. Beto lo ve');
SELECT is(pg_temp.estado('93000000-0000-0000-0000-000000000001'), 'en_revision', '3. sigue en revisión: falta Ana');
SELECT pg_temp.como('A');
SELECT is(pg_temp.sin_ver('gasto_en_revision'), 1, '3. Ana también tiene el aviso');
SELECT lives_ok($$SELECT marcar_vistos()$$, '3. Ana lo ve');
SELECT is(pg_temp.estado('93000000-0000-0000-0000-000000000001'), 'activo', '3. todos lo vieron: vuelve a activo');

-- ====================================================================================
-- 4. Si rechaza quien pagó, el gasto se rechaza entero (27). Lo mismo si después de los
--    rechazos solo queda él. Pares: sin cambios (Beto>Ana 45).
-- ====================================================================================
SELECT lives_ok($$SELECT crear_gasto('93000000-0000-0000-0000-000000000002', pg_temp.g(1), 'Nafta', 60, '2026-08-02',
    'igual', jsonb_build_array(pg_temp.p('Ana', 60), pg_temp.p('Beto'), pg_temp.p('Dani')))$$, '4. Ana anota la nafta');
SELECT is(pg_temp.pares(), 'Beto>Ana:65.00 Dani>Ana:20.00', '4. (antes de rechazar: Beto 45 + 20, Dani 20)');
SELECT lives_ok($$SELECT rechazar_parte('93000000-0000-0000-0000-000000000002', 'La pagó otro')$$,
  '4. Ana, que pagó, rechaza');
SELECT is(pg_temp.estado('93000000-0000-0000-0000-000000000002'), 'rechazado', '4. el gasto queda rechazado para todos');
SELECT is(pg_temp.pares(), 'Beto>Ana:45.00', '4. y no cuenta');
SELECT pg_temp.como('B');
SELECT is(pg_temp.aviso('gasto_rechazado', '93000000-0000-0000-0000-000000000002') ->> 'motivo', 'La pagó otro',
  '4. a Beto le llega gasto_rechazado con el motivo');
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT crear_gasto('93000000-0000-0000-0000-000000000003', pg_temp.g(1), 'Peaje', 40, '2026-08-02',
    'igual', jsonb_build_array(pg_temp.p('Ana', 40), pg_temp.p('Beto')))$$, '4. Ana anota el peaje con Beto');
SELECT pg_temp.como('B');
SELECT lives_ok($$SELECT rechazar_parte('93000000-0000-0000-0000-000000000003')$$, '4. Beto rechaza');
SELECT is(pg_temp.estado('93000000-0000-0000-0000-000000000003'), 'rechazado', '4. solo queda quien pagó: rechazado');
SELECT is(pg_temp.pares(), 'Beto>Ana:45.00', '4. sin cambios');

-- ====================================================================================
-- 5. Modo 'montos': Beto paga $50 (Ana 20, Beto 10, Caro 20). Caro rechaza → lo absorbe
--    Beto (26) y queda en revisión.
--    Pares: antes Ana/Beto 45 − 20 = Beto>Ana 25 y Caro>Beto 20; después Caro nada.
-- ====================================================================================
SELECT lives_ok($$SELECT crear_gasto('93000000-0000-0000-0000-000000000004', pg_temp.g(1), 'Cena', 50, '2026-08-03',
    'montos', jsonb_build_array(pg_temp.p('Ana', 0, 20), pg_temp.p('Beto', 50, 10), pg_temp.p('Caro', 0, 20)))$$,
  '5. Beto anota la cena por montos');
SELECT is(pg_temp.pares(), 'Beto>Ana:25.00 Caro>Beto:20.00', '5. Beto>Ana 25 y Caro>Beto 20');
SELECT pg_temp.como('C');
SELECT lives_ok($$SELECT rechazar_parte('93000000-0000-0000-0000-000000000004', 'Comí en otro lado')$$,
  '5. Caro rechaza');
SELECT is(pg_temp.partes('93000000-0000-0000-0000-000000000004'),
  'Ana:20.00:activa Beto:30.00:activa Caro:20.00:rechazada', '5. lo de Caro lo absorbe Beto (decisión 26)');
SELECT is(pg_temp.estado('93000000-0000-0000-0000-000000000004'), 'en_revision', '5. en revisión');
SELECT is(pg_temp.pares(), 'Beto>Ana:25.00', '5. Caro ya no debe nada');
SELECT pg_temp.como('A');
SELECT is((pg_temp.aviso('gasto_en_revision', '93000000-0000-0000-0000-000000000004') ->> 'parte_nueva')::numeric, 20.00,
  '5. a Ana le llega el aviso: su parte no cambió');

-- ====================================================================================
-- 6. Pagos (28): si lo anota quien recibe, cuenta; si lo anota quien entrega, se confirma.
--    Beto>Ana 25 → Ana anota que Beto le pagó $30 → Ana>Beto 5 → Beto anota que le pagó
--    $10 (por confirmar, no cuenta) → Ana confirma → Ana>Beto 15 → Beto anota $5 más →
--    Ana "no lo recibí" → sigue Ana>Beto 15.
-- ====================================================================================
SELECT is((registrar_pago_grupo('94000000-0000-0000-0000-000000000001', pg_temp.g(1), pg_temp.m('Beto'),
    pg_temp.m('Ana'), 30, '2026-08-04') ->> 'estado'), 'confirmado', '6. Ana (recibe) anota $30 de Beto: cuenta');
SELECT is(pg_temp.pares(), 'Ana>Beto:5.00', '6. ahora Ana le debe $5 a Beto');
SELECT pg_temp.como('B');
SELECT is(pg_temp.sin_ver('pago_grupo_nuevo'), 1, '6. a Beto le llega que Ana anotó su pago');
SELECT is((registrar_pago_grupo('94000000-0000-0000-0000-000000000002', pg_temp.g(1), pg_temp.m('Beto'),
    pg_temp.m('Ana'), 10, '2026-08-04', 'Transferencia') ->> 'estado'), 'por_confirmar',
  '6. Beto (entrega) anota $10: por confirmar');
SELECT is(pg_temp.pares(), 'Ana>Beto:5.00', '6. y todavía no cuenta');
SELECT pg_temp.como('A');
SELECT is((SELECT jsonb_array_length(estado_grupo(pg_temp.g(1)) -> 'por_confirmar')), 1, '6. Ana lo tiene por confirmar');
SELECT is(pg_temp.sin_ver('pago_grupo_por_confirmar'), 1, '6. con su aviso');
SELECT pg_temp.como('C');
SELECT throws_ok($$SELECT confirmar_pago_grupo('94000000-0000-0000-0000-000000000002')$$, '42501', NULL,
  '6. Caro no lo puede confirmar (no lo recibió)');
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT confirmar_pago_grupo('94000000-0000-0000-0000-000000000002')$$, '6. Ana confirma');
SELECT is(pg_temp.pares(), 'Ana>Beto:15.00', '6. ahora cuenta: Ana>Beto 15');
SELECT is(pg_temp.sin_ver('pago_grupo_por_confirmar'), 0, '6. el aviso de Ana queda visto');
SELECT is((confirmar_pago_grupo('94000000-0000-0000-0000-000000000002') ->> 'repetido')::boolean, true,
  '6. confirmarlo otra vez no hace nada');
SELECT pg_temp.como('B');
SELECT is(pg_temp.sin_ver('pago_grupo_confirmado'), 1, '6. a Beto le llega la confirmación');
SELECT lives_ok($$SELECT registrar_pago_grupo('94000000-0000-0000-0000-000000000003', pg_temp.g(1), pg_temp.m('Beto'),
    pg_temp.m('Ana'), 5, '2026-08-05')$$, '6. Beto anota $5 más');
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT rechazar_pago_grupo('94000000-0000-0000-0000-000000000003', 'No me llegó')$$,
  '6. Ana: no lo recibí');
SELECT is(pg_temp.pares(), 'Ana>Beto:15.00', '6. no cuenta');
SELECT throws_ok($$SELECT rechazar_pago_grupo('94000000-0000-0000-0000-000000000002')$$, '22023', NULL,
  '6. lo ya confirmado no se rechaza');
SELECT pg_temp.como('B');
SELECT is((SELECT datos ->> 'motivo' FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'pago_grupo_rechazado'),
  'No me llegó', '6. a Beto le llega el rechazo con el motivo');
SELECT throws_ok(format('SELECT registrar_pago_grupo(%L, %L, %L, %L, 5, %L)', '94000000-0000-0000-0000-0000000000f1',
    pg_temp.g(1), pg_temp.m('Caro'), pg_temp.m('Ana'), '2026-08-05'), '42501', NULL,
  '6. Beto no anota pagos entre Caro y Ana');

-- ====================================================================================
-- 7. Dani (sin app): Ana paga $40 entre Ana y Dani → Dani>Ana 20. Ana anota que Dani le
--    pagó $20 → cuenta de una vez. Ana le da $5 a Dani → también (quien recibe no tiene
--    app). Dani>Ana 5.
-- ====================================================================================
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT crear_gasto('93000000-0000-0000-0000-000000000005', pg_temp.g(1), 'Carpa', 40, '2026-08-05',
    'igual', jsonb_build_array(pg_temp.p('Ana', 40), pg_temp.p('Dani')))$$, '7. Ana anota la carpa con Dani');
SELECT is((registrar_pago_grupo('94000000-0000-0000-0000-000000000004', pg_temp.g(1), pg_temp.m('Dani'),
    pg_temp.m('Ana'), 20, '2026-08-05') ->> 'estado'), 'confirmado', '7. Dani le paga a Ana: cuenta');
SELECT is((registrar_pago_grupo('94000000-0000-0000-0000-000000000005', pg_temp.g(1), pg_temp.m('Ana'),
    pg_temp.m('Dani'), 5, '2026-08-05') ->> 'estado'), 'confirmado', '7. Ana le da $5 a Dani: cuenta (Dani no tiene app)');
SELECT is(pg_temp.pares(), 'Ana>Beto:15.00 Dani>Ana:5.00', '7. Dani>Ana 5');
SELECT pg_temp.como('C');
SELECT throws_ok(format('SELECT registrar_pago_grupo(%L, %L, %L, %L, 1, %L)', '94000000-0000-0000-0000-0000000000f2',
    pg_temp.g(1), pg_temp.m('Dani'), pg_temp.m('Ana'), '2026-08-05'), '42501', NULL,
  '7. Caro no anota lo que Dani le paga a Ana (Ana tiene app)');
SELECT is((SELECT count(*)::int FROM gastos WHERE id = '93000000-0000-0000-0000-000000000005'), 1,
  '7. Caro ve la carpa aunque no esté en ese par (§4.8)');

-- ====================================================================================
-- 8. Editar: solo quien lo anotó o quien lo pagó. Ana vuelve a incluir a Caro en el hotel
--    → $30 cada uno, activo. Pares: Ana/Beto = 30 − 20 − 40 = Ana>Beto 30; Caro>Ana 30.
-- ====================================================================================
SELECT throws_ok(format('SELECT editar_gasto(%L, %L, 90, %L, %L, %L)', '93000000-0000-0000-0000-000000000001',
    'Hotel', '2026-08-01', 'igual', jsonb_build_array(pg_temp.p('Ana', 90), pg_temp.p('Beto'), pg_temp.p('Caro'))),
  '42501', NULL, '8. Caro no edita el hotel (ni lo anotó ni lo pagó)');
SELECT throws_ok($$SELECT borrar_gasto('93000000-0000-0000-0000-000000000001')$$, '42501', NULL, '8. ni lo borra');
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT editar_gasto('93000000-0000-0000-0000-000000000001', 'Hotel', 90, '2026-08-01', 'igual',
    jsonb_build_array(pg_temp.p('Ana', 90), pg_temp.p('Beto'), pg_temp.p('Caro', 0, NULL, '{"reincluir": true}')))$$,
  '8. Ana vuelve a incluir a Caro');
SELECT is(pg_temp.partes('93000000-0000-0000-0000-000000000001'),
  'Ana:30.00:activa Beto:30.00:activa Caro:30.00:activa', '8. $30 cada uno otra vez');
SELECT is(pg_temp.pares(), 'Ana>Beto:30.00 Caro>Ana:30.00 Dani>Ana:5.00', '8. los pares cuadran');
SELECT throws_ok(format('SELECT editar_gasto(%L, %L, 50, %L, %L, %L)', '93000000-0000-0000-0000-000000000004',
    'Cena', '2026-08-03', 'montos',
    jsonb_build_array(pg_temp.p('Ana', 0, 20), pg_temp.p('Beto', 50, 10), pg_temp.p('Caro', 0, 20))),
  '42501', NULL, '8. Ana no anotó ni pagó la cena: no la edita');
SELECT pg_temp.como('B');
SELECT is((SELECT count(*)::int FROM avisos WHERE usuario_id = auth.uid() AND tipo = 'gasto_editado'), 1,
  '8. a Beto le llega que Ana editó el hotel');
SELECT lives_ok($$SELECT editar_gasto('93000000-0000-0000-0000-000000000004', 'Cena', 50, '2026-08-03', 'montos',
    jsonb_build_array(pg_temp.p('Ana', 0, 20), pg_temp.p('Beto', 50, 10), pg_temp.p('Caro', 0, 20)))$$,
  '8. Beto (anotó y pagó la cena) sí la edita');
SELECT is(pg_temp.partes('93000000-0000-0000-0000-000000000004'),
  'Ana:20.00:activa Beto:30.00:activa Caro:20.00:rechazada', '8. editar sin reincluir conserva el rechazo de Caro');

-- ====================================================================================
-- 9. Salir: solo con saldo 0 (30). Beto tiene +30: no puede. Ana anota que Caro le pagó
--    $30 → Caro queda en 0 → sale y deja de ver el grupo.
-- ====================================================================================
SELECT pg_temp.como('B');
SELECT is(pg_temp.neto('Beto'), 30.00, '9. Beto tiene +30');
SELECT throws_ok($$SELECT salir_de_grupo(pg_temp.g(1))$$, '22023', NULL, '9. con saldo no se sale');
SELECT pg_temp.como('A');
SELECT lives_ok($$SELECT registrar_pago_grupo('94000000-0000-0000-0000-000000000006', pg_temp.g(1), pg_temp.m('Caro'),
    pg_temp.m('Ana'), 30, '2026-08-06')$$, '9. Caro le paga a Ana');
INSERT INTO t VALUES ('pares_antes', pg_temp.pares());
SELECT pg_temp.como('C');
SELECT is(pg_temp.neto('Caro'), 0.00, '9. Caro queda en 0');
SELECT lives_ok($$SELECT salir_de_grupo(pg_temp.g(1))$$, '9. Caro sale');
SELECT is((SELECT count(*)::int FROM grupos), 0, '9. y deja de ver el grupo');
SELECT is((SELECT count(*)::int FROM gastos), 0, '9. ni sus gastos');
SELECT throws_ok($$SELECT estado_grupo(pg_temp.g(1))$$, '42501', NULL, '9. ni sus saldos');
SELECT is((salir_de_grupo(pg_temp.g(1)) ->> 'repetido')::boolean, true, '9. salir otra vez no hace nada');
SELECT pg_temp.como('A');
SELECT is(pg_temp.pares(), (SELECT valor FROM t WHERE clave = 'pares_antes'), '9. los saldos de los demás no cambian');
SELECT is((SELECT salio_at IS NOT NULL FROM grupo_miembros WHERE nombre = 'Caro'), true,
  '9. Caro sigue en la lista, como que salió');
SELECT throws_ok(format('SELECT crear_gasto(%L, %L, %L, 10, %L, %L, %L)', '93000000-0000-0000-0000-0000000000f3',
    pg_temp.g(1), 'Nada', '2026-08-06', 'igual', jsonb_build_array(pg_temp.p('Ana', 10), pg_temp.p('Caro'))),
  '22023', NULL, '9. a quien salió no se lo mete en gastos nuevos');

-- ====================================================================================
-- 10. RLS: quien no es miembro no ve nada; nadie escribe directo.
-- ====================================================================================
SELECT pg_temp.como('E');
SELECT is((SELECT count(*)::int FROM grupos), 0, '10. Eva no ve grupos');
SELECT is((SELECT count(*)::int FROM grupo_miembros), 0, '10. ni miembros');
SELECT is((SELECT count(*)::int FROM gastos), 0, '10. ni gastos');
SELECT is((SELECT count(*)::int FROM gasto_participantes), 0, '10. ni participantes');
SELECT is((SELECT count(*)::int FROM grupo_pagos), 0, '10. ni pagos');
SELECT is((SELECT count(*)::int FROM borrados_gastos), 0, '10. ni lápidas');
SELECT is((SELECT count(*)::int FROM avisos), 0, '10. ni avisos');
SELECT throws_ok($$SELECT estado_grupo(pg_temp.g(1))$$, '42501', NULL, '10. estado_grupo: 42501');
SELECT throws_ok($$SELECT agregar_persona(pg_temp.g(1), 'Intrusa')$$, '42501', NULL, '10. ni agrega gente');
SELECT throws_ok($$SELECT invitar_a_grupo(pg_temp.g(1))$$, '42501', NULL, '10. ni saca enlaces');
SELECT throws_ok($$SELECT rechazar_parte('93000000-0000-0000-0000-000000000001')$$, '42501', NULL, '10. ni rechaza');
SELECT throws_ok($$SELECT crear_grupo(pg_temp.g(1), 'Robado')$$, '42501', NULL, '10. ni reusa el id de un grupo ajeno');
SELECT throws_ok($$INSERT INTO grupos (id, nombre) VALUES ('91000000-0000-0000-0000-0000000000ff', 'X')$$,
  '42501', NULL, '10. nadie inserta directo en grupos');
SELECT throws_ok(format('INSERT INTO grupo_miembros (grupo_id, usuario_id, nombre) VALUES (%L, auth.uid(), %L)',
    pg_temp.g(1), 'Eva'), '42501', NULL, '10. ni se agrega sola como miembro');
SELECT pg_temp.como('A');
SELECT throws_ok($$UPDATE grupos SET nombre = 'X'$$, '42501', NULL, '10. ni un miembro cambia el grupo directo');
SELECT throws_ok($$UPDATE grupo_pagos SET estado = 'confirmado'$$, '42501', NULL, '10. ni confirma un pago directo');
SELECT throws_ok($$DELETE FROM grupo_miembros$$, '42501', NULL, '10. ni borra miembros');
SELECT throws_ok($$UPDATE gasto_participantes SET parte = 0$$, '42501', NULL, '10. ni cambia partes');
SELECT throws_ok($$INSERT INTO grupo_invitaciones (codigo, grupo_id) VALUES ('AAAAAAAAAA', pg_temp.g(1))$$,
  '42501', NULL, '10. ni se fabrica un código');

-- ====================================================================================
-- 11. Unirse con un código vencido, reemplazado o que no existe → NULL, siempre igual, y
--     cuenta como intento fallido (7.3).
-- ====================================================================================
INSERT INTO t VALUES ('codigo3', invitar_a_grupo(pg_temp.g(1)));
SELECT pg_temp.como('E');
SELECT is(unirse_a_grupo((SELECT valor FROM t WHERE clave = 'codigo')), NULL,
  '11. el enlace viejo de Ana (reemplazado por otro) ya no sirve');
SELECT is(unirse_a_grupo('ZZZZZZZZZZ'), NULL, '11. uno que no existe, igual');
RESET ROLE;
UPDATE grupo_invitaciones SET expira = now() - interval '1 second' WHERE codigo = (SELECT valor FROM t WHERE clave = 'codigo3');
SET LOCAL ROLE authenticated;
SELECT is(unirse_a_grupo((SELECT valor FROM t WHERE clave = 'codigo3')), NULL, '11. uno vencido, igual');
RESET ROLE;
SELECT is((SELECT count(*)::int FROM intentos_canje WHERE usuario = 'e0000000-0000-0000-0000-000000000000'), 3,
  '11. los tres cuentan para el límite de 10 por hora');
INSERT INTO intentos_canje (usuario) SELECT 'e0000000-0000-0000-0000-000000000000' FROM generate_series(1, 7);
SET LOCAL ROLE authenticated;
SELECT throws_ok($$SELECT unirse_a_grupo('ZZZZZZZZZZ')$$, 'PT429', NULL, '11. al décimo, 429');
SELECT is((SELECT count(*)::int FROM grupos), 0, '11. Eva sigue sin ver nada');

-- ====================================================================================
-- 12. Idempotencia: el sync reintenta todo sin duplicar nada.
-- ====================================================================================
SELECT pg_temp.como('A');
SELECT is((crear_grupo(pg_temp.g(1), 'Viaje a la costa') ->> 'repetido')::boolean, true, '12. crear_grupo');
SELECT is((agregar_persona(pg_temp.g(1), 'Dani', '92000000-0000-0000-0000-0000000000d1') ->> 'repetido')::boolean, true,
  '12. agregar_persona');
SELECT is((crear_gasto('93000000-0000-0000-0000-000000000005', pg_temp.g(1), 'Carpa', 40, '2026-08-05', 'igual',
    jsonb_build_array(pg_temp.p('Ana', 40), pg_temp.p('Dani'))) ->> 'repetido')::boolean, true, '12. crear_gasto');
SELECT is((registrar_pago_grupo('94000000-0000-0000-0000-000000000004', pg_temp.g(1), pg_temp.m('Dani'),
    pg_temp.m('Ana'), 20, '2026-08-05') ->> 'repetido')::boolean, true, '12. registrar_pago_grupo');
SELECT is((rechazar_pago_grupo('94000000-0000-0000-0000-000000000003') ->> 'repetido')::boolean, true,
  '12. rechazar_pago_grupo');
SELECT is((SELECT count(*)::int FROM grupo_miembros WHERE grupo_id = pg_temp.g(1)), 4, '12. siguen 4 miembros');
SELECT is((SELECT count(*)::int FROM grupo_pagos WHERE grupo_id = pg_temp.g(1)), 6, '12. y 6 pagos');
SELECT pg_temp.como('B');
SELECT is(unirse_a_grupo((SELECT valor FROM t WHERE clave = 'codigo2')), pg_temp.g(2), '12. unirse siendo miembro: el mismo grupo');
SELECT is((SELECT count(*)::int FROM grupo_miembros WHERE grupo_id = pg_temp.g(2)), 2, '12. sin otra fila');

-- ====================================================================================
-- 13. Borrar: un gasto (quien lo pagó) y un pago (quien lo anotó); las lápidas las ven
--     todos los miembros. Archivar.
-- ====================================================================================
SELECT lives_ok($$SELECT borrar_gasto('93000000-0000-0000-0000-000000000004')$$, '13. Beto (pagó) borra la cena');
SELECT is(pg_temp.pares(), 'Ana>Beto:10.00 Dani>Ana:5.00', '13. Ana/Beto: 30 − 40 = Ana>Beto 10');
SELECT throws_ok($$SELECT borrar_pago_grupo('94000000-0000-0000-0000-000000000004')$$, '42501', NULL,
  '13. Beto no borra un pago que anotó Ana');
SELECT lives_ok($$SELECT borrar_pago_grupo('94000000-0000-0000-0000-000000000002')$$, '13. Beto borra su pago de $10');
SELECT is(pg_temp.pares(), 'Dani>Ana:5.00', '13. Ana/Beto en 0');
SELECT is((borrar_pago_grupo('94000000-0000-0000-0000-000000000002') ->> 'repetido')::boolean, true,
  '13. borrarlo otra vez no hace nada');
SELECT pg_temp.como('A');
SELECT is((SELECT string_agg(tabla, ' ' ORDER BY tabla) FROM borrados_gastos WHERE grupo_id = pg_temp.g(1)),
  'gastos grupo_pagos', '13. Ana ve las dos lápidas');
SELECT is((SELECT count(*)::int FROM avisos WHERE usuario_id = auth.uid() AND tipo IN ('gasto_borrado', 'pago_grupo_borrado')), 2,
  '13. y los dos avisos');
SELECT lives_ok($$SELECT archivar_grupo(pg_temp.g(1))$$, '13. Ana archiva el viaje');
SELECT throws_ok(format('SELECT crear_gasto(%L, %L, %L, 10, %L, %L, %L)', '93000000-0000-0000-0000-0000000000f4',
    pg_temp.g(1), 'Nada', '2026-08-06', 'igual', jsonb_build_array(pg_temp.p('Ana', 10), pg_temp.p('Dani'))),
  '22023', NULL, '13. en un grupo archivado no se anotan gastos');
SELECT lives_ok($$SELECT archivar_grupo(pg_temp.g(1), false)$$, '13. lo desarchiva');
SELECT is((SELECT archivado FROM grupos WHERE id = pg_temp.g(1)), false, '13. activo otra vez');

-- ====================================================================================
-- 14. Lo que baja la app (cambios_gastos) y exportar mis datos.
-- ====================================================================================
SELECT is((SELECT jsonb_array_length(cambios_gastos() -> 'grupos')), 2, '14. Ana baja sus dos grupos');
SELECT is((SELECT jsonb_array_length(cambios_gastos() -> 'miembros')), 6, '14. con sus miembros (4 + 2)');
SELECT is((SELECT jsonb_array_length(cambios_gastos() -> 'gastos')), 5,
  '14. los gastos de los dos grupos (hotel, nafta, peaje, carpa y la luz)');
SELECT is((SELECT jsonb_array_length(cambios_gastos() -> 'pagos')), 5, '14. y sus pagos');
SELECT is((SELECT jsonb_array_length(cambios_gastos(now() + interval '1 minute') -> 'gastos')), 0,
  '14. desde después, ningún gasto');
SELECT is((SELECT jsonb_array_length(cambios_gastos(now() + interval '1 minute') -> 'grupos')), 2,
  '14. pero los grupos bajan siempre (así se sabe de cuáles salí)');
SELECT is((SELECT jsonb_array_length(exportar_mis_datos() -> 'grupo_pagos')), 5, '14. exportar trae los pagos del grupo');
SELECT pg_temp.como('C');
SELECT is((SELECT jsonb_array_length(cambios_gastos() -> 'grupos')), 0, '14. Caro, que salió, ya no baja el viaje');
-- Caro vuelve con un enlace nuevo: baja todo lo del grupo aunque sea viejo.
SELECT pg_temp.como('A');
INSERT INTO t VALUES ('codigo4', invitar_a_grupo(pg_temp.g(1)));
SELECT pg_temp.como('C');
SELECT is(unirse_a_grupo((SELECT valor FROM t WHERE clave = 'codigo4')), pg_temp.g(1), '14. Caro vuelve');
-- En una transacción todo tiene el mismo now(): se envejece lo demás a mano (sin triggers).
RESET ROLE;
SET LOCAL session_replication_role = replica;
UPDATE gastos SET updated_at = now() - interval '1 day';
UPDATE grupos SET updated_at = now() - interval '1 day';
UPDATE grupo_pagos SET updated_at = now() - interval '1 day';
UPDATE grupo_miembros SET updated_at = now() - interval '1 day' WHERE nombre <> 'Caro';
SET LOCAL session_replication_role = origin;
SET LOCAL ROLE authenticated;
SELECT is((SELECT jsonb_array_length(cambios_gastos(now() - interval '1 hour') -> 'gastos')), 4,
  '14. y el pull le trae los gastos viejos del viaje (entró después del cursor)');
SELECT is((SELECT jsonb_array_length(cambios_gastos(now() - interval '1 hour') -> 'miembros')), 4, '14. y sus miembros');
SELECT pg_temp.como('A');
SELECT is((SELECT jsonb_array_length(cambios_gastos(now() - interval '1 hour') -> 'gastos')), 0,
  '14. (control: a Ana, con el mismo cursor, no le baja nada)');
SELECT pg_temp.como('C');
SELECT is(pg_temp.neto('Caro'), 0.00, '14. con su saldo en 0, como lo dejó');

-- ====================================================================================
-- 15. Borrar la cuenta de Beto (9.7): su fila queda como persona sin app, con su nombre,
--     y los saldos de los demás no cambian.
-- ====================================================================================
SELECT pg_temp.como('A');
DELETE FROM t WHERE clave = 'pares_antes';
INSERT INTO t VALUES ('pares_antes', pg_temp.pares(2));
RESET ROLE;
DELETE FROM auth.users WHERE id = 'b0000000-0000-0000-0000-000000000000';
SET LOCAL ROLE authenticated;
SELECT pg_temp.como('A');
SELECT is((SELECT row(nombre, usuario_id IS NULL)::text FROM grupo_miembros WHERE grupo_id = pg_temp.g(2) AND nombre = 'Beto'),
  '(Beto,t)', '15. Beto queda en la casa como persona sin app');
SELECT is(pg_temp.pares(2), (SELECT valor FROM t WHERE clave = 'pares_antes'), '15. Ana le sigue debiendo lo mismo');
SELECT is((SELECT count(*)::int FROM gastos WHERE id = '93000000-0000-0000-0000-000000000021'), 1,
  '15. la luz que anotó Beto sigue en el grupo');
SELECT is((registrar_pago_grupo('94000000-0000-0000-0000-000000000021', pg_temp.g(2), pg_temp.m('Ana', 2),
    pg_temp.m('Beto', 2), 10, '2026-08-07') ->> 'estado'), 'confirmado', '15. Ana le paga: cuenta (ya no tiene app)');
SELECT is(pg_temp.pares(2), '', '15. la casa queda en 0');

SELECT * FROM finish();
ROLLBACK;
