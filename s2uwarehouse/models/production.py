# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ProducedLine(models.Model):
    _name = "s2u.warehouse.produced.line"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _description = "Produced line"
    _order = "date_produced, product_id"

    @api.one
    def _compute_produced_qty(self):

        tot_produced = 0.0

        for trans in self.produced_id.trans_ids:
            if trans.produced_line_id.id != self.id:
                continue
            if trans.product_id.product_id == self.product_id and trans.product_id.product_detail == self.product_detail:
                tot_produced += trans.qty

        self.produced_qty = tot_produced

    produced_id = fields.Many2one('s2u.warehouse.produced', string='Produced', required=True, index=True,
                                  ondelete='cascade')
    date_produced = fields.Date(string='Date', required=True,
                                default=lambda self: fields.Date.context_today(self))
    type = fields.Selection([
        ('produced', 'Producing'),
        ('leftover', 'Left over'),
        ('scrapped', 'Scrapped/lost')
    ], required=True, default='produced', string='Type', copy=False)
    produced_qty = fields.Float(string='Produced', compute=_compute_produced_qty, readonly=True)
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Shipment', ondelete='cascade',
                                  domain=[('state', 'in', ['production'])])


class ProducedAssignedUnit(models.Model):
    _name = "s2u.warehouse.produced.assigned.unit"

    produced_id = fields.Many2one('s2u.warehouse.produced', string='Produced', required=True, index=True,
                                  ondelete='cascade')
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', required=True, index=True, ondelete='restrict')
    on_unit = fields.Text(string='On unit', related='unit_id.on_unit', readonly=True)
    type = fields.Selection([
        ('singleton', 'Eenheid'),
        ('pallet', 'Pallet')
    ], string='Type', readonly=True, related='unit_id.type')
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Pallet', readonly=True, related='unit_id.pallet_id')
    pallet_factor = fields.Integer(string='Factor', readonly=True, related='unit_id.pallet_factor')
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', readonly=True,
                                  related='unit_id.location_id')
    active = fields.Boolean(default=True)

    @api.multi
    def unlink(self):

        for assigned in self:
            assigned.unit_id.unassign_unit()

        res = super(ProducedAssignedUnit, self).unlink()

        return res

    @api.model
    def create(self, vals):

        unit_model = self.env['s2u.warehouse.unit']

        unit = unit_model.search([('id', '=', vals['unit_id'])])
        unit.assign_unit()

        assigned = super(ProducedAssignedUnit, self).create(vals)
        return assigned

    @api.multi
    def write(self, vals):

        unit_model = self.env['s2u.warehouse.unit']

        for assigned in self:
            if vals.get('unit_id', False):
                assigned.unit_id.unassign_unit()
                unit = unit_model.search([('id', '=', vals['unit_id'])])
                unit.assign_unit()
            elif 'active' in vals:
                if not vals['active']:
                    assigned.unit_id.unassign_unit()
                else:
                    assigned.unit_id.assign_unit()

        return super(ProducedAssignedUnit, self).write(vals)


