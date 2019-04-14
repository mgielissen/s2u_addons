# -*- coding: utf-8 -*-

import datetime

from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = "s2u.account.invoice"

    @api.one
    def _compute_template(self):
        if self.template_id:
            self.prefix_invoice = self.template_id.render_template(self.template_id.prefix_invoice,
                                                                   entity=self.partner_id,
                                                                   contact=self.contact_id,
                                                                   address=self.address_id)
            self.postfix_invoice = self.template_id.render_template(self.template_id.postfix_invoice,
                                                                    entity=self.partner_id,
                                                                    contact=self.contact_id,
                                                                    address=self.address_id)
            self.date_display = self.template_id.render_template(self.template_id.date_display,
                                                                 date=datetime.datetime.now().strftime('%Y-%m-%d'))
        else:
            self.prefix_invoice = ''
            self.postfix_invoice = ''
            self.date_display = ''

    @api.model
    def _default_template(self):

        return self.env['s2u.sale.template'].search([('default', '=', True)], limit=1)

    template_id = fields.Many2one('s2u.sale.template', string='Template', default=_default_template)
    prefix_invoice = fields.Html('Prefix', compute=_compute_template, readonly=True)
    postfix_invoice = fields.Html('Postfix', compute=_compute_template, readonly=True)
    date_display = fields.Text('Date display', compute=_compute_template, readonly=True)

class AccountInvoiceLine(models.Model):
    _inherit = "s2u.account.invoice.line"

    sale_id = fields.Many2one('s2u.sale', string='SO', index=True,
                              ondelete='restrict')
    saleline_id = fields.Many2one('s2u.sale.line', string='SO', index=True,
                                  ondelete='set null')
    saledetailed_ids = fields.One2many('s2u.sale.invoice.line.label', 'line_id',
                                       string='Details', copy=True)

class SaleInvoiceLineLabel(models.Model):
    _name = "s2u.sale.invoice.line.label"
    _order = 'sequence'

    @api.one
    def _compute_value(self):
        self.calc_value_invoice = self.env['s2u.sale'].calc_value(self.saleline_id, self.label_id, 'invoice',
                                                                  self.value, so_type='invoice')

    line_id = fields.Many2one('s2u.account.invoice.line', string='Line', required=True, ondelete='cascade')
    saleline_id = fields.Many2one('s2u.sale.line', string='SO Line', ondelete='set null')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    value = fields.Text(string='Value')
    sequence = fields.Integer(string='Sequence', default=10)
    calc_value_invoice = fields.Text(string='Value', compute=_compute_value, readonly=True)


class AccountInvoicePOLine(models.Model):
    _inherit = "s2u.account.invoice.po.line"

    purchaseline_id = fields.Many2one('s2u.purchase.line', string='PO', index=True,
                                      ondelete='restrict')


