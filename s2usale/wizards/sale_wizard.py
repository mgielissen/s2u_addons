# -*- coding: utf-8 -*-
import base64

from odoo.exceptions import UserError, ValidationError
from odoo import _, api, fields, models


class ActionSOQuotation(models.TransientModel):
    """
    """
    _name = 's2usale.action.so.quotation'
    _description = 'Make quotation'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    sale_id = fields.Many2one('s2u.sale', string="SO", ondelete='set null')
    chance = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Chance')

    # use ../../.. notation in the selection, create invoices is splitting this condition value based on '/'
    condition = fields.Selection([
        ('100', '100%'),
        ('50/50', '50/50'),
        ('40/40/20', '40/40/20')
    ], default='100', string='Condition')
    confirmed_by = fields.Selection([
        ('mail', 'Mail'),
        ('signed', 'Signed copy'),
        ('po', 'Own PO'),
        ('shop', 'Webshop')
    ], string='Confirmed by')

    @api.model
    def default_get(self, fields):

        result = super(ActionSOQuotation, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        sale = self.env['s2u.sale'].browse(active_ids[0])
        if sale.chance:
            result['chance'] = sale.chance
        if sale.condition:
            result['condition'] = sale.condition
        result['sale_id'] = sale.id

        return result

    @api.multi
    def do_quotation(self):

        self.ensure_one()

        sale = self.sale_id

        invoice_vals = {}
        if sale.invoice_is_sale_address:
            invoice_vals = {
                'invoice_type': sale.type,
                'invoice_partner_id': sale.partner_id.id,
                'invoice_contact_id': sale.contact_id.id if sale.contact_id else False,
                'invoice_address_id': sale.address_id.id if sale.address_id else False
            }

        delivery_vals = {}
        if sale.delivery_is_sale_address:
            delivery = sale.partner_id.prepare_delivery(address=sale.address_id, contact=sale.contact_id)

            delivery_vals = {
                'delivery_type': sale.type,
                'delivery_partner_id': sale.partner_id.id,
                'delivery_contact_id': sale.contact_id.id if sale.contact_id else False,
                'delivery_address': delivery,
            }

            if sale.address_id:
                if sale.address_id.country_id:
                    delivery_vals['delivery_country_id'] = sale.address_id.country_id.id
            elif sale.partner_id.country_id:
                delivery_vals['delivery_country_id'] = sale.partner_id.country_id.id

            if sale.partner_id.tinno:
                delivery_vals['delivery_tinno'] = sale.partner_id.tinno

        if sale.name == 'Concept':
            name_quot = sale._new_number()
            vals = {
                'state': 'quot',
                'date_qu': fields.Date.context_today(self),
                'name': name_quot,
                'name_quot': name_quot,
                'chance': self.chance,
                'condition': self.condition
            }
            vals.update(invoice_vals)
            vals.update(delivery_vals)
            sale.write(vals)
        else:
            vals = {
                'date_qu': fields.Date.context_today(self),
                'state': 'quot',
                'chance': self.chance,
                'condition': self.condition
            }
            vals.update(invoice_vals)
            vals.update(delivery_vals)
            sale.write(vals)

        # cleanup old docs, not needed here
        attachments = self.env['ir.attachment'].sudo().search([('res_model', '=', 's2u.sale'),
                                                               ('res_id', '=', sale.id),
                                                               ('name', '=', 'Quotation-%s.pdf' % sale.name)])
        attachments.unlink()

        self.env.ref('s2usale.s2usale_quotations_so').render_qweb_pdf([sale.id])[0]

        result = {'type': 'ir.actions.act_window_close'}
        return result


class ActionSOOrder(models.TransientModel):
    """
    """
    _name = 's2usale.action.so.order'
    _description = 'Make order'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    sale_id = fields.Many2one('s2u.sale', string="SO", ondelete='set null')
    next_step = fields.Selection([
        ('confirm', 'Wat for confirmation'),
        ('payment', 'Wait for payment')
    ], string='Next step', default='confirm', required=True)

    @api.model
    def default_get(self, fields):

        result = super(ActionSOOrder, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        sale = self.env['s2u.sale'].browse(active_ids[0])
        result['sale_id'] = sale.id

        return result

    @api.multi
    def do_order(self):

        self.ensure_one()

        sale = self.sale_id

        order = 0
        for line in sale.line_ids:
            if line.for_order:
                order += 1
        if not order:
            for line in sale.line_ids:
                if line.qty_ids:
                    line.qty_ids[0].write({
                        'for_order': True
                    })
                    order += 1
            sale.invalidate_cache()
        if not order and not sale.overrule_action_order():
            return False

        sale.write({
            'state': 'order' if self.next_step == 'confirm' else 'payment',
            'date_so': fields.Date.context_today(self)
        })

        result = {'type': 'ir.actions.act_window_close'}
        return result


class ActionSOConfirm(models.TransientModel):
    """
    """
    _name = 's2usale.action.so.confirm'
    _description = 'Confirm order'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    sale_id = fields.Many2one('s2u.sale', string="SO", ondelete='set null')
    customer_code = fields.Char(string='Customer reference')
    confirmed_remark = fields.Char(string='Remark')
    confirmed_doc = fields.Binary(string="Doc. returned", attachment=True,
                                  help="This field holds the document you received back from the customer where he/she confirmes the order.")
    file_name = fields.Char(string="File Name")
    confirmed_by = fields.Selection([
        ('mail', 'Mail'),
        ('signed', 'Signed copy'),
        ('po', 'Own PO'),
        ('shop', 'Webshop')
    ], string='Confirmed by')
    confirmed_user_id = fields.Many2one('res.users', string='Confirmed by user', copy=False)

    @api.model
    def default_get(self, fields):

        result = super(ActionSOConfirm, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        sale = self.env['s2u.sale'].browse(active_ids[0])
        if sale.confirmed_by:
            result['confirmed_by'] = sale.confirmed_by
        if sale.confirmed_user_id:
            result['confirmed_user_id'] = sale.confirmed_user_id.id
        else:
            result['confirmed_user_id'] = self.env.user.id
        if sale.customer_code:
            result['customer_code'] = sale.customer_code
        if sale.confirmed_remark:
            result['confirmed_remark'] = sale.confirmed_remark
        result['sale_id'] = sale.id

        return result

    @api.multi
    def do_confirm(self):

        self.ensure_one()

        sale = self.sale_id

        sale.before_confirm()

        if sale.invoicing not in ['dropshipping']:
            if sale.delivery_ids:
                for delivery in sale.delivery_ids:
                    vals = {
                        'load_type': delivery.load_type,
                        'delivery_entity_id': delivery.delivery_partner_id.id,
                        'delivery_contact_id': delivery.delivery_contact_id.id if delivery.delivery_contact_id else False,
                        'delivery_address': delivery.delivery_address,
                        'delivery_country_id': delivery.delivery_partner_id.country_id.id if delivery.delivery_partner_id.country_id else False,
                        'delivery_tinno': delivery.delivery_partner_id.tinno,
                        'delivery_lang': delivery.delivery_partner_id.lang,
                        'date_delivery': sale.date_delivery,
                        'project': sale.project,
                        'reference': sale.reference,
                        'customer_code': self.customer_code
                    }
                    if delivery.load_entity_id:
                        vals['load_entity_id'] = delivery.load_entity_id.id
                    if delivery.load_address:
                        vals['load_address'] = delivery.load_address
                    if delivery.trailer_no:
                        vals['trailer_no'] = delivery.trailer_no
                    sale.create_outgoing(add_values=vals, devider=len(sale.delivery_ids))
            else:
                sale.create_outgoing()

        sale.write({
            'state': 'run',
            'date_confirm': fields.Date.context_today(self),
            'confirmed_user_id': self.env.user.id,
            'customer_code': self.customer_code,
            'confirmed_remark': self.confirmed_remark,
            'confirmed_by': self.confirmed_by,
            'confirmed_user_id': self.confirmed_user_id.id
        })

        # always create the invoice
        if sale.invoicing == 'confirm':
            sale.create_invoice()

        sale.sale_is_completed()

        if self.confirmed_doc:
            attachments = [(self.file_name, base64.b64decode(self.confirmed_doc))]
        else:
            attachments = []

        sale.message_post(body=self.confirmed_remark, subject='Order confirmed', attachments=attachments)

        # cleanup old docs, not needed here
        attachments = self.env['ir.attachment'].sudo().search([('res_model', '=', 's2u.sale'),
                                                               ('res_id', '=', sale.id),
                                                               ('name', '=', 'Order-%s.pdf' % sale.name)])
        attachments.unlink()

        self.env.ref('s2usale.s2usale_orders_so').render_qweb_pdf([sale.id])[0]

        return {
            'type': 'ir.actions.act_window_close'
        }


class ActionSOCancel(models.TransientModel):
    """
    """
    _name = 's2usale.action.so.cancel'
    _description = 'Cancel order'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    sale_id = fields.Many2one('s2u.sale', string="SO", ondelete='set null')
    cancel_reason = fields.Char(string='Cancel Reason')



    @api.model
    def default_get(self, fields):

        result = super(ActionSOCancel, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        sale = self.env['s2u.sale'].browse(active_ids[0])
        result['sale_id'] = sale.id

        return result

    @api.multi
    def do_cancel(self):

        self.ensure_one()

        todo_model = self.env['s2u.warehouse.outgoing.todo']

        sale = self.sale_id

        todos = todo_model.search([('sale_id', '=', sale.id)])
        outgoings = []
        for t in todos:
            if t.outgoing_id.state != 'draft':
                raise UserError(
                    _('Outgoing shipment [%s] already confirmed! Cancel not possible.' % t.outgoing_id.name))
            outgoings.append(t.outgoing_id)
        todos.unlink()

        for o in outgoings:
            if not o.todo_ids:
                o.unlink()

        sale.write({
            'state': 'cancel',
            'cancel_reason': self.cancel_reason
        })

        result = {'type': 'ir.actions.act_window_close'}
        return result