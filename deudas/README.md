# Sistema de Gestión de Deudas

Sistema completo para registrar y gestionar deudas personales con:
- **App Flutter (Admin)**: Aplicación móvil con soporte offline
- **Visor Web (Deudor)**: Página para que cada deudor consulte sus deudas
- **Backend**: Supabase (PostgreSQL + API REST)

## Estructura del Proyecto

```
deudas/
├── flutter_app/     # App móvil Flutter
├── visor_web/       # Visor web para Vercel
└── supabase/        # Schema de base de datos
```

---

## 1. Configuración de Supabase

1. Crea una cuenta en [Supabase](https://supabase.com)
2. Crea un nuevo proyecto
3. Ve a **SQL Editor** y ejecuta el contenido de `supabase/schema.sql`
4. Ve a **Settings > API** y copia:
   - `Project URL`
   - `anon public` key

---

## 2. Configuración de la App Flutter

### Requisitos
- Flutter 3.x instalado
- Android Studio o VS Code con extensiones Flutter

### Pasos

1. Navega a la carpeta:
   ```bash
   cd deudas/flutter_app
   ```

2. Instala dependencias:
   ```bash
   flutter pub get
   ```

3. Abre `lib/main.dart` y configura tus credenciales:
   ```dart
   const String supabaseUrl = 'TU_SUPABASE_URL';
   const String supabaseAnonKey = 'TU_SUPABASE_ANON_KEY';
   ```

4. Ejecuta la app:
   ```bash
   flutter run
   ```

---

## 3. Configuración del Visor Web (Vercel)

### Pasos

1. Abre `visor_web/js/app.js` y configura:
   ```javascript
   const SUPABASE_URL = 'TU_SUPABASE_URL';
   const SUPABASE_ANON_KEY = 'TU_SUPABASE_ANON_KEY';
   ```

2. Despliega en Vercel:
   - Crea cuenta en [Vercel](https://vercel.com)
   - Importa el proyecto o arrastra la carpeta `visor_web`
   - Se generará una URL como `https://tu-proyecto.vercel.app`

3. Actualiza la URL en la app Flutter para compartir enlaces:
   - Abre `lib/screens/deudores_screen.dart`
   - Busca `const baseUrl = 'https://tu-app.vercel.app'`
   - Reemplaza con tu URL de Vercel

---

## 4. Uso de la Aplicación

### Flujo del Administrador

1. **Crear Deudor**: Pestaña "Deudores" → botón "+"
2. **Registrar Deuda**: Botón "Nueva Deuda" → llenar formulario
3. **Compartir Enlace**: En la lista de deudores → "Compartir" o "Copiar enlace"

### Flujo del Deudor

1. Recibe el enlace por WhatsApp, SMS, etc.
2. Abre el enlace en cualquier navegador
3. Ve su lista de deudas y el total (solo lectura)

### Funcionamiento Offline

- Las deudas se guardan localmente inmediatamente
- Cuando hay conexión, se sincronizan automáticamente
- El indicador en la barra superior muestra el estado:
  - 🟢 Cloud ✓ = Conectado y sincronizado
  - 🟠 Cloud ↑ = Hay datos pendientes de sincronizar
  - 🟠 Cloud ✗ = Sin conexión

---

## Tecnologías Utilizadas

| Componente | Tecnología |
|------------|------------|
| App Móvil | Flutter + Dart |
| Offline Storage | Hive |
| Backend | Supabase (PostgreSQL) |
| Visor Web | HTML/CSS/JS puro |
| Hosting Web | Vercel |

---

## Licencia

Uso privado / personal.
