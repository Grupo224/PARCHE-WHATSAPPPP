# Parche de código WhatsApp para Frappe CRM

Este paquete corrige dos fallos del código de integración de WhatsApp en instalaciones Frappe/ERPNext v15 con **`crm` y `frappe_whatsapp` ya instaladas**:

- Un `403 PermissionError` al procesar mensajes de un número asociado a un Lead existente.
- Un `500 KeyError: 'entry'` cuando el cuerpo JSON del webhook no aparece en `frappe.local.form_dict`.

El instalador **solo modifica dos archivos de código** en el bench y guarda respaldos. No ejecuta `setup_whatsapp.py`, no configura sitios ni cuentas de WhatsApp, no cambia estados y no importa datos. El archivo de configuración específico de la instalación original fue retirado de este paquete. La operación normal del webhook, una vez configurado por el administrador, sí puede crear mensajes o Leads conforme a las apps instaladas.

## Requisitos

- Bench Frappe/ERPNext v15 en Linux con las apps `crm` y `frappe_whatsapp` instaladas.
- Comando `patch` disponible.
- Versiones de esas apps compatibles con los dos archivos `.patch`. Si no coinciden, el instalador se detiene antes de modificar el bench.
- Una cuenta propia de WhatsApp Business configurada por el administrador para utilizar el webhook. Este paquete no proporciona credenciales ni cuentas.

## Aplicación

```bash
git clone https://github.com/Grupo224/PARCHE-WHATSAPPPP.git
cd PARCHE-WHATSAPPPP
./apply.sh /ruta/al/bench
cd /ruta/al/bench
bench restart
```

`apply.sh` valida **ambos** parches antes de escribir. Si uno ya se aplicó o no corresponde a la versión instalada, termina sin cambios; no lo fuerces. Guarda respaldos `*.bak-AAAAMMDD-HHMMSS` junto a cada archivo modificado.

Para un sitio nuevo, configura tu propia `WhatsApp Account`, la URL y el token del webhook siguiendo la documentación de las apps que instalaste. No ejecutes ningún script de configuración de la versión anterior de este repositorio.

## Reversión

Restaura los dos archivos desde los respaldos que `apply.sh` imprimió y ejecuta `bench restart`. Si hay otros cambios locales posteriores en esos archivos, revísalos antes de restaurar.

## Alcance

| Archivo del bench | Corrección |
| --- | --- |
| `apps/crm/crm/api/whatsapp.py` | Consulta asignados sin exigir permiso de lectura al usuario Guest y evita que un error de permiso en la notificación interrumpa el webhook. |
| `apps/frappe_whatsapp/frappe_whatsapp/utils/webhook.py` | Lee el cuerpo JSON cuando `form_dict` no contiene `entry`. |

Una instalación con **solo ERPNext** no incluye estas integraciones: primero deben instalarse `crm` y `frappe_whatsapp` en el bench y en el sitio correspondiente.

