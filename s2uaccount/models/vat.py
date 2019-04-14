# -*- coding: utf-8 -*-

import time
import math

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _

class AccountVatCategory(models.Model):
    _name = "s2u.account.vat.category"
    _description = "VAT category"
    _order = "code"

    code = fields.Char(size=64, required=True, index=True)
    name = fields.Char(string='Category', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    parent_id = fields.Many2one('s2u.account.vat.category', string='Parent', ondelete='restrict')

    _sql_constraints = [
        ('code_company_uniq', 'unique (code, company_id)', 'The code of the category must be unique !')
    ]

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for category in self:
            name = category.code + ' - ' + category.name
            result.append((category.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        categories = self.search(domain + args, limit=limit)
        return categories.name_get()


class AccountVat(models.Model):
    _name = "s2u.account.vat"
    _description = "Vat"
    _order = "code"

    code = fields.Char(size=64, required=True, index=True)
    name = fields.Char(string='VAT', required=True, index=True)
    rule_ids = fields.One2many('s2u.account.vat.rule', 'vat_id',
                               string='VAT rules')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    rule_gross = fields.Char(string='Rule for gross amount', required=True)
    rule_net = fields.Char(string='Rule for net amount', required=True)
    rule_vat = fields.Char(string='Rule for VAT amount', required=True)
    type = fields.Selection([
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ], required=True, default='buy', index=True, string='Type')
    vat_report = fields.Selection([
        ('00', 'Group 00'),
        ('01', 'Group 01'),
        ('02', 'Group 02'),
        ('03', 'Group 03'),
        ('04', 'Group 04'),
        ('05', 'Group 05'),
        ('06', 'Group 06'),
        ('07', 'Group 07'),
        ('08', 'Group 08'),
        ('09', 'Group 09'),
        ('10', 'Group 10'),
        ('11', 'Group 11'),
        ('12', 'Group 12'),
        ('13', 'Group 13'),
        ('14', 'Group 14'),
        ('15', 'Group 15'),
        ('16', 'Group 16'),
        ('17', 'Group 17'),
        ('18', 'Group 18'),
        ('19', 'Group 19'),
        ('20', 'Group 20')
    ], required=True, default='00', string='Report')
    tinno_obligatory = fields.Boolean('TIN no. obligatory', default=False)
    category = fields.Selection([
        ('ser', 'Services'),
        ('del', 'Deliveries')
    ], required=True, default='ser', string='Category')

    _sql_constraints = [
        ('code_company_uniq', 'unique (code, company_id)', 'The code of the vat must be unique with the administration !')
    ]

    @api.multi
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(AccountVat, self).copy(default)

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for vat in self:
            if vat.type == 'buy':
                vat_type = 'Buy'
            else:
                vat_type = 'Sell'
            name = vat.code + ' (' + vat.name + ') - ' + vat_type
            result.append((vat.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        vats = self.search(domain + args, limit=limit)
        return vats.name_get()

    def calc_vat(self, amount, amount_is='net'):

        vat_amount = eval(self.rule_vat, {'amount': amount})
        if self.rule_ids:
            tmp_amount = 0.0
            for rule in self.rule_ids:
                if rule.rule_type == 'plus':
                    tmp_amount += vat_amount
                else:
                    tmp_amount -= vat_amount
            return tmp_amount
        else:
            return vat_amount

        return vat_amount

    def calc_netto_amount(self, gross_amount, vat_amount):

        if self.rule_ids:
            tmp_amount = 0.0
            for rule in self.rule_ids:
                if rule.rule_type == 'plus':
                    tmp_amount += vat_amount
                else:
                    tmp_amount -= vat_amount
            return gross_amount - tmp_amount
        else:
            return gross_amount

    def calc_gross_amount(self, net_amount, vat_amount):

        if self.rule_ids:
            tmp_amount = 0.0
            for rule in self.rule_ids:
                if rule.rule_type == 'plus':
                    tmp_amount += vat_amount
                else:
                    tmp_amount -= vat_amount
            return net_amount + tmp_amount
        else:
            return net_amount + vat_amount

    def calc_vat_from_gross_amount(self, gross_amount):

        netto_amount = eval(self.rule_net, {'amount': gross_amount})
        vat_amount = eval(self.rule_vat, {'amount': netto_amount})
        return vat_amount

    def calc_vat_from_netto_amount(self, netto_amount):

        vat_amount = eval(self.rule_vat, {'amount': netto_amount})
        return vat_amount

class AccountVatRule(models.Model):
    _name = "s2u.account.vat.rule"
    _description = "Vat rule"

    vat_id = fields.Many2one('s2u.account.vat', string='Vat', required=True, ondelete='cascade')
    rule_type = fields.Selection([
        ('plus', 'Plus'),
        ('min', 'Minus'),
    ], required=True, default='plus', index=True, string='Rule')
    account_id = fields.Many2one('s2u.account.account', string='Account')
    category_id = fields.Many2one('s2u.account.vat.category', string='Category', required=True)


class AccountVatCountry(models.Model):
    _name = "s2u.account.vat.country"
    _description = "VAT used in country"

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    country_id = fields.Many2one('res.country', string='Country', required=True)
    vat_sell_id = fields.Many2one('s2u.account.vat', string='VAT income (SO)', domain=[('type', '=', 'sell')],
                                  required=True)
    vat_buy_id = fields.Many2one('s2u.account.vat', string='VAT expense (PO)', domain=[('type', '=', 'buy')],
                                 required=True)

    _sql_constraints = [
        ('country_company_uniq', 'unique (country_id, company_id)', 'The country should be defined once !')
    ]