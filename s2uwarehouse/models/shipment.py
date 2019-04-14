# -*- coding: utf-8 -*-

import time
import math

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class OutgoingType(models.Model):
    _name = "s2u.warehouse.outgoing.type"
    _order = "name"

    name = fields.Char('Type', required=True)
    default = fields.Boolean('Default')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)


class OutgoingTodo(models.Model):
    _name = "s2u.warehouse.outgoing.todo"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _description = "Outgoing todo (sales order)"

    @api.one
    def _compute_shipped_qty(self):

        tot_shipped = 0.0
        tot_shipped_saldo = 0.0

        for trans in self.outgoing_id.trans_ids:
            if trans.outgoing_line_id.id != self.id:
                continue
            if trans.product_id.product_id == self.product_id and trans.product_id.product_detail == self.product_detail:
                tot_shipped += trans.qty
                tot_shipped_saldo += trans.qty
        if tot_shipped_saldo < 0.0:
            rmalines = self.env['s2u.warehouse.rma.line'].search([('todo_id', '=', self.id)])
            for rma in rmalines:
                tot_shipped_saldo += rma.product_qty

        self.shipped_qty = tot_shipped
        self.shipped_saldo_qty = tot_shipped_saldo

    @api.one
    def _compute_available_qty(self):

        available = self.env['s2u.warehouse.available'].search([('product_id', '=', self.product_id.id),
                                                                ('product_detail', '=', self.product_detail)])
        if available:
            self.available_qty = available[0].qty_available
        else:
            self.available_qty = 0.0

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Levering', required=True, index=True,
                                  ondelete='cascade')
    shipped_qty = fields.Float(string='Shipped', compute=_compute_shipped_qty, readonly=True)
    shipped_saldo_qty = fields.Float(string='Shipped saldo', compute=_compute_shipped_qty, readonly=True)
    type = fields.Selection([
        ('normal', 'Normal'),
        ('rest', 'Rest'),
        ('part', 'Part')
    ], required=True, default='normal', string='Type', copy=False, help="Give info about the shipment: normal, part or rest delivery of a specific SO.")
    notes = fields.Text('Notes')
    tot_weight = fields.Float(string='# Weight')
    tot_surface = fields.Float(string='# Surface')
    assigned_qty = fields.Float(string='Assigned')
    available_qty = fields.Float(string='Available', compute=_compute_available_qty, readonly=True)
    state = fields.Selection([
        ('draft', 'Pending'),
        ('production', 'Production'),
        ('ok', 'Todo'),
        ('done', 'Done'),
        ('rma', 'RMA')
    ], string='State', related='outgoing_id.state', readonly=True)
    distribution = fields.Char(string='Distribution')

    def get_pos_num(self, line_id):
        first_line = False
        for line in self.outgoing_id.todo_ids:
            if not first_line or line.id < first_line:
                first_line = line.id

        if not first_line:
            return 0

        return int(line_id) - int(first_line) + 1

    def build_transaction_key(self, trans):

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']

        transactions = trans_obj.search([('outgoing_id', '=', trans.outgoing_id.id),
                                         ('unit_id', '=', trans.unit_id.id),
                                         ('id', '!=', trans.id)], order='id')
        trans_key = '%s,%s' % (trans.qty, trans.outgoing_line_id.id)
        for t in transactions:
            trans_key = '%s;%s,%s' % (trans_key, t.qty, t.outgoing_line_id.id)
        return trans_key

    def used_in_prec(self, trans):

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']
        transactions = trans_obj.search([('outgoing_id', '=', trans.outgoing_id.id),
                                         ('unit_id', '=', trans.unit_id.id),
                                         ('id', '<', trans.id)], order='id')

        if transactions:
            return True

        return False

    def calc_palletisation(self):
        """This method prepares a dictionary with the total of pallets grouped by the items on in. Example:
           {2: 300,
            1: 350 + 500 pos 1}
           The dictionary is ordered by total pallets and then value"""
        self.ensure_one()

        palletisation = {}
        palletisation2 = {}

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']

        transactions = trans_obj.search([('outgoing_line_id', '=', self.id)])
        for trans in transactions:
            key = self.build_transaction_key(trans)
            if key not in palletisation:
                palletisation[key] = 1
            else:
                palletisation[key] += 1

        # TODO: versuchen die ID durch die POS im Dokument zu ersetzen; POS 1 kleinste der ids

        for pal in palletisation:
            word = pal.split(';')
            key = ''
            first = True
            for str2 in word:
                str3 = str2.split(',')
                pos = self.get_pos_num(str3[1])
                anzahl = '%.2f' % (float(str3[0]) * - 1)

                if first:
                    key = anzahl + ' Pos: ' + str(pos)
                    first = False
                else:
                    key = key + ' + ' + anzahl + ' Pos: ' + str(pos)
            palletisation2[key] = palletisation[pal]

        return palletisation2

    def calc_pallets_type(self):
        """This method prepares a dictionary with the total of pallets grouped by the pallet type. Example:
                   {3: Block pallet,
                    2: Euro pallet}
           The dictionary is ordered by the pallet type.
           When this pos has items on a pallet of a PREVIOUS pos, then the pallet should NOT be counted!!"""
        self.ensure_one()

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']
        types = {}
        types_pallet = {}
        transactions = trans_obj.search([('outgoing_line_id', '=', self.id)])
        for trans in transactions:
            if trans.unit_id.type == 'pallet' and not trans.item_picking:
                if not self.used_in_prec(trans):
                    key = str(trans.unit_id.pallet_id.id)
                    if key not in types:
                        types[key] = (1 * trans.unit_id.pallet_factor)
                        types_pallet[key] = trans.unit_id.pallet_id
                    else:
                        types[key] += (1 * trans.unit_id.pallet_factor)

        types_short = {}
        for k, v in iter(types.items()):
            types_short[k] = {
                'code': types_pallet[k].code,
                'total': v
            }
        return types_short

    def calc_pallets_used(self):
        """This method calculates the total used pallets for this pos without the pallets with items on it from a previous
           pos. The value returned is an integer """
        self.ensure_one()

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']
        count = 0
        transactions = trans_obj.search([('outgoing_line_id', '=', self.id)])
        trans_unit_ids = []
        for trans in transactions:
            if trans.unit_id.type == 'pallet' and not trans.item_picking and trans.unit_id.id not in trans_unit_ids:
                trans_unit_ids.append(trans.unit_id.id)
                if not self.used_in_prec(trans):
                    count += 1

            if trans.unit_id.type != 'pallet' and trans.parent_id and not trans.item_picking:
                if trans.parent_id.type == 'pallet' and not trans.item_picking and trans.parent_id.id not in trans_unit_ids:
                    trans_unit_ids.append(trans.parent_id.id)
                    if not self.used_in_prec(trans):
                        count += 1

        return count


