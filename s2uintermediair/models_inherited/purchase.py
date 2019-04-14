# -*- coding: utf-8 -*-

from openerp.tools.misc import formatLang
from openerp.tools.float_utils import float_round as round
from openerp import api, fields, models, _


class Purchase(models.Model):
    _inherit = "s2u.purchase"

    def userdef_calc_value(self, po_line, label, keyword, display, value, po_type):

        if keyword == 'startup-amount':
            return value.replace('{{startup-amount}}',
                                 formatLang(self.env, po_line.startup_costs, currency_obj=po_line.currency_id))

        return super(Purchase, self).userdef_calc_value(po_line, label, keyword, display, value, po_type)

    def _get_calc_count(self):

        for purchase in self:
            lines = self.env['s2u.purchase.line'].search([('purchase_id', '=', purchase.id),
                                                          ('intermediair_calc_id', '!=', False)])
            calc_ids = [l.ellerhold_calc_id.id for l in lines]
            calc_ids = list(set(calc_ids))
            purchase.intermediair_calc_count = len(calc_ids)

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

        lines = self.env['s2u.purchase.line'].search([('purchase_id', '=', self.id),
                                                      ('intermediair_calc_id', '!=', False)])
        calc_ids = [l.intermediair_calc_id.id for l in lines]
        calc_ids = list(set(calc_ids))

        if len(calc_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % calc_ids
        elif len(calc_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = calc_ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result

    _order_state2 = {
        'draft': [('readonly', False)],
        'request': [('readonly', False)],
    }

    date_artwork = fields.Date(string='Artwork delivery', copy=False,
                               readonly=True, states=_order_state2)
    intermediair_calc_count = fields.Integer(string='# of Calculations', compute='_get_calc_count', readonly=True)


class PurchaseLine(models.Model):
    _inherit = "s2u.purchase.line"

    @api.one
    def _compute_startup_costs(self):

        for qty in self.qty_ids:
            if qty.for_order:
                self.startup_costs = qty.startup_costs
                return
        if self.qty_ids:
            self.startup_costs = self.qty_ids[0].startup_costs
        else:
            self.startup_costs = 0.0
        return

    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string="Calculation", ondelete='set null')
    startup_costs = fields.Monetary(string='Startup', currency_field='currency_id', compute=_compute_startup_costs,
                                    readonly=True)


class PurchaseLineQty(models.Model):
    _inherit = "s2u.purchase.line.qty"

    @api.one
    @api.depends('price', 'qty', 'price_per', 'startup_costs')
    def _compute_amount(self):

        if not self.price_per or not self.price:
            self.amount = self.startup_costs
            return

        if self.price_per == 'total':
            self.amount = self.price + self.startup_costs
            return

        qty = self.env['s2u.baseproduct.abstract'].parse_qty(self.qty)
        if not qty:
            self.amount = 0.0
            return

        if self.price_per == 'item':
            self.amount = round(qty * self.price, 2) + self.startup_costs
            return

        if self.price_per in ['10', '100', '1000']:
            qty = qty / float(self.price_per)
            self.amount = round(qty * self.price, 2) + self.startup_costs
            return

    startup_costs = fields.Monetary(string='Startup', currency_field='currency_id', default=0.0)
    amount = fields.Monetary(compute=_compute_amount)
    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string="Project", ondelete='set null')
