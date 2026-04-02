# Documentación de la Suite de Pruebas (Test Suite)

La suite de pruebas para el backend de ContabilidadPersonal está escrita en **Pytest** y se encuentra en el directorio `/tests`. Consta de **141 tests funcionales** que validan la lógica de negocio, las rutas de la API, y la persistencia de datos (con aislamiento para no modificar archivos reales durante la ejecución).

A continuación se detalla todo el trabajo realizado y los archivos de pruebas creados.

## Estructura de Pruebas

### 🛠️ Configuración Global
- **`tests/conftest.py`**: Archivo de fixtures globales de Pytest. Contiene configuraciones iniciales, inyección de dependencias mockeadas (como `DataPipeline`) y un cliente de pruebas local (`TestClient`) para la API (FastAPI).

### 1. Infraestructura y Utilidades Claves
Estos tests cubren el motor y las herramientas transversales al sistema:
- **`tests/test_cache.py`**: Pruebas sobre la invalidación y recarga de la caché en memoria basada en archivos locales, asegurando frescura de los datos tras un cambio.
- **`tests/test_pipeline_engine.py`**: Pruebas sobre la ejecución secuencial de `TransformationPipeline` y manejo de la caché en línea de los datos procesados.
- **`tests/test_id_utils.py`**: Pruebas de generadores de identificadores únicos. Define colisiones MD5 y validaciones con la creación repetitiva de rows idénticos gracias al discriminador local.
- **`tests/test_mark_fixed_payments.py`**: Verifica rigurosamente la función `mark_fixed_payments` de la que dependen muchas integraciones (generación de la columna `INVERSION` basados en intervalos de fechas reales).

### 2. Etiquetado y Reglas Automáticas
Tests del sistema dinámico de categorización de gastos y persistencia JSON.
- **`tests/test_rules_storage.py`**: Pruebas del motor que aprende patrones de transacciones (`rules.json`). Prueba que al agregar una nueva regla se haga un `merge` en lugar de una sobreescritura total.
- **`tests/test_routes_transactions.py`**: Endpoint de transacciones maestras (`gastos_maestros.csv`). Pruebas HTTP del listado de transacciones, uso de filtros, splits, asignación masiva a grupos, y la correcta aplicación de status (como 404 para transacciones no halladas).

### 3. Sincronización (Fuentes y Base de datos)
- **`tests/test_routes_sync.py`**: Asegura el funcionamiento de la invocación de sincronización principal. Mockea librerías pesadas para afirmar que devuelve adecuadamente reportes de errores y que siempre forza una invalidación en las cachés relativas.

### 4. Pagos Interpolados, Deudas y Presupuestos
Sistema que requiere bases CSV auxiliares para configurar el modelado financiero.
- **`tests/test_variables_storage.py`**: Operaciones CRUD reales pero mapeadas a un directorio temporal (vía pytest `tmp_path`). Comprueba la creación, edición, borrado de "Grupos Fijos/Interpolados" y los "Pagos" asociados a dichos grupos.
- **`tests/test_routes_payments.py`**: Complemento de ruta HTTP del storage por encima de los CSVs (`/api/payments`). Prueba el rechazo de peticiones vacías (422 Pydantic) y fallos 404 adecuados. 
- **`tests/test_routes_budget.py`**: Asegura que la subida (POST) y petición (GET) de presupuestos mensuales guarde los bytes limpios en un archivo json (`presupuesto_config.json`).
- **`tests/test_routes_supabase_debts.py`**: Mocks diseñados para verificar las respuestas correctas de endpoints remotos conectándose a Supabase (mientras es a prueba de caídas o módulos no instalados temporalmente, respondiendo 500 ó 200).

### 5. Motores de Transformación Global (Pipeline)
- **`tests/test_data_pipeline.py`**: Validaciones asiladas de la clase `DataPipeline`. Garantiza cálculos correctos de `CREDITO` y `DEBITO` global y la llamada precisa de módulos pandas (`xlsx`).
- **`tests/test_transform_investments.py`**: Procesa la correcta mutabilidad y resiliencia a excepciones cuando la lógica global de mutación inyecta la columna `INVERSION`.

### 6. Visualización Interactiva (Servicios y Dashboards)
Validación robusta de los modelos y lógica tras las métricas interactivas y gráficas (React App). Todo endpoint de reporte se valida usando modelos restrictivos Pydantic.
- **`tests/test_investment_service.py`**: Aseguramiento de lógica que arma arreglos para ECharts en las Inversiones, asegurando longitud equitativa en arreglos temporales (`dates` y `saldo`).
- **`tests/test_routes_investments.py`**: Validación JSON Response del servicio completo en base API (`/api/investments/chart-data` y `/from-accounts`).
- **`tests/test_routes_dashboard.py`**: Confirmación sobre generación global unificada de dashboard report (`DashboardResponse`), asegurando que todos los atributos esperados salgan, sumado a endpoints directos de `cache stats`.

---

## 🏃‍♂️ Cómo Correr la Suite

Para mantener el software confiable luego de refactorizaciones o adiciones de funcionalidades futuras. Desde el entorno base, ejecuta:

```bash
# Entrar a la app python local
cd contabilidad/backend
source .venv/bin/activate

# Correr la totalidad de pruebas sin capturar logs excesivos
pytest tests/ -v

# O con salida simplificada (si hay averías):
pytest tests/ -q --tb=short
```

**Resultado actual (10 de Marzo 2026):**
`141 passed in ~6.86s`
