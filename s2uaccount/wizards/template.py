# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TemplateInit(models.TransientModel):
    _name = "wizard.template.init"
    _description = "Initialisation of accounts and vats"

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    use_template = fields.Selection([
        ('default', 'Default template'),
    ], string='Use', default='default')

    def _create_sequence(self):

        make_sequences = [
            {
                'code': 's2u.account.invoice',
                'name': 's2uFramework Invoice number',
                'use_date_range': True,
                'prefix': '%(range_year)s/'
            },
            {
                'code': 's2u.sale[quotation]',
                'name': 's2uFramework Quotation',
                'use_date_range': False,
                'prefix': 'QT'
            },
            {
                'code': 's2u.sale',
                'name': 's2uFramework Sales Order',
                'use_date_range': False,
                'prefix': 'SO'
            },
            {
                'code': 's2u.purchase',
                'name': 's2uFramework Purchase Order',
                'use_date_range': False,
                'prefix': 'PO'
            },
            {
                'code': 's2u.warehouse.outgoing',
                'name': 's2uFramework Warehouse Outgoing',
                'use_date_range': True,
                'prefix': '%(range_year)s/'
            },
            {
                'code': 's2u.warehouse.incoming',
                'name': 's2uFramework Warehouse Incoming',
                'use_date_range': True,
                'prefix': '%(range_year)s/'
            },
            {
                'code': 's2u.warehouse.unit',
                'name': 's2uFramework Warehouse Unit',
                'use_date_range': True,
                'prefix': '%(range_year)s/'
            },
            {
                'code': 's2u.warehouse.used.materials',
                'name': 's2uFramework Warehouse Used Materials',
                'use_date_range': True,
                'prefix': '%(range_year)s/'
            },
            {
                'code': 's2u.payment.transaction',
                'name': 's2uFramework Payment Transaction',
                'use_date_range': True,
                'prefix': '%(range_year)s/'
            },
            {
                'code': 's2u.project',
                'name': 's2uFramework Project',
                'use_date_range': False,
                'prefix': 'PR'
            },
            {
                'code': 's2u.warehouse.rma',
                'name': 's2uFramework Warehouse RMA',
                'use_date_range': True,
                'prefix': '%(range_year)s/'
            },
        ]

        for s in make_sequences:
            exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.company_id.id),
                                                            ('code', '=', s['code'])])
            if exists:
                continue

            seq = {
                'code': s['code'],
                'name': s['name'],
                'implementation': 'no_gap',
                'prefix': s['prefix'],
                'padding': 4,
                'number_increment': 1,
                'use_date_range': s['use_date_range'],
                'company_id': self.company_id.id
            }
            self.env['ir.sequence'].sudo().create(seq)

        return True

    @api.multi
    def init_template(self):
        self.ensure_one()

        account_cat_template = self.env['s2u.template.account.category']
        account_cat_model = self.env['s2u.account.category']
        account_vat_model = self.env['s2u.account.vat']

        self._create_sequence()

        cats = account_cat_template.sudo().search([('parent_id', '=', False)])
        for cat in cats:
            exists = account_cat_model.search([('code', '=', cat.code)])
            if not exists:
                account_cat_model.create({'code': cat.code,
                                          'name': cat.name,
                                          'type': cat.type})
            else:
                exists.write({'type': cat.type})

        cats = account_cat_template.sudo().search([('parent_id', '!=', False)])
        for cat in cats:
            cat_id = False
            parent_cat = account_cat_model.search([('code', '=', cat.parent_id.code)])
            if parent_cat:
                cat_id = parent_cat[0].id

            exists = account_cat_model.search([('code', '=', cat.code)])
            if not exists:
                account_cat_model.create({'code': cat.code,
                                          'name': cat.name,
                                          'parent_id': cat_id,
                                          'type': cat.type})
            else:
                exists.write({'type': cat.type})


        account_vat_cat_template = self.env['s2u.template.account.vat.category']
        account_vat_cat_model = self.env['s2u.account.vat.category']

        cats = account_vat_cat_template.sudo().search([('parent_id', '=', False)])
        for cat in cats:
            exists = account_vat_cat_model.search([('code', '=', cat.code)])
            if not exists:
                account_vat_cat_model.create({'code': cat.code,
                                              'name': cat.name})

        cats = account_vat_cat_template.sudo().search([('parent_id', '!=', False)])
        for cat in cats:
            cat_id = False
            parent_cat = account_vat_cat_model.search([('code', '=', cat.parent_id.code)])
            if parent_cat:
                cat_id = parent_cat[0].id

            exists = account_vat_cat_model.search([('code', '=', cat.code)])
            if not exists:
                account_vat_cat_model.create({'code': cat.code,
                                              'name': cat.name,
                                              'parent_id': cat_id})

        account_template = self.env['s2u.template.account.account']
        account_model = self.env['s2u.account.account']

        accounts = account_template.sudo().search([])
        update_accounts = []
        for account in accounts:
            cat_id = False
            if account.category_id:
                cats = account_cat_model.search([('code', '=', account.category_id.code)])
                if cats:
                    cat_id = cats[0].id

            exists = account_model.search([('code', '=', account.code)])
            if not exists:
                res = account_model.create({'code': account.code,
                                            'name': account.name,
                                            'type': account.type,
                                            'category_id': cat_id})
                update_accounts.append(account)

        vat_template = self.env['s2u.template.account.vat']
        vat_model = self.env['s2u.account.vat']
        vat_rule_model = self.env['s2u.account.vat.rule']

        vats = vat_template.sudo().search([])
        for vat in vats:
            exists = vat_model.search([('code', '=', vat.code)])
            if not exists:
                vat_id = vat_model.create({'code': vat.code,
                                           'name': vat.name,
                                           'rule_gross': vat.rule_gross,
                                           'rule_net': vat.rule_net,
                                           'rule_vat': vat.rule_vat,
                                           'type': vat.type,
                                           'tinno_obligatory': vat.tinno_obligatory,
                                           'category': vat.category,
                                           'vat_report': vat.vat_report})
                for rule in vat.rule_ids:
                    account_id = False
                    if rule.account_id:
                        accounts = account_model.search([('code', '=', rule.account_id.code)])
                        if accounts:
                            account_id = accounts[0].id
                    cat_id = False
                    if rule.category_id:
                        cats = account_vat_cat_model.search([('code', '=', rule.category_id.code)])
                        if cats:
                            cat_id = cats[0].id
                    vat_rule_model.create({'vat_id': vat_id.id,
                                           'account_id': account_id,
                                           'category_id': cat_id,
                                           'rule_type': rule.rule_type})
            else:
                exists.write({'vat_report': vat.vat_report})

        for account in update_accounts:
            vat_id = False
            if account.vat_id:
                vats = account_vat_model.search([('code', '=', account.vat_id.code)])
                if vats:
                    vat_id = vats[0].id
            if not vat_id:
                continue
            exists = account_model.search([('code', '=', account.code)])
            if exists:
                exists.write({
                    'vat_id': vat_id
                })
        return True

