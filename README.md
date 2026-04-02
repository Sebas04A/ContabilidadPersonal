# 💰 ContabilidadPersonal — Sistema de Contabilidad Personal

Sistema integral para gestionar finanzas personales: cuenta bancaria, tarjeta de crédito, inversiones, deudas y etiquetado de gastos. Incluye un backend API, una interfaz web React, una app Flutter para deudas, y múltiples módulos Python de procesamiento de datos.

---

## 📋 Tabla de Contenidos

1. [¿Qué es este proyecto?](#-qué-es-este-proyecto)
2. [Flujo de Uso Diario](#-flujo-de-uso-diario)
3. [Estructura General del Proyecto](#-estructura-general-del-proyecto)
4. [Módulo Principal: `contabilidad/`](#-módulo-principal-contabilidad)
   - [Backend (API FastAPI)](#contabilidadbackend--api-rest-fastapi)
   - [Frontend (React + TypeScript)](#contabilidadpagina--frontend-web-react--typescript)
   - [Módulos de Procesamiento de Datos](#módulos-de-procesamiento-de-datos-python)
5. [Ecosistema de Deudas: `deudas/`](#-ecosistema-de-deudas-deudas)
6. [Datos: `data/`](#-datos-data)
7. [Notebooks y Scripts](#-notebooks-y-scripts)
8. [Tecnologías Utilizadas](#️-tecnologías-utilizadas)
9. [Cómo Ejecutar](#-cómo-ejecutar)
10. [Documentación Adicional](#-documentación-adicional)

---

## 🎯 ¿Qué es este proyecto?

ContabilidadPersonal es un sistema que construí para tener **control total sobre mis finanzas personales**. El banco provee extractos de cuenta y estados de tarjeta de crédito como archivos Excel, pero no ofrece herramientas de análisis reales. Este sistema toma esos archivos crudos, los procesa, unifica, y expone todo a través de una interfaz web donde puedo:

- **Etiquetar cada transacción** con categoría, tags personalizados, nivel de prioridad y un índice de "felicidad" del gasto.
- **Visualizar mi situación financiera** en dashboards interactivos: saldo, tarjeta, inversiones, variaciones diarias.
- **Gestionar deudas personales** (lo que presto/me prestan) con una app Flutter y un visor web para compartir con deudores.
- **Presupuestar por mes** con categorías configurables.
- **Trackear inversiones** (CDPs, plazo fijo) y ver la evolución temporal.
- **Aplicar reglas inteligentes** para auto-clasificar transacciones recurrentes (motor de reglas basado en descripciones del banco).

El sistema NO depende de APIs bancarias: yo descargo los archivos Excel del banco, los dejo en la carpeta `data/nuevos/`, y el sistema hace el resto.

---

## 🔄 Flujo de Uso Diario

El uso típico del sistema sigue este ciclo:

```
  ┌─────────────────────────────────────────────────────────┐
  │  1. OBTENER DATOS                                       │
  │  Descargar archivos del banco → data/nuevos/            │
  │  • Extracto bancario (.xlsx) → data/nuevos/banca/       │
  │  • Estado de tarjeta (.xls)  → data/nuevos/tarjeta/     │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  2. LEVANTAR EL SISTEMA                                 │
  │  ./start_contabilidad.sh                                │
  │  → Backend en :8000  +  Frontend en :5173               │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  3. SINCRONIZAR (desde la web)                          │
  │  Página "Fuentes" → Subir/procesar archivos nuevos      │
  │  • Parsea extractos bancarios (.xlsx)                   │
  │  • Parsea estados de tarjeta (.xls con HTML tables)     │
  │  • Unifica todo en data/sistema/procesada/              │
  │  • Sincroniza con el archivo maestro de gastos          │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  4. ETIQUETAR TRANSACCIONES                             │
  │  Página "Etiquetado" → Para cada transacción:           │
  │  • Asignar nombre limpio (ej: "Uber", "Supermercado")   │
  │  • Elegir categoría, tags, prioridad                    │
  │  • Indicar felicidad del gasto (0-5)                    │
  │  • El motor de reglas aprende y auto-clasifica futuras  │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  5. CONFIGURAR                                          │
  │  • Inversiones → Registrar CDPs, plazos fijos activos   │
  │  • Pagos fijos → Definir gastos recurrentes (grupos)    │
  │  • Deudas → Registrar préstamos dados/recibidos         │
  │  • Presupuesto → Establecer límites por categoría       │
  │  • Variables → Ajustar métricas calculadas              │
  └──────────────────────┬──────────────────────────────────┘
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  6. ANALIZAR                                            │
  │  • Dashboard → Gráficos de saldo, variaciones, tarjeta  │
  │  • Inversiones → Evolución temporal de inversiones      │
  │  • Presupuesto → Gasto real vs. presupuestado           │
  │  • Variables → Métricas financieras derivadas           │
  │  • Deudas → Estado de lo prestado/adeudado              │
  └─────────────────────────────────────────────────────────┘
```

---

## 📂 Estructura General del Proyecto

```
ContabilidadPersonal/
├── contabilidad/                 # 🧠 Módulo principal (backend + frontend + lógica de datos)
│   ├── backend/                  #   API FastAPI — arquitectura en 4 capas
│   │   ├── routes/               #     [Capa 1] Rutas HTTP (10 módulos)
│   │   ├── services/             #     [Capa 2] Lógica de negocio y Extracción (ETL)
│   │   │   ├── bank_parser/      #       Lectura y validación de extractos bancarios (.xlsx)
│   │   │   ├── credit_card/      #       Scraping y parsing avanzado de TC (HTML tables)
│   │   │   ├── data_merger/      #       Unificación de banca + tarjeta y cortes
│   │   │   ├── notion/           #       Integración con Notion API
│   │   │   ├── dashboard_service.py
│   │   │   ├── investment_service.py
│   │   │   ├── sources_service.py
│   │   │   └── transaction_service.py
│   │   ├── storage/              #     [Capa 3] Acceso a datos y transformaciones
│   │   │   ├── snapshots/        #       Persistencia y versionado de datos inmutables
│   │   │   ├── reading/          #       Lectura del archivo consolidado (completo)
│   │   │   ├── data_pipeline.py  #       Pipeline principal con caché inteligente
│   │   │   ├── cache.py          #       DataCache con TTL
│   │   │   ├── pipeline_engine.py#       Motor de transformaciones secuenciales
│   │   │   ├── variables_storage.py #    CRUD de grupos/pagos (CSV)
│   │   │   ├── rules_storage.py  #       Motor de reglas de auto-etiquetado
│   │   │   └── transformations/  #       Transformaciones por dominio
│   │   ├── models/               #     [Capa 4] Modelos Pydantic comunes
│   │   ├── utils/                #     [Capa 4] Utilidades criptográficas
│   │   ├── main.py               #     Punto de entrada FastAPI
│   │   └── logger.py             #     Sistema de logs centralizado
│   ├── pagina/                   #   Frontend React (Vite + TypeScript + TailwindCSS)
│   ├── modules/                  #   Módulos de análisis auxiliares
│   │   ├── analisis/             #     Visualización con Plotly (para notebooks)
│   │   └── descripciones/        #     Manejo de descripciones de transacciones
│   ├── tagging/                  #   App Streamlit alternativa para clasificar gastos
│   ├── debts/                    #   Sub-módulo de migración de deudas a Supabase
│   ├── config.py                 #   Configuración central de rutas globales (PATH_DATA)
│   ├── models.py                 #   Estructuras compartidas (Payment, SavedChangesData)
│   ├── start_contabilidad.sh     #   Script de arranque orquestado (Linux/macOS)
│   └── run.bat                   #   Script de arranque (Windows)
│
├── deudas/                       # 📱 Ecosistema independiente de Deudas
│   ├── flutter_app/              #   App móvil Flutter (admin, offline-first)
│   ├── visor_web/                #   Visor web HTML/JS (solo lectura para deudores)
│   ├── supabase/                 #   Schema SQL + funciones PostgreSQL
│   └── tests/                    #   Tests del sistema de deudas
│
├── data/                         # 📊 Datos del sistema
│   ├── nuevos/                   #   Archivos crudos descargados del banco
│   │   ├── banca/                #     Extractos bancarios (.xlsx)
│   │   └── tarjeta/              #     Estados de tarjeta (.xls)
│   ├── sistema/                  #   Datos procesados por el sistema
│   │   ├── procesada/            #     Banca y tarjeta unificadas
│   │   ├── etiquetado/           #     etiquetas.csv + rules.json
│   │   └── interpolaciones/      #     grupos.csv + pagos.csv (inversiones y pagos fijos)
│   └── historicos/               #   Snapshots versionados por fecha (YYYY-MM-DD/)
│
├── notebooks/                    # 📓 Jupyter Notebooks de exploración
├── scripts/                      # 🔧 Scripts utilitarios y de migración
├── pyproject.toml                # 📦 Definición del paquete Python (pip install -e .)
└── settings.json                 # Configuración del IDE
```

---

## 🧠 Módulo Principal: `contabilidad/`

Este es el corazón del sistema. Contiene la lógica de procesamiento de datos financieros (Python/Pandas), la API REST que expone los datos, y la interfaz web para interactuar con ellos.

### Punto de Entrada

El sistema se levanta con el script `start_contabilidad.sh` (Linux/macOS) o `run.bat` (Windows), que inicia **simultáneamente**:
1. **Backend** en `http://localhost:8000` (FastAPI + Uvicorn)
2. **Frontend** en `http://localhost:5173` (Vite + React)

El script incluye:
- Prefijo por colores en la terminal (`[BACKEND]` azul, `[FRONTEND]` verde, `[SISTEMA]` gris)
- Detección automática de errores/warnings en los logs
- Soporte para modo debug vía `./start_contabilidad.sh debug`
- Limpieza de procesos al cerrar con `CTRL+C`

---

### `contabilidad/backend/` — API REST (FastAPI)

**Tecnologías**: FastAPI, Pandas, Pydantic, Uvicorn  
**Documentación detallada**: [`ARQUITECTURA_BACKEND.md`](contabilidad/backend/ARQUITECTURA_BACKEND.md)

#### Arquitectura en Capas

El backend está organizado en **4 capas** con responsabilidades bien definidas:

```
┌─────────────────────────────────────────────────────────────┐
│  CAPA 1: ROUTES  (contabilidad/backend/routes/)             │
│  Recibe requests HTTP, llama a servicios, devuelve JSON     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  CAPA 2: SERVICES  (contabilidad/backend/services/)         │
│  Lógica de negocio. Orquesta datos para la respuesta final  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  CAPA 3: STORAGE  (contabilidad/backend/storage/)           │
│  Acceso a datos: pipeline, caché, transformaciones, CSV     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  CAPA 4: MODELS + UTILS  (backend/models/, backend/utils/)  │
│  Estructuras de datos Pydantic y utilidades compartidas     │
└─────────────────────────────────────────────────────────────┘
```

#### Rutas del API — `routes/`

| Ruta | Archivo | Descripción |
|------|---------|-------------|
| `/api/transactions` | `transactions.py` | CRUD de transacciones etiquetadas. Filtros por fecha, categoría, estado. Edición: categoría, tags, prioridad, felicidad, splits, notas |
| `/api/sync` | `sync.py` | Sincronización de datos bancarios con el archivo maestro `gastos_maestros.csv` |
| `/api/groups`, `/api/payments` | `interpolated.py` | CRUD de pagos fijos e interpolados (gastos recurrentes, inversiones activas) |
| `/api/investments` | `investments.py` | Tracking de inversiones: detección automática desde cuenta (CDPs, plazo fijo) y datos para gráficas |
| `/api/supabase-debts` | `supabase_debts.py` | Consulta de deudas desde Supabase |
| `/api/dashboard` | `dashboard.py` | Series temporales para el dashboard: saldo, tarjeta, inversión, variaciones |
| `/api/sources` | `sources.py` | Gestión de fuentes: upload de archivos bancarios, procesamiento de extractos |
| `/api/variables` | `variables.py` | Variables y métricas financieras calculadas |
| `/api/budget` | `budget.py` | Configuración de presupuesto mensual (`presupuesto_config.json`) |
| `/api/rules` | `rules.py` | Gestión del motor de reglas de auto-etiquetado |

#### Servicios — `services/`

Capa de lógica de negocio. Los servicios son instancias inyectadas en las rutas.

| Archivo | Descripción |
|---------|-------------|
| `dashboard_service.py` | Calcula y agrega datos para el dashboard. Aplica filtros temporales, métricas comparativas y buildea series para ECharts |
| `investment_service.py` | Lógica de inversiones: obtiene CDPs/plazos fijos desde cuenta bancaria, prepara datos para gráfica de evolución de inversiones con períodos marcados |
| `sources_service.py` | Orquesta el procesamiento de nuevos archivos bancarios: parseo, normalización, unificación y guardado |
| `transaction_service.py` | CRUD completo de transacciones y etiquetas. Unifica banca + tarjeta, gestiona splits, aplica reglas automáticas. Maneja `etiquetas.csv` |

#### Storage — `storage/`

Capa de acceso a datos. Toda la lógica de lectura/escritura de archivos y procesamiento en Pandas.

| Archivo/Carpeta | Descripción |
|-----------------|-------------|
| `data_pipeline.py` | Singleton `DataPipeline` con caché inteligente (TTL + detección de cambios). Expone `get_account_data()`, `get_bank_data()`, `get_credit_card_data()` |
| `cache.py` | `DataCache`: caché en memoria con TTL configurable y detección de cambios por hash de timestamp + tamaño del archivo |
| `pipeline_engine.py` | `TransformationPipeline`: ejecuta transformaciones secuenciales sobre un DataFrame, con caché individual por paso |
| `variables_storage.py` | `InterpolationStorage`: CRUD de grupos de pagos y pagos individuales desde `grupos.csv` y `pagos.csv` |
| `rules_storage.py` | Motor de reglas: carga/guarda `rules.json`, aplica reglas de auto-clasificación a transacciones por coincidencia de descripción |
| `transformations/investments.py` | Transformación que inyecta la columna `INVERSION` al DataFrame según los pagos fijos registrados |
| `transformations/credit_cards.py` | Transformación que calcula `PAGO_TARJETA`, `ACUMULADO_TARJETA` y `TARJETA` (deuda estimada) |

#### Modelos — `models/`

Modelos Pydantic para validación de requests/responses, organizados por dominio.

| Archivo | Modelos |
|---------|---------|
| `dashboard_models.py` | Estructuras de respuesta del dashboard (series, variaciones, resúmenes) |
| `investment_models.py` | `AccountInvestment`, `InvestmentsFromAccountsResponse` |
| `interpolation_models.py` | Modelos para grupos y pagos interpolados |
| `budget_models.py` | `BudgetConfig` |
| `sync_models.py` | Modelos de sincronización |
| `transaction_models.py` | Modelos de transacciones y etiquetas |

#### Utilidades — `utils/`

| Archivo | Descripción |
|---------|-------------|
| `id_utils.py` | `generate_unique_id()` y `add_id_column()`: genera IDs MD5 deterministas por transacción basados en fecha, monto, descripción y fuente. Maneja duplicados con discriminador secuencial |

#### Suite de Pruebas (Tests)

El backend cuenta con una suite completa de pruebas usando `pytest` en el directorio `tests/`:

- **Cobertura**: Rutas HTTP (`TestClient`), Servicios de Dominio, Almacenamiento, Pipeline de Datos y Transformaciones.
- **Enfoque**: Aislamiento de dependencias usando `unittest.mock` y `tmp_path` (para no tocar archivos reales), testeo de lógica de caché y validación de estructuras Pydantic.
- **Ejecución**: `pytest tests/ -v` (140+ tests implementados).

#### Componentes de Soporte

- **`logger.py`** — Sistema de logs centralizado. Colores por nivel (DEBUG gris, INFO cyan, WARNING amarillo, ERROR rojo). Se configura con la variable de entorno `LOG_LEVEL`.
- **`main.py`** — Punto de entrada: configura CORS, registra todos los routers, pre-carga caché al inicio (`startup_event`). Expone `/api/cache/stats` y `/api/cache/invalidate`.

#### Nota sobre rutas de datos

Todos los módulos del backend usan `DATA_DIR` de `contabilidad/config.py` para referenciar archivos de datos. Esto garantiza que los paths sean correctos sin importar desde qué directorio se ejecute el servidor.

---

### `contabilidad/pagina/` — Frontend Web (React + TypeScript)

**Tecnologías**: React 18, TypeScript, Vite, TailwindCSS, ECharts, Tanstack Query, Lucide Icons

#### Páginas

| Página | Archivo | Descripción |
|--------|---------|-------------|
| **Etiquetado** | `Labeling.tsx` | Página principal de trabajo diario. Tabla de transacciones filtrable por fecha y estado. Al hacer click en una transacción, abre un modal para asignar: nombre limpio, categoría, tags, prioridad (1-5), felicidad (0-5), notas, splits, campo "pertenece a", si es reembolsable/fijo |
| **Dashboard** | `DataExplorer.tsx` | Explorador interactivo de datos. Gráficos ECharts de saldo, tarjeta, inversión, variaciones diarias. Filtros temporales y análisis comparativo |
| **Fuentes** | `Sources.tsx` | Gestión de archivos fuente: upload de extractos bancarios y estados de tarjeta, procesamiento y vista previa de datos, estado de sincronización |
| **Inversiones** | `InvestmentAnalysis.tsx` | Análisis visual de inversiones (CDPs, plazo fijo). Gráfico de evolución temporal, periodos activos, rendimiento |
| **Deudas** | `Debts.tsx` | Visualización de deudas personales desde Supabase. Gráfico de distribución por deudor, resumen de montos adeudados |
| **Presupuesto** | `MonthlyBudget.tsx` | Presupuesto mensual con categorías configurables. Comparación gasto real vs. presupuestado, análisis por categoría |
| **Variables** | `Variables.tsx` | Variables calculadas del sistema: métricas financieras derivadas |

#### Componentes Destacados

| Componente | Descripción |
|------------|-------------|
| `EditModal.tsx` | Modal completo de edición de transacciones (el componente más grande del frontend, ~49KB). Formulario con todos los campos de etiquetado |
| `DashboardChart.tsx` | Gráfico principal del dashboard (saldo, tarjeta, inversión) |
| `VariationsChart.tsx` | Gráfico de variaciones diarias y análisis temporal |
| `InvestmentChart.tsx` | Gráfico de evolución de inversiones |
| `CardChart.tsx` / `CardAnalysis.tsx` | Análisis y gráfico específico de tarjeta de crédito |
| `DebtsChart.tsx` | Gráfico de distribución de deudas |
| `PaymentCRUD.tsx` | CRUD completo de pagos interpolados/fijos |
| `Sidebar.tsx` | Navegación lateral de la app |
| `TransactionTable.tsx` | Tabla de transacciones reutilizable |
| `SearchModal.tsx` | Búsqueda global de transacciones |
| `CalendarPopover.tsx` | Selector de fechas |
| `AutoPaymentsModal.tsx` | Modal para gestión de pagos automáticos |

---

### Módulos de Procesamiento de Datos (Servicios del Backend)

Estos módulos conforman el motor ETL (Extract, Transform, Load) del sistema. Originalmente scripts separados, ahora están fuertemente integrados en los `services/` y `storage/` del backend FastAPI.

#### `backend/services/bank_parser/` — Lectura y Validación Bancaria

Módulo que lee los extractos bancarios (`.xlsx` o `.csv`) descargados, limpiándolos y normalizándolos a un formato estándar.

| Archivo | Función |
|---------|---------|
| `account.py` | Lee, normaliza y une archivos de la cuenta bancaria. Estandariza a: `FECHA`, `SALDO`, `DESCRIPCION`, `MONTO`, `DEBITO`, `CREDITO` |
| `FileProcessingConfig.py` | Dataclass de configuración (mapeo de columnas, formatos de fechas). Permite adaptar el sistema a diferentes plantillas bancarias |
| `get_variables.py` | Extrae transacciones derivadas (pagos de tarjeta, CDPs) |
| `validation.py` | Módulo QA. Compara el DataFrame entrante contra la captura histórica para detectar discrepancias celda por celda |

#### `backend/services/credit_card/` — Extracción Avanzada de Tarjetas de Crédito

Se encarga de *scrapear* y procesar estados de tarjeta descargados como `.xls` (que internamente son tablas HTML muy densas). Sigue una arquitectura modular dividida por dominios.

| Carpeta/Archivo | Función |
|---------|---------|
| `core.py` | Orquestador principal del pipeline de la tarjeta de crédito |
| `parsers/` | Parsers especializados: `html_reader` (BeautifulSoup), `metadata` (banco, corte, titular), `movements` (DataFrame consumos), `totals` (cargos adeudados) |
| `excel_writer.py` | Escritura del resultado en Pandas ExcelWriter con auto-ajuste de columnas |
| `models.py` | Definiciones estrictas Pydantic/Dataclass para los componentes de la tarjeta |

#### `backend/services/data_merger/` — Unificación Banca + Tarjeta

Combina las series de tiempo del banco con los consumos de tarjeta calculando la posición global de saldo neto.

| Archivo | Función |
|---------|---------|
| `general.py` | Lógica de unificación, primer día contable válido y reseteo de arrastres de saldos |
| `cut_credit_card.py` | Lógica de *corte temporal* para encuadrar las fechas de facturación con el consumo real |
| `interpolar.py` | Llenado avanzado de huecos (rellena datos faltantes entre fechas de cierre) |

#### `backend/storage/snapshots/` — Persistencia Inmutable (Versionado)

Genera las fotos históricas inmutables del estado financiero (`data/historicos/YYYY-MM-DD/`).

| Archivo | Función |
|---------|---------|
| `storage.py` | Guarda los puntos de guardado masivos (`guardar_toda_carpeta`, `guardar_nuevos_datos_finales`) |
| `changes_verification.py` | Diff temporal automatizado para no sobreescribir datos accidentalmente |

#### `backend/services/notion/` — Integración Remota

| Archivo | Función |
|---------|---------|
| `integracionNotion.py` | Cliente para la API de Notion. (Nota: Token por variable de entorno/hardcode) |

---

### Componentes Independientes (CLI & Dashboards)

#### `tagging/` — App de Etiquetado (Streamlit)

App independiente con Streamlit para clasificar transacciones manualmente. Es una alternativa al frontend React, útil para sesiones de etiquetado rápido.

| Archivo | Función |
|---------|---------|
| `app.py` | Interfaz Streamlit: formulario de edición por transacción con categoría, tags, prioridad, felicidad, notas, splits |
| `rules_handler.py` | **Motor de reglas inteligente**: aprende de transacciones etiquetadas (`learn_from_transaction()`). Mantiene dos mapas: `description_map` y `entity_data`. Auto-aplica categorías a nuevas transacciones similares via matching por substring case-insensitive (`apply_rules_to_df()`) |
| `sync.py` | Unifica datos de cuenta + tarjeta con ID único basado en contenido (`fecha|descripcion|monto|tipo`). |

#### `debts/` — Sub-módulo de Migración de Deudas

Herramientas Python para migrar datos de deudas desde DataFrames a Supabase.

| Archivo | Función |
|---------|---------|
| `lectura.py` | Leer deudas desde Supabase |
| `escritura.py` | Escribir deudas a Supabase (crear deudores, crear deudas) |
| `migrar.py` | Script de migración masiva desde DataFrame |
| `migrar_nuevo.py` | Versión actualizada de migración |
| `limpiar.py` | Limpieza de datos |
| `ejemplo_migracion.py` | Ejemplo práctico de uso |

**Guía detallada**: [`contabilidad/debts/README.md`](contabilidad/debts/README.md)

---

### Archivos Raíz de `contabilidad/`

| Archivo | Función |
|---------|---------|
| `config.py` | **Configuración central**: todas las rutas del sistema (`PATH_DATA`, `PATH_PROCESADOS`, `PATH_NUEVOS`, `PATH_BANCA_PROCESADA`, `PATH_TARJETA_UNIDA`, etc.) y definiciones de columnas para cada tipo de dato |
| `models.py` | Dataclasses compartidas: `Payment` (pago con monto, fechas, descripción), `SavedAccountChangesData` (metadatos de cambios guardados), `SavedChangesData` (datos de snapshot), `ConfigData`, `EnhancedJSONEncoder` (serialización de dataclasses, datetime, Path) |
| `start_contabilidad.sh` | Script de orquestación: levanta backend + frontend, colorea logs, detecta errores, soporta modo debug |
| `run.bat` | Equivalente para Windows |
| `__init__.py` | Marca el directorio como paquete Python |

---

## 📱 Ecosistema de Deudas: `deudas/`

Sistema independiente y completo para gestionar deudas personales ("quién le debe a quién").  
**Documentación detallada**: [`deudas/LOGICA_SISTEMA.md`](deudas/LOGICA_SISTEMA.md) · [`deudas/README.md`](deudas/README.md)

### Componentes

| Componente | Tecnología | Descripción |
|------------|------------|-------------|
| **App Flutter** | Flutter + Dart + Hive | Panel de administración. Offline-first con sincronización a Supabase. Se crean deudores, registran deudas, y procesan pagos |
| **Visor Web** | HTML/CSS/JS puro | Interfaz de solo lectura desplegada en Vercel. Los deudores acceden vía `?token=XYZ` y ven su estado de cuenta en tiempo real |
| **Supabase** | PostgreSQL + REST API | Base de datos en la nube con 4 tablas: `deudores`, `deudas`, `pagos`, `detalle_pagos` + vista `vista_estado_deudas` |

### Lógica de Negocio

- **Estado dinámico**: El estado de una deuda **no se almacena** en un campo. Se calcula sumando todos los `detalle_pagos` asociados y restando del monto original. Si queda `>= 0.01`, la deuda sigue viva.
- **Cruce automático (Netting)**: Si A le debe $50 a B y B le debe $30 a A, el sistema crea pagos virtuales (`es_compensacion=true`) por $30 en ambas direcciones para "matar" las deudas cruzadas sin dinero físico.
- **Sincronización offline**: Objetos con bandera `synced=false` se envían a Supabase vía UPSERT cuando hay conexión. El servicio de sync hace polling en segundo plano.
- **Visor web inteligente**: El visor ejecuta la misma lógica matemática de la app Flutter pero en JavaScript puro, replicando los cálculos de compensación y estados en el frontend.

---

## 📊 Datos: `data/`

El directorio `data/` contiene todos los archivos de datos del sistema. Los datos sensibles no se versionan en git.

| Carpeta | Contenido |
|---------|-----------|
| `nuevos/banca/` | Archivos `.xlsx` crudos descargados de banca en línea |
| `nuevos/tarjeta/` | Archivos `.xls` crudos de estados de tarjeta de crédito (internamente son HTML tables) |
| `sistema/procesada/banca/` | `banca_unida.xlsx` — Archivo unificado de todas las transacciones bancarias procesadas |
| `sistema/procesada/tarjeta/` | `tarjeta_unida.xlsx`, `tarjeta_metadata_unida.xlsx` — Archivos procesados de tarjeta |
| `sistema/etiquetado/` | `gastos_maestros.csv` (archivo maestro con todas las transacciones etiquetadas) + `rules.json` (reglas de auto-etiquetado aprendidas) |
| `sistema/interpolaciones/` | `grupos.csv` (grupos de pagos: inversiones, gastos fijos) + `pagos.csv` (pagos individuales con fechas y montos) |
| `historicos/` | Snapshots inmutables por fecha (`YYYY-MM-DD/`): cada uno con `completo.xlsx`, `banca.xlsx`, `descripciones.xlsx`, `metadata.json` |

### Flujo de Transformación de Datos

```
   Archivos crudos del banco
   data/nuevos/banca/*.xlsx  +  data/nuevos/tarjeta/*.xls
          │                                │
          ▼                                ▼
   modules/account/reading/          credit_card/generate_clean_data.py
   Lee .xlsx, normaliza columnas     Parsea HTML tables, extrae movimientos
   (FECHA, SALDO, MONTO, DESC)      y metadata (empresa, fechas corte)
          │                                │
          ▼                                ▼
   data/sistema/procesada/          data/sistema/procesada/
   banca/banca_unida.xlsx           tarjeta/tarjeta_unida.xlsx
          │                                │
          └────────────┬───────────────────┘
                       ▼
   tagging/sync.py (sincronizar_db)
   Une cuenta + tarjeta, genera IDs
   únicos, aplica reglas automáticas
                       │
                       ▼
   data/sistema/etiquetado/gastos_maestros.csv
   (Archivo maestro: todas las transacciones con etiquetas)
                       │
                       ▼
   Backend DataPipeline (caché + transformaciones)
   Calcula inversiones, tarjeta, métricas
                       │
                       ▼
   API REST → Frontend React / Notebooks / Streamlit
```

---

## 📓 Notebooks y Scripts

### Notebooks (`notebooks/`)

Jupyter Notebooks para exploración interactiva de datos:

| Notebook | Uso |
|----------|-----|
| `cuenta.ipynb` | Análisis principal de cuenta bancaria |
| `etiquetado.ipynb` | Pruebas del sistema de etiquetado automático |
| `obtener_descripciones_pasadas.ipynb` | Extracción de descripciones históricas |
| `pagina_pruebas.ipynb` | Prototipos de visualización |

### Scripts (`scripts/`)

Scripts utilitarios y de migración (ejecución única):

| Script | Uso |
|--------|-----|
| `migrate_to_etiquetas.py` | Migración al nuevo sistema de etiquetas |
| `migrate_happiness.py` | Migración del campo de felicidad al modelo nuevo |
| `check_data.py` | Verificación de integridad de datos |
| `test_api.py` | Pruebas del API |
| `test_ids.py` | Verificación de IDs únicos |
| `reproduce_500.py`, `reproduce_nan.py` | Scripts de debugging para reproducir errores |

---

## 🛠️ Tecnologías Utilizadas

| Capa | Tecnología |
|------|------------|
| Backend API | Python 3.13, FastAPI, Uvicorn, Pandas, Pydantic |
| Frontend Web | React 18, TypeScript, Vite, TailwindCSS, ECharts, Tanstack Query |
| App Etiquetado | Streamlit |
| App Deudas | Flutter + Dart, Hive (offline) |
| Visor Deudas | HTML/CSS/JS puro (desplegado en Vercel) |
| Base de Datos Deudas | Supabase (PostgreSQL + REST API) |
| Visualización | Plotly, ECharts, ipywidgets |
| Datos | Excel (.xlsx/.xls), CSV, JSON |
| Integración Externa | Notion API |
| Logging | Python `logging` con colores por nivel |
| Empaquetado | setuptools (paquete `contabilidad-personal`, instalable con `pip install -e .`) |

---

## 🚀 Cómo Ejecutar

### Requisitos Previos

- Python 3.13+
- Node.js (para el frontend React)
- Git

### Instalación del Proyecto

Para que los módulos Python se enlacen correctamente sin problemas de importaciones, instala el proyecto en modo editable desde la raíz:

```bash
pip install -e .
```

Esto registra el paquete `contabilidad` en tu entorno Python, eliminando la necesidad de manipular `sys.path`.

### Ejecutar Backend + Frontend (Contabilidad)

```bash
# Linux/macOS
cd contabilidad
./start_contabilidad.sh          # Nivel INFO por defecto
./start_contabilidad.sh debug    # Activa LOG_LEVEL=DEBUG para máxima verbosidad

# Windows
cd contabilidad
run.bat
```

Esto levanta:
- **Backend**: `http://localhost:8000` (API docs interactivos en `/docs`)
- **Frontend**: `http://localhost:5173`

### App de Etiquetado (Streamlit)

```bash
cd contabilidad/tagging
streamlit run app.py
```

### Ecosistema de Deudas

Ver instrucciones detalladas en [`deudas/README.md`](deudas/README.md)

---

## 📝 Documentación Adicional

| Documento | Ubicación | Contenido |
|-----------|-----------|-----------|
| Arquitectura Backend | [`contabilidad/backend/ARQUITECTURA_BACKEND.md`](contabilidad/backend/ARQUITECTURA_BACKEND.md) | Arquitectura detallada del API, todos los endpoints con modelos, flujos de datos, sistema de caché/pipeline, configuración |
| Lógica Sistema Deudas | [`deudas/LOGICA_SISTEMA.md`](deudas/LOGICA_SISTEMA.md) | Modelos de datos, motor de negocio, cruce automático (netting), sincronización offline, diseño de UI |
| README Deudas | [`deudas/README.md`](deudas/README.md) | Guía de configuración y uso del ecosistema de deudas (Supabase, Flutter, Visor Web) |
| Migración Deudas | [`contabilidad/debts/README.md`](contabilidad/debts/README.md) | Guía de migración de deudas desde DataFrames a Supabase con ejemplos de código |
