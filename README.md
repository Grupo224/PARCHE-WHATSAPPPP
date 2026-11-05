# WhatsApp CRM Fix (Frappe)

Kit para reparar la integración WhatsApp ⇄ Frappe CRM en una instalación nueva de Frappe/ERPNext.

Corrige los fallos reales que encontramos en producción/demo:

1. **`crm/api/whatsapp.py`** — mensajes de números con Lead existente devolvían `403 PermissionError` (el webhook corre como `Guest` y `get_assigned_users` hacía `check_permission("read")`).
2. **`frappe_whatsapp/utils/webhook.py`** — el webhook fallaba intermitentemente con `500 KeyError: 'entry'` (dependía de `frappe.local.form_dict`).
3. **Estados de CRM** — `New`, `Contacted`, etc. en inglés rompían el Server Script de vinculación.
4. **Server Script de vinculación** — el que crea/vincular el Lead desde el mensaje entrante (estado en español, sin chequeos de permiso, owner correcto).
5. **WhatsApp Settings** — sin `default_outgoing_account` no aparece la pestaña WhatsApp en el CRM.
6. **IDs de WhatsApp Account** — espacios sobrantes en `business_id`/`app_id` rompían la suscripción al webhook.

## Requisitos

- Frappe/ERPNext v15.
- Apps instaladas: `frappe_whatsapp`, `crm`, `payments`.
- `WhatsApp Account` configurada y `Active`.

## Instalación

### Paso 1 — Clonar

```bash
git clone https://github.com/Grupo224/PARCHE-WHATSAPPPP.git
cd PARCHE-WHATSAPPPP
```

### Paso 2 — Parches de código (una vez)

```bash
./apply.sh /ruta/al/bench     # ej: /home/erpnext/frappe
```

Hace respaldo automático (`*.bak-YYYYMMDD-HHMMSS`) de los dos archivos antes de parchear.

### Paso 3 — Configuración y datos (una vez por sitio)

Edita la sección CONFIG al inicio de `setup_whatsapp.py`:

```python
SITE = "app.altoplano.mx"
SITES_PATH = "/home/erpnext/frappe/sites"
LEAD_OWNER = "Administrator"
WHATSAPP_ACCOUNT = "Altoplano"
```

Ejecuta:

```bash
cd /ruta/al/bench/sites
../env/bin/python /ruta/al/setup_whatsapp.py
```

### Paso 4 — Reiniciar

```bash
cd /ruta/al/bench
bench --site TU_SITIO clear-cache
kill -TERM $(pgrep -f 'gunicorn.*frappe.app:application' | sort -n | head -1)
```

## Verificar

Enviar un evento de prueba al webhook:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://TU_DOMINIO/api/method/frappe_whatsapp.utils.webhook.webhook \
  -H "Content-Type: application/json" \
  -d '{"object":"whatsapp_business_account","entry":[{"id":"WABA_ID","changes":[{"field":"messages","value":{"messaging_product":"whatsapp","metadata":{"display_phone_number":"9993588642","phone_number_id":"PHONE_ID"},"contacts":[{"profile":{"name":"Prueba"},"wa_id":"5219990000000"}],"messages":[{"from":"5219990000000","id":"wamid.TEST1","timestamp":"1793830000","type":"text","text":{"body":"prueba"}}]}}]}]}'
```

Esperado: `200` y el mensaje aparece en `WhatsApp Message` vinculado al Lead.

## Nota sobre el Webhook en Meta

La URL del webhook y el verify token se configuran en la app de Meta:

- **Callback URL:** `https://TU_DOMINIO/api/method/frappe_whatsapp.utils.webhook.webhook`
- **Verify token:** el mismo valor de `webhook_verify_token` de la `WhatsApp Account`.

## Revertir los parches de código

```bash
cp apps/crm/crm/api/whatsapp.py.bak-* apps/crm/crm/api/whatsapp.py
cp apps/frappe_whatsapp/frappe_whatsapp/utils/webhook.py.bak-* apps/frappe_whatsapp/frappe_whatsapp/utils/webhook.py
```

## Estructura

```
patches/crm-whatsapp.patch              → fix 403 (get_assignees + blindaje notify_agent)
patches/frappe-whatsapp-webhook.patch   → fix 500 KeyError 'entry' (lectura robusta del JSON)
apply.sh                                → aplica ambos parches con respaldo
setup_whatsapp.py                       → estados en español + Server Script + Settings + IDs
README.md
```
