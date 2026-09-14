# Arquitectura y Lógica del Sistema de Deudas

Este documento describe a detalle la arquitectura, los modelos de datos y la lógica de negocio detrás del Ecosistema de Deudas (App Flutter, Backend Supabase, y Visor Web).

El objetivo del sistema es llevar un registro claro de "quién le debe a quién", permitiendo cobros parciales, cruce de cuentas automático y funcionamiento "offline-first".

---

## 1. Arquitectura General

El proyecto está compuesto por tres ejes principales:

1. **App Móvil (Flutter):**
   - **Offline-First:** Utiliza `Hive` como base de datos local súper rápida. Todas las lecturas y escrituras suceden aquí instantáneamente.
   - **Sincronización:** Un `SyncService` corre en segundo plano y envía los datos pendientes a Supabase cuando hay conexión.
   - Es el "Panel de Administración" principal donde se crean deudores, deudas y se registran pagos.

2. **Backend Base de Datos (Supabase / PostgreSQL):**
   - Almacena la verdad absoluta en la nube.
   - Utiliza Vistas (`vista_estado_deudas`) para delegar al motor matemático la suma de los detalles de pagos.

3. **Visor Web (Vanilla HTML/JS/CSS):**
   - Interfaz de solo lectura en la nube para que el usuario pueda compartir un enlace (`?token=XYZ`) a sus deudores y estos vean su estado de cuenta en tiempo real, replicando las mismas reglas de visualización de la app.

---

## 2. Modelos de Datos

El diseño de la base de datos se basa en 4 tablas fundamentales que separan la "obligación" de su "liquidación".

### A. Deudores (Entidades)
Personas o contactos con los que interactúas económicamente.
- `id`, `nombre`, `token` (para el visor web).

### B. Deudas (Obligaciones / Facturas)
Cada vez que prestas dinero, pagas algo por alguien, o alguien paga algo por ti.
- `monto`: El valor original de la deuda.
- `esMiDeuda`: Estipula la dirección del flujo. `true` (Yo debo pagarle), `false` (Él me debe pagar).
- *Nota vital:* Esta tabla NO guarda si la deuda "está pagada". Eso se calcula dinámicamente.

### C. Pagos (Ingreso/Egreso de Dinero Físico/Virtual)
Representa un billete o transferencia global que se mueve de un lado al otro.
- `monto_total`: Cantidad del pago.
- `es_compensacion`: Si es `true`, significa que es un pago fantasma (virtual) creado por el sistema para "cruzar deudas" sin que el dinero físico se haya movido.

### D. Detalles de Pago (Asignación)
Tabla puente (`detalle_pagos`). Relaciona CADA dólar de un Pago con UNA Deuda específica.
- `pagoId`, `deudaId`, `monto_asignado`.
- Gracias a esta tabla, si haces un pago de $10 y tienes dos deudas de $5, el sistema divide el pago global en dos detalles de $5 que apuntan a cada deuda.

---

## 3. Motor Central: Lógica de Negocio

El corazón inteligente de la app es cómo se calculan y se cruzan las deudas en `database_service.dart`.

### 3.1. Estado Dinámico
Para saber el estado de una deuda, el sistema suma todos sus `detalle_pagos` correspondientes y los resta del `monto` original. 
Si el saldo restante es `>= 0.01` la deuda sigue viva.

### 3.2. Cruce Automático de Cuentas (Netting)
Si tienes un Deudor al que le debes dinero (`esMiDeuda = true`), pero él también te debe dinero a ti (`esMiDeuda = false`), no tiene sentido pasarse billetes físicamente. 
**El Sistema interviene ANTES de cualquier pago físico (`compensarDeudas`):**
1. Suma el total de "Mis Deudas".
2. Suma el total de "Sus Deudas".
3. Calcula el solapamiento: `Mínimo de ambos totales`.
4. Crea pagos **virtuales** (`esCompensacion = true`) en ambas direcciones por ese monto mínimo.
5. Asigna esos pagos a través de detalles hasta agotar ese monto, de la deuda más antigua a la más reciente (FIFO en cada lado).
*El resultado es que las deudas opuestas se "matan" entre sí automáticamente.*

