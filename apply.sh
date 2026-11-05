#!/usr/bin/env bash
set -euo pipefail

BENCH="${1:-}"

if [ -z "$BENCH" ]; then
  echo "Uso: ./apply.sh /ruta/al/bench"
  echo "Ej:  ./apply.sh /home/erpnext/frappe"
  exit 1
fi

if [ ! -d "$BENCH/apps/crm" ] || [ ! -d "$BENCH/apps/frappe_whatsapp" ]; then
  echo "No parece un bench de Frappe (falta apps/crm o apps/frappe_whatsapp): $BENCH"
  exit 1
fi

DIR="$(cd "$(dirname "$0")" && pwd)"
TS="$(date +%Y%m%d-%H%M%S)"

CRM="$BENCH/apps/crm/crm/api/whatsapp.py"
WH="$BENCH/apps/frappe_whatsapp/frappe_whatsapp/utils/webhook.py"

for f in "$CRM" "$WH"; do
  [ -f "$f" ] || { echo "No encontrado: $f"; exit 1; }
  cp -a "$f" "$f.bak-$TS"
done

echo "Aplicando crm-whatsapp.patch ..."
patch -p1 -d "$BENCH" < "$DIR/patches/crm-whatsapp.patch"

echo "Aplicando frappe-whatsapp-webhook.patch ..."
patch -p1 -d "$BENCH" < "$DIR/patches/frappe-whatsapp-webhook.patch"

echo
echo "Listo. Respaldos: $CRM.bak-$TS  y  $WH.bak-$TS"
echo "Reinicia gunicorn para cargar los cambios:"
echo "  cd $BENCH"
echo "  bench --site TU_SITIO clear-cache"
echo "  kill -TERM $(pgrep -f 'gunicorn.*frappe.app:application' | sort -n | head -1)"
