# Copyright (c) 2022, Shridhar Patil and contributors
# Altoplano changes (2026-11-05): synchronize account defaults.
from frappe.model.document import Document


class WhatsAppSettings(Document):
    def on_update(self):
        from frappe_whatsapp.altoplano.setup import configure_defaults
        configure_defaults()
