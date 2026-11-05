"""Regression tests without a running site. Run: python -m unittest discover -s tests -v.

These exercise real app functions with a fake Frappe DB/request boundary; they
are not a substitute for bench install-app/migrate on a staging Frappe site.
"""
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class Doc(dict):
    def __getattr__(self, name):
        return self.get(name)

    def __setattr__(self, name, value):
        self[name] = value

    def set(self, key, value):
        self[key] = value

    def save(self, **kwargs):
        return self

    def insert(self, **kwargs):
        self.name = self.get('name') or 'new-lead'
        return self


class Response:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status


class NativeAppTest(unittest.TestCase):
    def setUp(self):
        self.frappe = types.ModuleType('frappe')
        self.frappe.__path__ = []
        self.frappe.local = Doc(form_dict={})
        self.frappe.request = Mock()
        self.frappe.request.get_data.return_value = '{}'
        self.frappe.whitelist = lambda **kwargs: lambda f: f
        self.frappe._ = lambda s: s
        self.frappe.PermissionError = PermissionError
        self.frappe.get_installed_apps = Mock(return_value=['frappe', 'frappe_whatsapp', 'crm'])
        self.frappe.db = Mock()
        self.frappe.db.exists.return_value = False
        self.frappe.db.get_value.return_value = None
        self.frappe.get_doc = Mock(side_effect=lambda data, *args: Doc(data) if isinstance(data, dict) else Doc(name=args[0]))
        self.frappe.get_traceback = Mock(return_value='permission traceback')
        self.frappe.log_error = Mock()
        self.frappe.get_all = Mock(return_value=[])
        self.frappe.clear_document_cache = Mock()
        self.frappe.throw = Mock(side_effect=ValueError)
        self.settings = Doc(altoplano_create_leads=1, altoplano_lead_owner='Administrator')
        self.frappe.get_cached_doc = Mock(return_value=self.settings)
        self.frappe.get_single = Mock(return_value=self.settings)
        utils = types.ModuleType('frappe.utils')
        self.frappe.utils = utils
        app_utils = types.ModuleType('frappe_whatsapp.utils')
        app_utils.__path__ = [str(Path(__file__).resolve().parents[1] / 'frappe_whatsapp' / 'utils')]
        app_utils.get_whatsapp_account = Mock()
        wrappers = types.ModuleType('werkzeug.wrappers')
        wrappers.Response = Response
        self.resolver = Mock(return_value=(None, None))
        crm_api = types.ModuleType('crm.api')
        crm_api.__path__ = []
        crm_wa = types.ModuleType('crm.api.whatsapp')
        crm_doc = types.ModuleType('crm.api.doc')
        integrations = types.ModuleType('crm.integrations.api')
        integrations.get_contact_lead_or_deal_from_number = self.resolver
        mods = {
            'frappe': self.frappe, 'frappe.utils': utils,
            'frappe_whatsapp.utils': app_utils,
            'requests': types.ModuleType('requests'),
            'werkzeug': types.ModuleType('werkzeug'), 'werkzeug.wrappers': wrappers,
            'crm': types.ModuleType('crm'), 'crm.api': crm_api,
            'crm.api.whatsapp': crm_wa, 'crm.api.doc': crm_doc,
            'crm.integrations': types.ModuleType('crm.integrations'),
            'crm.integrations.api': integrations,
        }
        mods['crm'].api = crm_api
        crm_api.whatsapp = crm_wa
        self.modules = patch.dict(sys.modules, mods)
        self.modules.start()
        for name in ('frappe_whatsapp.utils.webhook', 'frappe_whatsapp.altoplano.crm', 'frappe_whatsapp.altoplano.setup'):
            sys.modules.pop(name, None)
        self.webhook = importlib.import_module('frappe_whatsapp.utils.webhook')
        self.crm = importlib.import_module('frappe_whatsapp.altoplano.crm')
        self.setup = importlib.import_module('frappe_whatsapp.altoplano.setup')

    def tearDown(self):
        self.modules.stop()

    @staticmethod
    def change(phone='phone1', sender='529993301990', msg='wamid.1', profile='Alfonso'):
        return {'field': 'messages', 'value': {
            'metadata': {'phone_number_id': phone},
            'contacts': [{'wa_id': sender, 'profile': {'name': profile}}],
            'messages': [{'from': sender, 'id': msg, 'type': 'text', 'text': {'body': 'Hola'}}],
        }}

    def test_raw_json_when_form_dict_has_no_entry(self):
        self.frappe.local.form_dict = {'cmd': 'webhook'}
        payload = {'entry': [{'changes': []}]}
        self.frappe.request.get_data.return_value = json.dumps(payload)
        self.assertEqual(self.webhook.read_payload(), payload)

    def test_parsed_form_payload_is_used(self):
        self.frappe.local.form_dict = {'entry': []}
        self.assertEqual(self.webhook.read_payload(), {'entry': []})
        self.frappe.request.get_data.assert_not_called()

    def test_malformed_json_returns_400_before_any_write(self):
        self.frappe.request.get_data.return_value = '{'
        self.assertEqual(self.webhook.post().status_code, 400)
        self.frappe.get_doc.assert_not_called()

    def test_json_array_returns_400(self):
        self.frappe.request.get_data.return_value = '[]'
        self.assertEqual(self.webhook.post().status_code, 400)

    def test_empty_and_missing_entries_do_not_crash(self):
        for data in ({}, {'entry': []}, {'entry': [{}]}):
            self.frappe.local.form_dict = data
            self.assertIsNone(self.webhook.post())

    def test_all_changes_in_all_entries_are_processed(self):
        self.frappe.local.form_dict = {'entry': [
            {'changes': [self.change()]},
            {'changes': [self.change(msg='wamid.2'), self.change(msg='wamid.3')]},
        ]}
        with patch.object(self.webhook, 'process_change') as process:
            self.webhook.post()
        self.assertEqual(process.call_count, 3)

    def test_invalid_late_entry_does_not_partially_write(self):
        self.frappe.local.form_dict = {'entry': [{'changes': [self.change()]}, {'changes': 'bad'}]}
        self.assertEqual(self.webhook.post().status_code, 400)
        self.frappe.get_doc.assert_not_called()

    def test_incoming_message_has_exact_account_and_profile(self):
        self.frappe.db.get_value.return_value = 'account1'
        self.webhook.process_change(self.change())
        inserted = [c.args[0] for c in self.frappe.get_doc.call_args_list if isinstance(c.args[0], dict)]
        self.assertEqual(inserted[0]['profile_name'], 'Alfonso')
        self.assertEqual(inserted[0]['whatsapp_account'], 'account1')

    def test_unknown_phone_does_not_fall_back_to_default(self):
        self.webhook.process_change(self.change(phone='unknown'))
        self.frappe.get_doc.assert_not_called()

    def test_replayed_message_not_inserted_again(self):
        self.frappe.db.get_value.return_value = 'account1'
        self.frappe.db.exists.return_value = True
        self.webhook.process_change(self.change())
        self.assertFalse(any(isinstance(c.args[0], dict) for c in self.frappe.get_doc.call_args_list))

    def test_statuses_without_known_messages_are_ignored(self):
        self.webhook.update_message_status({'statuses': [{'id': 'unknown', 'status': 'read'}]})
        self.frappe.get_doc.assert_not_called()

    def test_all_statuses_in_batch_are_updated(self):
        self.frappe.db.get_value.side_effect = ['msg1', 'msg2']
        self.webhook.update_message_status({'statuses': [{'id': 'a', 'status': 'sent'}, {'id': 'b', 'status': 'read'}]})
        self.assertEqual(self.frappe.get_doc.call_count, 2)

    def test_template_callback_needs_no_phone_metadata(self):
        with patch.object(self.webhook, 'update_template_status') as update:
            self.webhook.process_change({'field': 'message_template_status_update', 'value': {'event': 'APPROVED'}})
        update.assert_called_once_with({'event': 'APPROVED'})

    def test_existing_crm_reference_is_preserved(self):
        doc = Doc(type='Incoming', reference_name='existing')
        self.crm.link_incoming_message(doc)
        self.resolver.assert_not_called()

    def test_outgoing_message_does_not_create_lead(self):
        self.crm.link_incoming_message(Doc(type='Outgoing'))
        self.frappe.get_cached_doc.assert_not_called()

    def test_base_app_works_without_crm(self):
        self.frappe.get_installed_apps.return_value = ['frappe', 'frappe_whatsapp']
        self.crm.link_incoming_message(Doc(type='Incoming'))
        self.frappe.get_cached_doc.assert_not_called()

    def test_new_lead_uses_full_number_and_spanish_status(self):
        self.frappe.db.exists.side_effect = lambda dt, filters: dt == 'DocType' or (dt == 'CRM Lead Status' and filters == 'Nuevo') or dt == 'User'
        doc = Doc(type='Incoming', **{'from': '529993301990'}, profile_name='Alfonso')
        self.crm.link_incoming_message(doc)
        data = self.frappe.get_doc.call_args.args[0]
        self.assertEqual(data['mobile_no'], '+529993301990')
        self.assertEqual(data['status'], 'Nuevo')
        self.assertEqual(data['owner'], 'Administrator')
        self.assertEqual(doc.reference_name, 'new-lead')

    def test_english_status_is_supported_without_renaming(self):
        self.frappe.db.exists.side_effect = lambda dt, filters: dt == 'DocType' or (dt == 'CRM Lead Status' and filters == 'New') or dt == 'User'
        self.crm.link_incoming_message(Doc(type='Incoming', **{'from': '19565551234'}))
        self.assertEqual(self.frappe.get_doc.call_args.args[0]['status'], 'New')

    def test_existing_resolved_lead_does_not_create_duplicate(self):
        self.frappe.db.exists.return_value = True
        self.resolver.return_value = ('LEAD-1', 'CRM Lead')
        doc = Doc(type='Incoming', **{'from': '529993301990'})
        self.crm.link_incoming_message(doc)
        self.assertEqual(doc.reference_name, 'LEAD-1')
        self.frappe.get_doc.assert_not_called()

    def test_disabling_auto_create_is_respected(self):
        self.frappe.db.exists.return_value = True
        self.settings.altoplano_create_leads = 0
        self.crm.link_incoming_message(Doc(type='Incoming', **{'from': '529993301990'}))
        self.resolver.assert_not_called()

    def test_notification_adapter_does_not_bypass_public_permissions(self):
        wa = sys.modules['crm.api.whatsapp']
        protected = Mock(side_effect=PermissionError('read denied'))
        internal = Mock(return_value=['sales@example.com'])
        wa.get_assigned_users = protected
        exec('def notify_agent(doc):\n    return get_assigned_users(doc.reference_doctype, doc.reference_name)', wa.__dict__)
        sys.modules['crm.api.doc'].get_assignees = internal
        self.crm.prepare_notifications()
        notifier = wa.notify_agent
        self.crm.prepare_notifications()
        self.assertIs(wa.notify_agent, notifier)
        doc = Doc(doctype='WhatsApp Message', type='Incoming', reference_doctype='CRM Lead', reference_name='LEAD-1')
        self.assertEqual(wa.notify_agent(doc), ['sales@example.com'])
        protected.assert_not_called()
        with self.assertRaises(PermissionError):
            wa.get_assigned_users('CRM Lead', 'LEAD-1')
        self.frappe.get_installed_apps.return_value = ['frappe', 'crm']
        with self.assertRaises(PermissionError):
            wa.notify_agent(doc)

    def test_explicit_default_accounts_are_preserved(self):
        self.settings.default_incoming_account = 'chosen'
        self.settings.default_outgoing_account = 'chosen'
        self.setup.configure_defaults()
        self.frappe.db.set_single_value.assert_not_called()

    def test_multiple_accounts_are_not_chosen_arbitrarily(self):
        self.frappe.get_all.return_value = [Doc(name='a'), Doc(name='b')]
        self.setup.configure_defaults()
        self.frappe.db.set_single_value.assert_not_called()

    def test_sole_active_account_sets_both_defaults(self):
        self.frappe.get_all.return_value = [Doc(name='a')]
        self.setup.configure_defaults()
        self.assertEqual(self.frappe.db.set_single_value.call_count, 2)

    def test_setup_is_idempotent_and_does_not_change_existing_defaults(self):
        accounts = [Doc(name='a', is_default_incoming=0, is_default_outgoing=0)]
        self.frappe.get_all.return_value = accounts
        self.frappe.db.get_value.return_value = 'Active'
        self.frappe.db.set_single_value.side_effect = lambda dt, field, value: self.settings.set(field, value)
        self.frappe.db.set_value.side_effect = lambda dt, name, field, value, **kwargs: accounts[0].set(field, value)
        self.setup.configure_defaults()
        self.setup.configure_defaults()
        self.assertEqual(self.frappe.db.set_single_value.call_count, 2)
        self.assertEqual(self.frappe.db.set_value.call_count, 2)

    def test_account_flag_selection_updates_settings(self):
        self.settings.default_incoming_account = 'old'
        self.settings.default_outgoing_account = 'old'
        self.frappe.get_all.return_value = [Doc(name='new', is_default_incoming=1)]
        account = Doc(name='new', status='Active', is_default_incoming=1)
        self.setup.configure_defaults(account)
        self.assertEqual(self.settings.default_incoming_account, 'new')
        self.assertEqual(self.settings.default_outgoing_account, 'old')

    def test_notification_permission_failure_is_logged(self):
        wa = sys.modules['crm.api.whatsapp']
        wa.get_assigned_users = Mock(side_effect=PermissionError)
        exec('def notify_agent(doc):\n    return get_assigned_users(doc.reference_doctype, doc.reference_name)', wa.__dict__)
        sys.modules['crm.api.doc'].get_assignees = Mock(side_effect=PermissionError)
        self.crm.prepare_notifications()
        wa.notify_agent(Doc(doctype='WhatsApp Message', type='Incoming', reference_doctype='CRM Lead', reference_name='L'))
        self.frappe.log_error.assert_called_once()

    def test_known_legacy_script_is_disabled_but_body_preserved(self):
        self.frappe.db.exists.return_value = True
        script = Doc(reference_doctype='WhatsApp Message', script='filas = frappe.db.get_all("CRM Lead"\ntel = tel[-10:]\nnuevo.insert(ignore_permissions=True)')
        self.frappe.get_doc.return_value = script
        self.frappe.get_doc.side_effect = None
        self.setup.disable_legacy_script()
        self.frappe.db.set_value.assert_called_once_with('Server Script', self.setup.LEGACY_SCRIPT, 'disabled', 1)
        self.assertIn('nuevo.insert', script.script)

    def test_custom_legacy_script_is_left_untouched(self):
        self.frappe.db.exists.return_value = True
        self.frappe.get_doc.return_value = Doc(reference_doctype='WhatsApp Message', script='custom logic')
        self.frappe.get_doc.side_effect = None
        self.setup.disable_legacy_script()
        self.frappe.db.set_value.assert_not_called()

    def test_setup_does_nothing_before_schema_exists(self):
        self.setup.configure()
        self.frappe.get_all.assert_not_called()


if __name__ == '__main__':
    unittest.main()
