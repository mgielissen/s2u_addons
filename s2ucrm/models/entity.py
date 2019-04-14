# -*- coding: utf-8 -*-

from datetime import timedelta

import io
from io import BytesIO
import base64
import xlsxwriter

from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools


class CrmEntity(models.Model):
    _name = "s2u.crm.entity"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "CRM Entity"
    _order = "name, entity_code"

    @api.multi
    def compute_fiscalyear_dates(self, date):
        self.ensure_one()
        last_month = 12
        last_day = 31
        if (date.month < last_month or (date.month == last_month and date.day <= last_day)):
            date = date.replace(month=last_month, day=last_day)
        else:
            if last_month == 2 and last_day == 29 and (date.year + 1) % 4 != 0:
                date = date.replace(month=last_month, day=28, year=date.year + 1)
            else:
                date = date.replace(month=last_month, day=last_day, year=date.year + 1)
        date_to = date
        date_from = date + timedelta(days=1)
        if date_from.month == 2 and date_from.day == 29:
            date_from = date_from.replace(day=28, year=date_from.year - 1)
        else:
            date_from = date_from.replace(year=date_from.year - 1)
        return {'date_from': date_from, 'date_to': date_to}

    @api.model
    def _lang_get(self):
        languages = self.env['res.lang'].search([])
        return [(language.code, language.name) for language in languages]

    @api.model
    def _default_lang(self):
        domain = [
            ('code', '=', 'nl_NL'),
        ]
        if self.env['res.lang'].search(domain, limit=1):
            return 'nl_NL'
        else:
            return False

    @api.model
    def _default_country(self):
        domain = [
            ('code', '=', 'NL'),
        ]
        return self.env['res.country'].search(domain, limit=1)

    @api.multi
    @api.depends('name', 'entity_code')
    def name_get(self):
        result = []
        for entity in self:
            if entity.entity_code:
                name = '%s (%s)' % (entity.name, entity.entity_code)
            else:
                name = entity.name
            result.append((entity.id, name))
        return result

    def get_postal(self):

        addresses = self.env['s2u.crm.entity.address'].search([('entity_id', '=', self.id),
                                                               ('type', '=', 'pos')])
        if addresses:
            return addresses[0]

        addresses = self.env['s2u.crm.entity.address'].search([('entity_id', '=', self.id),
                                                               ('type', '=', 'def')])
        if addresses:
            return addresses[0]

        return False

    def get_physical(self):

        addresses = self.env['s2u.crm.entity.address'].search([('entity_id', '=', self.id),
                                                               ('type', '=', 'phy')])
        if addresses:
            return addresses[0]

        addresses = self.env['s2u.crm.entity.address'].search([('entity_id', '=', self.id),
                                                               ('type', '=', 'def')])
        if addresses:
            return addresses[0]

        return False

    @api.one
    def compute_default_address(self):

        def build_address(address):
            res = address.address
            if address.zip and address.city:
                res += '\n%s  %s' % (address.zip, address.city)
            elif address.city:
                res += '\n%s' % address.city
            elif address.zip:
                res += '\n%s' % address.zip
            if address.country_id and address.country_id.code != 'NL':
                res += '\n%s' % address.country_id.name
            return res

        address = self.env['s2u.crm.entity.address'].search([('entity_id', '=', self.id),
                                                             ('type', '=', 'def')], limit=1)
        if address:
            self.default_address = build_address(address)
            return

        address = self.env['s2u.crm.entity.address'].search([('entity_id', '=', self.id),
                                                             ('type', '=', 'phy')], limit=1)
        if address:
            self.default_address = build_address(address)
            return

        self.default_address = ''

    def prepare_delivery(self, address=False, contact=False):

        self.ensure_one()

        delivery = ''

        if self.type == 'b2c':
            if self.prefix:
                delivery = self.prefix + '\n'
            else:
                delivery = self.name + '\n'
            delivery += '%s\n' % self.address
            if self.zip and self.city:
                delivery += '%s  %s\n' % (self.zip, self.city)
            elif self.city:
                delivery += '%s\n' % self.city
            if self.country_id and self.country_id.code != 'NL':
                delivery += '%s\n' % self.country_id.name
        elif contact:
            delivery = contact.display_company + '\n'
            if contact.prefix:
                delivery += '%s\n' % contact.prefix
            else:
                delivery += '%s\n' % contact.name
            if not address:
                address = self.get_physical()
            if address:
                if address.address:
                    delivery += '%s\n' % address.address
                if address.zip and address.city:
                    delivery += '%s  %s\n' % (
                        address.zip, address.city)
                if address.country_id:
                    delivery += '%s\n' % address.country_id.name
            else:
                address = self.get_physical()
                if address:
                    delivery += '%s\n' % address.address
                    if address.zip and address.city:
                        delivery += '%s  %s\n' % (address.zip, address.city)
                    if address.country_id:
                        delivery += '%s\n' % address.country_id.name
        else:
            if not address:
                address = self.get_physical()
            if address:
                delivery = self.name + '\n'
                delivery += '%s\n' % address.address
                if address.zip and address.city:
                    delivery += '%s  %s\n' % (address.zip, address.city)
                elif address.city:
                    delivery += '%s\n' % address.city
                if address.country_id and self.country_id.code != 'NL':
                    delivery += '%s\n' % address.country_id.name

        return delivery

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):

        if args and len(args) == 1:
            if args[0][0] == 'name' and args[0][1] == 'ilike':
                val = args[0][2]
                args = ['|', ('name', 'ilike', val),
                             ('entity_code', '=', val)]

        return super(CrmEntity, self).search(args, offset, limit, order, count=count)

    @api.one
    def compute_rating(self):

        if self.rating:
            self.rating_visual = int(self.rating)
        else:
            self.rating_visual = 0

    @api.one
    def compute_is_favorite(self):

        res = self.env['s2u.crm.favorite'].search([('user_id', '=', self.env.user.id),
                                                   ('res_model', '=', 's2u.crm.entity'),
                                                   ('res_id', '=', self.id)])
        if res:
            self.is_favorite = True
        else:
            self.is_favorite = False

    @api.multi
    def action_make_favorite(self):

        self.ensure_one()

        res = self.env['s2u.crm.favorite'].search([('user_id', '=', self.env.user.id),
                                                   ('res_model', '=', 's2u.crm.entity'),
                                                   ('res_id', '=', self.id)])
        if res:
            return True

        self.env['s2u.crm.favorite'].create({'res_model': 's2u.crm.entity',
                                             'res_id': self.id})

        return True

    @api.multi
    def action_undo_favorite(self):

        self.ensure_one()

        res = self.env['s2u.crm.favorite'].search([('user_id', '=', self.env.user.id),
                                                   ('res_model', '=', 's2u.crm.entity'),
                                                   ('res_id', '=', self.id)])
        res.unlink()
        return True

    @api.model
    def create(self, vals):

        if vals.get('c_of_c') and vals.get('type', '') == 'b2b':
            exists = self.search([('c_of_c', '=', vals['c_of_c'])])
            if exists:
                raise UserError(_('Entity already exists with this Chamber of Commerce number!'))

        if vals.get('image'):
            tools.image_resize_images(vals)

        if 'skip_res_partner_sync' not in self.env.context:
            partner_vals = {
                'email': vals.get('email', False),
                'phone': vals.get('phone', False),
                'type': 'other'
            }

            if vals.get('type', False) == 'b2c':
                partner_vals['name'] = vals.get('name', False)
                partner_vals['street'] = vals.get('address', False)
                partner_vals['zip'] = vals.get('zip', False)
                partner_vals['city'] = vals.get('city', False)
                partner_vals['country_id'] = vals.get('country_id', False)
                partner_vals['is_company'] = False
            else:
                partner_vals['company_name'] = vals.get('name', False)
                partner_vals['is_company'] = True

            if vals.get('odoo_res_partner_id', False):
                self.env['res.partner'].search([('id', '=', vals['odoo_res_partner_id'])]).\
                    with_context({'skip_res_partner_sync': True}).write(partner_vals)
            else:
                res_partner = self.env['res.partner'].with_context({'skip_res_partner_sync': True}).create(partner_vals)
                vals['odoo_res_partner_id'] = res_partner.id

        entity = super(CrmEntity, self).create(vals)

        return entity

    @api.multi
    def write(self, vals):

        if vals.get('c_of_c') and vals.get('type', self.type) == 'b2b':
            exists = self.search([('c_of_c', '=', vals['c_of_c']),
                                  ('id', 'not in', self.ids)])
            if exists or len(self) > 1:
                raise UserError(_('Entity already exists with this Chamber of Commerce number!'))

        tools.image_resize_images(vals)

        res = super(CrmEntity, self).write(vals)

        if 'skip_res_partner_sync' not in self.env.context:
            for entity in self:
                partner_vals = {
                    'email': vals.get('email', entity.email),
                    'phone': vals.get('phone', entity.phone),
                    'type': 'other'
                }

                if vals.get('type', entity.type) == 'b2c':
                    partner_vals['is_company'] = False
                    partner_vals['name'] = vals.get('name', entity.name)
                    partner_vals['street'] = vals.get('address', entity.address)
                    partner_vals['zip'] = vals.get('zip', entity.zip)
                    partner_vals['city'] = vals.get('city', entity.city)
                    partner_vals['country_id'] = vals.get('country_id', entity.country_id.id if entity.country_id else False)
                else:
                    partner_vals['is_company'] = True
                    partner_vals['company_name'] = vals.get('name', entity.name)

                if entity.odoo_res_partner_id:
                    entity.odoo_res_partner_id.with_context({'skip_res_partner_sync': True}).write(partner_vals)
                else:
                    res_partner_id = self.env['res.partner'].with_context({'skip_res_partner_sync': True}).create(partner_vals)
                    entity.write({
                        'odoo_res_partner_id': res_partner_id.id
                    })

                if 'active' in vals and not vals.get('active', True):
                    entity.address_ids.write({
                        'active': False,
                    })
                    entity.contact_ids.write({
                        'active': False,
                    })
                    entity.delivery_ids.write({
                        'active': False,
                    })
                elif 'active' in vals and vals.get('active', False):
                    entity.address_ids.write({
                        'active': True,
                    })
                    entity.contact_ids.write({
                        'active': True,
                    })
                    entity.delivery_ids.write({
                        'active': True,
                    })

        return res

    @api.multi
    def unlink(self):

        for entity in self:
            if entity.odoo_res_partner_id:
                entity.odoo_res_partner_id.with_context({'skip_res_partner_sync': True}).write({
                    'active': False
                })

        res = super(CrmEntity, self).unlink()

        return res

    @api.multi
    def action_view_contacts(self):

        action = self.env.ref('s2ucrm.action_crm_entity_contact').read()[0]
        if self.contact_ids:
            action['domain'] = [('id', 'in', self.contact_ids.ids)]
            action['context'] = {'default_entity_id': self.id}
        else:
            action['context'] = {'default_entity_id': self.id}
            action['views'] = [(self.env.ref('s2ucrm.crm_entity_contact_form').id, 'form')]
            action['res_id'] = False

        return action

    def _get_contacts_count(self):

        for entity in self:
            entity.contacts_count = len(entity.contact_ids) if entity.contact_ids else 0

    @api.multi
    def action_view_addresses(self):

        action = self.env.ref('s2ucrm.action_crm_entity_address').read()[0]
        if self.address_ids:
            action['domain'] = [('id', 'in', self.address_ids.ids)]
            action['context'] = {'default_entity_id': self.id}
        else:
            action['context'] = {'default_entity_id': self.id}
            action['views'] = [(self.env.ref('s2ucrm.crm_entity_address_form').id, 'form')]
            action['res_id'] = False

        return action

    def _get_addresses_count(self):

        for entity in self:
            entity.addresses_count = len(entity.address_ids) if entity.address_ids else 0

    @api.multi
    def action_view_deliveries(self):

        action = self.env.ref('s2ucrm.action_crm_entity_delivery').read()[0]
        action['domain'] = [('id', 'in', self.delivery_ids.ids)]
        action['context'] = {'default_entity_id': self.id}

        return action

    def _get_deliveries_count(self):

        for entity in self:
            entity.deliveries_count = len(entity.delivery_ids) if entity.delivery_ids else 0

    @api.onchange('entity_code')
    def onchange_entity_code(self):
        if self.entity_code:
            self.entity_code = self.entity_code.upper()

    name = fields.Char(required=True, index=True, string='Name')
    prefix = fields.Char(string='Prefix')
    lang = fields.Selection(_lang_get, string='Language', default=_default_lang)
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True)
    address = fields.Char(index=True, string='Address')
    zip = fields.Char(index=True, string='Zip')
    city = fields.Char(index=True, string='City')
    country_id = fields.Many2one('res.country', string='Country', default=_default_country)
    communication = fields.Char(string='Communication')
    address_ids = fields.One2many('s2u.crm.entity.address', 'entity_id',
                                  string='Addresses')
    contact_ids = fields.One2many('s2u.crm.entity.contact', 'entity_id',
                                  string='Contacts')
    tinno = fields.Char('TIN no.')
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    phone = fields.Char(index=True, string='Phone')
    fax = fields.Char(index=True, string='Fax')
    mobile = fields.Char(index=True, string='Mobile')
    email = fields.Char(index=True, string='eMail')
    website = fields.Char(index=True, string='Website')
    skype = fields.Char(index=True, string='Skype')
    c_of_c = fields.Char(string='Chamber of Commerce', index=True)
    entity_code = fields.Char(string='Code', index=True)
    tag_ids = fields.Many2many('s2u.crm.tag', 's2u_crm_entity_tag_rel', 'entity_id', 'tag_id', string='Tags')
    bank_iban = fields.Char(index=True, string='IBAN')
    bank_bic = fields.Char(string='BIC')
    bank_name = fields.Char(string='Bank')
    payment_terms = fields.Integer(string='Payment terms (days)', default=30)
    payment_terms_text = fields.Char(string='Payment terms (text)', default='30 dagen netto')
    birthdate = fields.Date(string='Birthdate')
    external_id = fields.Char(string='External ID', index=True)
    trace_mail = fields.Boolean('Trace mail', default=False, index=True)
    active = fields.Boolean('Active', default=True)
    rating = fields.Selection([('1', '1'), ('2', '2'), ('3', '3')], string='Rating')
    rating_visual = fields.Integer(string='Rating', readonly=True, compute='compute_rating')
    is_favorite = fields.Boolean(string='Favorite', readonly=True, compute='compute_is_favorite')
    odoo_res_partner_id = fields.Many2one('res.partner', string='res.partner', index=True)
    state = fields.Selection([
        ('ok', 'Ok'),
        ('alert', 'Alert')
    ], required=True, default='ok', string='State', index=True)
    delivery_ids = fields.One2many('s2u.crm.entity.delivery', 'entity_id',
                                   string='Deliveries')
    migration_id = fields.Integer(string='Migration')
    contacts_count = fields.Integer(string='# of Contacts', compute='_get_contacts_count', readonly=True)
    addresses_count = fields.Integer(string='# of Addresses', compute='_get_addresses_count', readonly=True)
    deliveries_count = fields.Integer(string='# of Deliveries', compute='_get_deliveries_count', readonly=True)
    color = fields.Integer(string='Color Index')
    description = fields.Text(string='Description', index=True)
    # image: all image fields are base64 encoded and PIL-supported
    image = fields.Binary("Image", attachment=True,
                          help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )
    image_medium = fields.Binary("Medium-sized image", attachment=True,
                                 help="Medium-sized image of this contact. It is automatically " \
                                      "resized as a 128x128px image, with aspect ratio preserved. " \
                                      "Use this field in form views or some kanban views.")
    image_small = fields.Binary("Small-sized image", attachment=True,
                                help="Small-sized image of this contact. It is automatically " \
                                     "resized as a 64x64px image, with aspect ratio preserved. " \
                                     "Use this field anywhere a small image is required.")
    responsible_id = fields.Many2one('res.users', string='Responsible',
                                     default=lambda self: self.env.user)
    sexe = fields.Selection([
        ('m', 'Male'),
        ('f', 'Female')
    ], default='m', string='Sexe')
    image_fname = fields.Char('Image Name')
    default_address = fields.Text(string='Address', readonly=True, compute='compute_default_address')


