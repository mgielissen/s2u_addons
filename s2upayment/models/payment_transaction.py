# -*- coding: utf-8 -*-

import random
from datetime import datetime, timedelta

from odoo.http import request
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import api, fields, models, _

def random_token():
    # the token has an entropy of about 120 bits (6 bits/char * 20 chars)
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.SystemRandom().choice(chars) for i in xrange(20))

def now(**kwargs):
    dt = datetime.now() + timedelta(**kwargs)
    return dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)

class PaymentTransaction(models.Model):
    _name = 's2u.payment.transaction'
    _description = 'Payment Transaction'
    _order = 'id desc'

    @api.multi
    def start_transaction(self, acquirer, checkout_data, shoppingcart):

        shipment_costs = self.get_shipment_costs(checkout_data, shoppingcart)
        vals = {
            'name': random_token(),
            'reference': self._new_reference(acquirer.company_id.id),
            'trans_expiration': now(minutes=+5),
            'acquirer_id': acquirer.id,
            'company_id': acquirer.company_id.id,
            'currency_id': acquirer.company_id.currency_id.id,
            'tot_amount': self.get_total_amount(shoppingcart),
            'tot_costs': shipment_costs.price if shipment_costs else 0.0,
            'porto_product_id': shipment_costs.id if shipment_costs else False,
            'checkout_order_type': checkout_data.get('order_type', False),
            'checkout_company': checkout_data.get('company', False),
            'checkout_c_of_c': checkout_data.get('c_of_c', False),
            'checkout_tinno': checkout_data.get('tinno', False),
            'checkout_contact_prefix': checkout_data.get('contact_prefix', False),
            'checkout_name': checkout_data.get('name', False),
            'checkout_address': checkout_data.get('address', False),
            'checkout_zip': checkout_data.get('zip', False),
            'checkout_city': checkout_data.get('city', False),
            'checkout_country_id': checkout_data.get('country_id', False),
            'checkout_email': checkout_data.get('email', False),
            'checkout_phone': checkout_data.get('phone', False),
            'checkout_delivery_type': checkout_data.get('delivery_type', False),
            'checkout_order_delivery_type': checkout_data.get('order_delivery_type', False),
            'checkout_delivery_company': checkout_data.get('delivery_company', False),
            'checkout_delivery_name': checkout_data.get('delivery_name', False),
            'checkout_delivery_address': checkout_data.get('delivery_address', False),
            'checkout_delivery_zip': checkout_data.get('delivery_zip', False),
            'checkout_delivery_city': checkout_data.get('delivery_city', False),
            'checkout_delivery_country_id': checkout_data.get('delivery_country_id', False),
            'checkout_delivery_tinno': checkout_data.get('delivery_tinno', False),
        }

        transaction = self.sudo().create(vals)
        for item in shoppingcart:
            self.env['s2u.payment.transaction.item'].sudo().create({
                'trans_id': transaction.id,
                'product_id': item['product_id'],
                'product_model': item['product_model'],
                'product_name': item['product'],
                'qty': item['qty']
            })

        return transaction

    @api.multi
    def get_total_amount(self, shoppingcart):

        if not shoppingcart:
            return 0.0

        total_amount = 0.0
        for item in shoppingcart:
            total_amount += float(item['qty']) * float(item['price'])
        return total_amount

    @api.multi
    def get_shipment_costs(self, checkout_data, shoppingcart):

        if not checkout_data:
            return False

        if not shoppingcart:
            return False

        if checkout_data.get('delivery_different', 'False') == 'True':
            country_id = checkout_data.get('delivery_country_id', False)
        else:
            country_id = checkout_data.get('country_id', False)

        if not country_id:
            return False

        total_weight = 0.0
        for item in shoppingcart:
            total_weight += float(item['qty']) * float(item['weight'])

        costs_model = self.env['s2u.sale.country.portocosts']
        domain = [('country_id', '=', country_id),
                  ('weight', '>=', total_weight)]
        costs = costs_model.sudo().search(domain, limit=1)
        if not costs:
            return False
        return costs

    @api.one
    @api.depends('trans_expiration')
    def _transaction_valid(self):
        dt = now()
        if self.state != 'draft':
            self.is_valid = False
        if not self.trans_expiration:
            self.is_valid = False
        if dt > self.trans_expiration:
            self.is_valid = False

        self.is_valid = True

    @api.model
    def _new_reference(self, company_id):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', company_id),
                                                        ('code', '=', 's2u.payment.transaction')])
        if not exists:
            raise ValueError(_('Sequence for creating payment reference not exists!'))

        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.one
    @api.depends('tot_amount', 'tot_costs')
    def _compute_tot_to_pay(self):
        try:
            self.tot_to_pay = self.tot_amount + self.tot_costs
        except:
            self.tot_to_pay = 0.0

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id)
    acquirer_id = fields.Many2one('s2u.payment.acquirer', string='Acquirer', required=True)
    name = fields.Char(required=True, index=True, string='Trans ID', copy=False)
    trans_expiration = fields.Datetime(string='Expiration', copy=False)
    state = fields.Selection([('draft', 'Concept'),
                              ('done', 'Done'),
                              ('cancel', 'Cancel'),
                              ('error', 'Error'),
                              ('expired', 'Expired')], string='State', required=True, default='draft')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    tot_amount = fields.Monetary(string='Amount', currency_field='currency_id')
    tot_costs = fields.Monetary(string='Costs', currency_field='currency_id')
    tot_to_pay = fields.Monetary(string='To pay', currency_field='currency_id',
                                 store=True, readonly=True, compute='_compute_tot_to_pay')
    is_valid = fields.Boolean(string='Trans valid', compute=_transaction_valid)
    is_paid = fields.Boolean(string='Paid', default=False)
    reference = fields.Char(string='Reference', index=True, copy=False)
    checkout_order_type = fields.Char(string='Order type')
    checkout_company = fields.Char(string='Company')
    checkout_c_of_c = fields.Char(string='KvK Nr.')
    checkout_tinno = fields.Char(string='BTW Nr.')
    checkout_contact_prefix = fields.Char(string='Prefix')
    checkout_name = fields.Char(string='Name')
    checkout_address = fields.Char(string='Address')
    checkout_zip = fields.Char(string='ZIP')
    checkout_city = fields.Char(string='City')
    checkout_country_id = fields.Many2one('s2u.sale.country', string='Country')
    checkout_email = fields.Char(string='eMail')
    checkout_phone = fields.Char(string='Phone')
    checkout_delivery_type = fields.Char(string='Delivery type')
    checkout_order_delivery_type = fields.Char(string='Order delivery type')
    checkout_delivery_company = fields.Char(string='Company')
    checkout_delivery_name = fields.Char(string='Name')
    checkout_delivery_address = fields.Char(string='Address')
    checkout_delivery_zip = fields.Char(string='ZIP')
    checkout_delivery_city = fields.Char(string='City')
    checkout_delivery_country_id = fields.Many2one('s2u.sale.country', string='Country')
    checkout_delivery_tinno = fields.Char(string='BTW Nr.')
    item_ids = fields.One2many('s2u.payment.transaction.item', 'trans_id',
                               string='Items', copy=False)
    sale_id = fields.Many2one('s2u.sale', string='SO', index=True,
                              ondelete='restrict')
    porto_product_id = fields.Many2one('s2u.sale.country.portocosts', string='Porto', ondelete='set null')

    @api.multi
    def do_order_confirmation(self, method, sale, default_vals=None):

        self.ensure_one()
        return True

    @api.multi
    def confirm_transaction(self, method='manual', default_vals=None):

        self.ensure_one()

        # make sure we write the transaction correct,
        # in case something goes wrong, we do have the info of the completed transaction with the used acquirer
        vals = {
            'state': 'done'
        }
        if default_vals:
            vals.update(default_vals)
        self.write(vals)
        self._cr.commit()

        entity = False
        if request.env.user != request.website.user_id:
            entity = self.env['s2u.crm.entity'].sudo(). \
                search([('odoo_res_partner_id', '=', request.env.user.partner_id.id)], limit=1)

        if self.checkout_order_type == 'b2c':
            entity_vals = {
                'company_id': request.website.company_id.id,
                'type': 'b2c',
                'prefix': self.checkout_contact_prefix,
                'name': self.checkout_name,
                'phone': self.checkout_phone,
                'email': self.checkout_email,
                'address': self.checkout_address,
                'zip': self.checkout_zip,
                'city': self.checkout_city,
                'country_id': self.checkout_country_id.country_id.id if self.checkout_country_id else False
            }
            if entity:
                entity.sudo().write(entity_vals)
            else:
                if request.env.user != request.website.user_id:
                    entity_vals['odoo_res_partner_id'] = request.env.user.partner_id.id
                entity = self.env['s2u.crm.entity'].sudo().create(entity_vals)
            contact = False
            address = False
        else:
            entity_vals = {
                'company_id': request.website.company_id.id,
                'type': 'b2b',
                'name': self.checkout_company,
                'tinno': self.checkout_tinno,
                'phone': self.checkout_phone,
                'email': self.checkout_email,
                'c_of_c': self.checkout_c_of_c
            }
            if entity:
                entity.sudo().write(entity_vals)
            else:
                if request.env.user != request.website.user_id:
                    entity_vals['odoo_res_partner_id'] = request.env.user.partner_id.id
                entity = self.env['s2u.crm.entity'].sudo().create(entity_vals)

            address_vals = {
                'company_id': request.website.company_id.id,
                'entity_id': entity.id,
                'type': 'def',
                'address': self.checkout_address,
                'zip': self.checkout_zip,
                'city': self.checkout_city,
                'country_id': self.checkout_country_id.country_id.id if self.checkout_country_id else False
            }
            address = self.env['s2u.crm.entity.address'].sudo().search([('company_id', '=', request.website.company_id.id),
                                                                        ('entity_id', '=', entity.id),
                                                                        ('type', '=', 'def')], limit=1)
            if address:
                address.sudo().write(address_vals)
            else:
                address = self.env['s2u.crm.entity.address'].sudo().create(address_vals)

            if self.checkout_name:
                contact_vals = {
                    'company_id': request.website.company_id.id,
                    'entity_id': entity.id,
                    'name': self.checkout_name
                }
                contact = self.env['s2u.crm.entity.contact'].sudo().search(
                    [('company_id', '=', request.website.company_id.id),
                     ('entity_id', '=', entity.id),
                     ('name', '=', self.checkout_name)], limit=1)
                if not contact:
                    contact = self.env['s2u.crm.entity.contact'].sudo().create(contact_vals)
            else:
                contact = False

        if self.checkout_delivery_type == 'different':
            address = self.checkout_delivery_name
            address = '%s\n%s' % (address, self.checkout_delivery_address)
            if self.checkout_delivery_zip and self.checkout_delivery_city:
                address = '%s\n%s  %s' % (address, self.checkout_delivery_zip, self.checkout_delivery_city)
            elif self.checkout_delivery_zip:
                address = '%s\n%s' % (address, self.checkout_delivery_zip)
            elif self.checkout_delivery_city:
                address = '%s\n%s' % (address, self.checkout_delivery_city)
            if self.delivery_country_id:
                address = '%s\n%s' % (address, self.delivery_country_id.name)
            delivery_vals = {
                'company_id': self.company_id.id,
                'entity_id': entity.id,
                'delivery_country_id': self.checkout_delivery_country_id.country_id.id if self.checkout_delivery_country_id else False,
                'delivery_tinno': self.checkout_delivery_tinno,
                'delivery_address': address
            }
            delivery = self.env['s2u.crm.entity.delivery'].sudo().search(
                [('company_id', '=', request.website.company_id.id),
                 ('entity_id', '=', entity.id),
                 ('delivery_address', '=', address)], limit=1)
            if delivery:
                delivery.sudo().write(delivery_vals)
            else:
                delivery = self.env['s2u.crm.entity.delivery'].sudo().create(delivery_vals)
            delivery_country_id = entity.country_id.id if delivery.country_id else False
            delivery_address = address
        else:
            delivery_address = entity.prepare_delivery()
            delivery = False
            delivery_country_id = entity.country_id.id if entity.country_id else False

        vals = {
            'company_id': self.company_id.id,
            'type': entity.type,
            'partner_id': entity.id,
            'contact_id': contact.id if contact else False,
            'address_id': address.id if address else False,
            'invoice_type': entity.type,
            'invoice_partner_id': entity.id,
            'invoice_contact_id': contact.id if contact else False,
            'invoice_address_id': address.id if address else False,
            'delivery_type': entity.type,
            'delivery_partner_id': entity.id,
            'delivery_contact_id': contact.id if contact else False,
            'delivery_delivery_id': delivery.id if delivery else False,
            'delivery_address': delivery_address,
            'delivery_country_id': delivery_country_id,
            'delivery_tinno': delivery.delivery_tinno if delivery and delivery.delivery_tinno else False,
            'reference': self.reference,
            'project': _('Order over website'),
            'invoicing': 'confirm',
            'chance': 'high',
            'template_id': self.acquirer_id.so_template_id.id if self.acquirer_id.so_template_id else False
        }
        sale = self.env['s2u.sale'].sudo().create(vals)

        for item in self.item_ids:

            baseproduct = self.env['s2u.baseproduct.item'].sudo().search([('company_id', '=', self.company_id.id),
                                                                          ('res_model', '=', item.product_model),
                                                                          ('res_id', '=', item.product_id)], limit=1)
            if not baseproduct:
                raise ValueError(_('Base product not found in database! Please contact customer services to help you out.'))

            product = self.env[item.product_model].sudo().browse(item.product_id)
            if not product:
                raise ValueError(_('Product not found in database! Please contact customer services to help you out.'))

            sale_line = {
                'sale_id': sale.id,
                'product_id': baseproduct.id,
            }
            sale_line = self.env['s2u.sale.line'].sudo().create(sale_line)

            price = product.get_product_price(item.qty, False)
            qty_line = {
                'saleline_id': sale_line.id,
                'qty': str(item.qty),
                'price': price['price'],
                'price_per': price['price_per'],
                'price_is_net': price.get('price_is_net', True)
            }
            self.env['s2u.sale.line.qty'].sudo().create(qty_line)

        if self.porto_product_id:
            sale_line = {
                'sale_id': sale.id,
                'product_id': self.porto_product_id.product_id.id,
            }
            sale_line = self.env['s2u.sale.line'].sudo().create(sale_line)

            qty_line = {
                'saleline_id': sale_line.id,
                'qty': '1 x',
                'price': self.tot_costs,
                'price_per': 'total',
                'price_is_net': False
            }
            self.env['s2u.sale.line.qty'].sudo().create(qty_line)

        self.do_order_confirmation(method, sale, default_vals=default_vals)

        self.write({
            'sale_id': sale.id
        })
        self._cr.commit()

        if self.acquirer_id.so_template_id:
            self.acquirer_id.so_template_id.mail_template_id.send_mail(sale.id, force_send=False)

        return True


class PaymentTransactionItem(models.Model):
    _name = 's2u.payment.transaction.item'
    _description = 'Payment Transaction Shoppingcart'

    trans_id = fields.Many2one('s2u.payment.transaction', string='Transaction', ondelete='cascade')
    product_id = fields.Integer(string='Product ID')
    qty = fields.Integer(string='Qty')
    product_model = fields.Char(string='Model')
    product_name = fields.Char(string='Product')
