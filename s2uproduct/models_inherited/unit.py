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

        if saleline and saleline.product_id.product_type != 'stock':
            # in this case we assume another module is taking care of this
            return super(WarehouseUnitProductTransaction, self).financial_stock_on_outgoing(unitproduct, qty, saleline=saleline)

        product = self.env[unitproduct.product_id.res_model].browse(unitproduct.product_id.res_id)
        supplier = unitproduct.get_supplier()
        if supplier:
            account_po = product.get_po_account(supplier=supplier)
        else:
            account_po = product.po_account_id
        if not account_po:
            raise ValidationError(_('There is no po account defined for product %s!' % product.name))
        if not product.stock_account_id:
            raise ValidationError(_('There is no stock account defined for product %s!' % product.name))

        if unitproduct.serialnumber:
            description = '%s (%s)' % (account_po.name, unitproduct.serialnumber)
        else:
            description = '%s' % account_po.name
        move_values = {
            'res_model': 's2u.warehouse.unit.product.transaction',
            'res_id': self.id,
            'account_id': account_po.id,
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

        if rmaline.todo_id and rmaline.todo_id.saleline_id and rmaline.todo_id.saleline_id.product_id.product_type != 'stock':
            # in this case we assume another module is taking care of this
            return super(WarehouseUnitProductTransaction, self).financial_stock_on_rma(unitproduct, qty, product_usable,
                                                                                       rmaline=rmaline)

        # TODO: book diiferent when product is not usable

        product = self.env[unitproduct.product_id.res_model].browse(unitproduct.product_id.res_id)

        if not rmaline.account_po_id:
            raise ValidationError(_('There is no po account found in rma line for product %s!' % product.name))
        if not rmaline.account_stock_id:
            raise ValidationError(_('There is no stock account found in rma line for product %s!' % product.name))

        if unitproduct.serialnumber:
            description = '%s (%s)' % (rmaline.account_po_id.name, unitproduct.serialnumber)
        else:
            description = '%s' % rmaline.account_po_id.name
        move_values = {
            'res_model': 's2u.warehouse.unit.product.transaction',
            'res_id': self.id,
            'account_id': rmaline.account_po_id.id,
            'credit': qty * rmaline.product_value,
            'name': description
        }
        self.env['s2u.account.move'].create(move_values)

        if unitproduct.serialnumber:
            description = '%s (%s)' % (rmaline.account_stock_id.name, unitproduct.serialnumber)
        else:
            description = '%s' % rmaline.account_stock_id.name
        move_values = {
            'res_model': 's2u.warehouse.unit.product.transaction',
            'res_id': self.id,
            'account_id': rmaline.account_stock_id.id,
            'debit': qty * rmaline.product_value,
            'name': description
        }
        self.env['s2u.account.move'].create(move_values)

        return super(WarehouseUnitProductTransaction, self).financial_stock_on_rma(unitproduct, qty, product_usable,
                                                                                   rmaline=rmaline)