class OutgoingAssignedUnit(models.Model):
    _name = "s2u.warehouse.outgoing.assigned.unit"

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Levering', required=True, index=True,
                                  ondelete='cascade')
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', required=True, index=True, ondelete='restrict')
    on_unit = fields.Text(string='On unit', related='unit_id.on_unit', readonly=True)
    type = fields.Selection([
        ('singleton', 'Eenheid'),
        ('pallet', 'Unit')
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

        res = super(OutgoingAssignedUnit, self).unlink()

        return res

    @api.model
    def create(self, vals):

        unit_model = self.env['s2u.warehouse.unit']

        unit = unit_model.search([('id', '=', vals['unit_id'])])
        unit.assign_unit()

        assigned = super(OutgoingAssignedUnit, self).create(vals)
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

        return super(OutgoingAssignedUnit, self).write(vals)


class OutgoingAssignedUnitProduct(models.Model):
    _name = "s2u.warehouse.outgoing.assigned.unit.product"

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Levering', required=True, index=True,
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

        res = super(OutgoingAssignedUnitProduct, self).unlink()

        return res

    @api.model
    def create(self, vals):

        item_model = self.env['s2u.warehouse.unit.product']

        item = item_model.search([('id', '=', vals['unitproduct_id'])])
        item.assign_item(vals['assigned_qty'])

        assigned = super(OutgoingAssignedUnitProduct, self).create(vals)
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

        return super(OutgoingAssignedUnitProduct, self).write(vals)


class Outgoing(models.Model):
    _name = "s2u.warehouse.outgoing"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Outgoing"
    _order = "id desc"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Outgoing, self)._track_subtype(init_values)

    @api.multi
    @api.constrains('type', 'entity_id', 'contact_id')
    def _check_address_entity(self):
        for out in self:
            if out.type == 'b2b':
                if out.entity_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b delivery!'))
                if out.contact_id and out.contact_id.entity_id != out.entity_id:
                    raise ValueError(_('Contact does not belong to the selected delivery!'))
            else:
                if out.entity_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c delivery!'))

    @api.multi
    @api.constrains('load_type', 'load_entity_id')
    def _check_address_loading(self):
        for out in self:
            if out.load_type == 'b2b' and out.load_entity_id:
                if out.load_entity_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b loading!'))
            elif out.load_entity_id:
                if out.load_entity_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c loading!'))

    @api.multi
    def name_get(self):
        result = []
        for ship in self:
            if ship.entity_id.entity_code:
                client = ship.entity_id.entity_code
            else:
                client = ship.entity_id.name
            if ship.reference:
                name = '%s (%s) [%s]' % (ship.name, ship.reference, client)
            else:
                name = '%s [%s]' % (ship.name, client)
            result.append((ship.id, name))
        return result

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.warehouse.outgoing')])
        if not exists:
            raise ValueError(_('Sequence for creating s2u.warehouse.outgoing number not exists!'))

        sequence = exists[0]
        new_number = sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()
        if self.env.user.name:
            name = self.env.user.name.split(' ')
            initials = ''
            for n in name:
                initials = '%s%s' % (initials, n[0].upper())
            new_number = '%s/%s' % (new_number, initials)
        return new_number

    @api.onchange('entity_id')
    def _onchange_entity(self):
        if self.entity_id:
            self.delivery_entity_id = self.entity_id

    @api.onchange('delivery_entity_id')
    def _onchange_delivery_entity(self):
        if self.delivery_entity_id:
            delivery = self.delivery_entity_id.prepare_delivery()
            self.delivery_address = delivery

            address = self.delivery_entity_id.get_physical()
            if address and address.country_id:
                self.delivery_country_id = address.country_id
            else:
                self.delivery_country_id = False
            if self.delivery_entity_id.tinno:
                self.delivery_tinno = self.delivery_entity_id.tinno
            else:
                self.delivery_tinno = False
            if self.delivery_entity_id.lang:
                self.delivery_lang = self.delivery_entity_id.lang
            else:
                self.delivery_lang = False

    @api.onchange('delivery_contact_id')
    def _onchange_delivery_contact(self):
        if self.delivery_contact_id:
            delivery = self.delivery_contact_id.display_company + '\n'
            if self.delivery_contact_id.prefix:
                delivery += '%s\n' % self.delivery_contact_id.prefix
            else:
                delivery += '%s\n' % self.delivery_contact_id.name
            if self.delivery_contact_id.address_id:
                if self.delivery_contact_id.address_id.address:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.address
                if self.delivery_contact_id.address_id.zip and self.delivery_contact_id.address_id.city:
                    delivery += '%s  %s\n' % (self.delivery_contact_id.address_id.zip, self.delivery_contact_id.address_id.city)
                if self.delivery_contact_id.address_id.country_id:
                    delivery += '%s\n' % self.delivery_contact_id.address_id.country_id.name
            elif self.delivery_entity_id:
                address = self.delivery_entity_id.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name

            self.delivery_address = delivery

    @api.onchange('load_entity_id')
    def _onchange_load_entity(self):
        if self.load_entity_id:
            loading = self.load_entity_id.prepare_delivery()
            self.load_address = loading

    @api.one
    @api.depends('todo_ids')
    def _compute_tot_weight(self):

        tot_weight = 0.0
        for line in self.todo_ids:
            tot_weight += line.tot_weight

        self.tot_weight = tot_weight

    @api.one
    @api.depends('todo_ids')
    def _compute_tot_surface(self):
        tot_surface = 0.0
        for line in self.todo_ids:
            tot_surface += line.tot_surface

        self.tot_surface = tot_surface

    @api.one
    def _compute_is_ready(self):

        if self.state != 'ok':
            return False
        if self.todo_ids:
            is_ready = True
            for todo in self.todo_ids:
                if todo.product_qty != todo.assigned_qty:
                    is_ready = False
                    break
            self.is_ready = is_ready
        else:
            self.is_ready = False

    def calc_pallets_saldo(self):

        self.ensure_one()

        def keyindict(key_search, dict):
            for key, value in sorted(iter(dict.items())):
                if key == key_search:
                    return value
            return False

        trans_obj = self.env['s2u.warehouse.unit.product.transaction']
        correction_obj = self.env['s2u.warehouse.pallet.correction']
        retourn_obj = self.env['s2u.warehouse.incoming.pallet.retour']

        transfers = trans_obj.search(['|', ('incoming_id', '!=', False), ('outgoing_id', '!=', False),
                                           ('transaction_date', '<=', self.transaction_date),
                                           ('item_picking', '=', False),
                                           ('count_unit', '=', True)])
        correctings = correction_obj.search([('entry_date', '<=', self.transaction_date),
                                             ('entity_id', '=', self.entity_id.id)], order='entity_id')

        retourns = retourn_obj.search([('date_delivery', '<=', self.transaction_date)])

        customer_list = {}
        trans_unit_ids_in = []
        trans_unit_ids_out = []
        for correcting in correctings:
            if not keyindict(correcting.entity_id.name, customer_list):
                customer_list[correcting.entity_id.name] = {'pallet': {}}
            if not keyindict(correcting.pallet_id.full_name, customer_list[correcting.entity_id.name]['pallet']):
                customer_list[correcting.entity_id.name]['pallet'][correcting.pallet_id.full_name] = {'gesamt': 0,
                                                                                                      'today': 0,
                                                                                                      'before': 0}
            customer_list[correcting.entity_id.name]['pallet'][correcting.pallet_id.full_name]['gesamt']\
                += correcting.pallets
            if correcting.entry_date == self.transaction_date:
                customer_list[correcting.entity_id.name]['pallet'][correcting.pallet_id.full_name]['today']\
                    += correcting.pallets
            else:
                customer_list[correcting.entity_id.name]['pallet'][correcting.pallet_id.full_name]['before']\
                    += correcting.pallets

        for transfer in transfers:
            if transfer.unit_id.type == 'pallet' and not transfer.incoming_id and transfer.outgoing_id.entity_id.id == self.entity_id.id and transfer.unit_id.id not in trans_unit_ids_out:
                trans_unit_ids_out.append(transfer.unit_id.id)
                if not keyindict(transfer.outgoing_id.entity_id.name, customer_list):
                    customer_list[transfer.outgoing_id.entity_id.name] = {'pallet': {}}
                if not keyindict(transfer.unit_id.pallet_id.full_name,
                                 customer_list[transfer.outgoing_id.entity_id.name]['pallet']):
                    customer_list[transfer.outgoing_id.entity_id.name]['pallet'][
                        transfer.unit_id.pallet_id.full_name] = {'gesamt': 0,
                                                                 'today': 0,
                                                                 'before': 0}
                customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name][
                    'gesamt'] += (
                1 * transfer.unit_id.pallet_factor)
                if transfer.transaction_date == self.transaction_date:
                    customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name][
                        'today'] += (1 * transfer.unit_id.pallet_factor)
                else:
                    customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name][
                        'before'] += (1 * transfer.unit_id.pallet_factor)
            if transfer.unit_id.type != 'pallet' and transfer.parent_id:
                if transfer.parent_id.type == 'pallet' and not transfer.incoming_id and transfer.outgoing_id.entity_id.id == self.entity_id.id and transfer.parent_id.id not in trans_unit_ids_out:
                    trans_unit_ids_out.append(transfer.parent_id.id)
                    if not keyindict(transfer.outgoing_id.entity_id.name, customer_list):
                        customer_list[transfer.outgoing_id.entity_id.name] = {'pallet': {}}
                    if not keyindict(transfer.parent_id.pallet_id.full_name,
                                     customer_list[transfer.outgoing_id.entity_id.name]['pallet']):
                        customer_list[transfer.outgoing_id.entity_id.name]['pallet'][
                            transfer.parent_id.pallet_id.full_name] = {'gesamt': 0,
                                                                       'today': 0,
                                                                       'before': 0}
                    customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name][
                        'gesamt'] += (
                    1 * transfer.parent_id.pallet_factor)

                    if transfer.transaction_date == self.transaction_date:
                        customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name][
                            'today'] += (1 * transfer.parent_id.pallet_factor)
                    else:
                        customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name][
                            'before'] += (1 * transfer.parent_id.pallet_factor)

                if transfer.parent_id.type == 'pallet' and not transfer.outgoing_id and transfer.incoming_id.entity_id.id == self.entity_id.id and transfer.parent_id.id not in trans_unit_ids_in :
                    trans_unit_ids_in.append(transfer.parent_id.id)
                    if not keyindict(transfer.incoming_id.entity_id.name, customer_list):
                        customer_list[transfer.incoming_id.entity_id.name] = {'pallet': {}}
                    if not keyindict(transfer.parent_id.pallet_id.full_name,
                                     customer_list[transfer.incoming_id.entity_id.name]['pallet']):
                        customer_list[transfer.incoming_id.entity_id.name]['pallet'][
                            transfer.parent_id.pallet_id.full_name] = {'gesamt': 0,
                                                                       'today': 0,
                                                                       'before': 0}
                    customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name][
                        'gesamt'] += (
                    1 * transfer.parent_id.pallet_factor)

                    if transfer.transaction_date == self.transaction_date:
                        customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name][
                            'today'] += (1 * transfer.parent_id.pallet_factor)
                    else:
                        customer_list[transfer.outgoing_id.entity_id.name]['pallet'][transfer.parent_id.pallet_id.full_name][
                            'before'] += (1 * transfer.parent_id.pallet_factor)

            if transfer.unit_id.type == 'pallet' and not transfer.outgoing_id and transfer.incoming_id.entity_id.id == self.entity_id.id and transfer.unit_id.id not in trans_unit_ids_in:
                trans_unit_ids_in.append(transfer.unit_id.id)
                if not keyindict(transfer.incoming_id.entity_id.name, customer_list):
                    customer_list[transfer.incoming_id.entity_id.name] = {'pallet': {}}
                if not keyindict(transfer.unit_id.pallet_id.full_name,
                                 customer_list[transfer.incoming_id.entity_id.name]['pallet']):
                    customer_list[transfer.incoming_id.entity_id.name]['pallet'][
                        transfer.unit_id.pallet_id.full_name] = {'gesamt': 0,
                                                                 'today': 0,
                                                                 'before': 0}
                customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name][
                    'gesamt'] -= (1 * transfer.unit_id.pallet_factor)
                if transfer.transaction_date == self.transaction_date:
                    customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name][
                        'today'] -= (1 * transfer.unit_id.pallet_factor)
                else:
                    customer_list[transfer.incoming_id.entity_id.name]['pallet'][transfer.unit_id.pallet_id.full_name][
                        'before'] -= (1 * transfer.unit_id.pallet_factor)

        for retour in retourns:
            if retour.incoming_id.entity_id.name == self.entity_id.id:
                if not keyindict(retour.incoming_id.entity_id.name, customer_list):
                    customer_list[retour.incoming_id.entity_id.name] = {'pallet': {}}
                if not keyindict(retour.pallet_id.full_name, customer_list[retour.incoming_id.entity_id.name]['pallet']):
                    customer_list[retour.incoming_id.entity_id.name]['pallet'][retour.pallet_id.full_name] = {'gesamt': 0,
                                                                                                              'today': 0,
                                                                                                              'before': 0}
                customer_list[retour.incoming_id.entity_id.name]['pallet'][retour.pallet_id.full_name]['gesamt'] += retour.pallet_qty
                if retour.date_delivery == self.transaction_date:
                    customer_list[retour.incoming_id.entity_id.name]['pallet'][retour.pallet_id.full_name][
                        'today'] += retour.pallet_qty
                else:
                    customer_list[retour.incoming_id.entity_id.name]['pallet'][retour.pallet_id.full_name][
                        'before'] += retour.pallet_qty

        list_customer = []

        for key, value in sorted(iter(customer_list.items())):
            for key2, value2 in iter(value['pallet'].items()):
                temp = {
                    'customer': key,
                    'pallet': key2,
                    'gesamt': value2['gesamt'],
                    'today':  value2['today'],
                    'before': value2['before']
                }
                list_customer.append(temp)

        return list_customer

    def _get_invoice_count(self):

        for outgoing in self:
            invlines = self.env['s2u.account.invoice.line'].search([('outgoing_id', '=', outgoing.id)])
            invoice_ids = [l.invoice_id.id for l in invlines]
            invoice_ids = list(set(invoice_ids))
            outgoing.invoice_count = len(invoice_ids)

    def _get_production_count(self):

        for outgoing in self:
            lines = self.env['s2u.warehouse.produced.line'].search([('outgoing_id', '=', outgoing.id)])
            production_ids = [l.produced_id.id for l in lines]
            production_ids = list(set(production_ids))
            outgoing.production_count = len(production_ids)

    @api.multi
    def action_view_invoice(self):
        invlines = self.env['s2u.account.invoice.line'].search([('outgoing_id', '=', self.id)])
        invoice_ids = [l.invoice_id.id for l in invlines]
        invoice_ids = list(set(invoice_ids))

        action = self.env.ref('s2uaccount.action_invoice').read()[0]
        if len(invoice_ids) > 1:
            action['domain'] = [('id', 'in', invoice_ids)]
        elif len(invoice_ids) == 1:
            action['views'] = [(self.env.ref('s2uaccount.invoice_form').id, 'form')]
            action['res_id'] = invoice_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.model
    def _default_delivery_country(self):
        domain = [
            ('code', '=', 'NL'),
        ]
        return self.env['res.country'].search(domain, limit=1)

    @api.model
    def _delivery_lang_get(self):
        languages = self.env['res.lang'].search([])
        return [(language.code, language.name) for language in languages]

    @api.multi
    def action_view_production(self):
        lines = self.env['s2u.warehouse.produced.line'].search([('outgoing_id', '=', self.id)])
        production_ids = [l.produced_id.id for l in lines]
        production_ids = list(set(production_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_produced').read()[0]
        if len(production_ids) > 1:
            action['domain'] = [('id', 'in', production_ids)]
        elif len(production_ids) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_produced_form').id, 'form')]
            action['res_id'] = production_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_rma_count(self):

        for ship in self:
            rmas = self.env['s2u.warehouse.rma.line'].search([('todo_id', 'in', ship.todo_ids.ids)])
            rma_ids = [r.rma_id.id for r in rmas]
            rma_ids = list(set(rma_ids))
            ship.rma_count = len(rma_ids)

    @api.multi
    def action_view_rma(self):
        rmas = self.env['s2u.warehouse.rma.line'].search([('todo_id', 'in', self.todo_ids.ids)])
        rma_ids = [r.rma_id.id for r in rmas]
        rma_ids = list(set(rma_ids))

        action = self.env.ref('s2uwarehouse.action_warehouse_rma').read()[0]
        if len(rma_ids) > 1:
            action['domain'] = [('id', 'in', rma_ids)]
        elif len(rma_ids) == 1:
            action['views'] = [(self.env.ref('s2uwarehouse.warehouse_rma_form').id, 'form')]
            action['res_id'] = rma_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _get_serialnumber_count(self):

        for outgoing in self:
            serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('outgoing_id', '=', outgoing.id)])
            outgoing.serialnumber_count = len(serialnumbers)

    @api.multi
    def action_view_serialnumber(self):
        serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('outgoing_id', '=', self.id)])

        action = self.env.ref('s2uwarehouse.action_warehouse_serialnumber').read()[0]
        if len(serialnumbers) >= 1:
            action['domain'] = [('id', 'in', serialnumbers.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    _outgoing_state = {
        'draft': [('readonly', False)]
    }

    _outgoing_state_not_done = {
        'draft': [('readonly', False)],
        'production': [('readonly', False)],
        'ok': [('readonly', False)]
    }

    name = fields.Char(string='Shipment', required=True, index=True, copy=False,
                       default=_new_number, readonly=True, states=_outgoing_state)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_outgoing_state_not_done)
    entity_id = fields.Many2one('s2u.crm.entity', string='Klant', required=True, index=True,
                                readonly=True, states=_outgoing_state_not_done)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contactpersoon', index=True,
                                 readonly=True, states=_outgoing_state_not_done)
    state = fields.Selection([
        ('draft', 'Pending'),
        ('production', 'Production'),
        ('ok', 'Todo'),
        ('done', 'Done'),
        ('rma', 'RMA')
    ], required=True, default='draft', string='State', copy=False, track_visibility='onchange')
    transaction_date = fields.Date(string='Date', index=True, copy=False, required=True,
                                   readonly=True, states=_outgoing_state,
                                   default=lambda self: fields.Date.context_today(self))
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'outgoing_id',
                                string='Transactions', copy=False, readonly=True)
    units_assigned_ids = fields.One2many('s2u.warehouse.outgoing.assigned.unit', 'outgoing_id',
                                         string='Units assigned', copy=False)
    items_assigned_ids = fields.One2many('s2u.warehouse.outgoing.assigned.unit.product', 'outgoing_id',
                                         string='Items assigned', copy=False)
    todo_ids = fields.One2many('s2u.warehouse.outgoing.todo', 'outgoing_id',
                               string='Todo', readonly=True, states=_outgoing_state_not_done)
    reference = fields.Char(string='Our reference', index=True, readonly=True, states=_outgoing_state_not_done)
    customer_code = fields.Char(string='Your reference', index=True, readonly=True, states=_outgoing_state_not_done)
    outgoing_type_id = fields.Many2one('s2u.warehouse.outgoing.type', string='Delivery', required=True,
                                       ondelete='restrict')
    load_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_outgoing_state_not_done)
    load_entity_id = fields.Many2one('s2u.crm.entity', string='Loading entity', index=True,
                                     readonly=True, states=_outgoing_state_not_done)
    trailer_no = fields.Char(string='Trailer-No.', index=True, readonly=True, states=_outgoing_state)
    tot_weight = fields.Float(string='# Weight', compute=_compute_tot_weight, readonly=True)
    tot_surface = fields.Float(string='# Surface', compute=_compute_tot_surface, readonly=True)
    is_ready = fields.Boolean(string='Ready', compute=_compute_is_ready, readonly=True)
    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)
    production_count = fields.Integer(string='# of Productions', compute='_get_production_count', readonly=True)
    delivery_type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_outgoing_state_not_done)
    delivery_entity_id = fields.Many2one('s2u.crm.entity', string='Delivery', required=True, index=True,
                                         readonly=True, states=_outgoing_state_not_done)
    delivery_contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                          readonly=True, states=_outgoing_state_not_done)
    delivery_address = fields.Text(string='Leveradres', readonly=True, required=True, states=_outgoing_state_not_done)
    delivery_country_id = fields.Many2one('res.country', string='Leveringsland', default=_default_delivery_country)
    delivery_tinno = fields.Char('TIN no.')
    delivery_lang = fields.Selection(_delivery_lang_get, string='Language')
    load_address = fields.Text(string='Loading address', readonly=True, states=_outgoing_state_not_done)
    date_delivery = fields.Date(string='Date delivery', copy=False, readonly=True, states=_outgoing_state_not_done)
    project = fields.Char(string='Project', index=True, readonly=True, states=_outgoing_state_not_done)
    rma_count = fields.Integer(string='# of RMA\'s', compute='_get_rma_count', readonly=True)
    serialnumber_count = fields.Integer(string='# of Serialnumbers', compute='_get_serialnumber_count', readonly=True)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_outgoing_state_not_done)

    def all_items_selected(self, unit):

        unitproducts = self.env['s2u.warehouse.unit.product'].search([('unit_id', '=', unit.id)])

        onunit = [x.id for x in unitproducts]

        for line in self.items_assigned_ids:
            if line.unit_id.id == unit.id and line.unitproduct_id.id in onunit:
                if line.unitproduct_id.product_qty != line.assigned_qty:
                    return False
                onunit.remove(line.unitproduct_id.id)
        if onunit:
            return False
        return True

    @api.multi
    def serialnumber_shipped_trigger(self, todo, product, product_detail, serialnumber, shipped):

        return {
            'outgoing_line_id': todo.id,
            'product_id': product.id,
            'product_detail': product_detail,
            'name': serialnumber
        }

    @api.multi
    def do_assigned_unit_items(self):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        todo_model = self.env['s2u.warehouse.outgoing.todo']

        todos_cache = {}
        for assigned in self.items_assigned_ids:
            todos = todo_model.search([('outgoing_id', '=', self.id),
                                       ('product_id', '=', assigned.unitproduct_id.product_id.id),
                                       ('product_detail', '=', assigned.unitproduct_id.product_detail)])
            if not todos:
                raise ValidationError(_('You are trying to ship items which are not on the todo list!'))
            assigned_qty = assigned.assigned_qty
            for t in todos:
                if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0), 2) <= 0.0:
                    continue
                if assigned_qty > round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0), 2):
                    shipped = round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0), 2)
                    assigned_qty = round(assigned_qty - shipped, 2)
                    if t.id in todos_cache:
                        todos_cache[t.id] -= shipped
                    else:
                        todos_cache[t.id] = shipped * -1.0

                    assigned.unitproduct_id.write({
                        'product_qty': assigned.unitproduct_id.product_qty - shipped
                    })

                    product = self.env[assigned.unitproduct_id.product_id.res_model].browse(assigned.unitproduct_id.product_id.res_id)
                    supplier = assigned.unitproduct_id.get_supplier()
                    if supplier:
                        account_po = product.get_po_account(supplier=supplier)
                    else:
                        account_po = product.po_account_id
                    if not account_po:
                        raise ValidationError(_('There is no po account defined for product %s!' % product.name))
                    if not product.stock_account_id:
                        raise ValidationError(_('There is no stock account defined for product %s!' % product.name))

                    vals = {
                        'parent_id': False,
                        'unit_id': assigned.unitproduct_id.unit_id.id,
                        'location_id': assigned.unitproduct_id.unit_id.location_id.id,
                        'product_id': assigned.unitproduct_id.id,
                        'qty': shipped * -1.0,
                        'transaction_date': fields.Date.context_today(self),
                        'source_model': 's2u.warehouse.outgoing',
                        'source_id': self.id,
                        'outgoing_id': self.id,
                        'outgoing_line_id': t.id,
                        'item_picking': True,
                        'entity_id': self.entity_id.id,
                        'amount_po_stock': shipped * assigned.unitproduct_id.product_value,
                        'account_stock_id': product.stock_account_id.id,
                        'account_po_id': account_po.id
                    }
                    trans = trans_model.create(vals)
                    assigned.unitproduct_id.unit_id.empty_unit(write=True)

                    # This method can be inherited by other modules, to do something with the financial stock
                    trans.financial_stock_on_outgoing(assigned.unitproduct_id, shipped, saleline=t.saleline_id)

                    # This method can be inherited by other modules, to do something with the serialnumber shipped
                    if assigned.unitproduct_id.product_id.sn_registration:
                        sn_shipped = self.serialnumber_shipped_trigger(t,
                                                                       assigned.unitproduct_id.product_id,
                                                                       assigned.unitproduct_id.product_detail,
                                                                       assigned.unitproduct_id.serialnumber,
                                                                       shipped)
                        self.env['s2u.warehouse.serialnumber'].do_sn_shipped(sn_shipped)
                else:
                    shipped = assigned_qty
                    if t.id in todos_cache:
                        todos_cache[t.id] -= shipped
                    else:
                        todos_cache[t.id] = shipped * -1.0

                    assigned.unitproduct_id.write({
                        'product_qty': assigned.unitproduct_id.product_qty - shipped
                    })

                    product = self.env[assigned.unitproduct_id.product_id.res_model].browse(
                        assigned.unitproduct_id.product_id.res_id)
                    supplier = assigned.unitproduct_id.get_supplier()
                    if supplier:
                        account_po = product.get_po_account(supplier=supplier)
                    else:
                        account_po = product.po_account_id
                    if not account_po:
                        raise ValidationError(_('There is no po account defined for product %s!' % product.name))
                    if not product.stock_account_id:
                        raise ValidationError(_('There is no stock account defined for product %s!' % product.name))

                    vals = {
                        'parent_id': False,
                        'unit_id': assigned.unitproduct_id.unit_id.id,
                        'location_id': assigned.unitproduct_id.unit_id.location_id.id,
                        'product_id': assigned.unitproduct_id.id,
                        'qty': shipped * -1.0,
                        'transaction_date': fields.Date.context_today(self),
                        'source_model': 's2u.warehouse.outgoing',
                        'source_id': self.id,
                        'outgoing_id': self.id,
                        'outgoing_line_id': t.id,
                        'item_picking': True,
                        'entity_id': self.entity_id.id,
                        'amount_po_stock': shipped * assigned.unitproduct_id.product_value,
                        'account_stock_id': product.stock_account_id.id,
                        'account_po_id': account_po.id
                    }
                    trans = trans_model.create(vals)
                    assigned.unitproduct_id.unit_id.empty_unit(write=True)
                    assigned_qty = 0.0

                    # This method can be inherited by other modules, to do something with the financial stock
                    trans.financial_stock_on_outgoing(assigned.unitproduct_id, shipped, saleline=t.saleline_id)

                    # This method can be inherited by other modules, to do something with the serialnumbers shipped
                    if assigned.unitproduct_id.product_id.sn_registration:
                        sn_shipped = self.serialnumber_shipped_trigger(t,
                                                                       assigned.unitproduct_id.product_id,
                                                                       assigned.unitproduct_id.product_detail,
                                                                       assigned.unitproduct_id.serialnumber,
                                                                       shipped)
                        self.env['s2u.warehouse.serialnumber'].do_sn_shipped(sn_shipped)
                    break
            if assigned_qty:
                raise ValidationError(_('You have assigned items which are not on the todo list!'))

        return True

    @api.multi
    def do_assigned_units(self, units):
        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        unit_model = self.env['s2u.warehouse.unit']
        todo_model = self.env['s2u.warehouse.outgoing.todo']

        todos_cache = {}
        for unit in units:
            if not unit.active:
                raise ValidationError(_('You are trying to ship units which are not present!'))

            for childunit in unit_model.search([('parent_id', '=', unit.id)]):
                if not childunit.active:
                    raise ValidationError(_('You are trying to ship units which are not present!'))
                # needed when multiple products on the same unit,
                # we want an unit only counted once on the delivery note
                count_unit = True
                for product in childunit.line_ids:
                    todos = todo_model.search([('outgoing_id', '=', self.id),
                                               ('product_id', '=', product.product_id.id),
                                               ('product_detail', '=', product.product_detail)])
                    if not todos:
                        raise ValidationError(_('You are trying to ship items which are not on the todo list!'))

                    # try to make perfect match:
                    todo_id = False
                    for t in todos:
                        if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0), 2) == round(product.product_qty, 2):
                            todo_id = t.id
                            break

                    if not todo_id:
                        todo_id = todos[0].id
                        for t in todos:
                            if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0), 2) > 0.0:
                                todo_id = t.id
                                break

                    shipped = product.product_qty
                    if todo_id in todos_cache:
                        todos_cache[todo_id] -= shipped
                    else:
                        todos_cache[todo_id] = shipped * -1.0

                    product.write({
                        'product_qty': 0.0,
                        'assigned_qty': 0.0
                    })

                    real_product = self.env[product.product_id.res_model].browse(product.product_id.res_id)
                    supplier = product.get_supplier()
                    if supplier:
                        account_po = real_product.get_po_account(supplier=supplier)
                    else:
                        account_po = real_product.po_account_id
                    if not account_po:
                        raise ValidationError(_('There is no po account defined for product %s!' % real_product.name))
                    if not real_product.stock_account_id:
                        raise ValidationError(_('There is no stock account defined for product %s!' % real_product.name))

                    vals = {
                        'parent_id': childunit.parent_id.id,
                        'unit_id': childunit.id,
                        'location_id': childunit.location_id.id,
                        'product_id': product.id,
                        'qty': shipped * -1.0,
                        'transaction_date': fields.Date.context_today(self),
                        'source_model': 's2u.warehouse.outgoing',
                        'source_id': self.id,
                        'outgoing_id': self.id,
                        'entity_id': self.entity_id.id,
                        'outgoing_line_id': todo_id,
                        'count_unit': count_unit,
                        'amount_po_stock': shipped * product.product_value,
                        'account_stock_id': real_product.stock_account_id.id,
                        'account_po_id': account_po.id
                    }
                    trans = trans_model.create(vals)
                    count_unit = False

                    if todo_id:
                        t = self.env['s2u.warehouse.outgoing.todo'].search([('id', '=', todo_id)], limit=1)
                        # This method can be inherited by other modules, to do something with the financial stock
                        trans.financial_stock_on_outgoing(product, shipped, saleline=t.saleline_id)
                    else:
                        t = False
                        # This method can be inherited by other modules, to do something with the financial stock
                        trans.financial_stock_on_outgoing(product, shipped, saleline=False)

                    if product.product_id.sn_registration:
                        # This method can be inherited by other modules, to do something with the products shipped
                        sn_shipped = self.serialnumber_shipped_trigger(t,
                                                                       product.product_id,
                                                                       product.product_detail,
                                                                       product.serialnumber,
                                                                       shipped)
                        self.env['s2u.warehouse.serialnumber'].do_sn_shipped(sn_shipped)
                childunit.empty_unit(write=True)

            # needed when multiple products on the same unit,
            # we want an unit only counted once on the delivery note
            count_unit = True
            for product in unit.line_ids:
                todos = todo_model.search([('outgoing_id', '=', self.id),
                                           ('product_id', '=', product.product_id.id),
                                           ('product_detail', '=', product.product_detail)])
                if not todos:
                    raise ValidationError(_('You are trying to ship items which are not on the todo list!'))

                # try to make perfect match:
                todo_id = False
                for t in todos:
                    if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0), 2) == round(product.product_qty, 2):
                        todo_id = t.id
                        break

                # no perfect match, find first todo_id which needs products
                if not todo_id:
                    todo_id = todos[0].id
                    for t in todos:
                        if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0), 2) > 0.0:
                            todo_id = t.id
                            break

                shipped = product.product_qty
                if todo_id in todos_cache:
                    todos_cache[todo_id] -= shipped
                else:
                    todos_cache[todo_id] = shipped * -1.0

                product.write({
                    'product_qty': 0.0,
                    'assigned_qty': 0.0
                })

                real_product = self.env[product.product_id.res_model].browse(product.product_id.res_id)
                supplier = product.get_supplier()
                if supplier:
                    account_po = real_product.get_po_account(supplier=supplier)
                else:
                    account_po = real_product.po_account_id
                if not account_po:
                    raise ValidationError(_('There is no po account defined for product %s!' % real_product.name))
                if not real_product.stock_account_id:
                    raise ValidationError(_('There is no stock account defined for product %s!' % real_product.name))

                vals = {
                    # 'parent_id': unit.parent_id.id if unit.parent_id else False,
                    'unit_id': unit.id,
                    'location_id': unit.location_id.id,
                    'product_id': product.id,
                    'qty': shipped * -1.0,
                    'transaction_date': fields.Date.context_today(self),
                    'source_model': 's2u.warehouse.outgoing',
                    'source_id': self.id,
                    'outgoing_id': self.id,
                    'entity_id': self.entity_id.id,
                    'outgoing_line_id': todo_id,
                    'count_unit': count_unit,
                    'amount_po_stock': shipped * product.product_value,
                    'account_stock_id': real_product.stock_account_id.id,
                    'account_po_id': account_po.id
                }
                trans = trans_model.create(vals)
                count_unit = False
                # This method can be inherited by other modules, to do something with the products shipped
                if todo_id:
                    t = self.env['s2u.warehouse.outgoing.todo'].search([('id', '=', todo_id)], limit=1)
                    # This method can be inherited by other modules, to do something with the financial stock
                    trans.financial_stock_on_outgoing(product, shipped, saleline=t.saleline_id)
                else:
                    t = False
                    # This method can be inherited by other modules, to do something with the financial stock
                    trans.financial_stock_on_outgoing(product, shipped, saleline=False)
                if product.product_id.sn_registration:
                    sn_shipped = self.serialnumber_shipped_trigger(t,
                                                                   product.product_id,
                                                                   product.product_detail,
                                                                   product.serialnumber,
                                                                   shipped)
                    self.env['s2u.warehouse.serialnumber'].do_sn_shipped(sn_shipped)

            unit.empty_unit(write=True)

        return True

    @api.multi
    def do_confirm(self):

        assigned_units_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assigned_items_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        self.ensure_one()

        assigned_units = assigned_units_model.search([('outgoing_id', '=', self.id)])
        assigned_items = assigned_items_model.search([('outgoing_id', '=', self.id)])

        if not assigned_units and not assigned_items:
            raise UserError(_('Nothing is assigned at the moment, "confirm" is not possible!'))

        if assigned_units:
            units = [au.unit_id for au in assigned_units if au.active]
            self.do_assigned_units(units)
            assigned_units.write({
                'active': False
            })

        if assigned_items:
            self.do_assigned_unit_items()
            assigned_items.write({
                'active': False
            })
        self.write({
            'state': 'ok'
        })

    @api.multi
    def unit_for_assignment(self, unit, todos_cache, calc_only=False):
        unit_model = self.env['s2u.warehouse.unit']
        todo_model = self.env['s2u.warehouse.outgoing.todo']

        if not unit.active:
            return False

        if unit.assigned_qty != 0 and not calc_only:
            return False

        todos_tmp_cache = {}
        for childunit in unit_model.search([('parent_id', '=', unit.id)]):
            if not childunit.active:
                return False
            if childunit.assigned_qty != 0:
                return False
            for product in childunit.line_ids:
                todos = todo_model.search([('outgoing_id', '=', self.id),
                                           ('product_id', '=', product.product_id.id),
                                           ('product_detail', '=', product.product_detail)])
                if not todos:
                    return False
                if product.assigned_qty != 0.0:
                    return False
                assigned = False
                for t in todos:
                    if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) + todos_tmp_cache.get(t.id, 0.0) - product.product_qty, 2) >= 0.0:
                        shipped = product.product_qty
                        if t.id in todos_tmp_cache:
                            todos_tmp_cache[t.id] -= shipped
                        else:
                            todos_tmp_cache[t.id] = shipped * -1.0
                        assigned = True
                        break

                if not assigned:
                    for t in todos:
                        if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) + todos_tmp_cache.get(t.id, 0.0), 2) > 0.0 and product.product_qty > 0.0:
                            shipped = product.product_qty
                            if t.id in todos_tmp_cache:
                                todos_tmp_cache[t.id] -= shipped
                            else:
                                todos_tmp_cache[t.id] = shipped * -1.0
                            assigned = True
                            break

                if not assigned:
                    return False

        for product in unit.line_ids:
            todos = todo_model.search([('outgoing_id', '=', self.id),
                                       ('product_id', '=', product.product_id.id),
                                       ('product_detail', '=', product.product_detail)])
            if not todos:
                return False
            if product.assigned_qty != 0.0 and not calc_only:
                return False
            assigned = False

            for t in todos:
                if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) + todos_tmp_cache.get(t.id, 0.0) - product.product_qty, 2) >= 0.0:
                    shipped = product.product_qty
                    if t.id in todos_tmp_cache:
                        todos_tmp_cache[t.id] -= shipped
                    else:
                        todos_tmp_cache[t.id] = shipped * -1.0
                    assigned = True
                    break
            if not assigned:
                for t in todos:
                    if round(t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) + todos_tmp_cache.get(t.id, 0.0), 2) > 0.0 and product.product_qty > 0.0:
                        shipped = product.product_qty
                        if t.id in todos_tmp_cache:
                            todos_tmp_cache[t.id] -= shipped
                        else:
                            todos_tmp_cache[t.id] = shipped * -1.0
                        assigned = True
                        break

            if not assigned:
                return False

        for id, qty in iter(todos_tmp_cache.items()):
            if id in todos_cache:
                todos_cache[id] += qty
            else:
                todos_cache[id] = qty

        return True

    def item_allowed(self, item):
        """"Checks if a unit.product is not already assigned by assigned.unit where the item is placed on"""

        assign_unit_model = self.env['s2u.warehouse.outgoing.assigned.unit']

        units = [item.unit_id.id]
        if item.unit_id.parent_id:
            units.append(item.unit_id.parent_id.id)

        assigned = assign_unit_model.search([('unit_id', 'in', units)])
        if assigned:
            return False
        else:
            return True

    @api.multi
    def item_for_assignment(self, item, assigned_qty, todos_cache, calc_only=False):

        if not item.unit_id.active:
            return False
        if item.unit_id.parent_id and not item.unit_id.parent_id.active:
            return False

        if not self.item_allowed(item):
            return False

        for todo in self.todo_ids:
            if not (todo.product_id.id == item.product_id.id and todo.product_detail == item.product_detail):
                continue
            qty_to_assign = round(todo.product_qty + todo.shipped_qty + todos_cache.get(todo.id, 0.0), 2)
            if qty_to_assign <= 0.0:
                continue

            if assigned_qty <= qty_to_assign:
                if todo.id in todos_cache:
                    todos_cache[todo.id] -= assigned_qty
                else:
                    todos_cache[todo.id] = assigned_qty * -1.0
                return True
        return False

    @api.multi
    def calculate_assigned(self, state=False):

        todo_model = self.env['s2u.warehouse.outgoing.todo']

        self.ensure_one()

        self.todo_ids.write({
            'assigned_qty': 0.0
        })

        if state and state in ['ok', 'done']:
            return True

        todo_cache = {}
        for assigned in self.units_assigned_ids:
            self.unit_for_assignment(assigned.unit_id, todo_cache, calc_only=True)

        for assigned in self.items_assigned_ids:
            self.item_for_assignment(assigned.unitproduct_id, assigned.assigned_qty, todo_cache, calc_only=True)

        for id, qty in iter(todo_cache.items()):
            # assigned values are negative (like shipment, products going out the warehouse),
            # this is why we use * -1.0, we want a positive value shown to the user, just a matter of taste
            todo_model.search([('id', '=', id)]).write({
                'assigned_qty': qty * -1.0
            })

        return True

    @api.multi
    def do_assign(self):
        self.ensure_one()

        pick_form = self.env.ref('s2uwarehouse.wizard_confirm_and_pick_view', False)
        ctx = dict(
            default_model='s2u.warehouse.outgoing',
            default_res_id=self.id,
        )
        return {
            'name': _('Assign units and items'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2u.warehouse.confirm.pick',
            'views': [(pick_form.id, 'form')],
            'view_id': pick_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def create_production(self, date_produced=False):

        self.ensure_one()

        vals = {
            'name': self.project
        }

        lines = []
        for item in self.todo_ids:
            total_to_produce = item.product_qty + item.shipped_qty - item.assigned_qty
            if total_to_produce <= 0.0:
                continue
            linevals = {
                'product_id': item.product_id.id,
                'product_qty': total_to_produce,
                'product_detail': item.product_detail,
                'product_value': item.product_value,
                'outgoing_id': self.id
            }
            if date_produced:
                linevals['date_produced'] = date_produced
            lines.append((0, 0, linevals))
        if lines:
            vals['line_ids'] = lines
            production = self.env['s2u.warehouse.produced'].create(vals)
            return production

        return False

    @api.multi
    def do_production(self):

        self.ensure_one()

        production = self.create_production()
        if production:
            self.write({
                'state': 'production'
            })

            action_rec = self.env['ir.model.data'].xmlid_to_object('s2uwarehouse.warehouse_produced_form')

            return {
                'type': 'ir.actions.act_window',
                'name': _('Production for Delivery'),
                'res_model': 's2u.warehouse.produced',
                'res_id': production.id,
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': action_rec.id,
                'target': 'current',
                'nodestroy': True,
            }

    @api.multi
    def undo_confirm(self):

        assigned_units_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assigned_items_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        self.ensure_one()

        for trans in self.trans_ids:
            trans.product_id.write({
                'product_qty': trans.product_id.product_qty - trans.qty
            })
            trans.product_id.unit_id.empty_unit(write=True)

        units = assigned_units_model.search([('outgoing_id', '=', self.id), ('active', '=', False)])
        units.write({
            'active': True
        })

        items = assigned_items_model.search([('outgoing_id', '=', self.id), ('active', '=', False)])
        items.write({
            'active': True
        })

        serialnumbers = self.env['s2u.warehouse.serialnumber'].search([('outgoing_id', '=', self.id)])
        serialnumbers.unlink()

        self.trans_ids.unlink()

        self.write({
            'state': 'draft'
        })

    @api.multi
    def undo_production(self):

        assigned_units_model = self.env['s2u.warehouse.outgoing.assigned.unit']
        assigned_items_model = self.env['s2u.warehouse.outgoing.assigned.unit.product']

        self.ensure_one()

        for trans in self.trans_ids:
            trans.product_id.write({
                'product_qty': trans.product_id.product_qty - trans.qty
            })
            trans.product_id.unit_id.empty_unit(write=True)

        units = assigned_units_model.search([('outgoing_id', '=', self.id), ('active', '=', False)])
        units.write({
            'active': True
        })

        items = assigned_items_model.search([('outgoing_id', '=', self.id), ('active', '=', False)])
        items.write({
            'active': True
        })

        self.trans_ids.unlink()

        self.write({
            'state': 'draft'
        })

    @api.multi
    def create_invoice(self, so):
        invoice_model = self.env['s2u.account.invoice']

        self.ensure_one()

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
                'net_amount': t.shipped_qty * -1.0 * t.product_value,
                'account_id': account.id,
                'descript': name,
                'qty': str(t.shipped_qty * -1.0),
                'net_price': t.product_value,
                'sale_id': t.sale_id.id
            }

            vat_sell_id = False
            if (self.delivery_country_id and so.delivery_country_id and self.delivery_country_id.id != so.delivery_country_id.id) or (self.delivery_country_id and not so.delivery_country_id):
                country_vat = self.env['s2u.account.vat.country'].search([('country_id', '=', self.delivery_country_id.id)])
                if not country_vat:
                    raise UserError(_('Please define Country VAT rule for country %s!' % self.delivery_country_id.name))
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
                'delivery_address': self.delivery_address,
                'delivery_country_id': self.delivery_country_id.id if self.delivery_country_id else False,
                'delivery_tinno': self.delivery_tinno,
                'delivery_ref': self.name
            }
            invoice_model += invoice_model.create(invdata)
        return invoice_model

    @api.multi
    def create_backorders(self):
        outgoing_model = self.env['s2u.warehouse.outgoing']

        for shipment in self:
            todos = []
            for t in shipment.todo_ids:
                if (t.shipped_qty + t.product_qty) <= 0.0:
                    continue

                vals = {
                    'sale_id': t.sale_id.id if t.sale_id else False,
                    'saleline_id': t.saleline_id.id if t.saleline_id else False,
                    'product_id': t.product_id.id,
                    'product_detail': t.product_detail,
                    'product_qty': t.product_qty + t.shipped_qty,
                    'product_value': t.product_value,
                    'type': 'rest'
                }
                todos.append((0, 0, vals))

            if todos:
                if shipment.reference:
                    reference = shipment.reference + ' [backorder]'
                else:
                    reference = shipment.reference
                outgoing = outgoing_model.create({
                    'type': shipment.type,
                    'entity_id': shipment.entity_id.id,
                    'contact_id': shipment.contact_id.id if shipment.contact_id else False,
                    'delivery_type': shipment.delivery_type,
                    'delivery_entity_id': shipment.delivery_entity_id.id,
                    'delivery_contact_id': shipment.delivery_contact_id.id if shipment.delivery_contact_id else False,
                    'delivery_address': shipment.delivery_address,
                    'project': shipment.project,
                    'reference': reference,
                    'outgoing_type_id': shipment.outgoing_type_id.id,
                    'todo_ids': todos
                })
                outgoing_model += outgoing

        return outgoing_model

    @api.multi
    def sale_is_completed(self):
        for shipment in self:
            sales_orders = []
            for t in shipment.todo_ids:
                if t.shipped_qty:
                    sales_orders.append(t.sale_id.id)
            sales_orders = list(set(sales_orders))

            # for each SO delivery a separate invoice
            for so in self.env['s2u.sale'].browse(sales_orders):
                if so.invoicing == 'delivery':
                    shipment.create_invoice(so)
                so.sale_is_completed()

        return True

    @api.multi
    def do_done(self):

        self.ensure_one()

        if not self.trans_ids:
            raise UserError(_('Nothing is shipped at the moment, "done" is not possible!'))

        self.create_backorders()
        self.sale_is_completed()

        for t in self.todo_ids:
            if (t.product_qty + t.shipped_qty) > 0.0:
                t.write({
                    'type': 'part'
                })

        self.write({
            'state': 'done'
        })

    @api.multi
    def do_rma(self):

        self.ensure_one()

        lines = []
        for todo in self.todo_ids:
            if todo.shipped_saldo_qty < 0.0:
                if todo.product_id.sn_registration:
                    trans = self.env['s2u.warehouse.unit.product.transaction'].search([('outgoing_line_id', '=', todo.id)])
                    for t in trans:
                        lines.append((0, 0, {
                            'product_id': todo.product_id.id,
                            'product_detail': todo.product_detail,
                            'product_value': t.amount_po_stock,
                            'qty': '1 stuks',
                            'product_qty': 1.0,
                            'todo_id': todo.id,
                            'serialnumber': t.product_id.serialnumber,
                            'account_po_id': t.account_po_id.id if t.account_po_id else False,
                            'account_stock_id': t.account_stock_id.id if t.account_stock_id else False
                        }))
                else:
                    trans = self.env['s2u.warehouse.unit.product.transaction'].search([('outgoing_line_id', '=', todo.id)])
                    for t in trans:
                        qty = t.qty * -1.0
                        lines.append((0, 0, {
                            'product_id': todo.product_id.id,
                            'product_detail': todo.product_detail,
                            'product_value': round(t.amount_po_stock / qty, 2),
                            'qty': '%d x' % int(qty),
                            'product_qty': qty,
                            'todo_id': todo.id,
                            'account_po_id': t.account_po_id.id if t.account_po_id else False,
                            'account_stock_id': t.account_stock_id.id if t.account_stock_id else False
                    }))
        if lines:
            rma_vals = {
                'type': self.type,
                'entity_id': self.entity_id.id,
                'contact_id': self.contact_id.id if self.contact_id else False,
                'reference': self.name,
                'line_ids': lines
            }
            return self.env['s2u.warehouse.rma'].create(rma_vals)
        else:
            return False

    @api.model
    def create(self, vals):

        out = super(Outgoing, self).create(vals)
        if vals.get('state', False):
            out.calculate_assigned(state=vals['state'])
        else:
            out.calculate_assigned()

        return out

    @api.multi
    def write(self, vals):

        res = super(Outgoing, self).write(vals)
        for out in self:
            if vals.get('state', False):
                out.calculate_assigned(state=vals['state'])
            else:
                out.calculate_assigned()

        return res

    @api.multi
    def unlink(self):

        for shipment in self:
            if shipment.state != 'draft':
                raise ValidationError(_('You can not delete a closed shipment!'))

            for assigned in shipment.units_assigned_ids:
                assigned.unit_id.unassign_unit()
            for assigned in shipment.items_assigned_ids:
                assigned.unitproduct_id.unassign_item(assigned.assigned_qty)

            for trans in shipment.trans_ids:
                trans.product_id.write({
                    'product_qty': trans.product_id.product_qty - trans.qty
                })
                trans.product_id.unit_id.empty_unit(write=True)

        res = super(Outgoing, self).unlink()

        return res


