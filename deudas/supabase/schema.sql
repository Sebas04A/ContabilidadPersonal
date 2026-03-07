-- Schema para Supabase
-- Ejecutar en el SQL Editor de Supabase

-- ========================================
-- 1. TABLAS PRINCIPALES
-- ========================================

-- Tabla de deudores (Entidad)
CREATE TABLE IF NOT EXISTS deudores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre TEXT NOT NULL,
    token TEXT UNIQUE DEFAULT gen_random_uuid()::TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced BOOLEAN DEFAULT FALSE -- Para sincronización offline-first
);

-- Tabla de deudas (Obligaciones / Facturas)
-- Nota: Ya no tiene 'pagada' ni 'fecha_pago' porque eso se calcula
CREATE TABLE IF NOT EXISTS deudas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deudor_id UUID NOT NULL REFERENCES deudores(id) ON DELETE CASCADE,
    titulo TEXT NOT NULL,
    monto DECIMAL(10,2) NOT NULL, -- El monto original de la deuda
    fecha_gasto DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced BOOLEAN DEFAULT FALSE,
    es_mi_deuda BOOLEAN DEFAULT FALSE
);

-- Tabla de pagos (Transacciones Globales)
-- Representa el dinero físico entregado
CREATE TABLE IF NOT EXISTS pagos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deudor_id UUID NOT NULL REFERENCES deudores(id) ON DELETE CASCADE,
    monto_total DECIMAL(10,2) NOT NULL,
    fecha_pago DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced BOOLEAN DEFAULT FALSE,
    es_compensacion BOOLEAN DEFAULT FALSE
);

-- Tabla de detalles (Asignación / Distribución)
-- Relaciona CADA dólar de un pago con UNA deuda específica
CREATE TABLE IF NOT EXISTS detalle_pagos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pago_id UUID NOT NULL REFERENCES pagos(id) ON DELETE CASCADE,
    deuda_id UUID NOT NULL REFERENCES deudas(id) ON DELETE CASCADE,
    monto_asignado DECIMAL(10,2) NOT NULL, -- Cuánto de este pago va a esta deuda
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced BOOLEAN DEFAULT FALSE
);

-- ========================================
-- 2. VISTAS (VIEWS) - Lógica de Negocio
-- ========================================

-- Vista unificada para consultar el estado de las deudas
DROP VIEW IF EXISTS vista_estado_deudas;
CREATE OR REPLACE VIEW vista_estado_deudas AS
SELECT 
    d.id,
    d.titulo,
    d.monto as monto_original,
    d.fecha_gasto,
    d.deudor_id,
    d.es_mi_deuda,
    COALESCE(SUM(dp.monto_asignado), 0) as monto_pagado,
    (d.monto - COALESCE(SUM(dp.monto_asignado), 0)) as saldo_pendiente,
    CASE 
        WHEN (d.monto - COALESCE(SUM(dp.monto_asignado), 0)) <= 0.001 THEN 'PAGADA' -- Tolerancia flotante
        WHEN COALESCE(SUM(dp.monto_asignado), 0) > 0 THEN 'PARCIAL'
        ELSE 'PENDIENTE'
    END as estado
FROM deudas d
LEFT JOIN detalle_pagos dp ON d.id = dp.deuda_id
GROUP BY d.id;

-- ========================================
-- 3. SEGURIDAD (RLS)
-- ========================================

ALTER TABLE deudores ENABLE ROW LEVEL SECURITY;
ALTER TABLE deudas ENABLE ROW LEVEL SECURITY;
ALTER TABLE pagos ENABLE ROW LEVEL SECURITY;
ALTER TABLE detalle_pagos ENABLE ROW LEVEL SECURITY;

-- Políticas Públicas (Lectura por Token)
CREATE POLICY "Deudores visibles por token" ON deudores
    FOR SELECT USING (true); -- En producción, filtrar por token si es necesario, pero aquí simplificamos para la app del admin

CREATE POLICY "Deudas visibles público" ON deudas FOR SELECT USING (true);
CREATE POLICY "Pagos visibles público" ON pagos FOR SELECT USING (true);
CREATE POLICY "Detalles visibles público" ON detalle_pagos FOR SELECT USING (true);

-- Políticas Admin (Todo permitido)
-- Asumimos que la app usa service_role key o anon key con permisos full para simplificar este demo
CREATE POLICY "Admin full access deudores" ON deudores FOR ALL USING (true);
CREATE POLICY "Admin full access deudas" ON deudas FOR ALL USING (true);
CREATE POLICY "Admin full access pagos" ON pagos FOR ALL USING (true);
CREATE POLICY "Admin full access detalles" ON detalle_pagos FOR ALL USING (true);

-- ========================================
-- 4. ÍNDICES
-- ========================================
CREATE INDEX IF NOT EXISTS idx_deudas_deudor ON deudas(deudor_id);
CREATE INDEX IF NOT EXISTS idx_pagos_deudor ON pagos(deudor_id);
CREATE INDEX IF NOT EXISTS idx_detalle_pago ON detalle_pagos(pago_id);
CREATE INDEX IF NOT EXISTS idx_detalle_deuda ON detalle_pagos(deuda_id);
