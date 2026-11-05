"""Idempotent, site-local setup invoked by install-app and migrate."""
import frappe

LEGACY_SCRIPT = "Vincular WhatsApp a Cliente Potencial"


def after_install():
    configure()


def after_migrate():
    configure()


def after_app_install(app_name):
    if app_name == "crm":
        configure()


def configure():
    if not frappe.db.exists("DocType", "WhatsApp Settings"):
        return
    # No Meta requests, tokens, hardcoded domains or manual commits here.
    for account in frappe.get_all("WhatsApp Account", pluck="name"):
        for field in ("business_id", "app_id", "phone_id"):
            value = frappe.db.get_value("WhatsApp Account", account, field)
            if value and value != value.strip():
                frappe.db.set_value("WhatsApp Account", account, field, value.strip(), update_modified=False)
    configure_defaults()
    disable_legacy_script()


def disable_legacy_script():
    if not frappe.db.exists("DocType", "Server Script") or not frappe.db.exists("Server Script", LEGACY_SCRIPT):
        return
    script = frappe.get_doc("Server Script", LEGACY_SCRIPT)
    # Preserve the body for rollback, and only retire the known patch script.
    body = script.get("script") or ""
    markers = ('filas = frappe.db.get_all("CRM Lead"', 'tel = tel[-10:]', 'nuevo.insert(ignore_permissions=True)')
    if script.get("reference_doctype") == "WhatsApp Message" and all(m in body for m in markers):
        frappe.db.set_value("Server Script", LEGACY_SCRIPT, "disabled", 1)


def configure_defaults(doc=None, method=None):
    """Preserve explicit settings; infer only from a flag or a sole active account."""
    settings = frappe.get_single("WhatsApp Settings")
    accounts = frappe.get_all(
        "WhatsApp Account", filters={"status": "Active"},
        fields=["name", "is_default_incoming", "is_default_outgoing"],
    )
    for direction in ("incoming", "outgoing"):
        # A freshly selected account flag is an explicit administrator choice.
        if doc and doc.get("status") == "Active" and doc.get("is_default_" + direction):
            settings.set("default_" + direction + "_account", doc.name)
            frappe.db.set_single_value("WhatsApp Settings", "default_" + direction + "_account", doc.name)
        field = "default_" + direction + "_account"
        flag = "is_default_" + direction
        selected = settings.get(field)
        if not selected:
            marked = [a.name for a in accounts if a.get(flag)]
            if len(marked) == 1:
                selected = marked[0]
            elif len(accounts) == 1:
                selected = accounts[0].name
            if selected:
                frappe.db.set_single_value("WhatsApp Settings", field, selected)
        if selected and frappe.db.get_value("WhatsApp Account", selected, "status") == "Active":
            # Synchronize the flags consumed by upstream get_whatsapp_account.
            for account in accounts:
                expected = int(account.name == selected)
                if int(account.get(flag) or 0) != expected:
                    frappe.db.set_value("WhatsApp Account", account.name, flag, expected, update_modified=False)
    frappe.clear_document_cache("WhatsApp Settings", "WhatsApp Settings")
