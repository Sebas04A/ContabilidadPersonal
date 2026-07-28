-- Identidad del cruce e idempotencia del sync.
--
-- Hasta ahora un cruce eran dos pagos virtuales sueltos que solo se podían reconocer
-- por heurística (misma fecha ±1s, y una ventana de 2s en get_historial). Con `cruce_id`
-- los dos lados quedan atados de verdad.
--
-- `idem_key` es la clave que genera el cliente al crear la intención de pago: permite
-- reintentar el sync tantas veces como haga falta sin duplicar pagos ni cruces.

ALTER TABLE pagos ADD COLUMN IF NOT EXISTS cruce_id UUID;
ALTER TABLE pagos ADD COLUMN IF NOT EXISTS idem_key UUID;

COMMENT ON COLUMN pagos.cruce_id IS
    'Los dos pagos virtuales de un mismo cruce comparten este id. NULL si no es un cruce.';
COMMENT ON COLUMN pagos.idem_key IS
    'Clave de idempotencia del cliente: reintentar el mismo pago no lo duplica.';

CREATE UNIQUE INDEX IF NOT EXISTS idx_pagos_idem_key
    ON pagos(idem_key) WHERE idem_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pagos_cruce ON pagos(cruce_id) WHERE cruce_id IS NOT NULL;

-- ── Backfill de los cruces históricos ───────────────────────────────────────
-- Los dos lados de un cruce se crearon con el mismo deudor, el mismo monto y la misma
-- fecha (`fecha_pago` es DATE, así que el desempate de −1 segundo no sobrevivió). Se
-- emparejan de dos en dos por `created_at` dentro de cada grupo.
-- Solo se marcan los grupos que forman parejas completas. Si un grupo quedó impar es que
-- ese "cruce" nunca estuvo bien formado (un lado sin el otro, o montos que no cuadran):
-- se deja en NULL a propósito, para que se vea, en vez de inventarle una pareja.
WITH numerados AS (
    SELECT id,
           row_number() OVER (PARTITION BY deudor_id, fecha_pago, monto_total
                              ORDER BY created_at, id) - 1 AS pos,
           count(*)     OVER (PARTITION BY deudor_id, fecha_pago, monto_total) AS en_grupo,
           deudor_id, fecha_pago, monto_total
    FROM pagos
    WHERE es_compensacion AND cruce_id IS NULL
), asignado AS (
    -- Determinístico a propósito: si el backfill se corre dos veces, da el mismo id.
    SELECT id,
           md5(deudor_id::text || '|' || fecha_pago::text || '|' ||
               monto_total::text || '|' || (pos / 2)::text)::uuid AS nuevo_cruce_id
    FROM numerados
    WHERE en_grupo % 2 = 0
)
UPDATE pagos p
SET cruce_id = a.nuevo_cruce_id
FROM asignado a
WHERE p.id = a.id;