class CrmEntityDelivery(models.Model):
    _name = "s2u.crm.entity.delivery"
    _rec_name = "delivery_address"

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

    entity_id = fields.Many2one('s2u.crm.entity', string='Entity', required=True, ondelete='cascade')
    delivery_address = fields.Text(string='Address', required=True)
    delivery_country_id = fields.Many2one('res.country', string='Leveringsland', default=_default_delivery_country, required=True)
    delivery_tinno = fields.Char('TIN no.')
    delivery_lang = fields.Selection(_delivery_lang_get, string='Language')
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    active = fields.Boolean('Active', default=True)
    delivery_note = fields.Text(string='Note')
    migration_id = fields.Integer(string='Migration')


class CrmEntityAddress(models.Model):
    _name = "s2u.crm.entity.address"
    _description = "CRM Entity Address"
    _order = "entity_id, city, address"
    _rec_name = "address"

    @api.multi
    @api.depends('address', 'city', 'type')
    def name_get(self):
        result = []
        for address in self:
            if address.address and address.city:
                name = '%s - %s' % (address.city, address.address)
            elif address.address:
                name = '%s' % address.address
            else:
                name = '-'
            if address.type == 'pos':
                name = 'Postal: %s' % name
            elif address.type == 'inv':
                name = 'Invoice: %s' % name

            result.append((address.id, name))
        return result

    @api.model
    def create(self, vals):

        address = super(CrmEntityAddress, self).create(vals)

        if 'skip_res_partner_sync' not in self.env.context:
            if address.type == 'def' and address.entity_id.odoo_res_partner_id:
                partner_vals = {
                    'street': vals.get('address', False),
                    'zip': vals.get('zip', False),
                    'city': vals.get('city', False),
                    'country_id': vals.get('country_id', False)
                }
                address.entity_id.odoo_res_partner_id.with_context({'skip_res_partner_sync': True}).write(partner_vals)

        return address

    @api.multi
    def write(self, vals):

        res = super(CrmEntityAddress, self).write(vals)

        if 'skip_res_partner_sync' not in self.env.context:
            for address in self:
                if address.type == 'def' and address.entity_id.odoo_res_partner_id:
                    partner_vals = {
                        'street': vals.get('address', False),
                        'zip': vals.get('zip', False),
                        'city': vals.get('city', False),
                        'country_id': vals.get('country_id', False)
                    }
                    address.entity_id.odoo_res_partner_id.with_context({'skip_res_partner_sync': True}).write(partner_vals)

        return res

    address = fields.Text(index=True, string='Address')
    zip = fields.Char(index=True, string='Zip')
    city = fields.Char(index=True, string='City')
    country_id = fields.Many2one('res.country', string='Country')
    entity_id = fields.Many2one('s2u.crm.entity', string='Company', ondelete='cascade', required=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    type = fields.Selection([
        ('def', 'Default'),
        ('pos', 'Postal'),
        ('phy', 'Physical'),
        ('inv', 'Invoice')
    ], required=True, default='def', string='Type', index=True)
    external_id = fields.Char(string='External ID', index=True)
    active = fields.Boolean('Active', default=True)
    migration_id = fields.Integer(string='Migration')
    inv_by_mail = fields.Boolean(string='Invoice by mail', default=False)
    email = fields.Char(string='eMail')


class CrmEntityContact(models.Model):
    _name = "s2u.crm.entity.contact"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "CRM Entity Contact"
    _order = "entity_id, name"

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):

        new_args = []
        if args:
            for arg in args:
                if arg[0] == 'name' and arg[1] == 'ilike':
                    val = arg[2]
                    new_args.append('|')
                    new_args.append('|')
                    new_args.append(['name', 'ilike', val])
                    new_args.append(['search_key', '=', val])
                    new_args.append(['sub_company_name', 'ilike', val])
                else:
                    new_args.append(arg)
            args = new_args

        return super(CrmEntityContact, self).search(args, offset, limit, order, count=count)

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', ('search_key', '=', name + '%'), ('sub_company_name', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        contacts = self.search(domain + args, limit=limit)
        return contacts.name_get()

    @api.multi
    @api.constrains('entity_id', 'address_id')
    def _check_address_entity(self):
        for contact in self:
            if contact.entity_id and contact.address_id:
                if contact.entity_id != contact.address_id.entity_id:
                    raise ValueError(_('Address does not belong to the selected company!'))

    @api.multi
    @api.depends('name', 'sub_company', 'sub_company_name')
    def name_get(self):
        result = []
        for contact in self:
            if contact.sub_company:
                name = '%s (%s)' % (contact.name, contact.sub_company_name)
            else:
                name = contact.name
            result.append((contact.id, name))
        return result

    @api.one
    @api.depends('entity_id.name', 'sub_company', 'sub_company_name')
    def _compute_display_company(self):
        if self.sub_company:
            self.display_company = self.sub_company_name
        elif self.entity_id:
            self.display_company = self.entity_id.name
        else:
            self.display_company = ''

    @api.one
    def compute_is_favorite(self):

        res = self.env['s2u.crm.favorite'].search([('user_id', '=', self.env.user.id),
                                                   ('res_model', '=', 's2u.crm.entity.contact'),
                                                   ('res_id', '=', self.id)])
        if res:
            self.is_favorite = True
        else:
            self.is_favorite = False

    @api.multi
    def action_make_favorite(self):

        self.ensure_one()

        res = self.env['s2u.crm.favorite'].search([('user_id', '=', self.env.user.id),
                                                   ('res_model', '=', 's2u.crm.entity.contact'),
                                                   ('res_id', '=', self.id)])
        if res:
            return True

        self.env['s2u.crm.favorite'].create({'res_model': 's2u.crm.entity.contact',
                                             'res_id': self.id})
        return True

    @api.multi
    def action_undo_favorite(self):

        self.ensure_one()

        res = self.env['s2u.crm.favorite'].search([('user_id', '=', self.env.user.id),
                                                   ('res_model', '=', 's2u.crm.entity.contact'),
                                                   ('res_id', '=', self.id)])
        res.unlink()
        return True

    @api.model
    def create(self, vals):

        if vals.get('image'):
            tools.image_resize_images(vals)

        if vals.get('sub_company', False):
            name = 'Contact: %s (%s)' % (vals['name'], vals['sub_company_name'])
        else:
            name = 'Contact: %s' % vals['name']

        res_partner = self.env['res.partner'].create({
            'name': name,
            'email': vals.get('email', False)
        })
        vals['odoo_res_partner_id'] = res_partner.id

        contact = super(CrmEntityContact, self).create(vals)

        return contact

    @api.multi
    def write(self, vals):

        tools.image_resize_images(vals)

        res = super(CrmEntityContact, self).write(vals)

        for contact in self:
            if vals.get('sub_company', contact.sub_company):
                name = 'Contact: %s (%s)' % (vals.get('name', contact.name),
                                             vals.get('sub_company', contact.sub_company))
            else:
                name = 'Contact: %s' % vals.get('name', contact.name)

            if contact.odoo_res_partner_id:
                contact.odoo_res_partner_id.write({
                    'name': name,
                    'email': vals.get('email', contact.email)
                })
            else:
                res_partner_id = self.env['res.partner'].create({
                    'name': name,
                    'email': vals.get('email', contact.email)
                })
                contact.write({
                    'odoo_res_partner_id': res_partner_id.id
                })

        return res

    @api.multi
    def unlink(self):

        for contact in self:
            if contact.odoo_res_partner_id:
                contact.odoo_res_partner_id.write({
                    'active': False
                })

        res = super(CrmEntityContact, self).unlink()

        return res

    @api.model
    def default_get(self, fields):

        result = super(CrmEntityContact, self).default_get(fields)

        context = self._context
        entity_id = context.get('parent_id', False)
        if entity_id:
            default_address = self.env['s2u.crm.entity.address'].search([('entity_id', '=', entity_id),
                                                                         ('type', '=', 'def')], limit=1)
            if default_address:
                result['address_id'] = default_address.id

        return result

    @api.onchange('entity_id')
    def _entity_id(self):

        if not self.entity_id:
            return False

        default_address = self.env['s2u.crm.entity.address'].search([('entity_id', '=', self.entity_id.id),
                                                                     ('type', '=', 'def')], limit=1)
        if default_address:
            self.address_id = default_address.id

    prefix = fields.Char(string='Prefix')
    name = fields.Char(required=True, index=True, string='Name')
    phone = fields.Char(index=True, string='Phone')
    mobile = fields.Char(index=True, string='Mobile')
    email = fields.Char(index=True, string='eMail')
    skype = fields.Char(index=True, string='Skype')
    communication = fields.Char(string='Communication')
    position = fields.Char(string='Position')
    entity_id = fields.Many2one('s2u.crm.entity', string='Company', ondelete='cascade',
                                domain=[('type', '=', 'b2b')], required=True)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address')
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    search_key = fields.Char(string='Search key', index=True)
    tag_ids = fields.Many2many('s2u.crm.tag', 's2u_crm_contact_tag_rel', 'contact_id', 'tag_id', string='Tags')
    address = fields.Char(index=True, string='Address')
    zip = fields.Char(index=True, string='Zip')
    city = fields.Char(index=True, string='City')
    country_id = fields.Many2one('res.country', string='Country')
    phone_privat = fields.Char(index=True, string='Phone')
    email_privat = fields.Char(index=True, string='eMail')
    birthdate = fields.Date(string='Birthdate')
    external_id = fields.Char(string='External ID', index=True)
    sub_company = fields.Boolean(string='Sub company', index=True, default=False)
    sub_company_name = fields.Char(index=True, string='Company')
    display_company = fields.Char(string='Company', store=True, readonly=True, compute='_compute_display_company')
    is_favorite = fields.Boolean(string='Favorite', readonly=True, compute='compute_is_favorite')
    odoo_res_partner_id = fields.Many2one('res.partner', string='res.partner', index=True)
    state = fields.Selection([
        ('ok', 'Ok'),
        ('alert', 'Alert')
    ], required=True, default='ok', string='State', index=True)
    active = fields.Boolean('Active', default=True)
    migration_id = fields.Integer(string='Migration')
    # image: all image fields are base64 encoded and PIL-supported
    image = fields.Binary("Image", attachment=True,
                          help="This field holds the image used as avatar for this contact, limited to 1024x1024px", )
    image_medium = fields.Binary("Medium-sized image", attachment=True,
                                 help="Medium-sized image of this contact. It is automatically " \
                                      "resized as a 128x128px image, with aspect ratio preserved. " \
                                      "Use this field in form views or some kanban views.")
    image_small = fields.Binary("Small-sized image", attachment=True,
                                help="Small-sized image of this contact. It is automatically " \
                                     "resized as a 64x64px image, with aspect ratio preserved. " \
                                     "Use this field anywhere a small image is required.")
    sexe = fields.Selection([
        ('m', 'Male'),
        ('f', 'Female')
    ], required=True, default='m', string='Sexe')
    image_fname = fields.Char('Image Name')
    reports_to_id = fields.Many2one('s2u.crm.entity.contact', string='Reports to')
    secretary_id = fields.Many2one('s2u.crm.entity.contact', string='Secretary')

    @api.multi
    def action_excel(self):

        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True
        })

        worksheet = workbook.add_worksheet()
        bold = workbook.add_format({'bold': True})

        worksheet.write('A1', 'Company', bold)
        worksheet.write('B1', 'Contact', bold)
        worksheet.write('C1', 'Address', bold)
        worksheet.write('D1', 'ZIP', bold)
        worksheet.write('E1', 'City', bold)
        worksheet.write('F1', 'Country', bold)
        worksheet.write('G1', 'Communication', bold)
        worksheet.write('H1', 'Prefix', bold)
        worksheet.write('I1', 'Image', bold)

        worksheet.write('A2', self.entity_id.name)
        if self.prefix:
            worksheet.write('B2', self.prefix)
        else:
            worksheet.write('B2', self.name)
        if self.address_id:
            worksheet.write('C2', self.address_id.address)
            worksheet.write('D2', self.address_id.zip)
            worksheet.write('E2', self.address_id.city)
            worksheet.write('F2', self.address_id.country_id.name)
        if self.communication:
            worksheet.write('G2', self.communication)
        if self.prefix:
            worksheet.write('H2', self.prefix)
        if self.entity_id.image and self.entity_id.image_fname:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            image_url = '%s/crm/logo/%d/%s' % (base_url, self.entity_id.id, self.entity_id.entity_code)
            worksheet.write('I2', image_url)
        workbook.close()
        xlsx_data = output.getvalue()

        values = {
            'name': "%s.xlsx" % self.name,
            'datas_fname': '%s.xlsx' % self.name,
            'res_model': 'ir.ui.view',
            'res_id': False,
            'type': 'binary',
            'public': False,
            'datas': base64.b64encode(xlsx_data)
        }

        attachment_id = self.env['ir.attachment'].sudo().create(values)
        base_url = self.env['ir.config_parameter'].get_param('web.base.url')
        download_url = '/web/content/' + str(attachment_id.id) + '?download=True'

        return {
            'name': 'Excel for merge',
            'type': 'ir.actions.act_url',
            "url": str(base_url) + str(download_url),
            'target': 'self',
        }