### 3.2.1. Con deudas elegidas a mano, el pago va antes que el cruce
El FIFO del cruce se lleva por delante las deudas más viejas, y eso choca con querer pagar
una deuda concreta: si el cruce se aplica primero, ya se comió parte de ella, así que
pagabas de más, o pagabas una que se iba a anular sola mientras otra quedaba viva.

Por eso, cuando el pago lleva **deudas elegidas** (`p_deudas_ids` en `registrar_pago`), el
orden se invierte:

1. **El pago se reparte solo entre las elegidas** del lado de quien paga, de la más
   antigua a la más reciente, hasta lo que de verdad les falta (neto del saldo a favor ya
   entregado). Una deuda del otro lado no recibe nada.
2. **Lo que sobre es saldo a favor** de quien pagó, y como todo saldo a favor abona sus
   otras deudas pendientes. La app pide confirmación antes de registrarlo.
3. **El cruce se calcula después**, sobre lo que quedó, en **FIFO puro**: la más antigua
   primero, aunque sea una elegida que el pago no alcanzó a completar.

> Tú debes Cena $40 (vieja) y Gasolina $30; él te debe $15.
> - Sin pago, el cruce tapa $15 de Cena.
> - Eliges Cena y pagas $30: Cena queda en $10, el cruce tapa esos $10 y los $5 que
>   sobran van a Gasolina. **Cena saldada, Gasolina en $25.**
> - Eliges Cena y pagas $10: Cena queda en $30 y el cruce igual le pone sus $15 (queda en $15).
> - Eliges Cena y pagas $50: $40 a Cena, $10 de saldo a favor que abona Gasolina, y el
>   cruce de $15 cae en Gasolina.

Sin deudas elegidas (modo automático) todo sigue como siempre: cruce primero y el pago
FIFO sobre el lado de quien paga.

La vista previa sale de la misma función: `estado_cuenta(p_deudor_id, p_pov, p_pago)` con
`p_pago = {monto, es_mi_pago, deudas_ids}` devuelve el estado tal como quedaría (con
`pago_planeado` por deuda y el `sobrante`), sin escribir nada, y `registrar_pago` escribe
los detalles leyendo ese mismo cálculo. La edge `get_estado_cuenta` lo expone con `pago`.
Verificación: `scripts/probar_pago_manual.py` (escenarios) y el fixture de paridad de la
app (`scripts/generar_casos_plan_pago.py`).

### 3.2.2. Editar el cruce de la última operación
El cruce se aplica solo al registrar un pago, y a veces cruza deudas que uno quería dejar
pendientes todavía. `editar_cruce(p_cruce_id, p_excluir, p_simular, p_idem_key)` las saca:

1. **El pago real no se toca.** Solo cambian los dos pagos virtuales del cruce y sus detalles.
2. **El cruce se recorta para que cuadre.** Sin las deudas excluidas, el cruce nuevo es lo
   que quede en el lado más chico; el lado más grande se recorta desde la deuda más
   reciente. Nunca se agregan deudas que no estaban en el cruce. `p_excluir = NULL`
   deshace el cruce entero; si queda en $0, los dos pagos virtuales se borran.
3. **Solo el cruce de la última operación**: ningún pago ajeno al cruce registrado más de
   5 s después (una operación posterior se calculó encima de él).
4. Como el cruce se deriva del estado, lo que se saca vuelve al cruce sugerido y **se cruza
   en el siguiente pago**.

> Cruce de $15. Tu lado: Cena $15. Su lado: Taxi $10 + Uber $5.
> Sacas Uber: su lado queda en $10, el cruce baja a $10 (Cena $10 con Taxi $10).
> Quedan pendientes Uber $5 y $5 de Cena. El neto no cambia.

