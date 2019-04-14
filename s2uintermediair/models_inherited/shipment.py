# -*- coding: utf-8 -*-

import time
import math

from openerp.osv import expression
from openerp.tools.float_utils import float_round as round
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.exceptions import UserError, ValidationError
from openerp import api, fields, models, _

class Outgoing(models.Model):
    _inherit = "s2u.warehouse.outgoing"

    @api.multi
    def create_invoice(self, so):

        invoice_model = self.env['s2u.account.invoice']

        if so:
            so_id = so.id
            lines = []
            for t in self.todo_ids:
                if not t.shipped_qty:
                    continue
                if t.sale_id.id != so_id:
                    continue

                product = self.env[t.product_id.res_model].browse(t.product_id.res_id)
                name = t.product_id.name
                if t.product_detail:
                    name = '%s %s' % (name, t.product_detail)
                account = product.get_so_account()
                if not account:
                    raise UserError(_('No financial account is defined for product %s!' % name))

                vals = {
                    'net_amount': t.shipped_qty * t.product_value * -1.0,
                    'account_id': account.id,
                    'descript': name,
                    'qty': str(t.shipped_qty * -1.0),
                    'net_price': t.product_value,
                    'sale_id': t.sale_id.id
                }

                # TODO:
                # if t.saleline_id:
                #    detailed = self.env['s2u.sale'].build_detailed(t.saleline_id, shipped_qty=int(t.shipped_qty * -1.0))
                #    vals['detailed_ids'] = detailed

                vat_sell_id = False
                if (so.delivery_country_id and so.invoice_address_id.country_id and so.delivery_country_id.id != so.invoice_address_id.country_id.id) or (so.delivery_country_id and not so.invoice_address_id.country_id):
                    country_vat = self.env['s2u.account.vat.country'].search([('country_id', '=', so.delivery_country_id.id)])
                    if not country_vat:
                        raise UserError(
                            _('Please define Country VAT rule for country %s!' % so.delivery_country_id.name))
                    vat_sell_id = country_vat.vat_sell_id

                if vat_sell_id:
                    vals['vat_id'] = vat_sell_id.id
                    vals['vat_amount'] = vat_sell_id.calc_vat_from_netto_amount(
                        vals['net_amount'])
                    vals['gross_amount'] = vat_sell_id.calc_gross_amount(
                        vals['net_amount'], vals['vat_amount'])
                elif so.invoice_partner_id.vat_sell_id:
                    vals['vat_id'] = so.invoice_partner_id.vat_sell_id.id
                    vals['vat_amount'] = so.invoice_partner_id.vat_sell_id.calc_vat_from_netto_amount(
                        vals['net_amount'])
                    vals['gross_amount'] = so.invoice_partner_id.vat_sell_id.calc_gross_amount(
                        vals['net_amount'], vals['vat_amount'])
                else:
                    vat = product.get_so_vat()
                    if vat:
                        vals['vat_id'] = vat.id
                        vals['vat_amount'] = vat.calc_vat_from_netto_amount(
                            vals['net_amount'])
                        vals['gross_amount'] = vat.calc_gross_amount(
                            vals['net_amount'], vals['vat_amount'])
                    elif account.vat_id:
                        vals['vat_id'] = account.vat_id.id
                        vals['vat_amount'] = account.vat_id.calc_vat_from_netto_amount(
                            vals['net_amount'])
                        vals['gross_amount'] = account.vat_id.calc_gross_amount(
                            vals['net_amount'], vals['vat_amount'])
                    else:
                        raise UserError(_('No VAT is defined for product %s!' % name))

                lines.append((0, 0, vals))

            if lines:
                invdata = {
                    'type': so.invoice_type,
                    'partner_id': so.invoice_partner_id.id,
                    'address_id': so.invoice_address_id.id if so.invoice_address_id else False,
                    'contact_id': so.invoice_contact_id.id if so.invoice_contact_id else False,
                    'project': self.project,
                    'reference': self.reference,
                    'line_ids': lines,
                    'delivery_address': so.delivery_address,
                    'delivery_country_id': so.delivery_country_id.id if so.delivery_country_id else False,
                    'delivery_tinno': so.delivery_tinno,
                    'delivery_ref': self.name
                }
                inv = invoice_model.create(invdata)

                account = self.env['s2u.account.account'].search([('code', '=', '8075')])
                if not account:
                    raise UserError(_('Please define account 8075 for \'Afvalbeheersbijdrage\'!'))

                # toevoegen van afvalbeheersbijdrage
                bijdrage = round(inv.amount_net * 0.001, 2)
                invlinedata = {
                    'invoice_id': inv.id,
                    'net_amount': bijdrage,
                    'account_id': account.id,
                    'descript': account.name,
                    'qty': '1 x',
                    'net_price': bijdrage
                }

                vat_sell_id = False
                if (so.delivery_country_id and so.invoice_address_id.country_id and so.delivery_country_id.id != so.invoice_address_id.country_id.id) or (so.delivery_country_id and not so.invoice_address_id.country_id):
                    country_vat = self.env['s2u.account.vat.country'].search([('country_id', '=', so.delivery_country_id.id)])
                    if not country_vat:
                        raise UserError(
                            _('Please define Country VAT rule for country %s!' % so.delivery_country_id.name))
                    vat_sell_id = country_vat.vat_sell_id

                if vat_sell_id:
                    invlinedata['vat_id'] = vat_sell_id.id
                    invlinedata['vat_amount'] = vat_sell_id.calc_vat_from_netto_amount(
                        bijdrage)
                    invlinedata['gross_amount'] = vat_sell_id.calc_gross_amount(
                        bijdrage, invlinedata['vat_amount'])
                elif inv.partner_id.vat_sell_id:
                    invlinedata['vat_id'] = inv.partner_id.vat_sell_id.id
                    invlinedata['vat_amount'] = inv.partner_id.vat_sell_id.calc_vat_from_netto_amount(
                        bijdrage)
                    invlinedata['gross_amount'] = inv.partner_id.vat_sell_id.calc_gross_amount(
                        bijdrage, invlinedata['vat_amount'])
                elif account.vat_id:
                    invlinedata['vat_id'] = account.vat_id.id
                    invlinedata['vat_amount'] = account.vat_id.calc_vat_from_netto_amount(
                        bijdrage)
                    invlinedata['gross_amount'] = account.vat_id.calc_gross_amount(
                        bijdrage, invlinedata['vat_amount'])
                else:
                    raise UserError(_('No VAT is defined for \'Afvalbeheersbijdrage\' %s!' % account.code))

                self.env['s2u.account.invoice.line'].create(invlinedata)

                invoice_model += inv
        else:
            invoice_model += super(Outgoing, self).create_invoice()

        return invoice_model

    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string='Calculation', ondelete='cascade')
