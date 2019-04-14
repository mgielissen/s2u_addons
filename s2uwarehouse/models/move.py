# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class WarehouseMoveScrapped(models.Model):
    _name = "s2u.warehouse.move.scrapped"
    _order = "id desc"

    _scrapped_state = {
        'draft': [('readonly', False)],
    }

    @api.onchange('unit_id', 'scrap_method')
    def onchange_unit(self):

        if not self.unit_id:
            return {'domain': {'product_id': [('unit_id', '=', False)]}}

        return {'domain': {'product_id': [('unit_id', '=', self.unit_id.id)]}}

    @api.one
    @api.constrains('product_qty')
    def _check_qty(self):
        if self.scrap_method == 'part' and self.product_qty <= 0.0:
                raise ValidationError(_('Scrapped qty must have a positive value!'))

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', required=True, index=True, ondelete='restrict',
                              readonly=True, states=_scrapped_state)
    scrap_method = fields.Selection([
        ('complete', 'Complete unit'),
        ('part', 'Some products')
    ], required=True, default='part', string='Scrap', copy=False)
    product_id = fields.Many2one('s2u.warehouse.unit.product', string='Product', index=True,
                                 ondelete='restrict', readonly=True, states=_scrapped_state)
    product_qty = fields.Float(string='Qty scrapped', readonly=True, states=_scrapped_state, default=1.0)
    remarks = fields.Text(string='Remarks', readonly=True, states=_scrapped_state, required=True)
    user_id = fields.Many2one('res.users', string='User', required=True,
                              default=lambda self: self.env.user, readonly=True, states=_scrapped_state, copy=False)
    date_entry = fields.Date(string='Date', default=lambda self: fields.Date.context_today(self), index=True,
                             required=True, readonly=True, states=_scrapped_state, copy=False)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('done', 'Confirmed')
    ], required=True, default='draft', string='State', copy=False)
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'scrapped_id',
                                string='Transactions', copy=False, readonly=True)

    @api.multi
    def do_confirm(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        unit_model = self.env['s2u.warehouse.unit']

        if not self.unit_id.active:
            raise ValidationError(_('The unit you are referencing does not exists anymore!'))

        if self.scrap_method == 'part':
            self.product_id.write({
                'product_qty': self.product_id.product_qty - self.product_qty
            })

            vals = {
                'unit_id': self.unit_id.id,
                'location_id': self.unit_id.location_id.id,
                'product_id': self.product_id.id,
                'qty': self.product_qty * -1.0,
                'transaction_date': self.date_entry,
                'source_model': 's2u.warehouse.move.scrapped',
                'source_id': self.id,
                'scrapped_id': self.id
            }
            trans_model.create(vals)
        else:
            for unit in unit_model.search([('parent_id', '=', self.unit_id.id)]):
                for product in unit.line_ids:
                    scrapped = product.product_qty
                    product.write({
                        'product_qty': 0.0
                    })

                    vals = {
                        'product_id': product.id,
                        'qty': scrapped * -1.0,
                        'transaction_date': self.date_entry,
                        'source_model': 's2u.warehouse.move.scrapped',
                        'source_id': self.id,
                        'scrapped_id': self.id
                    }
                    trans_model.create(vals)
                unit.empty_unit(write=True)

            for product in self.unit_id.line_ids:
                scrapped = product.product_qty
                product.write({
                    'product_qty': 0.0
                })

                vals = {
                    'product_id': product.id,
                    'qty': scrapped * -1.0,
                    'transaction_date': self.date_entry,
                    'source_model': 's2u.warehouse.move.scrapped',
                    'source_id': self.id,
                    'scrapped_id': self.id
                }
                trans_model.create(vals)

        self.unit_id.empty_unit(write=True)

        self.write({
            'state': 'done'
        })

    @api.multi
    def unlink(self):

        for product in self:
            if product.state == 'done':
                raise ValidationError(_('You can not delete a confirmed scrapped transaction!'))

        res = super(WarehouseMoveScrapped, self).unlink()

        return res


class WarehouseMoveCorrection(models.Model):
    _name = "s2u.warehouse.move.correction"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _order = "id desc"

    _correction_state = {
        'draft': [('readonly', False)],
    }

    @api.model
    def _default_location(self):
        return self.env['s2u.warehouse.location'].search([('usage', '=', 'normal')], limit=1)

    @api.one
    @api.constrains('product_qty')
    def _check_qty(self):
        if self.product_qty <= 0.0:
                raise ValidationError(_('Correction qty must have a positive value!'))

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', index=True, ondelete='restrict',
                              readonly=True, states=_correction_state)
    product_id = fields.Many2one(readonly=True, states=_correction_state)
    product_qty = fields.Float(readonly=True, states=_correction_state, required=False, default=1.0)
    product_detail = fields.Char(readonly=True, states=_correction_state)
    product_value = fields.Float(readonly=True, states=_correction_state)
    remarks = fields.Text(string='Remarks', readonly=True, states=_correction_state, required=True)
    user_id = fields.Many2one('res.users', string='User', required=True,
                              default=lambda self: self.env.user, readonly=True, states=_correction_state, copy=False)
    date_entry = fields.Date(string='Date', default=lambda self: fields.Date.context_today(self), index=True,
                             required=True, readonly=True, states=_correction_state, copy=False)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('done', 'Confirmed')
    ], required=True, default='draft', string='State', copy=False)
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'correction_id',
                                string='Transactions', copy=False, readonly=True)
    serialnumber = fields.Char(string='Serialnumber', index=True)
    sn_registration = fields.Boolean('S/N registration', related='product_id.sn_registration', readonly=True)
    create_unit = fields.Boolean('Create new unit', default=False)
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', default=_default_location)

    @api.multi
    def do_confirm(self):

        self.ensure_one()

        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        unit_model = self.env['s2u.warehouse.unit']

        if self.create_unit:
            unit = unit_model.create({
                'type': 'singleton',
                'location_id': self.location_id.id
            })
        else:
            if not self.unit_id.active:
                raise ValidationError(_('The unit you are referencing does not exists anymore!'))

        if self.product_id.sn_registration:
            transactions = self.env['s2u.warehouse.unit.product.transaction'].search([('rel_product_id', '=', self.product_id.id),
                                                                                      ('rel_serialnumber', 'ilike', self.serialnumber)])
            available = int(sum(t.qty for t in transactions))
            if available:
                raise ValidationError(_('serialnumber %s already exists for product %s' % (self.serialnumber, self.product_id.name)))

            vals = {
                'product_id': self.product_id.id,
                'product_qty': 1.0,
                'product_detail': self.product_detail,
                'product_value': self.product_value,
                'serialnumber': self.serialnumber,
                'sn_registration': True
            }
            if self.create_unit:
                vals['unit_id'] = unit.id
            else:
                vals['unit_id'] = self.unit_id.id
            product = self.env['s2u.warehouse.unit.product'].create(vals)
            product_id = product.id
        elif self.create_unit:
            vals = {
                'unit_id': unit.id,
                'product_id': self.product_id.id,
                'product_qty': self.product_qty,
                'product_detail': self.product_detail,
                'product_value': self.product_value
            }
            product = self.env['s2u.warehouse.unit.product'].create(vals)
            product_id = product.id
        else:
            products = self.env['s2u.warehouse.unit.product'].search([('unit_id', '=', self.unit_id.id),
                                                                      ('product_id', '=', self.product_id.id),
                                                                      ('product_detail', '=', self.product_detail),
                                                                      ('product_value', '=', self.product_value)])
            if products:
                products[0].write({
                    'product_qty': products[0].product_qty + self.product_qty
                })
                product_id = products[0].id
            else:
                vals = {
                    'unit_id': self.unit_id.id,
                    'product_id': self.product_id.id,
                    'product_qty': self.product_qty,
                    'product_detail': self.product_detail,
                    'product_value': self.product_value
                }
                product = self.env['s2u.warehouse.unit.product'].create(vals)
                product_id = product.id

        vals = {
            'product_id': product_id,
            'qty': self.product_qty,
            'transaction_date': self.date_entry,
            'source_model': 's2u.warehouse.move.correction',
            'source_id': self.id,
            'correction_id': self.id
        }
        if self.create_unit:
            vals['unit_id'] = unit.id
            vals['location_id'] = self.location_id.id
        else:
            vals['unit_id'] = self.unit_id.id
            vals['location_id'] = self.unit_id.location_id.id
        trans_model.create(vals)

        if self.create_unit:
            self.write({
                'state': 'done',
                'unit_id': unit.id
            })
        else:
            self.unit_id.empty_unit(write=True)

            self.write({
                'state': 'done'
            })

    @api.multi
    def copy(self, default=None):

        if self.unit_id.type in ['pallet', 'box']:
            unit = self.unit_id.copy()
            if isinstance(default, dict):
                default['unit_id'] = unit.id
            else:
                default = {
                    'unit_id': unit.id
                }
        correction = super(WarehouseMoveCorrection, self).copy(default=default)

        return correction

    @api.multi
    def unlink(self):

        for product in self:
            if product.state == 'done':
                raise ValidationError(_('You can not delete a confirmed correction transaction!'))

        res = super(WarehouseMoveCorrection, self).unlink()

        return res