class CrmTag(models.Model):
    _name = "s2u.crm.tag"
    _description = "CRM Tag"
    _order = "name"

    name = fields.Char(required=True, index=True, string='Tag')
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    migration_id = fields.Integer(string='Migration')
    color = fields.Integer(string='Color Index')
    color_select = fields.Selection([
        ('0', 'No color'),
        ('1', 'Dark orange'),
        ('2', 'Orange'),
        ('3', 'Yellow'),
        ('4', 'Light blue'),
        ('5', 'Brown'),
        ('6', 'Pink'),
        ('7', 'Turquoise'),
        ('8', 'Dark blue'),
        ('9', 'Red'),
        ('10', 'Green'),
        ('11', 'Purple'),
    ], required=True, default='0', string='Color')
    type = fields.Selection([
        ('entity', 'Entity'),
        ('contact', 'Contact'),
        ('all', 'All'),
    ], required=True, default='entity', string='Usability')

    @api.model
    def create(self, vals):

        if vals.get('color_select'):
            vals['color'] = int(vals['color_select'])
        elif vals.get('color'):
            vals['color_select'] = str(vals['color_select'])

        tag = super(CrmTag, self).create(vals)

        return tag

    @api.multi
    def write(self, vals):

        if vals.get('color_select'):
            vals['color'] = int(vals['color_select'])
        elif vals.get('color'):
            vals['color_select'] = str(vals['color'])

        res = super(CrmTag, self).write(vals)

        return res


