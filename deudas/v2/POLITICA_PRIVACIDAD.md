# Política de privacidad — Deudas (BORRADOR)

> **Borrador para revisión del dueño, sin publicar.** Escrito el 2026-09-24 como parte de la
> fase 7.2 de [`../PLAN_MULTIUSUARIO.md`](../PLAN_MULTIUSUARIO.md). Antes de publicarlo hay que:
> completar lo que está entre corchetes, revisarlo contra la Ley Orgánica de Protección de
> Datos Personales (LOPDP, Ecuador) y su reglamento (idealmente con alguien que sepa de
> derecho) y publicarlo en una URL pública (p. ej. en el visor: `/privacidad`), que es lo
> que pide la ficha de Play Store. Lo técnico de abajo describe cómo funciona hoy v2.

**Última actualización:** [fecha de publicación]

## 1. Quién es responsable de tus datos

[Nombre completo del responsable], [ciudad], Ecuador. Contacto para cualquier tema de
privacidad: **[correo de contacto]**.

## 2. Qué datos guardamos

| Dato | Para qué | De dónde sale |
|---|---|---|
| Correo electrónico | Iniciar sesión (enlace mágico o contraseña) | Lo das al registrarte |
| Nombre de perfil | Que tus contactos vinculados sepan quién les propone algo | Lo das al registrarte (o se toma del correo) |
| Tu libreta: contactos, deudas, pagos, notas y títulos | Llevar tus cuentas; es la función de la app | Lo anotas tú |
| Invitaciones, vínculos y propuestas | Ponerte de acuerdo con un contacto que también usa la app | Se crean cuando invitas, aceptas o respondes |
| IP de quien abre un enlace del visor, **cifrada con SHA-256** y borrada a la hora | Frenar abusos (límite de consultas por minuto) | La conexión |
| Intentos fallidos de canjear un código de invitación (sin el código) | Frenar a quien prueba códigos al azar | La conexión |

**No** usamos tus datos para publicidad, no los vendemos y no hacemos perfiles.

Los contactos que anotas en tu libreta (por ejemplo "Ana") son datos que tú ingresas sobre
otras personas. Eres responsable de anotarlos con su conocimiento.

## 3. Quién más ve tus datos

- **Nadie más ve tu libreta.** Cada usuario solo puede leer y escribir la suya; la base de
  datos lo hace cumplir con reglas de seguridad por fila.
- **Un contacto vinculado** (alguien a quien invitaste o que te invitó y aceptó) ve lo que
  le propones: monto, fecha, dirección y el título o nota de esa fila. Durante la
  conciliación inicial ve el monto, la fecha y la dirección de tu historial con él, **no**
  tus títulos.
- **El enlace del visor** que compartes con un contacto muestra a quien lo tenga el estado
  de cuenta con ese contacto. Puedes cambiar el enlace (el anterior deja de funcionar).
- **Proveedores:** la app guarda los datos en Supabase ([supabase.com](https://supabase.com)),
  con servidores en Estados Unidos (región us-east-2), lo que implica una transferencia
  internacional de datos. El visor se sirve desde Vercel. [Agregar Firebase si se
  implementan las notificaciones de la fase 7.1.]

## 4. Cuánto tiempo los guardamos

Mientras tengas la cuenta. Al borrarla (ver §5) se borra tu libreta completa en el momento.
Las copias de seguridad del proveedor se renuevan en [plazo, según el plan de Supabase].

Lo que un contacto vinculado ya aceptó está también en **su** libreta (como copia con la
dirección invertida) y es suyo: borrar tu cuenta no lo borra de la suya.

## 5. Tus derechos

Según la LOPDP tienes derecho de acceso, rectificación, eliminación, oposición,
portabilidad y a no ser objeto de decisiones automatizadas. En la app:

- **Acceso y portabilidad:** menú ⋮ → **"Exportar mis datos"** te da toda tu libreta en un
  archivo JSON.
- **Rectificación:** puedes editar cualquier fila tuya. Lo que ya acordaste con un contacto
  se cambia proponiéndoselo.
- **Eliminación:** menú ⋮ → **"Borrar mi cuenta"**. Se borra tu cuenta y toda tu libreta;
  tus vínculos se rompen.
- Para cualquier otra solicitud, escribe a **[correo de contacto]**. Respondemos en el
  plazo que marca la ley ([15 días]).

También puedes presentar un reclamo ante la Superintendencia de Protección de Datos
Personales.

## 6. Seguridad

Conexiones cifradas (HTTPS), contraseñas gestionadas por el proveedor de autenticación,
reglas de acceso por usuario en la base de datos y límites de uso contra abusos. Ningún
sistema es infalible: si detectamos una brecha que afecte tus datos, te avisaremos como
exige la ley.

## 7. Menores de edad

La app no está pensada para menores de [15] años.

## 8. Cambios

Si cambiamos esta política, lo avisaremos en la app antes de que el cambio aplique.
