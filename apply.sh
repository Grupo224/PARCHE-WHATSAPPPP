#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Uso: ./apply.sh /ruta/al/bench" >&2
  exit 2
fi

BENCH="${1%/}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRM="$BENCH/apps/crm/crm/api/whatsapp.py"
WHATSAPP="$BENCH/apps/frappe_whatsapp/frappe_whatsapp/utils/webhook.py"
CRM_PATCH="$DIR/patches/crm-whatsapp.patch"
WHATSAPP_PATCH="$DIR/patches/frappe-whatsapp-webhook.patch"

for file in "$CRM" "$WHATSAPP" "$CRM_PATCH" "$WHATSAPP_PATCH"; do
  if [ ! -f "$file" ]; then
    echo "No encontrado: $file" >&2
    exit 1
  fi
done

# Comprobar ambos parches antes de cambiar cualquier archivo del bench.
for patch_file in "$CRM_PATCH" "$WHATSAPP_PATCH"; do
  if ! patch --batch --forward --dry-run -p1 -d "$BENCH" < "$patch_file" >/dev/null 2>&1; then
    echo "El parche no coincide con esta versión o ya fue aplicado: $patch_file" >&2
    echo "No se modificó ningún archivo. Revisa la versión de crm/frappe_whatsapp." >&2
    exit 1
  fi
done

timestamp="$(date +%Y%m%d-%H%M%S)"
cp -a "$CRM" "$CRM.bak-$timestamp"
cp -a "$WHATSAPP" "$WHATSAPP.bak-$timestamp"

patch --batch --forward -p1 -d "$BENCH" < "$CRM_PATCH"
patch --batch --forward -p1 -d "$BENCH" < "$WHATSAPP_PATCH"

echo "Parches de código aplicados. Respaldos:"
echo "  $CRM.bak-$timestamp"
echo "  $WHATSAPP.bak-$timestamp"
echo "Reinicia los procesos del bench con: cd \"$BENCH\" && bench restart"
echo "No se modificaron sitios, cuentas de WhatsApp, estados ni datos de CRM."

