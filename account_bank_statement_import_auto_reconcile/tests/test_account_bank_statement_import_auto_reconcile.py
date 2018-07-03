# -*- coding: utf-8 -*-
# © 2017 Therp BV <http://therp.nl>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import base64
from datetime import timedelta
from openerp import fields
from openerp.tests.common import TransactionCase
from openerp.addons.account_bank_statement_import.models\
    .account_bank_statement_import import AccountBankStatementImport


class TestAccountBankStatementImportAutoReconcile(TransactionCase):
    def setUp(self):
        super(TestAccountBankStatementImportAutoReconcile, self).setUp()
        # we don't really have something to import, so we patch the
        # import routine to return what we want for our tests
        self.original_parse_file = AccountBankStatementImport._parse_file
        AccountBankStatementImport._parse_file = self._parse_file
        self.invoice = self.env.ref('account.invoice_4')
        self.rule = self.env.ref(
            'account_bank_statement_import_auto_reconcile.rule_amount_exact'
        )

    def tearDown(self):
        super(TestAccountBankStatementImportAutoReconcile, self).tearDown()
        AccountBankStatementImport._parse_file = self.original_parse_file

    def _parse_file(self, data):
        date = self.invoice.date_invoice
        return [
            {
                'currency_code': self.invoice.company_id.currency_id.name,
                'account_number': False,
                'name': 'Auto reconcile test',
                'date': fields.Date.to_string(
                    fields.Date.from_string(date) + timedelta(days=5)
                ),
                'transactions': [
                    {
                        'name': self.invoice.number,
                        'date': fields.Date.to_string(
                            fields.Date.from_string(date) + timedelta(days=5)
                        ),
                        'amount': self.invoice.residual,
                        'unique_import_id': '42',
                        'account_number':
                        self.invoice.partner_id.bank_ids[:1].acc_number,
                    },
                ],
            },
        ]

    def test_account_bank_statement_import_auto_reconcile(self):
        # first, we do an import with auto reconciliation turned off
        action = self.env['account.bank.statement.import'].create({
            'data_file': base64.b64encode('hello world'),
            'journal_id': self.env.ref('account.bank_journal').id,
            'auto_reconcile': False,
        }).import_file()
        # nothing should have happened
        self.assertEqual(self.invoice.state, 'open')
        self.env['account.bank.statement'].browse(
            action['context']['statement_ids']
        ).unlink()
        # now we do matching, but manipulate the matching to work on the
        # ref field only which is empty in our example
        self.rule.write({'match_st_name': False})
        action = self.env['account.bank.statement.import'].create({
            'data_file': base64.b64encode('hello world'),
            'journal_id': self.env.ref('account.bank_journal').id,
            'auto_reconcile': True,
        }).import_file()
        # nothing should have happened
        self.assertEqual(self.invoice.state, 'open')
        self.env['account.bank.statement'].browse(
            action['context']['statement_ids']
        ).unlink()
        # for exact amount matching, our first transaction should be matched
        # to the invoice's move line, marking the invoice as paid,
        # provided we allow matching by name
        self.rule.write({'match_st_name': True})
        action = self.env['account.bank.statement.import'].create({
            'data_file': base64.b64encode('hello world'),
            'journal_id': self.env.ref('account.bank_journal').id,
            'auto_reconcile': True,
        }).import_file()
        self.assertEqual(self.invoice.state, 'paid')

    def test_rule_options(self):
        self.rule.unlink()
        rule = self.env[
            'account.bank.statement.import.auto.reconcile.rule'
        ].create({
            'journal_id': self.env.ref('account.bank_journal').id,
            'rule_type':
            'account.bank.statement.import.auto.reconcile.exact.amount',
            'match_st_name': False,
        })
        rules = rule.get_rules()
        # explicitly written
        self.assertFalse(rules.match_st_name)
        # defaults must be used here too
        self.assertTrue(rules.match_st_ref)