class OutgoingUnitTransaction(models.TransientModel):
    _name = 's2u.warehouse.outgoing.unit'

    @api.model
    def default_get(self, fields):

        rec = super(OutgoingUnitTransaction, self).default_get(fields)

        return rec

    @api.multi
    def do_ship(self):
        context = self._context
        unit_ids = context.get('active_ids', [])

        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        unit_model = self.env['s2u.warehouse.unit']
        todo_model = self.env['s2u.warehouse.outgoing.todo']

        todos_cache = {}
        for unit_id in unit_ids:
            unit = unit_model.browse(unit_id)
            if not unit.active:
                raise ValidationError(_('You are trying to ship units which are not present!'))

            for childunit in unit_model.search([('parent_id', '=', unit.id)]):
                if not childunit.active:
                    raise ValidationError(_('You are trying to ship units which are not present!'))
                for product in childunit.line_ids:
                    todos = todo_model.search([('outgoing_id', '=', self.outgoing_id.id),
                                               ('product_id', '=', product.product_id.id),
                                               ('product_detail', '=', product.product_detail)])
                    if not todos:
                        raise ValidationError(_('You are trying to ship items which are not on the todo list!'))
                    todo_id = todos[0].id
                    for t in todos:
                        if t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) > 0.0:
                            todo_id = t.id
                            break

                    shipped = product.product_qty
                    if t.id in todos_cache:
                        todos_cache[t.id] -= shipped
                    else:
                        todos_cache[t.id] = shipped * -1.0

                    product.write({
                        'product_qty': 0.0
                    })

                    vals = {
                        'parent_id': childunit.parent_id.id,
                        'unit_id': childunit.id,
                        'location_id': childunit.location_id.id,
                        'product_id': product.id,
                        'qty': shipped * -1.0,
                        'transaction_date': self.transaction_date,
                        'source_model': 's2u.warehouse.outgoing',
                        'source_id': self.outgoing_id.id,
                        'outgoing_id': self.outgoing_id.id,
                        'entity_id': self.outgoing_id.entity_id.id,
                        'outgoing_line_id': todo_id
                    }
                    trans_model.create(vals)
                childunit.empty_unit(write=True)

            for product in unit.line_ids:
                todos = todo_model.search([('outgoing_id', '=', self.outgoing_id.id),
                                           ('product_id', '=', product.product_id.id),
                                           ('product_detail', '=', product.product_detail)])
                if not todos:
                    raise ValidationError(_('You are trying to ship items which are not on the todo list!'))
                todo_id = todos[0].id
                for t in todos:
                    if t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) > 0.0:
                        todo_id = t.id
                        break

                shipped = product.product_qty
                if t.id in todos_cache:
                    todos_cache[t.id] -= shipped
                else:
                    todos_cache[t.id] = shipped * -1.0

                product.write({
                    'product_qty': 0.0
                })

                vals = {
                    'parent_id': unit.parent_id.id if unit.parent_id else False,
                    'unit_id': unit.id,
                    'location_id': unit.location_id.id,
                    'product_id': product.id,
                    'qty': shipped * -1.0,
                    'transaction_date': self.transaction_date,
                    'source_model': 's2u.warehouse.outgoing',
                    'source_id': self.outgoing_id.id,
                    'outgoing_id': self.outgoing_id.id,
                    'entity_id': self.outgoing_id.entity_id.id,
                    'outgoing_line_id': todo_id
                }
                trans_model.create(vals)

            unit.empty_unit(write=True)

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', domain=[('state', '=', 'ok')],
                                  string='Shipment', ondelete='set null')
    transaction_date = fields.Date(string='Date', default=lambda self: fields.Date.context_today(self))