class ResPartner(models.Model):

    _inherit = 'res.partner'

    @api.multi
    def write(self, vals):

        res = super(ResPartner, self).write(vals)
        if 'skip_res_partner_sync' not in self.env.context:
            for partner in self:
                entity = self.env['s2u.crm.entity'].sudo().search([('odoo_res_partner_id', '=', partner.id)], limit=1)
                if entity:
                    if entity.type == 'b2b':
                        if partner.company_name:
                            entity.with_context({'skip_res_partner_sync': True}).write({
                                'name': partner.company_name
                            })
                            contact = self.env['s2u.crm.entity.contact'].sudo().search([('entity_id', '=', entity.id)], limit=1)
                            if contact:
                                contact.with_context({'skip_res_partner_sync': True}).write({
                                    'phone': partner.phone,
                                    'email': partner.email
                                })
                            else:
                                self.env['s2u.crm.entity.contact'].sudo().with_context({'skip_res_partner_sync': True}).create({
                                    'entity_id': entity.id,
                                    'name': partner.name,
                                    'phone': partner.phone,
                                    'email': partner.email
                                })
                            address = self.env['s2u.crm.entity.address'].sudo().search([('entity_id', '=', entity.id),
                                                                                        ('type', '=', 'def')], limit=1)
                            if address:
                                address.with_context({'skip_res_partner_sync': True}).write({
                                    'address': partner.street,
                                    'city': partner.city,
                                    'zip': partner.zip,
                                    'country_id': partner.country_id.id if partner.country_id else False,
                                })
                            else:
                                self.env['s2u.crm.entity.address'].sudo().with_context({'skip_res_partner_sync': True}).create({
                                    'entity_id': entity.id,
                                    'type': 'def',
                                    'address': partner.street,
                                    'city': partner.city,
                                    'zip': partner.zip,
                                    'country_id': partner.country_id.id if partner.country_id else False,
                                })
                        else:
                            entity.with_context({'skip_res_partner_sync': True}).write({
                                'type': 'b2c',
                                'name': partner.name,
                                'address': partner.street,
                                'city': partner.city,
                                'zip': partner.zip,
                                'country_id': partner.country_id.id if partner.country_id else False,
                                'phone': partner.phone,
                                'email': partner.email
                            })
                    elif entity.type == 'b2c':
                        if partner.company_name:
                            entity.with_context({'skip_res_partner_sync': True}).write({
                                'type': 'b2b',
                                'name': partner.company_name
                            })
                            self.env['s2u.crm.entity.contact'].sudo().with_context({'skip_res_partner_sync': True}).create({
                                'entity_id': entity.id,
                                'name': partner.name,
                                'phone': partner.phone,
                                'email': partner.email
                            })
                            self.env['s2u.crm.entity.address'].sudo().with_context({'skip_res_partner_sync': True}).create({
                                'entity_id': entity.id,
                                'type': 'def',
                                'address': partner.street,
                                'city': partner.city,
                                'zip': partner.zip,
                                'country_id': partner.country_id.id if partner.country_id else False,
                            })
                        else:
                            entity.with_context({'skip_res_partner_sync': True}).write({
                                'name': partner.name,
                                'address': partner.street,
                                'city': partner.city,
                                'zip': partner.zip,
                                'country_id': partner.country_id.id if partner.country_id else False,
                                'phone': partner.phone,
                                'email': partner.email
                            })

        return res


