-- Fase 9 (deudas/PLAN_MULTIUSUARIO.md §4.8): dos arreglos que aparecieron con la prueba de
-- punta a punta (scripts/v2/probar_grupos.py), al limpiar el grupo de prueba.
--
--   1. Un grupo no se podía borrar: `DELETE FROM grupos` fallaba con 23503. Las cascadas
--      grupos → grupo_miembros y grupos → gastos → gasto_participantes corren una detrás de
--      otra, y la comprobación de gasto_participantes → grupo_miembros (NO ACTION) se hacía
--      apenas se iban los miembros, cuando las partes todavía estaban. Lo mismo con las dos
--      puntas de grupo_pagos. Ahora esas FK se comprueban al final de la transacción: el
--      borrado entero pasa, y borrar un miembro que un gasto o un pago nombra sigue
--      fallando (ningún RPC lo hace: salir solo pone `salio_at`).
--   2. Al borrarse la última cuenta con app de un grupo, el grupo quedaba sin nadie que
--      pudiera verlo (solo personas sin app, 9.7), para siempre. Ahora se borra con sus
--      gastos, pagos y lápidas: son datos que ya nadie puede leer (decisión 34 de §3.3,
--      para que el dueño la revise). Un grupo con alguna cuenta viva no se toca, aunque
--      esa persona haya salido.
--
-- `_perfil_sin_gastos` es copia exacta de su versión de 20260924160000 más las líneas
-- marcadas «v2 fase 9, grupos sin nadie».

ALTER TABLE public.gasto_participantes
    ALTER CONSTRAINT gasto_participantes_miembro_fkey DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE public.grupo_pagos
    ALTER CONSTRAINT grupo_pagos_de_miembro_grupo_id_fkey DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE public.grupo_pagos
    ALTER CONSTRAINT grupo_pagos_para_miembro_grupo_id_fkey DEFERRABLE INITIALLY DEFERRED;

-- Al borrarse una cuenta, sus gastos sueltos quedaron sin dueño (SET NULL): se van. Corre
-- después de las cascadas (los triggers de las FK se llaman "RI_…" y van antes), cuando
-- sus deudas ya se fueron con sus contactos.
CREATE OR REPLACE FUNCTION public._perfil_sin_gastos() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    DELETE FROM gastos WHERE grupo_id IS NULL AND creado_por IS NULL;
    DELETE FROM borrados_gastos WHERE owner_id = OLD.id;
    -- «v2 fase 9, grupos sin nadie»: el FK ya pasó a persona sin app la fila de miembro de
    -- esta cuenta; el grupo en el que no queda ninguna cuenta se va, con sus lápidas.
    DELETE FROM grupos g
     WHERE NOT EXISTS (SELECT 1 FROM grupo_miembros m WHERE m.grupo_id = g.id AND m.usuario_id IS NOT NULL);
    DELETE FROM borrados_gastos b
     WHERE b.grupo_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM grupos g WHERE g.id = b.grupo_id);
    -- «fin v2 fase 9, grupos sin nadie»
    RETURN NULL;
END $$;