class OutgoingUnitProductTransaction(models.TransientModel):
    _name = 's2u.warehouse.outgoing.unit.product'

    @api.model
    def default_get(self, fields):

        rec = super(OutgoingUnitProductTransaction, self).default_get(fields)

        context = self._context
        active_model = context.get('active_model')
        unitproduct_ids = context.get('active_ids', [])

        # Checks on context parameters
        if active_model != 's2u.warehouse.unit.product':
            raise UserError(_(
                "Programmation error: the expected model for this action is 's2u.warehouse.unit.product'. The provided one is '%d'.") % active_model)

        lines = []
        unitproducts = self.env['s2u.warehouse.unit.product'].browse(unitproduct_ids)
        for p in unitproducts:
            lines.append((0, 0, {
                'product_id': p.product_id.id,
                'product_value': p.product_value,
                'product_qty': p.product_qty,
                'qty_ship': p.product_qty,
                'product_detail': p.product_detail,
                'location_id': p.location_id.id,
                'unit_id': p.unit_id.id,
                'unitproduct_id': p.id
            }))
        rec['line_ids'] = lines

        location = self.env['s2u.warehouse.location'].search([('usage', '=', 'outgoing')], limit=1)
        if location:
            rec['location_id'] = location.id

        return rec

    def all_items_selected(self, unit):

        unitproducts = self.env['s2u.warehouse.unit.product'].search([('unit_id', '=', unit.id)])

        onunit = [x.id for x in unitproducts]

        for line in self.line_ids:
            if line.unit_id.id == unit.id and line.unitproduct_id.id in onunit:
                if line.product_qty != line.qty_ship:
                    return False
                onunit.remove(line.unitproduct_id.id)
        if onunit:
            return False
        return True

    @api.multi
    def do_ship(self):
        unit_model = self.env['s2u.warehouse.unit']
        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        todo_model = self.env['s2u.warehouse.outgoing.todo']

        if self.outgoing_id.state == 'draft':
            raise ValidationError(_('Please confirm this outgoing shipment first, before shipping goods!'))

        if self.outgoing_id.state != 'ok':
            raise ValidationError(_('This outgoing shipment is closed, you can not ship goods for it!'))

        if self.type == 'existing':
            units_to_ship = []
            for line in self.line_ids:
                if line.product_qty != line.qty_ship and line.qty_ship != 0.0:
                    raise ValidationError(_('You want to ship existing units, the qty to ship should be equal to qty on unit!'))
                if line.unit_id not in units_to_ship:
                    if not self.all_items_selected(line.unit_id):
                        raise ValidationError(
                            _('You want to ship unit %s, but you have not selected all items on it!' % line.unit_id.name))
                    if unit_model.search([('parent_id', '=', line.unit_id.id)]):
                        raise ValidationError(
                            _('Unit %s has child units on it, please select this unit over units and not over items!' % line.unit_id.name))

                    units_to_ship.append(line.unit_id)

            todos_cache = {}
            for unit in units_to_ship:
                if not unit.active:
                    raise ValidationError(_('You are trying to ship units which are not present!'))

                for product in unit.line_ids:
                    todos = todo_model.search([('outgoing_id', '=', self.outgoing_id.id),
                                               ('product_id', '=', product.product_id.id),
                                               ('product_detail', '=', product.product_detail)])
                    if not todos:
                        raise ValidationError(_('You are trying to ship items which are not on the todo list!'))
                    todo_id = todos[0].id
                    for t in todos:
                        if t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) > 0.0:
                            todo_id = t.id
                            break

                    shipped = product.product_qty
                    if t.id in todos_cache:
                        todos_cache[t.id] -= shipped
                    else:
                        todos_cache[t.id] = shipped * -1.0

                    product.write({
                        'product_qty': 0.0
                    })

                    vals = {
                        'parent_id': unit.parent_id.id if unit.parent_id else False,
                        'unit_id': unit.id,
                        'location_id': unit.location_id.id,
                        'product_id': product.id,
                        'qty': shipped * -1.0,
                        'transaction_date': self.transaction_date,
                        'source_model': 's2u.warehouse.outgoing',
                        'source_id': self.outgoing_id.id,
                        'outgoing_id': self.outgoing_id.id,
                        'entity_id': self.outgoing_id.entity_id.id,
                        'outgoing_line_id': todo_id
                    }
                    trans_model.create(vals)
                unit.empty_unit(write=True)
            return True

        if self.type in ['singleton', 'box']:
            unit = unit_model.create({
                'type': self.type,
                'location_id': self.location_id.id
            })
        else:
            unit = unit_model.create({
                'type': self.type,
                'pallet_id': self.pallet_id.id,
                'pallet_factor': self.pallet_factor,
                'location_id': self.location_id.id
            })

        for line in self.line_ids:
            move_vals = {
                'from_unit_id': line.unit_id.id,
                'unit_id': unit.id,
                'product_id': line.unitproduct_id.id,
                'product_qty': line.qty_ship,
                'date_entry': self.transaction_date
            }

            move = self.env['s2u.warehouse.move.product'].create(move_vals)
            move.do_confirm()

        todos_cache = {}
        for product in unit.line_ids:
            todos = todo_model.search([('outgoing_id', '=', self.outgoing_id.id),
                                       ('product_id', '=', product.product_id.id),
                                       ('product_detail', '=', product.product_detail)])
            if not todos:
                raise ValidationError(_('You are trying to ship items which are not on the todo list!'))
            todo_id = todos[0].id
            for t in todos:
                if t.shipped_qty + t.product_qty + todos_cache.get(t.id, 0.0) > 0.0:
                    todo_id = t.id
                    break

            shipped = product.product_qty
            if t.id in todos_cache:
                todos_cache[t.id] -= shipped
            else:
                todos_cache[t.id] = shipped * -1.0

            product.write({
                'product_qty': 0.0
            })

            vals = {
                'parent_id': False,
                'unit_id': unit.id,
                'location_id': unit.location_id.id,
                'product_id': product.id,
                'qty': shipped * -1.0,
                'transaction_date': self.transaction_date,
                'source_model': 's2u.warehouse.outgoing',
                'source_id': self.outgoing_id.id,
                'outgoing_id': self.outgoing_id.id,
                'outgoing_line_id': todo_id
            }
            trans_model.create(vals)

        unit.empty_unit(write=True)
        return True

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', domain=[('state', '=', 'ok')],
                                  string='Shipment', ondelete='set null')
    transaction_date = fields.Date(string='Date', default=lambda self: fields.Date.context_today(self),
                                   required=True)
    type = fields.Selection([
        ('existing', 'Existing'),
        ('singleton', 'Virtual'),
        ('pallet', 'Unit'),
        ('box', 'Box')
    ], required=True, default='existing', string='Unit')
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Pallet', ondelete='set null')
    pallet_factor = fields.Integer(string='Factor', default=1)
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', ondelete='set null')
    group_items = fields.Boolean('Group', default=False, help="If you want all products on the same pallet or in the same box, select this option.")
    line_ids = fields.One2many('s2u.warehouse.outgoing.unit.product.line', 'add_id', string='Lines')


