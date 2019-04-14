# -*- coding: utf-8 -*-

import datetime

from odoo.tools.misc import formatLang
from openerp.exceptions import UserError, ValidationError
from openerp import api, fields, models, _


class Sale(models.Model):
    _inherit = "s2u.sale"

    def _get_calc_count(self):

        for sale in self:
            lines = self.env['s2u.sale.line'].search([('sale_id', '=', sale.id),
                                                      ('intermediair_calc_id', '!=', False)])
            calc_ids = [l.intermediair_calc_id.id for l in lines]
            calc_ids = list(set(calc_ids))
            sale.intermediair_calc_count = len(calc_ids)

    @api.multi
    def action_view_intermediair_calc(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2uintermediair.action_calc')
        list_view_id = imd.xmlid_to_res_id('s2uintermediair.calc_tree')
        form_view_id = imd.xmlid_to_res_id('s2uintermediair.calc_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }

        lines = self.env['s2u.sale.line'].search([('sale_id', '=', self.id),
                                                  ('intermediair_calc_id', '!=', False)])
        calc_ids = [l.ellerhold_calc_id.id for l in lines]
        calc_ids = list(set(calc_ids))

        if len(calc_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % calc_ids
        elif len(calc_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = calc_ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    def userdef_calc_value(self, so_line, label, keyword, display, value, po_type):

        PRICE_PER = {
            'item': _('per Item'),
            '10': _('per 10'),
            '100': _('per 100'),
            '1000': _('per 1000'),
            'total': ''
        }

        if keyword == 'total-amount':
            amount = formatLang(self.env, so_line.price, currency_obj=so_line.currency_id)
            amount = [c for c in amount if c in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', ',', '-', '+']]
            amount = ''.join(amount)
            if value == '{{total-amount}}':
                return '%s %s' % (amount, PRICE_PER[so_line.price_per])
            else:
                return value.replace('{{total-amount}}', amount)

        return False

    intermediair_image = fields.Binary("Image", attachment=True)
    intermediair_calc_count = fields.Integer(string='# of Calculations', compute='_get_calc_count', readonly=True)

    @api.multi
    def manage_invoice_lines(self, lines, condition):

        self.ensure_one()
        layout = False
        add_bijdrage = False
        for l in self.line_ids:
            if l.intermediair_calc_id:
                add_bijdrage = True
                break

        if add_bijdrage:
            net_amount = 0.0
            for l in lines:
                net_amount += l[2]['net_amount']
            if net_amount:
                account = self.env['s2u.account.account'].search([('code', '=', '8075')])
                if not account:
                    raise UserError(_('Please define account 8075 for \'Afvalbeheersbijdrage\'!'))

                # toevoegen van afvalbeheersbijdrage
                bijdrage = round(round(net_amount * 0.001, 2) * float(condition) / 100.0, 2)
                invlinedata = {
                    'net_amount': bijdrage,
                    'account_id': account.id,
                    'descript': account.name,
                    'qty': '1 x',
                    'net_price': bijdrage,
                    'price_per': 'total',
                    'saledetail_ids': []
                }

                invlinedata['saledetail_ids'].append((5,))
                for l in self.line_ids:
                    for layout_label in l.label_ids:
                        if layout_label.on_invoice:
                            vals = {
                                'label_id': layout_label.label_id.id,
                                'sequence': layout_label.sequence,
                                'display': layout_label.display,
                                'on_invoice': layout_label.on_invoice
                            }
                            if layout_label.calc_value_order:
                                vals['value'] = layout_label.calc_value_order
                            elif layout_label.value:
                                vals['value'] = layout_label.value
                            else:
                                vals['value'] = ''
                            invlinedata['saledetail_ids'].append((0, 0, vals))

                vat_sell_id = False
                if (self.delivery_country_id and self.invoice_address_id.country_id and self.delivery_country_id.id != self.invoice_address_id.country_id.id) or (self.delivery_country_id and not self.invoice_address_id.country_id):
                    country_vat = self.env['s2u.account.vat.country'].search([('country_id', '=', self.delivery_country_id.id)])
                    if not country_vat:
                        raise UserError(
                            _('Please define Country VAT rule for country %s!' % self.delivery_country_id.name))
                    vat_sell_id = country_vat.vat_sell_id

                if vat_sell_id:
                    invlinedata['vat_id'] = vat_sell_id.id
                    invlinedata['vat_amount'] = vat_sell_id.calc_vat_from_netto_amount(
                        bijdrage)
                    invlinedata['gross_amount'] = vat_sell_id.calc_gross_amount(
                        bijdrage, invlinedata['vat_amount'])
                elif self.invoice_partner_id.vat_sell_id:
                    invlinedata['vat_id'] = self.invoice_partner_id.vat_sell_id.id
                    invlinedata['vat_amount'] = self.invoice_partner_id.vat_sell_id.calc_vat_from_netto_amount(
                        bijdrage)
                    invlinedata['gross_amount'] = self.invoice_partner_id.vat_sell_id.calc_gross_amount(
                        bijdrage, invlinedata['vat_amount'])
                elif account.vat_id:
                    invlinedata['vat_id'] = account.vat_id.id
                    invlinedata['vat_amount'] = account.vat_id.calc_vat_from_netto_amount(
                        bijdrage)
                    invlinedata['gross_amount'] = account.vat_id.calc_gross_amount(
                        bijdrage, invlinedata['vat_amount'])
                else:
                    raise UserError(_('No VAT is defined for \'Afvalbeheersbijdrage\' %s!' % account.code))

                lines.append((0, 0, invlinedata))

        return super(Sale, self).manage_invoice_lines(lines, condition)

    @api.multi
    def action_quotation(self):

        self.ensure_one()

        lines = self.env['s2u.intermediair.calc']
        for line in self.line_ids:
            if line.intermediair_calc_id:
                lines += line.intermediair_calc_id
        if lines:
            line.write({
                'state': 'draft'
            })

        return super(Sale, self).action_quotation()

    @api.multi
    def action_order(self):

        self.ensure_one()

        lines = self.env['s2u.intermediair.calc']
        for line in self.line_ids:
            if line.intermediair_calc_id:
                lines += line.intermediair_calc_id
        if lines:
            lines.write({
                'state': 'order'
            })

        return super(Sale, self).action_order()

    @api.multi
    def action_confirm(self):

        self.ensure_one()

        lines = self.env['s2u.intermediair.calc']
        for line in self.line_ids:
            if line.intermediair_calc_id:
                lines += line.intermediair_calc_id
        if lines:
            lines.write({
                'state': 'confirm'
            })

            if self.invoicing == 'dropshipping':
                if self.delivery_ids:
                    for delivery in self.delivery_ids:
                        vals = {
                            'load_type': delivery.load_type,
                            'delivery_entity_id': delivery.delivery_partner_id.id,
                            'delivery_contact_id': delivery.delivery_contact_id.id if delivery.delivery_contact_id else False,
                            'delivery_address': delivery.delivery_address,
                            'delivery_country_id': delivery.delivery_partner_id.country_id.id if delivery.delivery_partner_id.country_id else False,
                            'delivery_tinno': delivery.delivery_partner_id.tinno,
                            'delivery_lang': delivery.delivery_partner_id.lang,
                            'date_delivery': self.date_delivery,
                            'project': self.project,
                            'reference': self.reference
                        }
                        if delivery.load_entity_id:
                            vals['load_entity_id'] = delivery.load_entity_id.id
                        if delivery.load_address:
                            vals['load_address'] = delivery.load_address
                        if delivery.trailer_no:
                            vals['trailer_no'] = delivery.trailer_no
                        self.create_outgoing(add_values=vals, devider=len(self.delivery_ids))
                else:
                    vals = {
                        'load_type': lines[0].load_type,
                        'delivery_entity_id': self.delivery_partner_id.id,
                        'delivery_contact_id': self.delivery_contact_id.id if self.delivery_contact_id else False,
                        'delivery_address': self.delivery_address,
                        'delivery_country_id': self.delivery_partner_id.country_id.id if self.delivery_partner_id.country_id else False,
                        'delivery_tinno': self.delivery_partner_id.tinno,
                        'delivery_lang': self.delivery_partner_id.lang,
                        'date_delivery': self.date_delivery,
                        'project': self.project,
                        'reference': self.reference
                    }
                    if lines[0].load_entity_id:
                        vals['load_entity_id'] = lines[0].load_entity_id.id
                    if lines[0].load_address:
                        vals['load_address'] = lines[0].load_address
                    if lines[0].trailer_no:
                        vals['trailer_no'] = lines[0].trailer_no
                    self.create_outgoing(add_values=vals)

        return super(Sale, self).action_confirm()

    @api.multi
    def action_cancel(self):

        self.ensure_one()

        lines = self.env['s2u.intermediair.calc']
        for line in self.line_ids:
            if line.intermediair_calc_id:
                lines += line.intermediair_calc_id
        if lines:
            lines.write({
                'state': 'rejected'
            })

        return super(Sale, self).action_cancel()

    @api.multi
    def action_undo(self):

        self.ensure_one()

        lines = self.env['s2u.intermediair.calc']
        for line in self.line_ids:
            if line.intermediair_calc_id:
                lines += line.intermediair_calc_id
        if lines:
            lines.write({
                'state': 'draft'
            })

        return super(Sale, self).action_undo()


class SaleLine(models.Model):
    _inherit = "s2u.sale.line"

    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string="Project", ondelete='set null')
