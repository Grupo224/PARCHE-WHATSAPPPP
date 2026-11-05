#!/usr/bin/env python3
"""
Reparación completa de la integración WhatsApp <-> Frappe CRM.

Se ejecuta UNA vez por sitio nuevo. Es idempotente (puede re-ejecutarse).

Uso:
    cd /ruta/al/bench/sites
    ../env/bin/python /ruta/al/setup_whatsapp.py

Hace:
1. Renombra los estados de CRM Lead / CRM Deal al español.
2. Crea/actualiza el Server Script que vincula mensajes entrantes a Leads.
3. Configura WhatsApp Settings (cuenta por defecto entrada/salida).
4. Normaliza los IDs de WhatsApp Account (quita espacios sobrantes).
"""

import frappe

# ================= CONFIG =================
SITE = "app.altoplano.mx"                     # nombre del sitio
SITES_PATH = "/home/erpnext/frappe/sites"     # ruta al directorio sites del bench
LEAD_OWNER = "Administrator"                  # usuario dueño de los leads creados por el webhook
WHATSAPP_ACCOUNT = "Altoplano"                # nombre de la WhatsApp Account
# ===========================================

LEAD_STATUS = [
    ("New", "Nuevo"),
    ("Contacted", "Contactado"),
    ("Nurture", "En seguimiento"),
    ("Qualified", "Calificado"),
    ("Unqualified", "No calificado"),
    ("Converted", "Convertido"),
    ("Junk", "Descartado"),
]
DEAL_STATUS = [
    ("Qualification", "Calificación"),
    ("Demo/Making", "Demostración"),
    ("Proposal/Quotation", "Propuesta/Cotización"),
    ("Negotiation", "Negociación"),
    ("Ready to Close", "Listo para cerrar"),
    ("Won", "Ganado"),
    ("Lost", "Perdido"),
]

SERVER_SCRIPT_NAME = "Vincular WhatsApp a Cliente Potencial"

# __LEAD_OWNER__ se reemplaza por LEAD_OWNER al guardar.
SERVER_SCRIPT = '''tel = ""
for ch in (doc.get("from") or doc.get("to") or ""):
    if ch.isdigit():
        tel = tel + ch
if len(tel) > 10:
    tel = tel[-10:]

if tel and not doc.get("reference_name"):
    filas = frappe.db.get_all("CRM Lead", fields=["name", "mobile_no", "phone"], limit_page_length=0)
    hallado = ""
    for f in filas:
        num_m = "".join(c for c in (f.get("mobile_no") or "") if c.isdigit())
        num_p = "".join(c for c in (f.get("phone") or "") if c.isdigit())
        if len(num_m) > 10:
            num_m = num_m[-10:]
        if len(num_p) > 10:
            num_p = num_p[-10:]
        if (num_m and num_m == tel) or (num_p and num_p == tel):
            hallado = f.get("name")
            break

    if hallado:
        frappe.db.set_value("WhatsApp Message", doc.name, "reference_doctype", "CRM Lead", update_modified=False)
        frappe.db.set_value("WhatsApp Message", doc.name, "reference_name", hallado, update_modified=False)
    else:
        etiqueta = doc.get("profile_name") or ""
        if not etiqueta:
            etiqueta = "WhatsApp " + tel
        numero = doc.get("from") or doc.get("to")
        estado = frappe.db.get_value("CRM Lead Status", {"name": "Nuevo"}, "name")
        if not estado:
            estado = frappe.db.get_value("CRM Lead Status", {}, "name")
        nuevo = frappe.get_doc({
            "doctype": "CRM Lead",
            "first_name": etiqueta,
            "lead_name": etiqueta,
            "mobile_no": numero,
            "phone": numero,
            "status": estado,
            "lead_owner": "__LEAD_OWNER__",
        })
        nuevo.insert(ignore_permissions=True)
        frappe.db.set_value("CRM Lead", nuevo.name, "owner", "__LEAD_OWNER__", update_modified=False)
        frappe.db.set_value("WhatsApp Message", doc.name, "reference_doctype", "CRM Lead", update_modified=False)
        frappe.db.set_value("WhatsApp Message", doc.name, "reference_name", nuevo.name, update_modified=False)
'''


def rename_statuses():
    for doctype, pairs in (("CRM Lead Status", LEAD_STATUS), ("CRM Deal Status", DEAL_STATUS)):
        for old, new in pairs:
            if frappe.db.exists(doctype, old):
                frappe.rename_doc(doctype, old, new, merge=False)
                print("   %s: %s -> %s" % (doctype, old, new))
    print("1) Estados renombrados.")


def ensure_server_script():
    if frappe.db.exists("Server Script", SERVER_SCRIPT_NAME):
        ss = frappe.get_doc("Server Script", SERVER_SCRIPT_NAME)
    else:
        ss = frappe.get_doc({"doctype": "Server Script", "name": SERVER_SCRIPT_NAME})
    ss.script_type = "DocType Event"
    ss.reference_doctype = "WhatsApp Message"
    ss.doctype_event = "After Insert"
    ss.event_frequency = "All"
    ss.disabled = 0
    ss.script = SERVER_SCRIPT.replace("__LEAD_OWNER__", LEAD_OWNER)
    ss.flags.ignore_permissions = True
    ss.save(ignore_permissions=True)
    print("2) Server Script listo:", SERVER_SCRIPT_NAME)


def configure_whatsapp_settings():
    if not frappe.db.exists("DocType", "WhatsApp Settings"):
        print("2b) (sin DocType WhatsApp Settings, se omite)")
        return
    doc = frappe.get_doc("WhatsApp Settings")
    changed = False
    for f in ("default_incoming_account", "default_outgoing_account"):
        if doc.has_field(f) and not doc.get(f):
            doc.set(f, WHATSAPP_ACCOUNT)
            changed = True
    if changed:
        doc.flags.ignore_permissions = True
        doc.save(ignore_permissions=True)
        print("3) WhatsApp Settings: cuenta por defecto ->", WHATSAPP_ACCOUNT)
    else:
        print("3) WhatsApp Settings ya configurado.")


def normalize_whatsapp_account():
    if not frappe.db.exists("WhatsApp Account", WHATSAPP_ACCOUNT):
        print("4) (WhatsApp Account no existe:", WHATSAPP_ACCOUNT + ")")
        return
    acc = frappe.get_doc("WhatsApp Account", WHATSAPP_ACCOUNT)
    changed = False
    for f in ("business_id", "app_id", "phone_id"):
        v = acc.get(f)
        if v and v != v.strip():
            acc.set(f, v.strip())
            changed = True
    if changed:
        acc.flags.ignore_permissions = True
        acc.save(ignore_permissions=True)
        print("4) IDs de WhatsApp Account normalizados.")
    else:
        print("4) IDs de WhatsApp Account ya correctos.")


def main():
    frappe.init(site=SITE, sites_path=SITES_PATH)
    frappe.connect()
    try:
        rename_statuses()
        ensure_server_script()
        configure_whatsapp_settings()
        normalize_whatsapp_account()
        frappe.db.commit()
        print()
        print("Listo. Reinicia gunicorn:")
        print("  bench --site %s clear-cache" % SITE)
        print("  kill -TERM $(pgrep -f 'gunicorn.*frappe.app:application' | sort -n | head -1)")
    finally:
        frappe.destroy()


if __name__ == "__main__":
    main()
