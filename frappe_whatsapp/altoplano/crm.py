"""CRM integration without changing CRM's source or public permission checks."""
from functools import wraps
from types import FunctionType

import frappe


def prepare_notifications():
    """Replace only CRM's private notifier with an isolated copy of its globals.

    CRM main calls a read-protected API while notifying assignees as Guest.
    Use CRM's internal assignee lookup only inside that private notification
    function. The whitelisted API and other functions retain their permissions.
    The wrapper is safe across sites: it delegates on sites without this app.
    """
    if "crm" not in frappe.get_installed_apps():
        return
    import crm.api.whatsapp as whatsapp
    from crm.api.doc import get_assignees

    original = getattr(whatsapp, "notify_agent", None)
    if not original or getattr(original, "_altoplano_adapter", False):
        return
    if "get_assigned_users" not in original.__code__.co_names:
        return  # Already fixed upstream, or a different CRM notification schema.
    namespace = dict(original.__globals__, get_assigned_users=get_assignees)
    internal_notify = FunctionType(
        original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__
    )
    internal_notify.__kwdefaults__ = original.__kwdefaults__

    @wraps(original)
    def notify(doc, *args, **kwargs):
        if (
            doc.doctype != "WhatsApp Message"
            or doc.get("type") != "Incoming"
            or "frappe_whatsapp" not in frappe.get_installed_apps()
        ):
            return original(doc, *args, **kwargs)
        try:
            return internal_notify(doc, *args, **kwargs)
        except frappe.PermissionError:
            # A notification failure must not discard the received message.
            frappe.log_error(title="WhatsApp CRM notification permission error", message=frappe.get_traceback())

    notify._altoplano_adapter = True
    whatsapp.notify_agent = notify


def link_incoming_message(doc):
    """Link/create before insert; downstream CRM/chat events see the reference."""
    if doc.get("type") != "Incoming" or doc.get("reference_name"):
        return
    if "crm" not in frappe.get_installed_apps() or not frappe.db.exists("DocType", "CRM Lead"):
        return
    settings = frappe.get_cached_doc("WhatsApp Settings")
    if not settings.get("altoplano_create_leads"):
        return
    number = "".join(c for c in (doc.get("from") or "") if c.isdigit())
    if not number:
        return

    # Re-use CRM's resolver for its formatting and contact/deal matching logic.
    from crm.integrations.api import get_contact_lead_or_deal_from_number
    name, doctype = get_contact_lead_or_deal_from_number(number)
    if name and doctype:
        doc.reference_doctype, doc.reference_name = doctype, name
        return

    # Exact full international numbers only; never collapse different countries
    # to their last ten digits as the previous Server Script did.
    for field in ("mobile_no", "phone"):
        name = frappe.db.get_value("CRM Lead", {field: ["in", [number, "+" + number]]}, "name")
        if name:
            doc.reference_doctype, doc.reference_name = "CRM Lead", name
            return

    status = settings.get("altoplano_lead_status")
    if not status:
        for candidate in ("Nuevo", "New"):
            if frappe.db.exists("CRM Lead Status", candidate):
                status = candidate
                break
    if not status:
        status = frappe.db.get_value("CRM Lead Status", {}, "name", order_by="creation asc")
    if not status or not frappe.db.exists("CRM Lead Status", status):
        frappe.throw("Configure a valid CRM lead status in WhatsApp Settings.")
    owner = settings.get("altoplano_lead_owner") or "Administrator"
    if not frappe.db.exists("User", {"name": owner, "enabled": 1, "user_type": "System User"}):
        frappe.throw("Configure an enabled System User as the WhatsApp lead owner.")
    lead = frappe.get_doc({
        "doctype": "CRM Lead",
        "first_name": doc.get("profile_name") or "WhatsApp " + number,
        "mobile_no": "+" + number,
        "phone": "+" + number,
        "status": status,
        "lead_owner": owner,
        "owner": owner,
    })
    lead.insert(ignore_permissions=True)
    doc.reference_doctype, doc.reference_name = "CRM Lead", lead.name
