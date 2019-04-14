# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class OutgoingTodo(models.Model):
    _inherit = "s2u.warehouse.outgoing.todo"

    @api.multi
    def name_get(self):
        result = []
        for line in self:
            if line.saleline_id:
                if line.saleline_id.product_id and line.saleline_id.product_detail:
                    name = '%s/%s %s' % (line.saleline_id.sale_id.name, line.saleline_id.product_id.name,
                                         line.saleline_id.product_detail)
                elif line.saleline_id.product_id:
                    name = '%s/%s' % (line.saleline_id.sale_id.name, line.saleline_id.product_id.name)
                else:
                    name = '%s' % line.saleline_id.sale_id.name
            else:
                name = '%s/%s' % (line.outgoing_id.name, str(line.id))

            result.append((line.id, name))
        return result

    saleline_id = fields.Many2one('s2u.sale.line', string='SO Line', ondelete='restrict', index=True)
    sale_id = fields.Many2one('s2u.sale', string='SO', index=True, related='saleline_id.sale_id')
    purchase_id = fields.Many2one('s2u.purchase', string='PO', index=True,
                                  ondelete='set null')


class Outgoing(models.Model):
    _inherit = "s2u.warehouse.outgoing"

    @api.multi
    def unlink(self):

        for shipment in self:
            todos = self.env['s2u.warehouse.outgoing.todo'].search([('outgoing_id', '=', shipment.id),
                                                                    ('sale_id', '!=', False)])
            if todos:
                raise ValidationError(_('This shipment contains lines from sales order [%s]! Delete is not possible' % todos[0].sale_id.name))

        res = super(Outgoing, self).unlink()

        return res

    @api.multi
    def do_purchase(self):

        self.ensure_one()

        wiz_form = self.env.ref('s2usale.view_warehouse_outgoing_purchase', False)
        ctx = dict(
            default_model='s2u.warehouse.outgoing',
            default_res_id=self.id,
        )
        return {
            'name': _('Purchase products'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2u.warehouse.outgoing.purchase.add',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }

    def _get_purchase_count(self):

        for ship in self:
            purchases = []
            for line in ship.todo_ids:
                if line.purchase_id:
                    purchases.append(line.purchase_id.id)
            purchases = list(set(purchases))
            ship.purchase_count = len(purchases)

    @api.multi
    def action_view_purchase(self):
        purchases = []
        for line in self.todo_ids:
            if line.purchase_id:
                purchases.append(line.purchase_id.id)
        purchases = list(set(purchases))

        action = self.env.ref('s2usale.action_purchase').read()[0]
        if len(purchases) > 1:
            action['domain'] = [('id', 'in', purchases)]
        elif len(purchases) == 1:
            action['views'] = [(self.env.ref('s2usale.purchase_form').id, 'form')]
            action['res_id'] = purchases[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.one
    def _compute_template(self):

        if self.template_id:
            self.prefix_delivery = self.template_id.render_template(self.template_id.prefix_delivery,
                                                                    entity=self.delivery_entity_id,
                                                                    contact=self.delivery_contact_id,
                                                                    address=False,
                                                                    user=self.user_id,
                                                                    other=False)
            self.postfix_delivery = self.template_id.render_template(self.template_id.postfix_delivery,
                                                                     entity=self.delivery_entity_id,
                                                                     contact=self.delivery_contact_id,
                                                                     address=False,
                                                                     user=self.user_id,
                                                                     other=False)
            self.date_display = self.template_id.render_template(self.template_id.date_display,
                                                                 date=datetime.datetime.now().strftime('%Y-%m-%d'))
        else:
            self.prefix_delivery = ''
            self.postfix_delivery = ''
            self.date_display = ''

    @api.model
    def _default_template(self):

        return self.env['s2u.sale.template'].search([('default', '=', True)], limit=1)

    purchase_count = fields.Integer(string='# of Purchases', compute='_get_purchase_count', readonly=True)
    template_id = fields.Many2one('s2u.sale.template', string='Template', default=_default_template)
    prefix_delivery = fields.Html('Prefix', compute=_compute_template, readonly=True)
    postfix_delivery = fields.Html('Postfix', compute=_compute_template, readonly=True)
    date_display = fields.Text('Date display', compute=_compute_template, readonly=True)


class IncomingLine(models.Model):
    _inherit = "s2u.warehouse.incoming.line"

    purchase_id = fields.Many2one('s2u.purchase', string='PO', index=True, domain=[('state', '=', 'confirm')],
                                  ondelete='restrict')


class Incoming(models.Model):
    _inherit = "s2u.warehouse.incoming"

    def _get_purchase_count(self):

        for incoming in self:
            lines = self.env['s2u.warehouse.incoming.line'].search([('incoming_id', '=', incoming.id),
                                                                    ('purchase_id', '!=', False)])
            purchase_ids = [l.purchase_id.id for l in lines]
            purchase_ids = list(set(purchase_ids))
            incoming.purchase_count = len(purchase_ids)

    @api.multi
    def action_view_purchase(self):
        lines = self.env['s2u.warehouse.incoming.line'].search([('incoming_id', '=', self.id),
                                                                ('purchase_id', '!=', False)])
        purchase_ids = [l.purchase_id.id for l in lines]
        purchase_ids = list(set(purchase_ids))

        action = self.env.ref('s2usale.action_purchase').read()[0]
        if len(purchase_ids) > 1:
            action['domain'] = [('id', 'in', purchase_ids)]
        elif len(purchase_ids) == 1:
            action['views'] = [(self.env.ref('s2usale.purchase_form').id, 'form')]
            action['res_id'] = purchase_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def unlink(self):

        for shipment in self:
            lines = self.env['s2u.warehouse.incoming.line'].search([('incoming_id', '=', shipment.id),
                                                                    ('purchase_id', '!=', False)])
            if lines:
                raise ValidationError(_('This shipment contains lines from purchase order [%s]! Delete is not possible' % lines[0].purchase_id.name))

        res = super(Incoming, self).unlink()

        return res

    purchase_count = fields.Integer(string='# of Purchases', compute='_get_purchase_count', readonly=True)


class OutgoingPurchaseAddTransaction(models.TransientModel):
    _name = 's2u.warehouse.outgoing.purchase.add'

    @api.model
    def default_get(self, fields):

        rec = super(OutgoingPurchaseAddTransaction, self).default_get(fields)

        context = self._context
        active_model = context.get('active_model')
        outgoing_id = context.get('active_id', False)

        # Checks on context parameters
        if not active_model or not outgoing_id:
            raise UserError(
                _("Programmation error: wizard action executed without active_model or active_id in context."))
        if active_model != 's2u.warehouse.outgoing':
            raise UserError(_(
                "Programmation error: the expected model for this action is 's2u.warehouse.outgoing'. The provided one is '%d'.") % active_model)

        lines = []
        todos = self.env['s2u.warehouse.outgoing.todo'].search([('outgoing_id', '=', outgoing_id)])
        for t in todos:
            if t.purchase_id:
                continue
            if t.product_qty + t.shipped_qty <= 0.0:
                continue

            if t.product_id.res_model == 's2u.sale.product':
                po_prices = self.env['s2u.sale.product.purchase'].search([('product_id', '=', t.product_id.res_id)], order='po_price')
                if po_prices:
                    lines.append((0, _,  {
                        'product_id': t.product_id.id,
                        'product_detail': t.product_detail,
                        'qty_purchase': _('%d stuks' % int(t.product_qty + t.shipped_qty)),
                        'entity_id': po_prices[0].entity_id.id,
                        'po_price': po_prices[0].po_price,
                        'todo_id': t.id
                    }))
        rec.update({
            'outgoing_id': outgoing_id,
            'line_ids': lines
        })

        return rec

    @api.multi
    def do_purchase(self):

        suppliers = {}
        for line in self.line_ids:
            total_to_purchase = self.env['s2u.baseproduct.abstract'].parse_qty(line.qty_purchase)
            if total_to_purchase <= 0.0:
                continue

            vals = {
                'product_id': line.product_id.id,
                'product_detail': line.product_detail,
                'qty_ids': [(0, 0, {
                    'qty': line.qty_purchase,
                    'price': line.po_price,
                    'price_per':  'item',
                    'amount': total_to_purchase * line.po_price,
                })],
                'date_delivery': fields.Date.context_today(self),
            }
            if suppliers.get(line.entity_id.id, False):
                suppliers[line.entity_id.id]['lines'].append((0, 0, vals))
                suppliers[line.entity_id.id]['todo'] += line.todo_id
            else:
                suppliers[line.entity_id.id] = {
                    'todo': line.todo_id,
                    'lines': [(0, 0, vals)]
                }

        for supplier_id, item in iter(suppliers.items()):
            vals = {
                'partner_id': supplier_id,
                'line_ids': item['lines'],
                'outgoing_id': self.outgoing_id.id
            }
            purchase = self.env['s2u.purchase'].create(vals)
            item['todo'].write({
                'purchase_id': purchase.id
            })

        return {
            'type': 'ir.actions.act_window_close'
        }

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Levering')
    line_ids = fields.One2many('s2u.warehouse.outgoing.purchase.add.item', 'add_id', string='Lines')


class OutgoingPurchaseAddTransactionItem(models.TransientModel):
    _name = 's2u.warehouse.outgoing.purchase.add.item'

    add_id = fields.Many2one('s2u.warehouse.outgoing.purchase.add', string='Add', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True)
    product_detail = fields.Char(string='Details')
    qty_purchase = fields.Char(string='Qty', required=True)
    entity_id = fields.Many2one('s2u.crm.entity', string='Supplier', required=True, ondelete='set null')
    po_price = fields.Monetary(string='PO Price', currency_field='currency_id', required=True)
    todo_id = fields.Many2one('s2u.warehouse.outgoing.todo', string='Todo', ondelete='set null')

    @api.one
    @api.constrains('qty_purchase')
    def _check_qty_received(self):
        if not self.qty_purchase:
            raise ValidationError("Please enter value for 'Qty'.")
        if not self.env['s2u.baseproduct.abstract'].parse_qty(self.qty_purchase):
            raise ValidationError("Invalid value for 'Qty'.")


class RMA(models.Model):
    _inherit = "s2u.warehouse.rma"

    @api.one
    def _compute_template(self):

        if self.template_id:
            self.prefix_rma = self.template_id.render_template(self.template_id.prefix_rma,
                                                               entity=self.entity_id,
                                                               contact=self.contact_id,
                                                               address=self.address_id)
            self.postfix_rma = self.template_id.render_template(self.template_id.postfix_rma,
                                                                entity=self.entity_id,
                                                                contact=self.contact_id,
                                                                address=self.address_id)
            self.date_display = self.template_id.render_template(self.template_id.date_display,
                                                                 date=datetime.datetime.now().strftime('%Y-%m-%d'))
        else:
            self.prefix_rma = ''
            self.postfix_rma = ''
            self.date_display = ''

    @api.model
    def _default_template(self):

        return self.env['s2u.sale.template'].search([('default', '=', True)], limit=1)

    template_id = fields.Many2one('s2u.sale.template', string='Template', default=_default_template)
    prefix_rma = fields.Html('Postfix', compute=_compute_template, readonly=True)
    postfix_rma = fields.Html('Postfix', compute=_compute_template, readonly=True)
    date_display = fields.Text('Date display', compute=_compute_template, readonly=True)
