# Altoplano WhatsApp para Frappe / ERPNext v15

Aplicación completa basada en **shridarpatil/frappe_whatsapp, rama master**, con los arreglos de `Grupo224/PARCHE-WHATSAPPPP` integrados en código y hooks nativos.

**Rama instalable: `version-15`. Nombre interno: `frappe_whatsapp`.**
La rama `main` conserva el kit anterior como historial. Esta rama no necesita `apply.sh`, ejecutar `setup_whatsapp.py`, editar archivos de CRM ni habilitar Server Scripts.

## Instalación nueva

Desde la carpeta de tu bench, con Frappe / ERPNext v15:

```console
bench get-app --branch version-15 https://github.com/Grupo224/PARCHE-WHATSAPPPP.git
bench --site TU_SITIO install-app frappe_whatsapp
bench --site TU_SITIO migrate
bench restart
```

Bench obtiene el nombre `frappe_whatsapp` de `pyproject.toml` y renombra la carpeta clonada. No se instala con el nombre del repositorio.

Después, abre **WhatsApp Account**, registra tus credenciales de Meta y activa la cuenta. En **WhatsApp Settings**, selecciona cuentas de entrada/salida si tienes varias. Con una sola cuenta activa los valores por defecto se completan automáticamente. La instalación no crea tokens, no suscribe apps en Meta y no envía mensajes.

Frappe CRM es opcional para la integración base. Para usar la pestaña WhatsApp y crear leads se necesita la versión de `crm` que usa los DocTypes **WhatsApp Message / WhatsApp Settings / WhatsApp Account** (rama `main` de CRM consultada al implementar). La nueva integración `whatsapp` de CRM `develop`, que utiliza **WA Message / WA Account**, es otra aplicación y no es intercambiable con esta.

## Interfaz de chat en Desk

`whatsapp_chat` es la app compañera de interfaz. Se revisó la rama `develop` y se conserva como aplicación independiente:

```console
bench get-app --branch develop https://github.com/shridarpatil/whatsapp_chat.git
bench --site TU_SITIO install-app whatsapp_chat
bench build --app whatsapp_chat
bench restart
```

Instala primero `frappe_whatsapp`. No vuelvas a instalar el chat si ya está instalado. La burbuja de chat se muestra en Desk; la pestaña de CRM depende de la versión de Frappe CRM.

## Si frappe_whatsapp ya está instalada

Esta rama **reemplaza el origen del código de la misma app**; no es una segunda app con otro nombre. No desinstales `frappe_whatsapp` ni borres sus DocTypes. Cambiar su código afecta a todos los sitios del mismo bench que la utilizan.

Primero respalda los sitios y revisa si tienes modificaciones locales:

```console
bench --site TU_SITIO backup --with-files
git -C apps/frappe_whatsapp status --short
git -C apps/frappe_whatsapp remote -v
```

Si hay cambios locales, guárdalos/revísalos antes de cambiar de rama. No uses `reset --hard` ni `get-app --overwrite` para saltarte esa revisión. Los respaldos de sitio no incluyen tus modificaciones de código.

Si la copia está limpia y su remote habitual se llama `upstream` (el nombre habitual de Bench):

```console
git -C apps/frappe_whatsapp remote set-url upstream https://github.com/Grupo224/PARCHE-WHATSAPPPP.git
git -C apps/frappe_whatsapp fetch upstream version-15
git -C apps/frappe_whatsapp switch -c altoplano-version-15 --track upstream/version-15
bench setup requirements --python
bench --site TU_SITIO migrate
bench build --app frappe_whatsapp
bench restart
```

Si tu remote tiene otro nombre, sustituye `upstream` por el nombre observado. Conserva el URL y el commit anteriores si necesitas volver. No cambies `crm` ni `whatsapp_chat` para aplicar estos arreglos. Ejecuta `migrate` por cada sitio que use esta app.

## Qué cambia

