"""Migrate existing sites to native lifecycle setup."""
from frappe_whatsapp.altoplano.setup import configure


def execute():
    configure()