class ProducedAssignedUnitProduct(models.Model):
    _name = "s2u.warehouse.produced.assigned.unit.product"

    produced_id = fields.Many2one('s2u.warehouse.produced', string='Produced', required=True, index=True,
                                  ondelete='cascade')
    unitproduct_id = fields.Many2one('s2u.warehouse.unit.product', string='Item', required=True, index=True, ondelete='restrict')
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', readonly=True,
                              related='unitproduct_id.unit_id')
    current_location_id = fields.Many2one('s2u.warehouse.location', string='Location', readonly=True,
                                          related='unitproduct_id.location_id')
    assigned_qty = fields.Float(string='Qty assigned', required=True)
    active = fields.Boolean(default=True)

    @api.multi
    def unlink(self):

        for assigned in self:
            assigned.unitproduct_id.unassign_item(assigned.assigned_qty)

        res = super(ProducedAssignedUnitProduct, self).unlink()

        return res

    @api.model
    def create(self, vals):

        item_model = self.env['s2u.warehouse.unit.product']

        item = item_model.search([('id', '=', vals['unitproduct_id'])])
        item.assign_item(vals['assigned_qty'])

        assigned = super(ProducedAssignedUnitProduct, self).create(vals)
        return assigned

    @api.multi
    def write(self, vals):

        item_model = self.env['s2u.warehouse.unit.product']

        for assigned in self:
            if vals.get('unitproduct_id', False) or 'assigned_qty' in vals:
                assigned.unitproduct_id.unassign_item(assigned.assigned_qty)
                if vals.get('unitproduct_id', False):
                    item = item_model.search([('id', '=', vals['unitproduct_id'])])
                else:
                    item = assigned.unitproduct_id
                if 'assigned_qty' in vals:
                    assigned_qty = vals['assigned_qty']
                else:
                    assigned_qty = assigned.assigned_qty
                item.assign_item(assigned_qty)
            elif 'active' in vals:
                if not vals['active']:
                    assigned.unitproduct_id.unassign_item(assigned.assigned_qty)
                else:
                    assigned.unitproduct_id.assign_item(assigned.assigned_qty)

        return super(ProducedAssignedUnitProduct, self).write(vals)