| Kit anterior | Implementación nativa |
| --- | --- |
| Parche manual de `webhook.py` | JSON desde el cuerpo cuando `form_dict` no contiene `entry`; errores de envoltura devuelven 400; callbacks vacíos se aceptan. |
| Lectura del primer evento | Se procesan todos los `entry` / `changes`, los perfiles por remitente y todos los estados del lote. |
| `403` al notificar desde Guest | Adaptador privado del notificador CRM: utiliza `get_assignees` dentro de una copia aislada de su contexto. La API pública `get_assigned_users` conserva sus verificaciones. |
| Server Script de vinculación | Método Python de la app antes de insertar el mensaje; crea o vincula el lead sin requerir Server Scripts. |
| Estado fijo en español | Respeta el estado configurado; si está vacío usa `Nuevo`, `New` o el primer estado existente. No renombra el pipeline. |
| Cuenta y dominio fijos | Configuración por sitio; las cuentas elegidas se conservan. Varias cuentas sin selección requieren elegir en Settings. |
| IDs con espacios | Normalización de `phone_id`, `business_id`, `app_id` en instalación/migración y antes de guardar cuentas. |

El webhook conserva la ruta:

```text
https://TU_DOMINIO/api/method/frappe_whatsapp.utils.webhook.webhook
```

Los mensajes entrantes se aceptan solo para un `phone_id` que corresponda a una cuenta **Active** del sitio. Un ID desconocido no cae en la cuenta predeterminada. Los callbacks de plantilla sin metadata continúan funcionando.

Los reenvíos secuenciales de un `message_id` ya guardado se omiten. Esto no introduce un índice único ni garantiza exclusión de duplicados ante solicitudes simultáneas. La vinculación conserva el teléfono completo con código de país; deja de reducirlo indiscriminadamente a diez dígitos.

## Configuración de leads

En **WhatsApp Settings → Altoplano CRM**:

- **Create Leads from Incoming WhatsApp Messages:** activado por defecto; se puede desactivar.
- **New Lead Owner:** `Administrator` por defecto; cambia a un usuario de sistema activo.
- **New Lead Status:** nombre exacto de un estado existente; vacío activa la resolución anterior.

Se conservan referencias ya encontradas por CRM. Solo se crean leads para mensajes entrantes sin referencia y con CRM instalada. Las validaciones/campos obligatorios personalizados de CRM siguen aplicándose.

La migración desactiva el Server Script anterior **Vincular WhatsApp a Cliente Potencial** solo si detecta el código del kit conocido. Conserva el documento y su contenido para revisión y rollback. Scripts personalizados con otra lógica se mantienen y deben revisarse para evitar solapamientos.

## Actualizaciones

```console
bench update --apps frappe_whatsapp
```

El remote y la rama de seguimiento deben apuntar a esta variante. Las futuras actualizaciones upstream deben incorporarse a `version-15`; cambiar al upstream original elimina estos cambios.

## Verificación

Pruebas de regresión locales:

```console
python -m unittest discover -s tests -v
```

Pruebas sobre límites simulados de Frappe: JSON bruto/parseado/inválido/vacío, lotes, estados sin mensaje local, cuentas desconocidas, reenvíos, referencias CRM, estado inglés/español, permisos de notificaciones y configuración repetible.

El paquete se construye como wheel y sdist. **No se ejecutó `bench install-app` en un sitio real ni una prueba de Meta desde este entorno**: no hay MariaDB, Redis ni un sitio Frappe conectado. Antes de usarla en producción, valida en un sitio de pruebas:

1. `install-app` en un sitio nuevo y `migrate` dos veces.
2. Un mensaje real de número nuevo: un lead y una referencia en WhatsApp Message.
3. Otro mensaje del mismo número: misma referencia, sin `403`.
4. Entregado/leído y una actualización de plantilla.
5. Pestaña de CRM y burbuja de chat; prueba cada cuenta si hay varias.
6. Instalación de CRM después de esta app, si ese es tu orden de despliegue.

## Procedencia y licencia

Base: `shridarpatil/frappe_whatsapp` `master`, commit `08bc1f6af2e36022d7a5f77641c8ba2ef8c16aaa`.
Interfaz consultada: `shridarpatil/whatsapp_chat` `develop`, commit `4ad3712528e9a56b536bccd190231663f04b8e7b`; no se copia su código en esta app.
Kit de origen: `Grupo224/PARCHE-WHATSAPPPP` `main`, commit `3d81d2c620b15f06967672321ce2bba34c6c11a2`.

Se conserva la autoría y `license.txt` del proyecto base. El notificador de CRM se reutiliza desde la instalación existente; su código no se distribuye en esta app. Las referencias históricas de upstream están en `README.upstream.md`.
