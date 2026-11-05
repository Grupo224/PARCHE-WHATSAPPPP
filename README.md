# WhatsApp CRM Fix (Frappe)

Parches para reparar la integración WhatsApp ⇄ Frappe CRM en instalaciones de Frappe/ERPNext.

## Qué corrige

1. **`crm/api/whatsapp.py`** — los mensajes entrantes de números que ya tienen un Lead devolvían `403 PermissionError` (el webhook corre como `Guest` y `get_assigned_users` hacía `check_permission("read")` sobre `CRM Lead`). Se cambia por `get_assignees` y se blinda `notify_agent`.

2. **`frappe_whatsapp/utils/webhook.py`** — el webhook fallaba intermitentemente con `500 KeyError: 'entry'` porque dependía de `frappe.local.form_dict`. Ahora lee el cuerpo JSON de forma robusta.

## Aplicar

```bash
./apply.sh /ruta/al/bench
```

Ejemplo:

```bash
./apply.sh /home/erpnext/frappe
```

El script hace respaldo automático (`*.bak-YYYYMMDD-HHMMSS`) de los dos archivos antes de parchear.

## Reiniciar

```bash
cd /ruta/al/bench
bench --site TU_SITIO clear-cache
kill -TERM $(pgrep -f 'gunicorn.*frappe.app:application' | sort -n | head -1)
```

## Verificar

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  https://TU_DOMINIO/api/method/frappe_whatsapp.utils.webhook.webhook \
  -H "Content-Type: application/json" \
  -d '{"object":"whatsapp_business_account","entry":[{"id":"WABA_ID","changes":[{"field":"messages","value":{"messaging_product":"whatsapp","metadata":{"display_phone_number":"9993588642","phone_number_id":"PHONE_ID"},"contacts":[{"profile":{"name":"Prueba"},"wa_id":"5219990000000"}],"messages":[{"from":"5219990000000","id":"wamid.TEST1","timestamp":"1793830000","type":"text","text":{"body":"prueba"}}]}}]}]}'
```

Esperado: `200` y el mensaje aparece en `WhatsApp Message` vinculado al Lead.

## Requisitos

- Apps `frappe_whatsapp` y `crm` instaladas.
- `WhatsApp Account` configurada y `Active`.
- `WhatsApp Settings` con `default_outgoing_account` apuntando a la cuenta (para que aparezca la pestaña WhatsApp en el CRM).

## Revertir

```bash
cp apps/crm/crm/api/whatsapp.py.bak-* apps/crm/crm/api/whatsapp.py
cp apps/frappe_whatsapp/frappe_whatsapp/utils/webhook.py.bak-* apps/frappe_whatsapp/frappe_whatsapp/utils/webhook.py
```