class OutgoingUnitProductTransactionLine(models.TransientModel):
    _name = 's2u.warehouse.outgoing.unit.product.line'
    _inherit = "s2u.baseproduct.transaction.abstract"

    add_id = fields.Many2one('s2u.warehouse.outgoing.unit.product', string='Ship', required=True)
    qty_ship = fields.Float(string='Ship')
    qty_open = fields.Float(string='Qty open')
    product_qty = fields.Float(required=False, default=1.0)
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', ondelete='set null')
    unit_id = fields.Many2one('s2u.warehouse.unit', string='Unit', ondelete='set null')
    unitproduct_id = fields.Many2one('s2u.warehouse.unit.product', string='Unit product', ondelete='set null')


class IncomingLine(models.Model):
    _name = "s2u.warehouse.incoming.line"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _description = "Incoming line (purchase order)"
    _order = "date_delivery, product_id"

    @api.one
    def _compute_received_qty(self):

        tot_received = 0.0

        for trans in self.incoming_id.trans_ids:
            if trans.incoming_line_id.id != self.id:
                continue
            if trans.product_id.product_id == self.product_id and trans.product_id.product_detail == self.product_detail:
                tot_received += trans.qty

        self.received_qty = tot_received

    _incoming_state = {
        'draft': [('readonly', False)],
    }

    _incoming_wait_state = {
        'draft': [('readonly', False)],
        'wait': [('readonly', False)],
    }

    incoming_id = fields.Many2one('s2u.warehouse.incoming', string='Levering', required=True, index=True,
                                  ondelete='cascade')
    state = fields.Selection([
        ('draft', 'Concept'),
        ('wait', 'Wait for goods'),
        ('done', 'Done')
    ], related='incoming_id.state')
    date_delivery = fields.Date(string='Date delivery')
    received_qty = fields.Float(string='Received', compute=_compute_received_qty, readonly=True)
    product_id = fields.Many2one(readonly=True, states=_incoming_state)
    product_qty = fields.Float(readonly=True, states=_incoming_state)
    product_detail = fields.Char(readonly=True, states=_incoming_state)


class IncomingPalletsRetour(models.Model):
    _name = "s2u.warehouse.incoming.pallet.retour"
    _description = "Pallets retour"
    _order = "date_delivery, pallet_id, pallet_qty"

    incoming_id = fields.Many2one('s2u.warehouse.incoming', string='Levering', required=True, index=True,
                                  ondelete='cascade')
    date_delivery = fields.Date(string='Date retour', required=True, default=lambda self: fields.Date.context_today(self))
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Pallet', index=True, required=True)
    pallet_qty = fields.Integer(string='Qty', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)


class Incoming(models.Model):
    _name = "s2u.warehouse.incoming"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Delivery"
    _order = "date_delivery, name desc"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(Incoming, self)._track_subtype(init_values)

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.warehouse.incoming')])
        if not exists:
            raise ValueError(_('Sequence for creating s2u.warehouse.incoming number not exists!'))

        sequence = exists[0]
        new_number = sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()
        if self.env.user.name:
            name = self.env.user.name.split(' ')
            initials = ''
            for n in name:
                initials = '%s%s' % (initials, n[0].upper())
            new_number = '%s/%s' % (new_number, initials)
        return new_number

    @api.one
    @api.depends('line_ids.date_delivery', 'state')
    def _compute_date_delivery(self):
        dl = False
        if self.state in ['draft', 'wait']:
            for delivery in self.line_ids:
                if not delivery.date_delivery:
                    continue
                if not dl or delivery.date_delivery < dl:
                    dl = delivery.date_delivery
        self.date_delivery = dl

    @api.model
    def _default_warehouse(self):

        return self.env['s2u.warehouse'].search([('default', '=', True)])

    _incoming_state = {
        'draft': [('readonly', False)],
    }

    _wait_state = {
        'wait': [('readonly', False)],
    }

    _incoming_wait_state = {
        'draft': [('readonly', False)],
        'wait': [('readonly', False)],
    }

    name = fields.Char(string='Levering', required=True, index=True, copy=False,
                       default=_new_number, readonly=True, states=_incoming_state)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    entity_id = fields.Many2one('s2u.crm.entity', string='Leverancier', required=True, index=True,
                                readonly=True, states=_incoming_state)
    line_ids = fields.One2many('s2u.warehouse.incoming.line', 'incoming_id',
                               string='Expected', copy=True, readonly=True, states=_incoming_wait_state)
    pallet_ids = fields.One2many('s2u.warehouse.incoming.pallet.retour', 'incoming_id',
                                 string='Pallets retour', copy=False, readonly=True, states=_wait_state)
    date_delivery = fields.Date(string='Date delivery', compute=_compute_date_delivery, store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('wait', 'Wait for goods'),
        ('done', 'Done')
    ], required=True, default='draft', string='State', copy=False, track_visibility='onchange')
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'incoming_id',
                                string='Transactions', copy=False, readonly=True)
    reference = fields.Char(string='Reference', index=True, copy=False, readonly=True, states=_incoming_state)
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Outgoing', index=True,
                                  ondelete='set null')
    warehouse_id = fields.Many2one('s2u.warehouse', string='Warehouse', required=True, index=True,
                                   readonly=True, states=_incoming_state, default=_default_warehouse)

    @api.multi
    def do_confirm(self):

        self.ensure_one()

        self.write({
            'state': 'wait'
        })

    @api.multi
    def undo_confirm(self):

        self.ensure_one()

        unit_ids = []
        for trans in self.trans_ids:
            trans.product_id.write({
                'product_qty': trans.product_id.product_qty - trans.qty
            })
            trans.product_id.unit_id.empty_unit(write=True)
            unit_ids.append(trans.unit_id.id)

        if self.outgoing_id:
            assigned_units = self.env['s2u.warehouse.outgoing.assigned.unit'].search([('outgoing_id', '=', self.outgoing_id.id),
                                                                                      ('unit_id', 'in', unit_ids)])
            assigned_units.unlink()
            self.outgoing_id.calculate_assigned()

        self.trans_ids.unlink()

        self.write({
            'state': 'draft'
        })

    @api.multi
    def do_done(self):

        self.ensure_one()

        if not self.trans_ids:
            raise UserError(_('Nothing is received at the moment, "done" is not possible!'))

        self.write({
            'state': 'done'
        })

    @api.multi
    def undo_done(self):

        self.ensure_one()

        self.write({
            'state': 'wait'
        })

    @api.multi
    def unlink(self):

        for shipment in self:
            if shipment.state == 'done':
                raise ValidationError(_('You can not delete a closed shipment!'))

            for trans in shipment.trans_ids:
                trans.product_id.write({
                    'product_qty': trans.product_id.product_qty - trans.qty
                })
                trans.product_id.unit_id.empty_unit(write=True)

        res = super(Incoming, self).unlink()

        return res

    @api.multi
    def do_receive_goods(self):

        self.ensure_one()

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        lines = []
        po_products = self.env['s2u.warehouse.incoming.line'].search([('incoming_id', '=', self.id)])
        for p in po_products:
            tot_received = 0.0

            transactions = trans_model.search([('incoming_id', '=', self.id)])
            for trans in transactions:
                if trans.product_id.product_id.id == p.product_id.id and trans.product_id.product_detail == p.product_detail:
                    tot_received += trans.qty

            lines.append({
                'line_id': p.id,
                'product_id': p.product_id.id,
                'product_value': p.product_value,
                'product_detail': p.product_detail,
                'qty_open': p.product_qty - tot_received
            })

        trans_vals = {
            'incoming_id': self.id,
        }

        location = self.env['s2u.warehouse.location'].search([('usage', '=', 'incoming')], limit=1)
        if location:
            trans_vals['location_id'] = location.id

        trans = self.env['s2u.warehouse.incoming.add'].create(trans_vals)
        for line in lines:
            line['add_id'] = trans.id
            self.env['s2u.warehouse.incoming.add.item'].create(line)

        action = self.env.ref('s2uwarehouse.action_warehouse_incoming_transaction').read()[0]
        action['target'] = 'new'
        action['views'] = [(self.env.ref('s2uwarehouse.view_warehouse_incoming_transaction').id, 'form')]
        action['res_id'] = trans.id
        return action


