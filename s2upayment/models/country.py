# -*- coding: utf-8 -*-

import math

from odoo import api, fields, models, _
from odoo import tools, modules
from odoo.addons.base.ir.ir_mail_server import encode_header_param


class Country(models.Model):
    _name = 's2u.sale.country'
    _description = 'Sale product in countries'

    _order = 'country_id'
    _rec_name = 'country_id'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    country_id = fields.Many2one('res.country', string='Country', index=True, required=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    costs_ids = fields.One2many('s2u.sale.country.portocosts', 'country_id',
                                string='Costs', copy=True)
    default = fields.Boolean(string='Default', default=False)

    def allowed_countries(self, company_id):
        countries = []
        for allowed in self.sudo().search([('company_id', '=', company_id)]):
            countries.append(allowed)
        return countries

    def default_country(self, company_id):
        countries = self.sudo().search([('company_id', '=', company_id),
                                        ('default', '=', True)])
        if countries:
            return countries[0].id
        else:
            countries = self.sudo().search([('company_id', '=', company_id)])
            if countries:
                return countries[0].id
        return False

    def convert_country(self, company_id, res_country_id):
        if not res_country_id:
            return False
        countries = self.sudo().search([('company_id', '=', company_id),
                                        ('country_id', '=', res_country_id)])
        if countries:
            return countries[0].id
        else:
            return False

class CountryPortoCosts(models.Model):
    _name = 's2u.sale.country.portocosts'
    _description = 'Shipment costs per country per wieght'
    _order = 'weight'

    @api.one
    @api.depends('price')
    def _compute_gross_amount(self):
        self.price_gross = self.price

    country_id = fields.Many2one('s2u.sale.country', string='Country', index=True, required=True)
    currency_id = fields.Many2one('res.currency', related='country_id.currency_id', store=True)
    weight = fields.Float(string='Till weight (kg)', digits=(16, 3))
    price = fields.Monetary(string='Shipment costs', currency_field='currency_id', index=True)
    price_is_net = fields.Boolean(string='Price is netto', default=False)
    price_gross = fields.Monetary(string='Gross', currency_field='currency_id',
                                  store=True, readonly=True, compute='_compute_gross_amount')
    vat_id = fields.Many2one('s2u.account.vat', string='Vat', domain=[('type', '=', 'sell')])
    product_id = fields.Many2one('s2u.baseproduct.item', string='Porto product', required=True, index=True,
                                 domain=[('product_type', '=', 'service')])