class WarehouseMoveUnit(models.Model):
    _name = "s2u.warehouse.move.unit"
    _order = "id desc"

    _move_state = {
        'draft': [('readonly', False)],
    }

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', required=True, index=True, ondelete='restrict',
                              readonly=True, states=_move_state)
    user_id = fields.Many2one('res.users', string='User', required=True,
                              default=lambda self: self.env.user, readonly=True, states=_move_state, copy=False)
    date_entry = fields.Date(string='Date', default=lambda self: fields.Date.context_today(self), index=True,
                             required=True, readonly=True, states=_move_state, copy=False)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('done', 'Confirmed')
    ], required=True, default='draft', string='State', copy=False)
    from_location_id = fields.Many2one('s2u.warehouse.location', string='From location', index=True,
                                       ondelete='restrict', readonly=True, states=_move_state)
    location_id = fields.Many2one('s2u.warehouse.location', string='New location', index=True,
                                  ondelete='restrict', readonly=True, states=_move_state)
    movement_to = fields.Selection([
        ('location', 'New location'),
        ('unit', 'On other pallet')
    ], required=True, default='location', string='To', copy=False)
    to_unit_id = fields.Many2one('s2u.warehouse.unit', string='New unit', index=True, ondelete='restrict',
                                 readonly=True, states=_move_state)
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'moveunit_id',
                                string='Transactions', copy=False, readonly=True)

    @api.multi
    def do_confirm(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        if not self.unit_id.active:
            raise ValidationError(_('The unit you are referencing does not exists anymore!'))

        current_location_id = self.unit_id.location_id.id
        if self.unit_id.parent_id:
            current_parent_id = self.unit_id.parent_id.id
        else:
            current_parent_id = False

        if current_location_id == self.location_id.id:
            raise ValidationError(_('You are trying to move to same location!'))

        if self.movement_to == 'location':
            self.unit_id.write({
                'parent_id': False,
                'location_id': self.location_id.id
            })

            to_move = self.env['s2u.warehouse.unit.product']
            to_move += self.unit_id.line_ids
            children = self.env['s2u.warehouse.unit'].search([('parent_id', '=', self.unit_id.id)])
            for child in children:
                to_move += child
            for product in to_move:
                vals = {
                    'parent_id': current_parent_id,
                    'unit_id': product.unit_id.id,
                    'location_id': current_location_id,
                    'product_id': product.id,
                    'qty': product.product_qty * -1,
                    'transaction_date': self.date_entry,
                    'source_model': 's2u.warehouse.move.unit',
                    'source_id': self.id,
                    'moveunit_id': self.id
                }
                trans_model.create(vals)

                vals = {
                    'unit_id': product.unit_id.id,
                    'location_id': self.location_id.id,
                    'product_id': product.id,
                    'qty': product.product_qty,
                    'transaction_date': self.date_entry,
                    'source_model': 's2u.warehouse.move.unit',
                    'source_id': self.id,
                    'moveunit_id': self.id
                }
                trans_model.create(vals)

            self.write({
                'state': 'done',
                'from_location_id': current_location_id,
                'to_unit_id': False
            })
        else:
            if self.unit_id.assigned_qty != 0:
                raise ValidationError(
                    _('This pallet is assigned, you can not place it on another pallet!'))
            children = self.env['s2u.warehouse.unit'].search([('parent_id', '=', self.unit_id.id)])
            if children:
                raise ValidationError(_('This pallet contains already other units on it, you can not place it on another pallet!'))
            if self.to_unit_id.parent_id:
                raise ValidationError(
                    _('The pallet you want to put this pallet on is already placed on another pallet!'))

            for product in self.unit_id.line_ids:
                vals = {
                    'parent_id': current_parent_id,
                    'unit_id': product.unit_id.id,
                    'location_id': current_location_id,
                    'product_id': product.id,
                    'qty': product.product_qty * -1,
                    'transaction_date': self.date_entry,
                    'source_model': 's2u.warehouse.move.unit',
                    'source_id': self.id,
                    'moveunit_id': self.id
                }
                trans_model.create(vals)

                vals = {
                    'unit_id': product.unit_id.id,
                    'parent_id': self.to_unit_id.id,
                    'location_id': self.to_unit_id.location_id.id,
                    'product_id': product.id,
                    'qty': product.product_qty,
                    'transaction_date': self.date_entry,
                    'source_model': 's2u.warehouse.move.unit',
                    'source_id': self.id,
                    'moveunit_id': self.id
                }
                trans_model.create(vals)

            self.unit_id.write({
                'parent_id': self.to_unit_id.id,
                'location_id': self.to_unit_id.location_id.id
            })

            self.write({
                'state': 'done',
                'from_location_id': current_location_id,
                'location_id': False
            })


    @api.multi
    def unlink(self):

        for move in self:
            if move.state == 'done':
                raise ValidationError(_('You can not delete a confirmed move!'))

        res = super(WarehouseMoveUnit, self).unlink()

        return res


class WarehouseMoveProduct(models.Model):
    _name = "s2u.warehouse.move.product"
    _order = "id desc"

    _move_state = {
        'draft': [('readonly', False)],
    }

    @api.onchange('from_unit_id')
    def onchange_from_unit(self):

        if not self.from_unit_id:
            return {'domain': {'product_id': [('unit_id', '=', False)]}}

        return {'domain': {'product_id': [('unit_id', '=', self.from_unit_id.id)]}}

    @api.one
    @api.constrains('product_qty')
    def _check_qty(self):
        if self.product_qty <= 0.0:
                raise ValidationError(_('Move qty must have a positive value!'))

    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    from_unit_id = fields.Many2one('s2u.warehouse.unit', string='From unit', required=True, index=True, ondelete='restrict',
                                   readonly=True, states=_move_state)
    unit_id = fields.Many2one('s2u.warehouse.unit', string='New unit', required=True, index=True, ondelete='restrict',
                              readonly=True, states=_move_state)
    product_id = fields.Many2one('s2u.warehouse.unit.product', string='Product', required=True, index=True,
                                 ondelete='restrict', readonly=True, states=_move_state)
    product_qty = fields.Float(string='Qty move', required=True, readonly=True, states=_move_state)
    user_id = fields.Many2one('res.users', string='User', required=True,
                              default=lambda self: self.env.user, readonly=True, states=_move_state, copy=False)
    date_entry = fields.Date(string='Date', default=lambda self: fields.Date.context_today(self), index=True,
                             required=True, readonly=True, states=_move_state, copy=False)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('done', 'Confirmed')
    ], required=True, default='draft', string='State', copy=False)
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'moveproduct_id',
                                string='Transactions', copy=False, readonly=True)

    @api.multi
    def do_confirm(self):

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        if not self.from_unit_id.active:
            raise ValidationError(_('The unit you are referencing does not exists!'))

        if not self.unit_id.active:
            raise ValidationError(_('The unit you are referencing does not exists!'))

        if self.from_unit_id.id == self.unit_id.id:
            raise ValidationError(_('You try moving items to the same unit!'))

        self.product_id.write({
            'product_qty': self.product_id.product_qty - self.product_qty
        })

        vals = {
            'unit_id': self.from_unit_id.id,
            'parent_id': self.from_unit_id.parent_id.id if self.from_unit_id.parent_id else False,
            'location_id': self.from_unit_id.location_id.id,
            'product_id': self.product_id.id,
            'qty': self.product_qty * -1.0,
            'transaction_date': self.date_entry,
            'source_model': 's2u.warehouse.move.product',
            'source_id': self.id,
            'moveproduct_id': self.id
        }
        trans_model.create(vals)

        self.from_unit_id.empty_unit(write=True)

        if self.product_id.sn_registration:
            vals = {
                'unit_id': self.unit_id.id,
                'product_id': self.product_id.product_id.id,
                'product_qty': self.product_qty,
                'product_value': self.product_id.product_value,
                'product_detail': self.product_id.product_detail,
                'serialnumber': self.product_id.serialnumber,
                'sn_registration': True
            }
            product = self.env['s2u.warehouse.unit.product'].create(vals)
        else:
            present = self.env['s2u.warehouse.unit.product'].search([('unit_id', '=', self.unit_id.id),
                                                                     ('product_id', '=', self.product_id.product_id.id),
                                                                     ('product_detail', '=', self.product_id.product_detail)])
            if present:
                product = present[0]
                product.write({
                    'product_qty': product.product_qty + self.product_qty
                })
            else:
                vals = {
                    'unit_id': self.unit_id.id,
                    'product_id': self.product_id.product_id.id,
                    'product_qty': self.product_qty,
                    'product_value': self.product_id.product_value,
                    'product_detail': self.product_id.product_detail,
                }
                product = self.env['s2u.warehouse.unit.product'].create(vals)

        vals = {
            'unit_id': self.unit_id.id,
            'parent_id': self.unit_id.parent_id.id if self.unit_id.parent_id else False,
            'location_id': self.unit_id.location_id.id,
            'product_id': product.id,
            'qty': self.product_qty,
            'transaction_date': self.date_entry,
            'source_model': 's2u.warehouse.move.product',
            'source_id': self.id,
            'moveproduct_id': self.id
        }
        trans_model.create(vals)

        self.write({
            'state': 'done'
        })

    @api.multi
    def unlink(self):

        for product in self:
            if product.state == 'done':
                raise ValidationError(_('You can not delete a confirmed move transaction!'))

        res = super(WarehouseMoveProduct, self).unlink()

        return res