class IncomingAddTransaction(models.TransientModel):
    _name = 's2u.warehouse.incoming.add'

    @api.multi
    def do_add(self):

        def check_serialnumbers(product, serialnumbers, parsed_qty, check_if_exists=False):
            if not product.sn_registration:
                return []
            sn_lines = []
            if serialnumbers:
                for sn in serialnumbers.split('\n'):
                    if not sn.strip():
                        continue
                    if check_if_exists:
                        available = False
                        for check in sn_lines:
                            if check.upper() == sn.upper():
                                available = True
                                break
                        if not available:
                            transactions = self.env['s2u.warehouse.unit.product.transaction'].search([('rel_product_id', '=', product.id),
                                                                                                      ('rel_serialnumber', 'ilike', sn)])
                            available = int(sum(t.qty for t in transactions))
                        if available:
                            raise ValidationError(_('serialnumber %s already exists for product %s' % (sn, product.name)))
                    sn_lines.append(sn)
            if parsed_qty[2]:
                item_qty = int(parsed_qty[2])
                if parsed_qty[0]:
                    item_qty = int(parsed_qty[0]) * item_qty
            else:
                item_qty = 0
            if item_qty != len(sn_lines):
                raise ValidationError(_('You received %d products and entered %d serialnumbers.' % (int(item_qty), len(sn_lines))))

            return sn_lines

        unit_model = self.env['s2u.warehouse.unit']
        product_model = self.env['s2u.warehouse.unit.product']
        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        if self.incoming_id.state == 'draft':
            raise ValidationError(_('Please confirm this incoming shipment first, before receiving goods!'))

        if self.incoming_id.state != 'wait':
            raise ValidationError(_('This incoming shipment is closed, you can not receive goods for it!'))

        units_received = []

        if self.pallets:
            # we receive the items on pallets
            total_qty = 0.0
            for item in self.line_ids:
                parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                if not parsed_qty:
                    raise ValidationError(_("Please enter a valid value for 'Qty'!"))
                if parsed_qty[0]:
                    total_qty += (float(parsed_qty[0]) * parsed_qty[2])
                else:
                    total_qty += parsed_qty[2]

                check_serialnumbers(item.product_id, item.serialnumbers, parsed_qty, check_if_exists=True)

            # we only create the pallets when we have items on it
            if total_qty > 0.0:
                for i in range(self.pallets):
                    unit = unit_model.create({
                        'type': 'pallet',
                        'pallet_id': self.pallet_id.id,
                        'pallet_factor': self.pallet_factor,
                        'location_id': self.location_id.id
                    })
                    units_received.append(unit)

                    count_unit = True
                    for item in self.line_ids:
                        parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                        sn_lines = check_serialnumbers(item.product_id, item.serialnumbers, parsed_qty)
                        sn_index = 0
                        if parsed_qty[2]:
                            # we hebben te maken met een verpakking op de pallet
                            if parsed_qty[0]:
                                for box_no in range(parsed_qty[0]):
                                    box = unit_model.create({
                                        'type': 'box',
                                        'location_id': self.location_id.id,
                                        'parent_id': unit.id
                                    })
                                    if item.product_id.sn_registration:
                                        for i in range(int(parsed_qty[2])):
                                            vals = {
                                                'unit_id': box.id,
                                                'product_id': item.product_id.id,
                                                'product_qty': 1.0,
                                                'product_value': item.product_value,
                                                'product_detail': item.product_detail,
                                                'serialnumber': sn_lines[sn_index],
                                                'sn_registration': True
                                            }
                                            product = product_model.create(vals)
                                            sn_index += 1

                                            vals = {
                                                'unit_id': box.id,
                                                'parent_id': unit.id,
                                                'location_id': box.location_id.id,
                                                'product_id': product.id,
                                                'qty': 1.0,
                                                'transaction_date': self.transaction_date,
                                                'source_model': 's2u.warehouse.incoming',
                                                'source_id': self.incoming_id.id,
                                                'incoming_id': self.incoming_id.id,
                                                'supplier_no': self.supplier_no,
                                                'entity_id': self.incoming_id.entity_id.id,
                                                'incoming_line_id': item.line_id.id
                                            }
                                            trans_model.create(vals)
                                    else:
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
                                            'source_model': 's2u.warehouse.incoming',
                                            'source_id': self.incoming_id.id,
                                            'incoming_id': self.incoming_id.id,
                                            'supplier_no': self.supplier_no,
                                            'entity_id': self.incoming_id.entity_id.id,
                                            'incoming_line_id': item.line_id.id
                                        }
                                        trans_model.create(vals)
                            else:
                                if item.product_id.sn_registration:
                                    for i in range(int(parsed_qty[2])):
                                        vals = {
                                            'unit_id': unit.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': 1.0,
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail,
                                            'serialnumber': sn_lines[sn_index],
                                            'sn_registration': True
                                        }
                                        product = product_model.create(vals)
                                        sn_index += 1

                                        vals = {
                                            'product_id': product.id,
                                            'unit_id': unit.id,
                                            'location_id': unit.location_id.id,
                                            'qty': 1.0,
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.incoming',
                                            'source_id': self.incoming_id.id,
                                            'incoming_id': self.incoming_id.id,
                                            'supplier_no': self.supplier_no,
                                            'entity_id': self.incoming_id.entity_id.id,
                                            'incoming_line_id': item.line_id.id,
                                            'count_unit': count_unit
                                        }
                                        trans_model.create(vals)
                                        count_unit = False
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
                                        'source_model': 's2u.warehouse.incoming',
                                        'source_id': self.incoming_id.id,
                                        'incoming_id': self.incoming_id.id,
                                        'supplier_no': self.supplier_no,
                                        'entity_id': self.incoming_id.entity_id.id,
                                        'incoming_line_id': item.line_id.id,
                                        'count_unit': count_unit
                                    }
                                    trans_model.create(vals)
                                    count_unit = False
        else:
            # we receive the items without a placeholder
            total_qty = 0.0
            for item in self.line_ids:
                parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                if not parsed_qty:
                    raise ValidationError(_("Please enter a valid value for 'Qty'!"))
                if parsed_qty[0]:
                    total_qty += (float(parsed_qty[0]) * parsed_qty[2])
                else:
                    total_qty += parsed_qty[2]

                check_serialnumbers(item.product_id, item.serialnumbers, parsed_qty, check_if_exists=True)

            if total_qty > 0.0:
                unit = unit_model.create({
                    'type': 'singleton',
                    'location_id': self.location_id.id
                })
                units_received.append(unit)
                count_unit = True
                for item in self.line_ids:
                    parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                    sn_lines = check_serialnumbers(item.product_id, item.serialnumbers, parsed_qty)
                    sn_index = 0
                    if parsed_qty[2]:
                        # we hebben te maken met een verpakking
                        if parsed_qty[0]:
                            for box_no in range(parsed_qty[0]):
                                box = unit_model.create({
                                    'type': 'box',
                                    'location_id': self.location_id.id,
                                    'parent_id': unit.id
                                })

                                if item.product_id.sn_registration:
                                    for i in range(int(parsed_qty[2])):
                                        vals = {
                                            'unit_id': box.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': 1.0,
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail,
                                            'serialnumber': sn_lines[sn_index],
                                            'sn_registration': True
                                        }
                                        product = product_model.create(vals)
                                        sn_index += 1

                                        vals = {
                                            'product_id': product.id,
                                            'unit_id': box.id,
                                            'parent_id': unit.id,
                                            'location_id': box.location_id.id,
                                            'qty': 1.0,
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.incoming',
                                            'source_id': self.incoming_id.id,
                                            'incoming_id': self.incoming_id.id,
                                            'supplier_no': self.supplier_no,
                                            'entity_id': self.incoming_id.entity_id.id,
                                            'incoming_line_id': item.line_id.id
                                        }
                                        trans_model.create(vals)
                                else:
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
                                        'source_model': 's2u.warehouse.incoming',
                                        'source_id': self.incoming_id.id,
                                        'incoming_id': self.incoming_id.id,
                                        'supplier_no': self.supplier_no,
                                        'entity_id': self.incoming_id.entity_id.id,
                                        'incoming_line_id': item.line_id.id
                                    }
                                    trans_model.create(vals)
                        else:
                            if item.product_id.sn_registration:
                                for i in range(int(parsed_qty[2])):
                                    vals = {
                                        'unit_id': unit.id,
                                        'product_id': item.product_id.id,
                                        'product_qty': 1.0,
                                        'product_value': item.product_value,
                                        'product_detail': item.product_detail,
                                        'serialnumber': sn_lines[sn_index],
                                        'sn_registration': True
                                    }
                                    product = product_model.create(vals)
                                    sn_index += 1

                                    vals = {
                                        'product_id': product.id,
                                        'unit_id': unit.id,
                                        'location_id': unit.location_id.id,
                                        'qty': 1.0,
                                        'transaction_date': self.transaction_date,
                                        'source_model': 's2u.warehouse.incoming',
                                        'source_id': self.incoming_id.id,
                                        'incoming_id': self.incoming_id.id,
                                        'supplier_no': self.supplier_no,
                                        'entity_id': self.incoming_id.entity_id.id,
                                        'incoming_line_id': item.line_id.id,
                                        'count_unit': count_unit
                                    }
                                    trans_model.create(vals)
                                    count_unit = False
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
                                    'source_model': 's2u.warehouse.incoming',
                                    'source_id': self.incoming_id.id,
                                    'incoming_id': self.incoming_id.id,
                                    'supplier_no': self.supplier_no,
                                    'entity_id': self.incoming_id.entity_id.id,
                                    'incoming_line_id': item.line_id.id,
                                    'count_unit': count_unit
                                }
                                trans_model.create(vals)
                                count_unit = False

        if self.incoming_id.outgoing_id:
            for unit in units_received:
                self.env['s2u.warehouse.outgoing.assigned.unit'].create({
                    'outgoing_id': self.incoming_id.outgoing_id.id,
                    'unit_id': unit.id
                })
            self.incoming_id.outgoing_id.calculate_assigned()

    incoming_id = fields.Many2one('s2u.warehouse.incoming', string='Levering')
    pallets = fields.Integer(string='Units', requird=True, default=0)
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Unit')
    pallet_factor = fields.Integer(string='Unit factor', default=1, requird=True)
    line_ids = fields.One2many('s2u.warehouse.incoming.add.item', 'add_id', string='Lines')
    location_id = fields.Many2one('s2u.warehouse.location', string='Location')
    transaction_date = fields.Date(string='Date', copy=False, required=True,
                                   default=lambda self: fields.Date.context_today(self))
    supplier_no = fields.Char('Supplier No.')


class IncomingAddTransactionItem(models.TransientModel):
    _name = 's2u.warehouse.incoming.add.item'
    _inherit = "s2u.baseproduct.transaction.abstract"

    add_id = fields.Many2one('s2u.warehouse.incoming.add', string='Pallet', required=True)
    line_id = fields.Many2one('s2u.warehouse.incoming.line', string='Incoming line', ondelete='set null')
    qty_received = fields.Char(string='Qty received')
    qty_open = fields.Float(string='Qty open')
    product_qty = fields.Float(required=False, default=1.0)
    serialnumbers = fields.Text(string='S/N')
    sn_registration = fields.Boolean(string='Product registration', related='product_id.sn_registration', readonly=True)

    @api.one
    @api.constrains('qty_received')
    def _check_qty_received(self):
        if not self.qty_received:
            raise ValidationError("Please enter value for 'Qty'.")
        if not self.env['s2u.warehouse.uom'].parse_qty(self.qty_received):
            raise ValidationError("Invalid value for 'Qty'.")


class PalletCorrection(models.Model):
    _name = "s2u.warehouse.pallet.correction"
    _description = "Pallet Correction"
    _order = "id desc"

    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
                                 default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one('res.users', string='User', track_visibility='onchange',
                              readonly=True,  default=lambda self: self.env.user)
    entity_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True, index=True)
    entry_date = fields.Date(string='Date', index=True, copy=False, required=True, readonly=True,
                             default=lambda self: fields.Date.context_today(self))
    pallets = fields.Integer(string='qty', required=True)
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Unit', required=True)
    note = fields.Text(string='Note', required=True)