Ojo: si quien pagó tiene saldo a favor, ese crédito abona solo sus deudas pendientes, así
que una deuda reabierta puede seguir viéndose saldada. La vista previa lo avisa.

`p_simular` hace lo mismo dentro de un subbloque que se revierte y devuelve el estado tal
como quedaría: vista previa y escritura son el mismo código. Cada edición real queda en la
tabla `cruces_editados` (antes y después: basta para restaurarla a mano), que además da la
idempotencia por `idem_key`. Web: botón «Editar» en el cruce del estado de cuenta. App:
icono en el detalle del deudor (solo con conexión y sin cambios pendientes de subir).
Verificación: `scripts/probar_editar_cruce.py [--replica]`.

### 3.3. Sincronización en la App (`SyncService`)
Cada objeto (`Deuda`, `Pago`, etc.) tiene una bandera `synced`.
- Cuando creas un objeto y estás desconectado, se guarda en el celular con `synced = false`.
- El servicio en segundo plano hace polling (o reacciona cundo vuelve el internet).
- Lee los que tienen `synced = false`, hace un bulk insert/update (Hacia Supabase vía UPSERT), y si el servidor responde con 200 OK, la app los marca como `synced = true`.
- Al bajar (`pullFromServer`, `refrescarDeudorDesdeServidor`) se **borran** los pagos y
  detalles ya sincronizados que el servidor ya no tiene (un cruce editado o deshecho). Lo
  que aún no se subió no se toca, y si una tabla llega al tope de 1000 filas no se poda.

---

## 4. Diseño de Estructura e Interfaz de Usuario (UI/UX)

La UI se diseñó buscando un sentimiento Premium (`AppTheme`: colores Neón, fondos oscuros *Navy*, sombras con blur y glassmorphism).

### Pantalla Saldar Cuentas (Caja de Pago)
Maneja una distribución matemática avanzada en tiempo real:
- **Prioridad Visual:** Arriba aparecen siempre las deudas activas que están exigiéndote un pago.
- **Selección manual:** solo se marcan deudas del lado de quien paga (incluidas las que hoy
  tapa el cruce entero). Al marcar o escribir el monto, la tarjeta se recalcula **al
  instante** con `PlanPago` (Dart, espejo de la función SQL según §3.2.1) y enseguida se
  confirma con `get_estado_cuenta` + `pago`; si difieren, gana el servidor. El botón de
  confirmar se bloquea hasta que llega esa confirmación, así lo que se ve es lo que
  `registrar_pago` escribe. Si el pago supera lo que necesitan las elegidas, un diálogo
  pide confirmar el sobrante como saldo a favor. El orden de las tarjetas se congela en la
  primera carga para que las casillas no salten bajo el dedo.
- **Opacidad:** Tras realizar la matemática temporal en Dart, si la app advierte que la deuda se va a aniquilar por un "Cruce" (compensada), manda esa tarjeta al fondo de la lista, reduce su opacidad al 40% y la tacha para que el usuario entienda que *"El sistema la eliminó sola, no te preocupes por ella"*.
- **Desglose de Pago:** La tarjeta muestra transparentemente el "Saldo Original", luego descuenta lo que se va de "Cruce Automático", e indica finalmente si requirió "Dinero de tu pago" para saldarse.

### Visor Web (`visor_web/js/app.js`)
Puesto que es un cliente tonto conectado vía API REST simple, el visor hace toda la **magia en el frontend**:
1. Descarga el listado de Deudas, Pagos y Detalles.
2. Ejecuta un script en Javascript (`processDebts()`) idéntico a las matemáticas en Dart de la app.
3. Encuentra las interjecciones, separa las deudas compensadas de las cobrables reales, y renderiza la pantalla usando el mismo algoritmo visual, logrando tener un espejo preciso de la App Móvil sin depender de computación costosa en la nube.

---
*Documento generado para referencia arquitectónica y mantenimiento futuro de Ecosistema Deudas.*
