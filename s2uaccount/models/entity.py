# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class CrmEntity(models.Model):
    _inherit = "s2u.crm.entity"

    @api.one
    def get_vat_sell(self):

        if self.country_id:
            country_vat = self.env['s2u.account.vat.country'].search([('country_id', '=', self.country_id.id)])
            if country_vat:
                self.vat_sell_id = country_vat.vat_sell_id
        else:
            self.vat_sell_id = False

    @api.one
    def get_vat_buy(self):

        if self.country_id:
            country_vat = self.env['s2u.account.vat.country'].search([('country_id', '=', self.country_id.id)])
            if country_vat:
                self.vat_buy_id = country_vat.vat_buy_id
        else:
            self.vat_buy_id = False

    vat_sell_id = fields.Many2one('s2u.account.vat', string='VAT income (SO)', compute=get_vat_sell)
    vat_buy_id = fields.Many2one('s2u.account.vat', string='VAT expense (PO)', compute=get_vat_buy)
    payment_term_id = fields.Many2one('s2u.account.payment.term', string='Payment terms', ondelete='restrict')