class OutgoingCreateProduction(models.TransientModel):
    _name = 's2u.warehouse.outgoing.create.production'

    @api.model
    def default_get(self, fields):

        rec = super(OutgoingCreateProduction, self).default_get(fields)

        context = self._context
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        outgoing = self.env['s2u.warehouse.outgoing'].browse(active_ids[0])
        rec['project'] = outgoing.project

        lines = []
        for outgoing_id in active_ids:
            lines.append((0, 0, {
                'outgoing_id': outgoing_id
            }))
        rec['line_ids'] = lines

        return rec

    project = fields.Char(string='Project', required=True)
    line_ids = fields.One2many('s2u.warehouse.outgoing.create.production.line', 'create_id', string='Outgoings')

    @api.multi
    def action_production(self):

        self.ensure_one()

        vals = {
            'name': self.project
        }

        lines = []
        for line in self.line_ids:
            for item in line.outgoing_id.todo_ids:
                total_to_produce = item.product_qty + item.shipped_qty - item.assigned_qty
                if total_to_produce <= 0.0:
                    continue
                linevals = {
                    'product_id': item.product_id.id,
                    'product_qty': total_to_produce,
                    'product_detail': item.product_detail,
                    'product_value': item.product_value,
                    'outgoing_id': line.outgoing_id.id
                }
                lines.append((0, 0, linevals))
        vals['line_ids'] = lines

        production = self.env['s2u.warehouse.produced'].create(vals)

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2uwarehouse.action_warehouse_produced')
        list_view_id = imd.xmlid_to_res_id('s2uwarehouse.warehouse_produced_tree')
        form_view_id = imd.xmlid_to_res_id('s2uwarehouse.warehouse_produced_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
            'views': [(form_view_id, 'form')],
            'res_id': production.id
        }

        return result


class OutgoingCreateProductionLine(models.TransientModel):
    _name = 's2u.warehouse.outgoing.create.production.line'

    create_id = fields.Many2one('s2u.warehouse.outgoing.create.production', string='Create', ondelete='set null')
    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string="Outgoing", ondelete='set null')


class OutgoingMergeWith(models.TransientModel):
    _name = 's2u.warehouse.outgoing.merge.with'

    @api.model
    def default_get(self, fields):

        rec = super(OutgoingMergeWith, self).default_get(fields)

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

        outgoing = self.env['s2u.warehouse.outgoing'].browse(outgoing_id)
        if not outgoing.entity_id:
            raise UserError(_("No customer selected! Merge not possible."))

        rec.update({
            'outgoing_id': outgoing_id,
            'entity_id': outgoing.entity_id.id
        })

        return rec

    @api.multi
    def do_merge(self):

        reference = self.merge_with_id.reference
        if reference:
            if self.outgoing_id.reference:
                reference = '%s, %s' % (self.outgoing_id.reference, reference)
            self.outgoing_id.write({
                'reference': reference
            })

        self.env.cr.execute("UPDATE s2u_warehouse_outgoing_todo SET outgoing_id = %s WHERE outgoing_id=%s", (self.outgoing_id.id, self.merge_with_id.id))
        self.env.cr.execute("UPDATE s2u_warehouse_outgoing_assigned_unit SET outgoing_id = %s WHERE outgoing_id=%s", (self.outgoing_id.id, self.merge_with_id.id))
        self.env.cr.execute("UPDATE s2u_warehouse_outgoing_assigned_unit_product SET outgoing_id = %s WHERE outgoing_id=%s", (self.outgoing_id.id, self.merge_with_id.id))
        self.env.cr.execute("UPDATE s2u_warehouse_outgoing_unit SET outgoing_id = %s WHERE outgoing_id=%s", (self.outgoing_id.id, self.merge_with_id.id))
        self.merge_with_id.unlink()

    outgoing_id = fields.Many2one('s2u.warehouse.outgoing', string='Merge with', ondelete='set null')
    merge_with_id = fields.Many2one('s2u.warehouse.outgoing', string='Merge with', ondelete='set null')
    entity_id = fields.Many2one('s2u.crm.entity', string='Customer', ondelete='set null')


class RMALine(models.Model):
    _name = "s2u.warehouse.rma.line"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _description = "RMA line (returning goods from customer)"
    _order = "date_delivery, product_id"

    @api.one
    def _compute_received_qty(self):

        tot_received = 0.0

        for trans in self.rma_id.trans_ids:
            if trans.rma_line_id.id != self.id:
                continue
            trans_product_detail = trans.product_id.product_detail if trans.product_id.product_detail else ''
            self_product_detail = self.product_detail if self.product_detail else ''
            if trans.product_id.product_id == self.product_id and trans_product_detail == self_product_detail:
                tot_received += trans.qty

        self.received_qty = tot_received

    rma_id = fields.Many2one('s2u.warehouse.rma', string='RMA', required=True, index=True,
                             ondelete='cascade')
    date_delivery = fields.Date(string='Expected')
    received_qty = fields.Float(string='Received', compute=_compute_received_qty, readonly=True)
    serialnumber = fields.Char(string='Serial number', index=True)
    todo_id = fields.Many2one('s2u.warehouse.outgoing.todo', string='Outgoing', required=True, index=True,
                              ondelete='cascade')
    sn_registration = fields.Boolean(string='Product registration', related='product_id.sn_registration', readonly=True)
    account_po_id = fields.Many2one('s2u.account.account', string='Account PO', domain=[('type', '=', 'expense')])
    account_stock_id = fields.Many2one('s2u.account.account', string='Account Stock', domain=[('type', '=', 'stock')])


class RMANotUsable(models.Model):
    _name = "s2u.warehouse.rma.notusable"
    _inherit = "s2u.baseproduct.transaction.abstract"
    _description = "RMA not usable (returning goods from customer not usable)"

    rma_line_id = fields.Many2one('s2u.warehouse.rma.line', string='RMA Line', required=True, index=True,
                                  ondelete='cascade')
    rma_id = fields.Many2one('s2u.warehouse.rma', string='RMA', related='rma_line_id.rma_id', store=True)
    notusable_qty = fields.Float(string='Not usable', required=True)
    serialnumber = fields.Char(string='Serial number')
    transaction_date = fields.Date(string='Date', index=True, copy=False, required=True,
                                   default=lambda self: fields.Date.context_today(self))