class ResCompany(models.Model):

    _inherit = 'res.company'

    entity_id = fields.Many2one('s2u.crm.entity', string='Entity')
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address')
    migration_id = fields.Integer(string='Migration')
    font_style = fields.Char(string='Font style', default='font-family: Times New Roman; font-size:12px')
    image_footer = fields.Binary("Image Footer", attachment=True)


class CrmLead(models.Model):
    _name = "s2u.crm.lead"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "CRM Lead"

    company_name = fields.Char(index=True, string='Company')
    contact_name = fields.Char(index=True, string='Contact')
    prefix = fields.Char(string='Prefix')
    address = fields.Char(index=True, string='Address')
    zip = fields.Char(index=True, string='Zip')
    city = fields.Char(index=True, string='City')
    country_id = fields.Many2one('res.country', string='Country')
    tinno = fields.Char('TIN no.')
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    phone = fields.Char(index=True, string='Phone')
    fax = fields.Char(index=True, string='Fax')
    mobile = fields.Char(index=True, string='Mobile')
    email = fields.Char(index=True, string='eMail')
    website = fields.Char(index=True, string='Website')
    skype = fields.Char(index=True, string='Skype')
    c_of_c = fields.Char(string='Chamber of Commerce', index=True)
    date_lead = fields.Date(string='Lead Date', index=True, copy=False,
                            default=lambda self: fields.Date.context_today(self))
    info = fields.Text(string='Info')
    state = fields.Selection([
        ('new', 'New'),
        ('entity', 'Entity'),
        ('contact', 'Contact'),
        ('later', 'Later'),
    ], required=True, default='new', string='State', index=True)
    migration_id = fields.Integer(string='Migration')

    @api.multi
    def action_later(self):
        self.ensure_one()
        self.write({
            'state': 'later'
        })

    def convert_lead(self):

        entity_model = self.env['s2u.crm.entity']

        if not (self.phone or self.email):
            raise UserError(_('A phone or email address is required!'))

        if self.phone and self.email:
            entities = entity_model.search(['|', ('phone', '=', self.phone),
                                                 ('email', '=', self.email)])
        elif self.phone:
            entities = entity_model.search([('phone', '=', self.phone)])
        else:
            entities = entity_model.search([('email', '=', self.email)])

        if entities:
            if self.company_name:
                raise UserError(_('Entity with this phone and/or mail address is already present!'))
            else:
                raise UserError(_('Contact with this phone and/or mail address is already present!'))

        if self.company_name:
            entity_vals = {
                'type': 'b2b',
                'name': self.company_name,
                'tinno': self.tinno,
                'phone': self.phone,
                'fax': self.fax,
                'mobile': self.mobile,
                'email': self.email,
                'website': self.website,
                'skype': self.skype,
                'c_of_c ': self.c_of_c
            }
        elif self.contact_name:
            entity_vals = {
                'type': 'b2c',
                'name': self.contact_name,
                'phone': self.phone,
                'fax': self.fax,
                'mobile': self.mobile,
                'email': self.email,
                'website': self.website,
                'skype': self.skype,
                'address': self.address,
                'zip': self.zip,
                'city': self.city,
                'country_id': self.country_id.id if self.country_id else False
            }
        else:
            raise UserError(_('Company or contact should be present to convert!'))

        entity = entity_model.create(entity_vals)

        if self.company_name:
            if self.address:
                address_vals = {
                    'entity_id': entity.id,
                    'address': self.address,
                    'zip': self.zip,
                    'city': self.city,
                    'country_id': self.country_id.id if self.country_id else False
                }

                self.env['s2u.crm.entity.address'].create(address_vals)

            if self.contact_name:
                contact_vals = {
                    'entity_id': entity.id,
                    'prefix': self.prefix,
                    'name': self.contact_name,
                    'phone': self.phone,
                    'mobile': self.mobile,
                    'email': self.email,
                    'skype': self.skype
                }
                self.env['s2u.crm.entity.contact'].create(contact_vals)

        return entity

    @api.multi
    def action_convert(self):
        self.ensure_one()

        entity = self.convert_lead()

        if entity.type == 'b2b':
            self.write({
                'state': 'entity'
            })
        else:
            self.write({
                'state': 'contact'
            })


class CrmEntityMessage(models.Model):
    _name = "s2u.crm.entity.message"
    _description = "CRM Entity message"
    _order = "dt_message desc"

    entity_id = fields.Many2one('s2u.crm.entity', string='Company', ondelete='cascade', required=True)
    dt_message = fields.Datetime(string='Date/time', index=True, copy=False,
                                 default=lambda self: fields.Datetime.now())
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address')
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact')
    message = fields.Html(string='Message')
    type = fields.Selection([
        ('note', 'Note'),
        ('inbox', 'Inbox'),
        ('sent', 'Sent'),
    ], required=True, default='note', string='Type')
    subject = fields.Char(string='Subject')
    migration_id = fields.Integer(string='Migration')



class CrmFavorite(models.Model):
    _name = "s2u.crm.favorite"
    _description = "CRM Favorites"

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Id.', required=True, index=True)
    migration_id = fields.Integer(string='Migration')
