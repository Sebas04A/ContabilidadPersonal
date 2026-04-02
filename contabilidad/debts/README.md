# Guía de Migración de Deudas

Este directorio contiene herramientas para migrar tus deudas existentes al nuevo sistema.

## Archivos

- `lectura.py` - Leer datos desde Supabase
- `escritura.py` - Escribir datos a Supabase
- `migrar.py` - Script de migración desde DataFrame
- `ejemplo_migracion.py` - Ejemplo práctico de uso

## Uso Rápido

### 1. Preparar tus datos

Tu DataFrame debe tener estas columnas:
- `Tipo` (opcional) - Si existe, solo migrará filas con "Doy"
- `Persona` o `PERSONA_NOTION` - Nombre del deudor
- `NOTION` - Monto de la deuda
- `DESCRIPCION_NOTION` - Descripción
- `FECHA_REAL` - Fecha del gasto

### 2. Ejecutar dry-run (simulación)

```python
import pandas as pd
from contabilidad.deudas.migrar import migrar_deudas_desde_df

# Cargar tu DataFrame
df = pd.read_csv('tus_datos.csv')
# O si ya está en memoria:
# df = tu_dataframe

# Primero hacer dry-run para verificar
resultado = migrar_deudas_desde_df(df, dry_run=True)
```

### 3. Ejecutar migración real

```python
# Si todo se ve bien, ejecutar la migración
resultado = migrar_deudas_desde_df(df, dry_run=False)
print(resultado)
```

## Ejemplo Completo

```python
import pandas as pd
from contabilidad.deudas.migrar import migrar_deudas_desde_df

# Tu DataFrame de ejemplo
data = {
    'Tipo': ['Doy', 'Doy', 'Doy'],
    'NOTION': [210.00, 20.82, 45.00],
    'Persona': ['Madre', 'Madre', 'Ñaña'],
    'DESCRIPCION_NOTION': [
        'Pago dermatologo',
        'Medicamentos',
        'Milanesa Uber'
    ],
    'FECHA_REAL': ['2024-09-30', '2024-10-23', '2024-11-20']
}

df = pd.DataFrame(data)
df['FECHA_REAL'] = pd.to_datetime(df['FECHA_REAL'])

# 1. DRY RUN
print("=== SIMULACIÓN ===")
resultado = migrar_deudas_desde_df(df, dry_run=True)

# 2. Si todo OK, migrar
input("Presiona Enter para ejecutar la migración real...")
resultado = migrar_deudas_desde_df(df, dry_run=False)

print(f"\n✅ Migración completada: {resultado}")
```

## Funciones Disponibles

### Escritura Individual

```python
from contabilidad.deudas.escritura import (
    obtener_o_crear_deudor,
    crear_deuda
)
from datetime import datetime

# Crear/obtener deudor
deudor = obtener_o_crear_deudor("Juan Pérez")

# Crear deuda
deuda = crear_deuda(
    titulo="Almuerzo",
    monto=25.50,
    deudor_id=deudor['id'],
    fecha_gasto=datetime(2024, 1, 15)
)
```

### Lectura

```python
from contabilidad.deudas.lectura import (
    obtener_todas_deudas,
    obtener_resumen_por_deudor
)

# Ver todas las deudas pendientes
df_deudas = obtener_todas_deudas(solo_pendientes=True)
print(df_deudas)

# Resumen por deudor
df_resumen = obtener_resumen_por_deudor()
print(df_resumen)
```

## Troubleshooting

**Error: "Columna no encontrada"**
- Verifica que tu DataFrame tenga las columnas correctas
- Usa `df.columns` para ver qué columnas tienes

**Error de conexión a Supabase**
- Verifica las credenciales en `escritura.py` y `lectura.py`
- Asegúrate de haber ejecutado el schema SQL

**Deudas duplicadas**
- El script no verifica duplicados
- Si necesitas limpiar, usa la función de lectura para verificar primero