class RMA(models.Model):
    _name = "s2u.warehouse.rma"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "RMA"
    _order = "date_rma desc, name"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(RMA, self)._track_subtype(init_values)

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.warehouse.rma')])
        if not exists:
            raise ValueError(_('Sequence for creating s2u.warehouse.rma number not exists!'))

        sequence = exists[0]
        new_number = sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()
        if self.env.user.name:
            name = self.env.user.name.split(' ')
            initials = ''
            for n in name:
                initials = '%s%s' % (initials, n[0].upper())
            new_number = '%s/%s' % (new_number, initials)
        return new_number

    @api.one
    @api.depends('line_ids.date_delivery', 'state')
    def _compute_date_delivery(self):
        dl = False
        if self.state in ['draft', 'wait']:
            for delivery in self.line_ids:
                if not delivery.date_delivery:
                    continue
                if not dl or delivery.date_delivery < dl:
                    dl = delivery.date_delivery
        self.date_delivery = dl

    @api.model
    def _default_warehouse(self):

        return self.env['s2u.warehouse'].search([('default', '=', True)])

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.multi
    @api.constrains('type', 'entity_id', 'contact_id', 'address_id')
    def _check_address_entity(self):
        for rma in self:
            if rma.type == 'b2b':
                if rma.entity_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b customer!'))
                if rma.contact_id and rma.contact_id.entity_id != rma.entity_id:
                    raise ValueError(_('Contact does not belong to the selected customer!'))
                if rma.address_id and rma.address_id.entity_id != rma.entity_id:
                    raise ValueError(_('Address does not belong to the selected customer!'))
            else:
                if rma.entity_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c customer!'))

    _rma_state = {
        'draft': [('readonly', False)],
    }

    _rma_wait_state = {
        'draft': [('readonly', False)],
        'wait': [('readonly', False)],
    }

    name = fields.Char(string='RMA', required=True, index=True, copy=False,
                       default=_new_number, readonly=True, states=_rma_state)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_rma_state)
    entity_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True, index=True,
                                readonly=True, states=_rma_state)
    partner_id = fields.Many2one('s2u.crm.entity', string='Customer', related='entity_id')
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True,
                                 readonly=True, states=_rma_wait_state)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True, readonly=True,
                                 states=_rma_wait_state)
    line_ids = fields.One2many('s2u.warehouse.rma.line', 'rma_id',
                               string='Expected', copy=True, readonly=True, states=_rma_wait_state)
    date_delivery = fields.Date(string='Expected', compute=_compute_date_delivery, store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('wait', 'Wait for goods'),
        ('done', 'Done')
    ], required=True, default='draft', string='State', copy=False, track_visibility='onchange')
    trans_ids = fields.One2many('s2u.warehouse.unit.product.transaction', 'rma_id',
                                string='Transactions', copy=False, readonly=True)
    reference = fields.Char(string='Reference', index=True, copy=False, readonly=True, states=_rma_wait_state)
    warehouse_id = fields.Many2one('s2u.warehouse', string='Warehouse', required=True, index=True,
                                   readonly=True, states=_rma_state, default=_default_warehouse)
    notusable_ids = fields.One2many('s2u.warehouse.rma.notusable', 'rma_id',
                                    string='Not usable', copy=False, readonly=True)
    date_rma = fields.Date(string='RMA Date', index=True, copy=False,
                           default=lambda self: fields.Date.context_today(self), required=True)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_rma_wait_state)

    @api.multi
    def do_confirm(self):

        self.ensure_one()

        self.write({
            'state': 'wait'
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
        self.notusable_ids.unlink()

        self.write({
            'state': 'draft'
        })

    @api.multi
    def do_done(self):

        self.ensure_one()

        self.write({
            'state': 'done'
        })

    @api.multi
    def undo_done(self):

        self.ensure_one()

        self.write({
            'state': 'wait'
        })

    @api.multi
    def unlink(self):

        for shipment in self:
            if shipment.state == 'done':
                raise ValidationError(_('You can not delete a closed shipment!'))

            for trans in shipment.trans_ids:
                trans.product_id.write({
                    'product_qty': trans.product_id.product_qty - trans.qty
                })
                trans.product_id.unit_id.empty_unit(write=True)

        res = super(RMA, self).unlink()

        return res

    @api.multi
    def do_receive_goods(self):

        self.ensure_one()

        trans_model = self.env['s2u.warehouse.unit.product.transaction']

        lines = []
        po_products = self.env['s2u.warehouse.rma.line'].search([('rma_id', '=', self.id)])
        for p in po_products:
            tot_received = 0.0

            transactions = trans_model.search([('rma_id', '=', self.id)])
            for trans in transactions:
                if trans.product_id.product_id.id == p.product_id.id and trans.product_id.product_detail == p.product_detail:
                    tot_received += trans.qty

            lines.append({
                'line_id': p.id,
                'product_id': p.product_id.id,
                'product_value': p.product_value,
                'serialnumber': p.serialnumber,
                'product_detail': p.product_detail,
                'qty_open': p.product_qty - tot_received
            })

        trans_vals = {
            'rma_id': self.id,
        }

        location = self.env['s2u.warehouse.location'].search([('usage', '=', 'incoming')], limit=1)
        if location:
            trans_vals['location_id'] = location.id
        else:
            raise ValidationError(_('Please define incoming location for warehouse!'))

        trans = self.env['s2u.warehouse.rma.add'].create(trans_vals)
        for line in lines:
            line['add_id'] = trans.id
            self.env['s2u.warehouse.rma.add.item'].create(line)

        action = self.env.ref('s2uwarehouse.action_warehouse_rma_transaction').read()[0]
        action['target'] = 'new'
        action['views'] = [(self.env.ref('s2uwarehouse.view_warehouse_rma_transaction').id, 'form')]
        action['res_id'] = trans.id
        return action


class RMAAddTransaction(models.TransientModel):
    _name = 's2u.warehouse.rma.add'

    @api.multi
    def do_add(self):

        unit_model = self.env['s2u.warehouse.unit']
        product_model = self.env['s2u.warehouse.unit.product']
        trans_model = self.env['s2u.warehouse.unit.product.transaction']
        notusable_model = self.env['s2u.warehouse.rma.notusable']

        if self.rma_id.state == 'draft':
            raise ValidationError(_('Please confirm this RMA shipment first, before receiving goods!'))

        if self.rma_id.state != 'wait':
            raise ValidationError(_('This RMA is closed, you can not receive goods for it!'))

        notusable_location = self.env['s2u.warehouse.location'].search([('usage', '=', 'not')], limit=1)

        if self.pallets:
            # we receive the items on pallets
            total_qty = 0.0
            for item in self.line_ids:
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
                        'type': 'pallet',
                        'pallet_id': self.pallet_id.id,
                        'pallet_factor': self.pallet_factor,
                        'location_id': self.location_id.id
                    })

                    count_unit = True
                    for item in self.line_ids:
                        parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                        if parsed_qty[2]:
                            # we hebben te maken met een verpakking op de pallet
                            if parsed_qty[0]:
                                for box_no in range(parsed_qty[0]):
                                    box = unit_model.create({
                                        'type': 'box',
                                        'location_id': self.location_id.id,
                                        'parent_id': unit.id
                                    })
                                    if item.product_id.sn_registration:
                                        for i in range(int(parsed_qty[2])):
                                            vals = {
                                                'unit_id': box.id,
                                                'product_id': item.product_id.id,
                                                'product_qty': 1.0,
                                                'product_value': item.product_value,
                                                'product_detail': item.product_detail,
                                                'serialnumber': item.serialnumber,
                                                'sn_registration': True
                                            }
                                            product = product_model.create(vals)

                                            vals = {
                                                'unit_id': box.id,
                                                'parent_id': unit.id,
                                                'location_id': box.location_id.id,
                                                'product_id': product.id,
                                                'qty': 1.0,
                                                'transaction_date': self.transaction_date,
                                                'source_model': 's2u.warehouse.rma',
                                                'source_id': self.rma_id.id,
                                                'rma_id': self.rma_id.id,
                                                'entity_id': self.rma_id.entity_id.id,
                                                'rma_line_id': item.line_id.id,
                                                'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                                'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                                'amount_po_stock': -1.0 * item.line_id.product_value
                                            }
                                            trans = trans_model.create(vals)
                                            trans.financial_stock_on_rma(product, 1.0, item.product_usable, rmaline=item.line_id)

                                            if item.product_usable == 'no':
                                                notusable = notusable_model.create({
                                                    'rma_line_id': item.line_id.id,
                                                    'product_id': item.product_id.id,
                                                    'product_qty': 1.0,
                                                    'notusable_qty': 1.0,
                                                    'product_value': item.product_value,
                                                    'product_detail': item.product_detail,
                                                    'serialnumber': item.serialnumber
                                                })
                                                if not notusable_location:
                                                    raise UserError(_("Please define a location for type \'Not usable\'!"))
                                                vals = {
                                                    'unit_id': box.id,
                                                    'parent_id': unit.id,
                                                    'location_id': notusable_location.id,
                                                    'product_id': product.id,
                                                    'qty': -1.0,
                                                    'transaction_date': self.transaction_date,
                                                    'source_model': 's2u.warehouse.rma',
                                                    'source_id': self.rma_id.id,
                                                    'rma_id': self.rma_id.id,
                                                    'rma_notusable_id': notusable.id
                                                }
                                                trans_model.create(vals)
                                    else:
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
                                            'source_model': 's2u.warehouse.rma',
                                            'source_id': self.rma_id.id,
                                            'rma_id': self.rma_id.id,
                                            'entity_id': self.rma_id.entity_id.id,
                                            'rma_line_id': item.line_id.id,
                                            'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                            'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                            'amount_po_stock': -1.0 * parsed_qty[2] * item.line_id.product_value
                                        }
                                        trans = trans_model.create(vals)
                                        trans.financial_stock_on_rma(product, parsed_qty[2], item.product_usable, rmaline=item.line_id)

                                        if item.product_usable == 'no':
                                            notusable = notusable_model.create({
                                                'rma_line_id': item.line_id.id,
                                                'product_id': item.product_id.id,
                                                'product_qty': parsed_qty[2],
                                                'notusable_qty': parsed_qty[2],
                                                'product_value': item.product_value,
                                                'product_detail': item.product_detail
                                            })
                                            if not notusable_location:
                                                raise UserError(_("Please define a location for type \'Not usable\'!"))
                                            vals = {
                                                'unit_id': box.id,
                                                'parent_id': unit.id,
                                                'location_id': notusable_location.id,
                                                'product_id': product.id,
                                                'qty': -1.0 * parsed_qty[2],
                                                'transaction_date': self.transaction_date,
                                                'source_model': 's2u.warehouse.rma',
                                                'source_id': self.rma_id.id,
                                                'rma_id': self.rma_id.id,
                                                'rma_notusable_id': notusable.id
                                            }
                                            trans_model.create(vals)
                            else:
                                if item.product_id.sn_registration:
                                    for i in range(int(parsed_qty[2])):
                                        vals = {
                                            'unit_id': unit.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': 1.0,
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail,
                                            'serialnumber': item.serialnumber,
                                            'sn_registration': True
                                        }
                                        product = product_model.create(vals)

                                        vals = {
                                            'product_id': product.id,
                                            'unit_id': unit.id,
                                            'location_id': unit.location_id.id,
                                            'qty': 1.0,
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.rma',
                                            'source_id': self.rma_id.id,
                                            'rma_id': self.rma_id.id,
                                            'entity_id': self.rma_id.entity_id.id,
                                            'rma_line_id': item.line_id.id,
                                            'count_unit': count_unit,
                                            'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                            'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                            'amount_po_stock': -1.0 * item.line_id.product_value
                                        }
                                        trans = trans_model.create(vals)
                                        trans.financial_stock_on_rma(product, 1.0, item.product_usable,
                                                                     rmaline=item.line_id)
                                        count_unit = False

                                        if item.product_usable == 'no':
                                            notusable = notusable_model.create({
                                                'rma_line_id': item.line_id.id,
                                                'product_id': item.product_id.id,
                                                'product_qty': 1.0,
                                                'notusable_qty': 1.0,
                                                'product_value': item.product_value,
                                                'product_detail': item.product_detail,
                                                'serialnumber': item.serialnumber
                                            })
                                            if not notusable_location:
                                                raise UserError(_("Please define a location for type \'Not usable\'!"))
                                            vals = {
                                                'unit_id': box.id,
                                                'parent_id': unit.id,
                                                'location_id': notusable_location.id,
                                                'product_id': product.id,
                                                'qty': -1.0,
                                                'transaction_date': self.transaction_date,
                                                'source_model': 's2u.warehouse.rma',
                                                'source_id': self.rma_id.id,
                                                'rma_id': self.rma_id.id,
                                                'rma_notusable_id': notusable.id
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
                                        'source_model': 's2u.warehouse.rma',
                                        'source_id': self.rma_id.id,
                                        'rma_id': self.rma_id.id,
                                        'entity_id': self.rma_id.entity_id.id,
                                        'rma_line_id': item.line_id.id,
                                        'count_unit': count_unit,
                                        'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                        'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                        'amount_po_stock': -1.0 * parsed_qty[2] * item.line_id.product_value
                                    }
                                    trans = trans_model.create(vals)
                                    trans.financial_stock_on_rma(product, parsed_qty[2], item.product_usable,
                                                                 rmaline=item.line_id)
                                    count_unit = False

                                    if item.product_usable == 'no':
                                        notusable = notusable_model.create({
                                            'rma_line_id': item.line_id.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': parsed_qty[2],
                                            'notusable_qty': parsed_qty[2],
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail,
                                            'serialnumber': item.serialnumber
                                        })
                                        if not notusable_location:
                                            raise UserError(_("Please define a location for type \'Not usable\'!"))
                                        vals = {
                                            'unit_id': box.id,
                                            'parent_id': unit.id,
                                            'location_id': notusable_location.id,
                                            'product_id': product.id,
                                            'qty': -1.0 * parsed_qty[2],
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.rma',
                                            'source_id': self.rma_id.id,
                                            'entity_id': self.rma_id.entity_id.id,
                                            'rma_notusable_id': notusable.id
                                        }
                                        trans_model.create(vals)
        else:
            # we receive the items without a placeholder
            total_qty = 0.0
            for item in self.line_ids:
                parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                if not parsed_qty:
                    raise ValidationError(_("Please enter a valid value for 'Qty'!"))
                if parsed_qty[0]:
                    total_qty += (float(parsed_qty[0]) * parsed_qty[2])
                else:
                    total_qty += parsed_qty[2]

            if total_qty > 0.0:
                unit = unit_model.create({
                    'type': 'singleton',
                    'location_id': self.location_id.id
                })
                count_unit = True
                for item in self.line_ids:
                    parsed_qty = self.env['s2u.warehouse.uom'].parse_qty(item.qty_received)
                    if parsed_qty[2]:
                        # we hebben te maken met een verpakking
                        if parsed_qty[0]:
                            for box_no in range(parsed_qty[0]):
                                box = unit_model.create({
                                    'type': 'box',
                                    'location_id': self.location_id.id,
                                    'parent_id': unit.id
                                })

                                if item.product_id.sn_registration:
                                    for i in range(int(parsed_qty[2])):
                                        vals = {
                                            'unit_id': box.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': 1.0,
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail,
                                            'serialnumber': item.serialnumber,
                                            'sn_registration': True
                                        }
                                        product = product_model.create(vals)

                                        vals = {
                                            'product_id': product.id,
                                            'unit_id': box.id,
                                            'parent_id': unit.id,
                                            'location_id': box.location_id.id,
                                            'qty': 1.0,
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.rma',
                                            'source_id': self.rma_id.id,
                                            'rma_id': self.rma_id.id,
                                            'entity_id': self.rma_id.entity_id.id,
                                            'rma_line_id': item.line_id.id,
                                            'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                            'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                            'amount_po_stock': -1.0 * item.line_id.product_value
                                        }
                                        trans = trans_model.create(vals)
                                        trans.financial_stock_on_rma(product, 1.0, item.product_usable,
                                                                     rmaline=item.line_id)

                                        if item.product_usable == 'no':
                                            notusable = notusable_model.create({
                                                'rma_line_id': item.line_id.id,
                                                'product_id': item.product_id.id,
                                                'product_qty': 1.0,
                                                'notusable_qty': 1.0,
                                                'product_value': item.product_value,
                                                'product_detail': item.product_detail,
                                                'serialnumber': item.serialnumber
                                            })
                                            if not notusable_location:
                                                raise UserError(_("Please define a location for type \'Not usable\'!"))
                                            vals = {
                                                'unit_id': box.id,
                                                'parent_id': unit.id,
                                                'location_id': notusable_location.id,
                                                'product_id': product.id,
                                                'qty': -1.0,
                                                'transaction_date': self.transaction_date,
                                                'source_model': 's2u.warehouse.rma',
                                                'source_id': self.rma_id.id,
                                                'rma_id': self.rma_id.id,
                                                'rma_notusable_id': notusable.id
                                            }
                                            trans_model.create(vals)
                                else:
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
                                        'source_model': 's2u.warehouse.rma',
                                        'source_id': self.rma_id.id,
                                        'rma_id': self.rma_id.id,
                                        'entity_id': self.rma_id.entity_id.id,
                                        'rma_line_id': item.line_id.id,
                                        'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                        'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                        'amount_po_stock': -1.0 * parsed_qty[2] * item.line_id.product_value
                                    }
                                    trans = trans_model.create(vals)
                                    trans.financial_stock_on_rma(product, parsed_qty[2], item.product_usable,
                                                                 rmaline=item.line_id)

                                    if item.product_usable == 'no':
                                        notusable = notusable_model.create({
                                            'rma_line_id': item.line_id.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': parsed_qty[2],
                                            'notusable_qty': parsed_qty[2],
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail,
                                            'serialnumber': item.serialnumber
                                        })
                                        if not notusable_location:
                                            raise UserError(_("Please define a location for type \'Not usable\'!"))
                                        vals = {
                                            'unit_id': box.id,
                                            'parent_id': unit.id,
                                            'location_id': notusable_location.id,
                                            'product_id': product.id,
                                            'qty': -1.0 * parsed_qty[2],
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.rma',
                                            'source_id': self.rma_id.id,
                                            'rma_id': self.rma_id.id,
                                            'rma_notusable_id': notusable.id
                                        }
                                        trans_model.create(vals)
                        else:
                            if item.product_id.sn_registration:
                                for i in range(int(parsed_qty[2])):
                                    vals = {
                                        'unit_id': unit.id,
                                        'product_id': item.product_id.id,
                                        'product_qty': 1.0,
                                        'product_value': item.product_value,
                                        'product_detail': item.product_detail,
                                        'serialnumber': item.serialnumber,
                                        'sn_registration': True
                                    }
                                    product = product_model.create(vals)

                                    vals = {
                                        'product_id': product.id,
                                        'unit_id': unit.id,
                                        'location_id': unit.location_id.id,
                                        'qty': 1.0,
                                        'transaction_date': self.transaction_date,
                                        'source_model': 's2u.warehouse.rma',
                                        'source_id': self.rma_id.id,
                                        'rma_id': self.rma_id.id,
                                        'entity_id': self.rma_id.entity_id.id,
                                        'rma_line_id': item.line_id.id,
                                        'count_unit': count_unit,
                                        'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                        'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                        'amount_po_stock': -1.0 * item.line_id.product_value
                                    }
                                    trans = trans_model.create(vals)
                                    trans.financial_stock_on_rma(product, 1.0, item.product_usable,
                                                                 rmaline=item.line_id)
                                    count_unit = False

                                    if item.product_usable == 'no':
                                        notusable = notusable_model.create({
                                            'rma_line_id': item.line_id.id,
                                            'product_id': item.product_id.id,
                                            'product_qty': 1.0,
                                            'notusable_qty': 1.0,
                                            'product_value': item.product_value,
                                            'product_detail': item.product_detail,
                                            'serialnumber': item.serialnumber
                                        })
                                        if not notusable_location:
                                            raise UserError(_("Please define a location for type \'Not usable\'!"))
                                        vals = {
                                            'unit_id': unit.id,
                                            'location_id': notusable_location.id,
                                            'product_id': product.id,
                                            'qty': -1.0,
                                            'transaction_date': self.transaction_date,
                                            'source_model': 's2u.warehouse.rma',
                                            'source_id': self.rma_id.id,
                                            'rma_id': self.rma_id.id,
                                            'rma_notusable_id': notusable.id
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
                                    'source_model': 's2u.warehouse.rma',
                                    'source_id': self.rma_id.id,
                                    'rma_id': self.rma_id.id,
                                    'entity_id': self.rma_id.entity_id.id,
                                    'rma_line_id': item.line_id.id,
                                    'count_unit': count_unit,
                                    'account_po_id': item.line_id.account_po_id.id if item.line_id.account_po_id else False,
                                    'account_stock_id': item.line_id.account_stock_id.id if item.line_id.account_stock_id else False,
                                    'amount_po_stock': -1.0 * parsed_qty[2] * item.line_id.product_value
                                }
                                trans = trans_model.create(vals)
                                trans.financial_stock_on_rma(product, parsed_qty[2], item.product_usable,
                                                             rmaline=item.line_id)
                                count_unit = False

                                if item.product_usable == 'no':
                                    notusable = notusable_model.create({
                                        'rma_line_id': item.line_id.id,
                                        'product_id': item.product_id.id,
                                        'product_qty': parsed_qty[2],
                                        'notusable_qty': parsed_qty[2],
                                        'product_value': item.product_value,
                                        'product_detail': item.product_detail,
                                        'serialnumber': item.serialnumber
                                    })
                                    if not notusable_location:
                                        raise UserError(_("Please define a location for type \'Not usable\'!"))
                                    vals = {
                                        'unit_id': unit.id,
                                        'location_id': notusable_location.id,
                                        'product_id': product.id,
                                        'qty': -1.0 * parsed_qty[2],
                                        'transaction_date': self.transaction_date,
                                        'source_model': 's2u.warehouse.rma',
                                        'source_id': self.rma_id.id,
                                        'rma_id': self.rma_id.id,
                                        'rma_notusable_id': notusable.id
                                    }
                                    trans_model.create(vals)

    rma_id = fields.Many2one('s2u.warehouse.rma', string='RMA')
    pallets = fields.Integer(string='Units', requird=True)
    pallet_id = fields.Many2one('s2u.warehouse.pallet', string='Unit')
    pallet_factor = fields.Integer(string='Unit factor', default=1, requird=True)
    line_ids = fields.One2many('s2u.warehouse.rma.add.item', 'add_id', string='Lines')
    location_id = fields.Many2one('s2u.warehouse.location', string='Location', required=True)
    transaction_date = fields.Date(string='Date', copy=False, required=True,
                                   default=lambda self: fields.Date.context_today(self))


class RMAAddTransactionItem(models.TransientModel):
    _name = 's2u.warehouse.rma.add.item'
    _inherit = "s2u.baseproduct.transaction.abstract"

    add_id = fields.Many2one('s2u.warehouse.rma.add', string='Pallet', required=True, ondelete='cascade')
    line_id = fields.Many2one('s2u.warehouse.rma.line', string='RMA line', ondelete='set null')
    qty_received = fields.Char(string='Qty received', default=0.0)
    qty_open = fields.Float(string='Qty open')
    product_qty = fields.Float(required=False, default=1.0)
    product_usable = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string='Usable')
    serialnumber = fields.Char(string='Serialnumber')
    sn_registration = fields.Boolean(string='Product registration', related='product_id.sn_registration', readonly=True)

    @api.one
    @api.constrains('qty_received')
    def _check_qty_received(self):
        if not self.qty_received:
            raise ValidationError("Please enter value for 'Qty'.")
        if not self.env['s2u.warehouse.uom'].parse_qty(self.qty_received):
            raise ValidationError("Invalid value for 'Qty'.")
