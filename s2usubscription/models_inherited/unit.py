# -*- coding: utf-8 -*-

import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class WarehouseUnitProductTransaction(models.Model):
    _inherit = "s2u.warehouse.unit.product.transaction"

    @api.one
    def unlink(self):

        for trans in self:
            moves = self.env['s2u.account.move'].search([('res_model', '=', 's2u.warehouse.unit.product.transaction'),
                                                         ('res_id', '=', trans.id)])
            moves.unlink()

        return super(WarehouseUnitProductTransaction, self).unlink()

    @api.multi
    def financial_stock_on_outgoing(self, unitproduct, qty, saleline=False):

        if not (saleline and saleline.product_id.res_model == 's2u.subscription.template'):
            # in this case we assume another module is taking care of this
            return super(WarehouseUnitProductTransaction, self).financial_stock_on_outgoing(unitproduct, qty, saleline=saleline)
        template = self.env[saleline.product_id.res_model].browse(saleline.product_id.res_id)
        product = self.env[unitproduct.product_id.res_model].browse(unitproduct.product_id.res_id)
        if not template.stock_account_id:
            raise ValidationError(_('There is no stock account defined for service %s!' % template.name))
        if not product.stock_account_id:
            raise ValidationError(_('There is no stock account defined for product %s!' % product.name))

        if unitproduct.serialnumber:
            description = '%s (%s)' % (template.stock_account_id.name, unitproduct.serialnumber)
        else:
            description = '%s' % template.stock_account_id.name
        move_values = {
            'res_model': 's2u.warehouse.unit.product.transaction',
            'res_id': self.id,
            'account_id': template.stock_account_id.id,
            'debit': qty * unitproduct.product_value,
            'name': description
        }
        self.env['s2u.account.move'].create(move_values)

        if unitproduct.serialnumber:
            description = '%s (%s)' % (product.stock_account_id.name, unitproduct.serialnumber)
        else:
            description = '%s' % product.stock_account_id.name
        move_values = {
            'res_model': 's2u.warehouse.unit.product.transaction',
            'res_id': self.id,
            'account_id': product.stock_account_id.id,
            'credit': qty * unitproduct.product_value,
            'name': description
        }
        self.env['s2u.account.move'].create(move_values)

        return super(WarehouseUnitProductTransaction, self).financial_stock_on_outgoing(unitproduct, qty,
                                                                                        saleline=saleline)

    @api.multi
    def financial_stock_on_rma(self, unitproduct, qty, product_usable, rmaline):

        if not (rmaline.todo_id and rmaline.todo_id.saleline_id.product_id.res_model == 's2u.subscription.template'):
            # in this case we assume another module is taking care of this
            return super(WarehouseUnitProductTransaction, self).financial_stock_on_rma(unitproduct, qty, product_usable,
                                                                                       rmaline=rmaline)

        # TODO: book different when product is not usable

        template = self.env[rmaline.todo_id.saleline_id.product_id.res_model].browse(rmaline.todo_id.saleline_id.product_id.res_id)
        product = self.env[unitproduct.product_id.res_model].browse(unitproduct.product_id.res_id)

        if not product.stock_account_id:
            raise ValidationError(_('There is no stock account found in rma line for product %s!' % product.name))
        if not template.stock_account_id:
            raise ValidationError(_('There is no stock account found in rma line for service %s!' % template.name))

        if unitproduct.serialnumber:
            description = '%s (%s)' % (template.stock_account_id.name, unitproduct.serialnumber)
        else:
            description = '%s' % template.stock_account_id.name
        move_values = {
            'res_model': 's2u.warehouse.unit.product.transaction',
            'res_id': self.id,
            'account_id': template.stock_account_id.id,
            'credit': qty * rmaline.product_value,
            'name': description
        }
        self.env['s2u.account.move'].create(move_values)

        if unitproduct.serialnumber:
            description = '%s (%s)' % (product.stock_account_id.name, unitproduct.serialnumber)
        else:
            description = '%s' % product.stock_account_id.name
        move_values = {
            'res_model': 's2u.warehouse.unit.product.transaction',
            'res_id': self.id,
            'account_id': product.stock_account_id.id,
            'debit': qty * rmaline.product_value,
            'name': description
        }
        self.env['s2u.account.move'].create(move_values)

        return super(WarehouseUnitProductTransaction, self).financial_stock_on_rma(unitproduct, qty, product_usable,
                                                                                   rmaline=rmaline)