class Produced(models.Model):
    _name = "s2u.warehouse.produced"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Delivery"
    _order = "date_produced, name"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Produced, self)._track_subtype(init_values)

    @api.one
    @api.depends('line_ids.date_produced', 'state')
    def _compute_date_produced(self):
        dl = False
        if self.state in ['draft', 'wait']:
            for delivery in self.line_ids:
                if not dl or delivery.date_produced < dl:
                    dl = delivery.date_produced
        self.date_produced = dl

    _produced_state = {
        'draft': [('readonly', False)],
    }

    _wait_state = {
        'wait': [('readonly', False)],
    }

    _produced_wait_state = {
        'draft': [('readonly', False)],
        'wait': [('readonly', False)],
    }

    name = fields.Char(string='Assignment', required=True, index=True, copy=False, readonly=True, states=_produced_state)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    line_ids = fields.One2many('s2u.warehouse.produced.line', 'produced_id',
                               string='Produced', copy=True, readonly=True, states=_produced_wait_state)
    date_produced = fields.Date(string='Planning', compute=_compute_date_produced, store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Pending'),
        ('wait', 'In production'),
        ('done', 'Done'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State', copy=False, track_visibility='onchange')
    unit_ids = fields.One2many('s2u.warehouse.unit', 'produced_id',
                               string='Units', copy=False, readonly=True, states=_produced_wait_state)
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'produced_id',
                                string='Transactions', copy=False, readonly=True)
    units_assigned_ids = fields.One2many('s2u.warehouse.produced.assigned.unit', 'produced_id',
                                         string='Units assigned', copy=False)
    items_assigned_ids = fields.One2many('s2u.warehouse.produced.assigned.unit.product', 'produced_id',
                                         string='Items assigned', copy=False)
    reference = fields.Char(string='Reference', index=True, readonly=True, states=_produced_wait_state)
    project = fields.Char(string='Project', index=True, readonly=True, states=_produced_wait_state)

    @api.multi
    def do_assigned_unit_items(self):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        for assigned in self.items_assigned_ids:
            assigned_qty = assigned.assigned_qty

            assigned.unitproduct_id.write({
                'product_qty': assigned.unitproduct_id.product_qty - assigned_qty
            })

            vals = {
                'parent_id': False,
                'unit_id': assigned.unitproduct_id.unit_id.id,
                'location_id': assigned.unitproduct_id.unit_id.location_id.id,
                'product_id': assigned.unitproduct_id.id,
                'qty': assigned_qty * -1.0,
                'transaction_date': fields.Date.context_today(self),
                'source_model': 's2u.warehouse.produced',
                'source_id': self.id,
                'produced_id': self.id,
                'item_picking': True
            }
            trans_model.create(vals)
            assigned.unitproduct_id.unit_id.empty_unit(write=True)

        return True

    @api.multi
    def do_assigned_units(self, units):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        unit_model = self.env['s2u.warehouse.unit']

        for unit in units:
            if not unit.active:
                raise ValidationError(_('You are trying to ship units which are not present!'))

            for childunit in unit_model.search([('parent_id', '=', unit.id)]):
                if not childunit.active:
                    raise ValidationError(_('You are trying to ship units which are not present!'))
                for product in childunit.line_ids:
                    assigned_qty = product.product_qty

                    product.write({
                        'product_qty': 0.0
                    })

                    vals = {
                        'parent_id': childunit.parent_id.id,
                        'unit_id': childunit.id,
                        'location_id': childunit.location_id.id,
                        'product_id': product.id,
                        'qty': assigned_qty * -1.0,
                        'transaction_date': fields.Date.context_today(self),
                        'source_model': 's2u.warehouse.produced',
                        'source_id': self.id,
                        'produced_id': self.id,
                    }
                    trans_model.create(vals)
                childunit.empty_unit(write=True)

            for product in unit.line_ids:
                assigned = product.product_qty

                product.write({
                    'product_qty': 0.0
                })

                vals = {
                    'parent_id': unit.parent_id.id if unit.parent_id else False,
                    'unit_id': unit.id,
                    'location_id': unit.location_id.id,
                    'product_id': product.id,
                    'qty': assigned * -1.0,
                    'transaction_date': fields.Date.context_today(self),
                    'source_model': 's2u.warehouse.produced',
                    'source_id': self.id,
                    'produced_id': self.id
                }
                trans_model.create(vals)

            unit.empty_unit(write=True)

        return True

    @api.multi
    def do_confirm(self):

        self.write({
            'state': 'wait'
        })

    @api.multi
    def do_cancel(self):

        for production in self:
            for assigned in production.units_assigned_ids:
                assigned.unit_id.unassign_unit()
            for assigned in production.items_assigned_ids:
                assigned.unitproduct_id.unassign_item(assigned.assigned_qty)

        self.write({
            'state': 'cancel'
        })

    @api.multi
    def undo_done(self):

        assigned_units_model = self.env['s2u.warehouse.produced.assigned.unit']
        assigned_items_model = self.env['s2u.warehouse.produced.assigned.unit.product']

        self.ensure_one()

        for trans in self.trans_ids:
            trans.product_id.write({
                'product_qty': trans.product_id.product_qty - trans.qty
            })
            trans.product_id.unit_id.empty_unit(write=True)

        units = assigned_units_model.search([('produced_id', '=', self.id), ('active', '=', False)])
        units.write({
            'active': True
        })

        items = assigned_items_model.search([('produced_id', '=', self.id), ('active', '=', False)])
        items.write({
            'active': True
        })

        self.trans_ids.unlink()

        self.write({
            'state': 'draft'
        })


    @api.multi
    def do_done(self):
        assigned_units_model = self.env['s2u.warehouse.produced.assigned.unit']
        assigned_items_model = self.env['s2u.warehouse.produced.assigned.unit.product']

        self.ensure_one()

        tot_produced = 0.0
        for item in self.line_ids:
            tot_produced += item.produced_qty
        if not tot_produced:
            raise ValidationError(_('There is nothing produced, you can not close this production!'))

        assigned_units = assigned_units_model.search([('produced_id', '=', self.id)])
        units = [au.unit_id for au in assigned_units]
        self.do_assigned_units(units)
        assigned_units.write({
            'active': False
        })

        self.do_assigned_unit_items()
        assigned_items = assigned_items_model.search([('produced_id', '=', self.id)])
        assigned_items.write({
            'active': False
        })

        self.write({
            'state': 'done'
        })

    @api.multi
    def unlink(self):

        for production in self:
            if production.state != 'draft':
                raise ValidationError(_('You can not delete a confirmed production!'))
            for assigned in production.units_assigned_ids:
                assigned.unit_id.unassign_unit()
            for assigned in production.items_assigned_ids:
                assigned.unitproduct_id.unassign_item(assigned.assigned_qty)

        res = super(Produced, self).unlink()

        return res


class ProducedAddTransaction(models.TransientModel):
    _name = 's2u.warehouse.produced.add'

    @api.model
    def default_get(self, fields):

        unit_model = self.env['s2u.warehouse.unit']
        product_model = self.env['s2u.warehouse.unit.product']

        rec = super(ProducedAddTransaction, self).default_get(fields)

        context = self._context
        active_model = context.get('active_model')
        produced_id = context.get('active_id', False)

        # Checks on context parameters
        if not active_model or not produced_id:
            raise UserError(
                _("Programmation error: wizard action executed without active_model or active_id in context."))
        if active_model != 's2u.warehouse.produced':
            raise UserError(_(
                "Programmation error: the expected model for this action is 's2u.warehouse.produced'. The provided one is '%d'.") % active_model)

        lines = []
        products_used = {}
        po_products = self.env['s2u.warehouse.produced.line'].search([('produced_id', '=', produced_id)])
        for p in po_products:
            tot_received = 0.0

            units = unit_model.search([('active', 'in', [True, False]),
                                       ('produced_id', '=', produced_id)])
            for unit in units:
                products = product_model.search([('unit_id', '=', unit.id),
                                                 ('product_id', '=', p.product_id.id),
                                                 ('product_detail', '=', p.product_detail)])
                for product in products:
                    if product.id in products_used:
                        if product.product_qty - products_used[product.id] >= 0.0:
                            qty_add = product.product_qty - products_used[product.id]
                            if p.product_qty - tot_received >= qty_add:
                                tot_received += qty_add
                                products_used[product.id] += qty_add
                            else:
                                qty_add = p.product_qty - tot_received
                                tot_received += qty_add
                                products_used[product.id] += qty_add
                        else:
                            continue
                    else:
                        if p.product_qty - tot_received >= product.product_qty:
                            tot_received += product.product_qty
                            products_used[product.id] = product.product_qty
                        else:
                            tot_received += p.product_qty - tot_received
                            products_used[product.id] = p.product_qty - tot_received

            lines.append((0, 0,  {
                'line_id': p.id,
                'outgoing_id': p.outgoing_id.id if p.outgoing_id else False,
                'product_id': p.product_id.id,
                'product_value': p.product_value,
                'product_detail': p.product_detail,
                'qty_open': p.product_qty - tot_received
            }))
        rec.update({
            'produced_id': produced_id,
            'line_ids': lines
        })

        location = self.env['s2u.warehouse.location'].search([('usage', '=', 'produced')], limit=1)
        if location:
            rec['location_id'] = location.id

        return rec

    @api.multi
    def do_add(self):
        unit_model = self.env['s2u.warehouse.unit']
        product_model = self.env['s2u.warehouse.unit.product']
        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        if self.produced_id.state == 'draft':
            raise ValidationError(_('Please confirm production first, before producing goods!'))

        if self.produced_id.state != 'wait':
            raise ValidationError(_('This production is closed, you can not produce new goods!'))

        outgoings_used = [False]
        for item in self.line_ids:
            if item.outgoing_id and item.outgoing_id not in outgoings_used:
                outgoings_used.append(item.outgoing_id)

        for outgoing in outgoings_used:
            units_produced = []
            if self.pallets:
                # we receive the items on pallets
                total_qty = 0.0
                for item in self.line_ids:
                    if not ((not outgoing and not item.outgoing_id) or (outgoing and item.outgoing_id and outgoing.id == item.outgoing_id.id)):
                        continue
                    parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                    if not parsed_qty:
                        raise ValidationError(_("Please enter a valid value for 'Qty'!"))
                    if parsed_qty[0]:
                        total_qty += (float(parsed_qty[0]) * parsed_qty[2])
                    else:
                        total_qty += parsed_qty[2]
                # we only create the pallets when we have items on it
                if total_qty > 0.0:
                    for i in range(self.pallets):
                        unit = unit_model.create({
                            'produced_id': self.produced_id.id,
                            'type': 'pallet',
                            'pallet_id': self.pallet_id.id,
                            'pallet_factor': self.pallet_factor,
                            'location_id': self.location_id.id
                        })

                        units_produced.append(unit)

                        for item in self.line_ids:
                            if not ((not outgoing and not item.outgoing_id) or (outgoing and item.outgoing_id and outgoing.id == item.outgoing_id.id)):
                                continue
                            parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                            if parsed_qty[2]:
                                # we hebben te maken met een verpakking op de pallet
                                if parsed_qty[0]:
                                    for box_no in range(parsed_qty[0]):
                                        box = unit_model.create({
                                            'produced_id': self.produced_id.id,
                                            'type': 'box',
                                            'location_id': self.location_id.id,
                                            'parent_id': unit.id
                                        })
                                        vals = {
                                            'unit_id': box.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': parsed_qty[2],
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail
                                        }
                                        product = product_model.create(vals)

                                        vals = {
                                            'unit_id': box.id,
                                            'parent_id': unit.id,
                                            'location_id': box.location_id.id,
                                            'product_id': product.id,
                                            'qty': parsed_qty[2],
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.produced',
                                            'source_id': self.produced_id.id,
                                            'produced_id': self.produced_id.id,
                                            'produced_line_id': item.line_id.id
                                        }
                                        trans_model.create(vals)
                                else:
                                    vals = {
                                        'unit_id': unit.id,
                                        'product_id': item.product_id.id,
                                        'product_qty': parsed_qty[2],
                                        'product_value': item.product_value,
                                        'product_detail': item.product_detail
                                    }
                                    product = product_model.create(vals)

                                    vals = {
                                        'product_id': product.id,
                                        'unit_id': unit.id,
                                        'location_id': unit.location_id.id,
                                        'qty': parsed_qty[2],
                                        'transaction_date': self.transaction_date,
                                        'source_model': 's2u.warehouse.produced',
                                        'source_id': self.produced_id.id,
                                        'produced_id': self.produced_id.id,
                                        'produced_line_id': item.line_id.id
                                    }
                                    trans_model.create(vals)
            else:
                # we receive the items without a placeholder
                total_qty = 0.0
                for item in self.line_ids:
                    if not ((not outgoing and not item.outgoing_id) or (outgoing and item.outgoing_id and outgoing.id == item.outgoing_id.id)):
                        continue
                    parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                    if not parsed_qty:
                        raise ValidationError(_("Please enter a valid value for 'Qty'!"))
                    if parsed_qty[0]:
                        total_qty += (float(parsed_qty[0]) * parsed_qty[2])
                    else:
                        total_qty += parsed_qty[2]
                if total_qty > 0.0:
                    unit = unit_model.create({
                        'produced_id': self.produced_id.id,
                        'type': 'singleton',
                        'location_id': self.location_id.id
                    })
                    units_produced.append(unit)
                    for item in self.line_ids:
                        if not ((not outgoing and not item.outgoing_id) or (outgoing and item.outgoing_id and outgoing.id == item.outgoing_id.id)):
                            continue
                        parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                        if parsed_qty[2]:
                            # we hebben te maken met een verpakking
                            if parsed_qty[0]:
                                for box_no in range(parsed_qty[0]):
                                    box = unit_model.create({
                                        'produced_id': self.produced_id.id,
                                        'type': 'box',
                                        'location_id': self.location_id.id,
                                        'parent_id': unit.id
                                    })
                                    vals = {
                                        'unit_id': box.id,
                                        'product_id': item.product_id.id,
                                        'product_qty': parsed_qty[2],
                                        'product_value': item.product_value,
                                        'product_detail': item.product_detail
                                    }
                                    product = product_model.create(vals)

                                    vals = {
                                        'product_id': product.id,
                                        'unit_id': box.id,
                                        'parent_id': unit.id,
                                        'location_id': box.location_id.id,
                                        'qty': parsed_qty[2],
                                        'transaction_date': self.transaction_date,
                                        'source_model': 's2u.warehouse.produced',
                                        'source_id': self.produced_id.id,
                                        'produced_id': self.produced_id.id,
                                        'produced_line_id': item.line_id.id
                                    }
                                    trans_model.create(vals)
                            else:
                                vals = {
                                    'unit_id': unit.id,
                                    'product_id': item.product_id.id,
                                    'product_qty': parsed_qty[2],
                                    'product_value': item.product_value,
                                    'product_detail': item.product_detail
                                }
                                product = product_model.create(vals)

                                vals = {
                                    'product_id': product.id,
                                    'unit_id': unit.id,
                                    'location_id': unit.location_id.id,
                                    'qty': parsed_qty[2],
                                    'transaction_date': self.transaction_date,
                                    'source_model': 's2u.warehouse.produced',
                                    'source_id': self.produced_id.id,
                                    'produced_id': self.produced_id.id,
                                    'produced_line_id': item.line_id.id
                                }
                                trans_model.create(vals)

            if outgoing:
                for unit in units_produced:
                    self.env['s2u.warehouse.outgoing.assigned.unit'].create({
                        'outgoing_id': outgoing.id,
                        'unit_id': unit.id
                    })
                outgoing.calculate_assigned()

    produced_id = fields.Many2one('s2u.warehouse.produced', string='Produced')
    pallets = fields.Integer(string='Units', requird=True)
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Unit')
    pallet_factor = fields.Integer(string='Unit factor', default=1, requird=True)
    line_ids = fields.One2many('s2u.warehouse.produced.add.item', 'add_id', string='Lines')
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', required=True)
    transaction_date = fields.Date(string='Date', index=True, copy=False, required=True,
                                   default=lambda self: fields.Date.context_today(self))

    @api.model
    def create(self, vals):

        # skip lines where not qty is entered, otherwise system raises error because field qty is required
        lines = []
        for l in vals['line_ids']:
            if l[2].get('qty_received', False):
                lines.append(l)
        vals.update({'line_ids': lines})
        res = super(ProducedAddTransaction, self).create(vals)
        return res


class ProducedAddTransactionItem(models.TransientModel):
    _name = 's2u.warehouse.produced.add.item'
    _inherit = "s2u.baseproduct.transaction.abstract"

    add_id = fields.Many2one('s2u.warehouse.produced.add', string='Pallet', required=True)
    qty_received = fields.Char(string='Qty', required=True)
    qty_open = fields.Float(string='Qty open')
    product_qty = fields.Float(required=False, default=1.0)
    line_id = fields.Many2one('s2u.warehouse.produced.line', string='Produced line', ondelete='set null')
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Shipment', related='line_id.outgoing_id')

    @api.one
    @api.constrains('qty_received')
    def _check_qty_received(self):
        if not self.qty_received:
            raise ValidationError("Please enter value for 'Qty'.")
        if not self.env['s2u.warehouse.uom'].parse_qty(self.qty_received):
            raise ValidationError("Invalid value for 'Qty'.")


class ProductionUsedMaterialsLine(models.Model):
    _name = "s2u.warehouse.production.used.materials.line"

    usedmaterials_id = fields.Many2one('s2u.warehouse.production.used.materials', string='Used materials', required=True, index=True,
                                       ondelete='cascade')
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', index=True, required=True)
    type = fields.Selection([
        ('singleton', 'Eenheid'),
        ('pallet', 'Pallet')
    ], string='Type', readonly=True, related='unit_id.type')
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Pallet', readonly=True, related='unit_id.pallet_id')
    pallet_factor = fields.Integer(string='Factor', readonly=True, related='unit_id.pallet_factor')
    on_unit = fields.Text(string='On unit', related='unit_id.on_unit', readonly=True)


class ProductionUsedMaterialsLineItem(models.Model):
    _name = "s2u.warehouse.production.used.materials.line.item"

    @api.one
    @api.constrains('product_qty')
    def _check_qty(self):
        if self.product_qty <= 0.0:
            raise ValidationError(_('Used qty must have a positive value!'))

    @api.onchange('product_id')
    def onchange_unit(self):

        if self.product_id:
            self.product_value = self.product_id.product_value

    usedmaterials_id = fields.Many2one('s2u.warehouse.production.used.materials', string='Used materials',
                                       required=True, index=True,
                                       ondelete='cascade')
    product_id = fields.Many2one('s2u.warehouse.unit.product', string='Product', required=True, index=True,
                                 domain=[('unit_id.active', '=', True)],
                                 ondelete='restrict')
    product_qty = fields.Float(string='Qty used', required=True)
    product_value = fields.Float(string='Price/value', digits=(16, 4))


class ProductionUsedMaterials(models.Model):
    _name = "s2u.warehouse.production.used.materials"
    _description = "Used materials"
    _order = "id desc"

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.warehouse.used.materials')])
        if not exists:
            raise ValueError(_('Sequence for creating s2u.warehouse.used.materials number not exists!'))

        sequence = exists[0]
        new_number = sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()
        if self.env.user.name:
            name = self.env.user.name.split(' ')
            initials = ''
            for n in name:
                initials = '%s%s' % (initials, n[0].upper())
            new_number = '%s/%s' % (new_number, initials)
        return new_number

    _used_state = {
        'draft': [('readonly', False)],
        'reserved': [('readonly', False)],
    }

    name = fields.Char(string='Number', required=True, index=True, copy=False,
                       default=_new_number, readonly=True, states=_used_state)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    line_ids = fields.One2many('s2u.warehouse.production.used.materials.line', 'usedmaterials_id',
                               string='Pallets', copy=False,
                               readonly=True, states=_used_state)
    line_item_ids = fields.One2many('s2u.warehouse.production.used.materials.line.item', 'usedmaterials_id',
                                    string='Items', copy=False,
                                    readonly=True, states=_used_state)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('reserved', 'Reserved'),
        ('done', 'Used'),
        ('cancel', 'Canceled')
    ], required=True, default='draft', string='State', copy=False)
    transaction_date = fields.Date(string='Date', index=True, copy=False, required=True,
                                   readonly=True, states=_used_state,
                                   default=lambda self: fields.Date.context_today(self))
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'usedmaterials_id',
                                string='Transactions', copy=False, readonly=True)
    descript = fields.Text(string='Description')
    reference = fields.Char(string='Reference', index=True, readonly=True, states=_used_state)
    project = fields.Char(string='Project', index=True, readonly=True, states=_used_state)

    @api.multi
    def do_confirm(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        unit_model = self.env['s2u.warehouse.unit']

        self.undo_confirm()

        for line in self.line_ids:
            if not line.unit_id.active:
                raise ValidationError(_('You are trying to use units which are not present!'))

            for unit in unit_model.search([('parent_id', '=', line.unit_id.id)]):
                if not unit.active:
                    raise ValidationError(_('You are trying to use units which are not present!'))
                for product in unit.line_ids:
                    used = product.product_qty

                    product.write({
                        'product_qty': 0.0
                    })

                    vals = {
                        'parent_id': unit.parent_id.id if unit.parent_id else False,
                        'unit_id': unit.id,
                        'location_id': unit.location_id.id,
                        'product_id': product.id,
                        'qty': used * -1.0,
                        'transaction_date': self.transaction_date,
                        'source_model': 's2u.warehouse.production.used.materials',
                        'source_id': self.id,
                        'usedmaterials_id': self.id
                    }
                    trans_model.create(vals)
                unit.empty_unit(write=True)

            for product in line.unit_id.line_ids:
                used = product.product_qty

                product.write({
                    'product_qty': 0.0
                })

                vals = {
                    'parent_id': line.unit_id.parent_id.id if line.unit_id.parent_id else False,
                    'unit_id': line.unit_id.id,
                    'location_id': line.unit_id.location_id.id,
                    'product_id': product.id,
                    'qty': used * -1.0,
                    'transaction_date': self.transaction_date,
                    'source_model': 's2u.warehouse.production.used.materials',
                    'source_id': self.id,
                    'usedmaterials_id': self.id
                }
                trans_model.create(vals)

            line.unit_id.empty_unit(write=True)

        for line in self.line_item_ids:
            if not line.product_id.unit_id.active:
                raise ValidationError(_('You are trying to use items which are not present!'))

            line.product_id.write({
                'product_qty': line.product_id.product_qty - line.product_qty
            })

            vals = {
                'parent_id': line.product_id.unit_id.parent_id.id if line.product_id.unit_id.parent_id else False,
                'unit_id': line.product_id.unit_id.id,
                'location_id': line.product_id.unit_id.location_id.id,
                'product_id': line.product_id.id,
                'qty': line.product_qty * -1.0,
                'transaction_date': self.transaction_date,
                'source_model': 's2u.warehouse.production.used.materials',
                'source_id': self.id,
                'usedmaterials_id': self.id
            }
            trans_model.create(vals)
            line.product_id.unit_id.empty_unit(write=True)

        self.write({
            'state': 'done'
        })

    @api.multi
    def do_reserved(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        unit_model = self.env['s2u.warehouse.unit']

        self.undo_confirm()

        for line in self.line_ids:
            if not line.unit_id.active:
                raise ValidationError(_('You are trying to use units which are not present!'))

            for unit in unit_model.search([('parent_id', '=', line.unit_id.id)]):
                if not unit.active:
                    raise ValidationError(_('You are trying to use units which are not present!'))
                for product in unit.line_ids:
                    used = product.product_qty

                    product.write({
                        'product_qty': 0.0
                    })

                    vals = {
                        'parent_id': unit.parent_id.id if unit.parent_id else False,
                        'unit_id': unit.id,
                        'location_id': unit.location_id.id,
                        'product_id': product.id,
                        'qty': used * -1.0,
                        'transaction_date': self.transaction_date,
                        'source_model': 's2u.warehouse.production.used.materials',
                        'source_id': self.id,
                        'usedmaterials_id': self.id
                    }
                    trans_model.create(vals)
                unit.empty_unit(write=True)

            for product in line.unit_id.line_ids:
                used = product.product_qty

                product.write({
                    'product_qty': 0.0
                })

                vals = {
                    'parent_id': line.unit_id.parent_id.id if line.unit_id.parent_id else False,
                    'unit_id': line.unit_id.id,
                    'location_id': line.unit_id.location_id.id,
                    'product_id': product.id,
                    'qty': used * -1.0,
                    'transaction_date': self.transaction_date,
                    'source_model': 's2u.warehouse.production.used.materials',
                    'source_id': self.id,
                    'usedmaterials_id': self.id
                }
                trans_model.create(vals)

            line.unit_id.empty_unit(write=True)

        for line in self.line_item_ids:
            if not line.product_id.unit_id.active:
                raise ValidationError(_('You are trying to use items which are not present!'))

            line.product_id.write({
                'product_qty': line.product_id.product_qty - line.product_qty
            })

            vals = {
                'parent_id': line.product_id.unit_id.parent_id.id if line.product_id.unit_id.parent_id else False,
                'unit_id': line.product_id.unit_id.id,
                'location_id': line.product_id.unit_id.location_id.id,
                'product_id': line.product_id.id,
                'qty': line.product_qty * -1.0,
                'transaction_date': self.transaction_date,
                'source_model': 's2u.warehouse.production.used.materials',
                'source_id': self.id,
                'usedmaterials_id': self.id
            }
            trans_model.create(vals)
            line.product_id.unit_id.empty_unit(write=True)

        self.write({
            'state': 'reserved'
        })

    @api.multi
    def undo_confirm(self):

        self.ensure_one()

        for trans in self.trans_ids:
            trans.product_id.write({
                'product_qty': trans.product_id.product_qty - trans.qty
            })
            trans.product_id.unit_id.empty_unit(write=True)

        self.trans_ids.unlink()

        self.write({
            'state': 'draft'
        })

    @api.multi
    def unlink(self):

        for used in self:
            if used.state == 'done':
                raise ValidationError(_('You can not delete a confirmed used materials!'))

        res = super(ProductionUsedMaterials, self).unlink()

        return res
