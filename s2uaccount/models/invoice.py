# -*- coding: utf-8 -*-

import uuid
import datetime
from lxml import etree
import io
import base64
import xlsxwriter

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class AccountInvoiceVat(models.Model):
    _name = "s2u.account.invoice.vat"
    _description = "Invoice vat"
    _order = "vat_code"

    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True)
    net_amount = fields.Monetary(string='Net', currency_field='currency_id')
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id')
    vat_id = fields.Many2one('s2u.account.vat', string='VAT')
    vat_code = fields.Char(string='VAT code')
    vat_name = fields.Char(string='VAT name')


class AccountInvoiceLineDetailed(models.Model):
    _name = "s2u.account.invoice.line.detailed"
    _order = 'sequence'

    line_id = fields.Many2one('s2u.account.invoice.line', string='Line', required=True, ondelete='cascade')
    detailed_label = fields.Char(string='Label', required=True)
    detailed_info = fields.Text(string='Details')
    sequence = fields.Integer(string='Sequence', default=10)


class AccountInvoiceLine(models.Model):
    _name = "s2u.account.invoice.line"
    _description = "Invoice line"

    @api.multi
    @api.constrains('vat_id')
    def _check_tinno_obligatory(self):
        for line in self:
            if line.vat_id and line.vat_id.tinno_obligatory:
                if not line.invoice_id.partner_id.tinno:
                    raise ValueError(_('Your debitor %s needs to have a valid TIN number!'
                                       % line.invoice_id.partner_id.name))

    @api.one
    @api.depends('net_amount', 'vat_amount')
    def _compute_gross_amount(self):
        if self.vat_id:
            self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)
        else:
            self.gross_amount = self.net_amount

    @api.one
    def _compute_price_after_discount(self):
        if self.discount:
            self.net_price_after_discount = round(self.net_price - (self.net_price * self.discount / 100.0), 2)
        else:
            self.net_price_after_discount = self.net_price

    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True)
    gross_amount = fields.Monetary(string='Gross', currency_field='currency_id',
                                   store=True, readonly=True, compute='_compute_gross_amount')
    net_amount = fields.Monetary(string='Net', currency_field='currency_id')
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id')
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 domain=[('type', '=', 'income')])
    vat_id = fields.Many2one('s2u.account.vat', string='VAT', required=True, domain=[('type', '=', 'sell')])
    descript = fields.Char(string='Description', required=True)
    financial_date = fields.Date(related='invoice_id.date_financial', store=True, readonly=True, index=True)
    qty = fields.Char(string='Qty', required=True, default='1 stuks')
    net_price = fields.Monetary(string='Price', currency_field='currency_id')
    net_price_after_discount = fields.Monetary(string='Price after discount', currency_field='currency_id',
                                               readonly=True, compute='_compute_price_after_discount')
    price_per = fields.Selection([
        ('item', 'Item'),
        ('10', 'per 10'),
        ('100', 'per 100'),
        ('1000', 'per 1000'),
        ('total', 'Total')
    ], required=True, default='item', string='Per')
    detailed_ids = fields.One2many('s2u.account.invoice.line.detailed', 'line_id',
                                   string='Details', copy=True)
    analytic_id = fields.Many2one('s2u.account.analytic', string='Analytic', ondelete='set null')
    discount = fields.Float(string='Discount', default='0.0')

    @api.onchange('account_id')
    def _onchange_account_id(self):
        if not self.account_id:
            return False
        if self.account_id.vat_id:
            self.vat_id = self.account_id.vat_id
        return False

    @api.onchange('qty', 'net_price', 'price_per', 'discount')
    def _onchange_qty_price(self):
        qty = self.env['s2u.baseproduct.abstract'].parse_qty(self.qty)
        if not qty:
            return False
        if not self.net_price:
            return False

        if self.price_per == 'total':
            if self.discount:
                self.net_amount = round(self.net_price - (self.net_price * self.discount / 100.0), 2)
            else:
                self.net_amount = round(self.net_price, 2)
        elif self.price_per == 'item':
            if self.discount:
                self.net_amount = round((qty * self.net_price) - ((qty * self.net_price) * self.discount / 100.0), 2)
            else:
                self.net_amount = round(qty * self.net_price, 2)
        elif self.price_per in ['10', '100', '1000']:
            qty = qty / float(self.price_per)
            if self.discount:
                self.net_amount = round((qty * self.net_price) - ((qty * self.net_price) * self.discount / 100.0), 2)
            else:
                self.net_amount = round(qty * self.net_price, 2)
        return False

    @api.onchange('vat_id')
    def _onchange_vat_id(self):
        if not self.vat_id:
            self.gross_amount = self.net_amount
            self.vat_amount = 0.0
            return False

        self.vat_amount = self.vat_id.calc_vat_from_netto_amount(self.net_amount)
        self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)

    @api.onchange('net_amount')
    def _onchange_net_amount(self):
        if not self.vat_id:
            self.gross_amount = self.net_amount
            self.vat_amount = 0.0
            return False

        self.vat_amount = self.vat_id.calc_vat_from_netto_amount(self.net_amount)
        self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)

    @api.onchange('vat_amount')
    def _onchange_vat_amount(self):
        if not self.vat_id:
            self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)
            return False

        self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)


class AccountInvoiceDetailed(models.Model):
    _name = "s2u.account.invoice.detailed"
    _order = 'sequence'

    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', required=True, ondelete='cascade')
    detailed_label = fields.Char(string='Label', required=True)
    detailed_info = fields.Text(string='Details')
    sequence = fields.Integer(string='Sequence', default=10)


class AccountInvoice(models.Model):
    _name = "s2u.account.invoice"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Sales invoice"
    _order = "id desc"

    @api.multi
    @api.constrains('type', 'partner_id', 'contact_id', 'address_id')
    def _check_address_entity(self):
        for invoice in self:
            if invoice.type == 'b2b':
                if invoice.partner_id.type != 'b2b':
                    raise ValueError(_('Please select a b2b debitor!'))
                if invoice.contact_id and invoice.contact_id.entity_id != invoice.partner_id:
                    raise ValueError(_('Contact does not belong to the selected debitor!'))
                if invoice.address_id and invoice.address_id.entity_id != invoice.partner_id:
                    raise ValueError(_('Address does not belong to the selected debitor!'))
            else:
                if invoice.partner_id.type != 'b2c':
                    raise ValueError(_('Please select a b2c debitor!'))

    @api.model
    def _default_account(self):
        domain = [
            ('type', '=', 'receivable'),
        ]
        return self.env['s2u.account.account'].search(domain, limit=1)

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.account.invoice')])
        if not exists:
            raise ValueError(_('Sequence for creating invoice number not exists!'))

        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.one
    @api.depends('line_ids.gross_amount', 'line_ids.net_amount', 'line_ids.vat_amount')
    def _compute_amount(self):
        self.amount_net = sum(line.net_amount for line in self.line_ids)
        self.amount_vat = sum(line.vat_amount for line in self.line_ids)
        self.amount_gross = sum(line.gross_amount for line in self.line_ids)

    def compute_open(self, amount_open, invoice_id):

        bank_accounting_model = self.env['s2u.account.bank.account']
        memorial_accounting_model = self.env['s2u.account.memorial.account']

        transactions = bank_accounting_model.search([('so_invoice_id', '=', invoice_id)])
        for trans in transactions:
            amount_open += trans.debit
            amount_open -= trans.credit
        transactions = memorial_accounting_model.search([('so_invoice_id', '=', invoice_id)])
        for trans in transactions:
            amount_open += trans.debit
            amount_open -= trans.credit

        return amount_open

    @api.one
    @api.depends('amount_gross',
                 'transactions_bank.debit', 'transactions_bank.credit',
                 'transactions_memorial.debit', 'transactions_memorial.credit',
                 'creditnota_id')
    def _compute_open(self):

        amount_open = self.compute_open(self.amount_gross, self.id)
        amount_open += self.creditnota_id.amount_gross

        self.amount_open = amount_open

    @api.multi
    def sync_open(self):

        for inv in self:
            current_state = inv.paid_state

            amount_open = inv.compute_open(inv.amount_gross, inv.id)
            amount_open += inv.creditnota_id.amount_gross

            vals = {
                'amount_open': amount_open
            }
            if round(amount_open, 2) <= 0.0 and inv.paid_state == 'open' and not inv.creditnota_id:
                vals['paid_state'] = 'paid'
            elif round(amount_open, 2) > 0.0 and inv.paid_state == 'paid' and not inv.creditnota_id:
                vals['paid_state'] = 'open'

            inv.write(vals)

            if round(amount_open, 2) <= 0.0 and not inv.creditnota_id:
                if current_state == 'open':
                    inv.invoice_paid()
            elif round(amount_open, 2) > 0.0 and not inv.creditnota_id:
                if current_state == 'paid':
                    inv.invoice_not_paid()

    @api.one
    @api.depends('date_invoice')
    def _compute_invoice_year(self):
        if not self.date_invoice:
            self.year_invoice = False
        else:
            invdat = datetime.datetime.strptime(self.date_invoice, '%Y-%m-%d')
            self.year_invoice = invdat.strftime("%Y")

    @api.one
    @api.depends('date_invoice')
    def _compute_invoice_month(self):
        if not self.date_invoice:
            self.month_invoice = False
        else:
            invdat = datetime.datetime.strptime(self.date_invoice, '%Y-%m-%d')
            self.month_invoice = "%02d (%s)" % (invdat.month, invdat.strftime("%B"))

    @api.multi
    def get_vat_values(self):
        vat_grouped = {}
        for line in self.line_ids:
            if not line.vat_id:
                continue
            if line.vat_id.id in vat_grouped:
                vat_grouped[line.vat_id.id]['net_amount'] += line.net_amount
                vat_grouped[line.vat_id.id]['vat_amount'] += line.vat_amount
            else:
                vat_grouped[line.vat_id.id] = {
                    'invoice_id': self.id,
                    'vat_id': line.vat_id.id,
                    'vat_code': line.vat_id.code,
                    'vat_name': line.vat_id.name,
                    'net_amount': line.net_amount,
                    'vat_amount': line.vat_amount
                }

        return vat_grouped

    @api.multi
    def compute_vats(self):
        account_invoice_vat = self.env['s2u.account.invoice.vat']
        for invoice in self:
            self._cr.execute("DELETE FROM s2u_account_invoice_vat WHERE invoice_id=%s", (invoice.id,))
            self.invalidate_cache()

            vat_grouped = invoice.get_vat_values()

            for vat in vat_grouped.values():
                account_invoice_vat.create(vat)

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        vat_grouped = self.get_vat_values()
        vat_lines = self.vat_ids.browse([])
        for vat in vat_grouped.values():
            vat_lines += vat_lines.new(vat)
        self.vat_ids = vat_lines

    @api.onchange('partner_id', 'date_invoice')
    def _onchange_partner_date_invoice(self):
        if self.partner_id and self.partner_id.payment_term_id:
            if self.date_invoice:
                due_date = datetime.datetime.strptime(self.date_invoice, "%Y-%m-%d")
                due_date = due_date + datetime.timedelta(days=self.partner_id.payment_term_id.payment_terms)
                self.date_due = due_date.strftime('%Y-%m-%d')

    @api.onchange('date_invoice')
    def _onchange_date_invoice(self):
        if self.date_invoice:
            self.date_financial = self.date_invoice

    @api.onchange('contact_id')
    def _onchange_contact(self):
        if self.contact_id:
            if self.contact_id.address_id:
                self.address_id = self.contact_id.address_id

    @api.one
    def _compute_payment_terms(self):
        if self.partner_id and self.partner_id.payment_term_id:
            self.payment_terms = _('Betaling binnen %d dagen onder vermelding van factuurnummer.') % self.partner_id.payment_term_id.payment_terms
        else:
            self.payment_terms = ''

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'draft':
            return 's2uaccount.mt_invoice_so_created'
        elif 'state' in init_values and self.state == 'proforma':
            return 's2uaccount.mt_invoice_so_proforma'
        elif 'state' in init_values and self.state == 'invoiced':
            return 's2uaccount.mt_invoice_so_validated'
        elif 'state' in init_values and self.state == 'reopen':
            return 's2uaccount.mt_invoice_so_reopened'
        elif 'state' in init_values and self.state == 'cancel':
            return 's2uaccount.mt_invoice_so_canceled'

        return super(AccountInvoice, self)._track_subtype(init_values)

    @api.multi
    def invoice_paid(self):
        """
        This method if fired when an invoice is paid (amount_open <= 0.0).
        Purpose is to overwrite the method in other modules, who needs
        to react on paid invoices.
        :return:
        """

        self.ensure_one()

        self.message_post(_('Invoice is paid.'))

        return True

    @api.multi
    def invoice_not_paid(self):
        """
        This method if fired when a paid invoice is reverted (payment is undone).
        Purpose is to overwrite the method in other modules, who needs
        to react on paid/not paid invoices.
        :return:
        """

        self.ensure_one()

        self.message_post(_('Invoice is not paid.'))

        return True

    @api.multi
    def _compute_email_address(self):

        if self.type == 'b2b':
            if self.address_id and self.address_id.inv_by_mail and self.address_id.email:
                self.use_email_address = self.address_id.email
            elif self.contact_id and self.contact_id.email:
                self.use_email_address = self.contact_id.email
            elif self.partner_id.email:
                self.use_email_address = self.partner_id.email
            else:
                self.use_email_address = False
        else:
            if self.partner_id.email:
                self.use_email_address = self.partner_id.email
            else:
                self.use_email_address = False

    def _get_default_access_token(self):
        return str(uuid.uuid4())

    def _compute_is_expired(self):
        now = datetime.datetime.now()
        for invoice in self:
            if invoice.date_due and fields.Datetime.from_string(invoice.date_due) < now:
                invoice.is_expired = True
            else:
                invoice.is_expired = False

    def _get_document_count(self):

        for sale in self:
            docs = self.env['s2u.document'].search([('res_model', '=', 's2u.account.invoice'),
                                                    ('res_id', '=', sale.id)])
            sale.document_count = len(docs.ids)

    @api.multi
    def action_view_document(self):
        action = self.env.ref('s2udocument.action_document').read()[0]
        action['domain'] = [('res_model', '=', 's2u.account.invoice'),
                            ('res_id', '=', self.id)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.partner_id.id,
            'default_doc_context': self._description if self._description else self._name,
            'default_rec_context': self.name,
            'default_res_model': 's2u.account.invoice',
            'default_res_id': self.id
        }
        action['context'] = str(context)
        return action

    @api.multi
    def action_excel(self):

        self.ensure_one()

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
        worksheet.write('J1', 'Invoice', bold)
        worksheet.write('K1', 'Descript', bold)

        if self.type == 'b2b':
            worksheet.write('A2', self.partner_id.name)
            if self.contact_id:
                if self.contact_id.prefix:
                    worksheet.write('B2', self.contact_id.prefix)
                else:
                    worksheet.write('B2', self.contact_id.name)
                if self.contact_id.communication:
                    worksheet.write('G2', self.contact_id.communication)
                if self.contact_id.prefix:
                    worksheet.write('H2', self.contact_id.prefix)
            if self.address_id:
                worksheet.write('C2', self.address_id.address)
                worksheet.write('D2', self.address_id.zip)
                worksheet.write('E2', self.address_id.city)
                worksheet.write('F2', self.address_id.country_id.name)
        else:
            if self.partner_id.prefix:
                worksheet.write('B2', self.partner_id.prefix)
            else:
                worksheet.write('B2', self.partner_id.name)
            worksheet.write('C2', self.partner_id.address)
            worksheet.write('D2', self.partner_id.zip)
            worksheet.write('E2', self.partner_id.city)
            worksheet.write('F2', self.partner_id.country_id.name)
            if self.partner_id.communication:
                worksheet.write('G2', self.partner_id.communication)
            if self.partner_id.prefix:
                worksheet.write('H2', self.partner_id.prefix)

        if self.partner_id.image and self.partner_id.image_fname:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            image_url = '%s/crm/logo/%d/%s' % (base_url, self.partner_id.id, self.partner_id.entity_code)
            worksheet.write('I2', image_url)

        worksheet.write('J2', self.name)
        worksheet.write('K2', self.reference if self.reference else '')

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

    _invoice_state = {
        'draft': [('readonly', False)],
        'proforma': [('readonly', False)],
        'reopen': [('readonly', False)],
    }

    name = fields.Char(string='Number', required=True, index=True, copy=False,
                       default='Concept')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency,
                                  readonly=True, states=_invoice_state)
    line_ids = fields.One2many('s2u.account.invoice.line', 'invoice_id',
                               string='Lines', copy=True, readonly=True, states=_invoice_state)
    vat_ids = fields.One2many('s2u.account.invoice.vat', 'invoice_id',
                               string='VAT summary', copy=True)
    date_invoice = fields.Date(string='Invoice Date', index=True, copy=False,
                               default=lambda self: fields.Date.context_today(self),
                               readonly=True, states=_invoice_state)
    year_invoice = fields.Char(string='Invoice Year',
                               store=True, readonly=True, compute='_compute_invoice_year')
    month_invoice = fields.Char(string='Invoice Month',
                                store=True, readonly=True, compute='_compute_invoice_month')
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 default=_default_account, domain=[('type', '=', 'receivable')],
                                 readonly=True, states=_invoice_state)
    amount_net = fields.Monetary(string='Amount Net',
                                 store=True, readonly=True, compute='_compute_amount')
    amount_vat = fields.Monetary(string='Amount VAT',
                                 store=True, readonly=True, compute='_compute_amount')
    amount_gross = fields.Monetary(string='Amount Gross',
                                   store=True, readonly=True, compute='_compute_amount')
    amount_open = fields.Monetary(string='Amount Open',
                                  store=True, readonly=True, compute='_compute_open')
    type = fields.Selection([
        ('b2c', 'B2C'),
        ('b2b', 'B2B'),
    ], required=True, default='b2b', string='Type', index=True, readonly=True, states=_invoice_state)
    partner_id = fields.Many2one('s2u.crm.entity', string='Debitor', required=True, index=True, readonly=True, states=_invoice_state)
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True, readonly=True, states=_invoice_state)
    address_id = fields.Many2one('s2u.crm.entity.address', string='Address', index=True, readonly=True, states=_invoice_state)
    date_due = fields.Date(string='Date due', index=True, copy=False, readonly=True, states=_invoice_state)
    customer_code = fields.Char(string='Your reference', index=True, readonly=True, states=_invoice_state)
    reference = fields.Char(string='Our reference', index=True, readonly=True, states=_invoice_state)
    remarks = fields.Text('Remarks', readonly=True, states=_invoice_state)
    date_financial = fields.Date(string='Financial Date', index=True, copy=False,
                                 default=lambda self: fields.Date.context_today(self), readonly=True, states=_invoice_state)
    transactions_bank = fields.One2many('s2u.account.bank.account', 'so_invoice_id',
                                        string='Trans. Bank', copy=False)
    transactions_memorial = fields.One2many('s2u.account.memorial.account', 'so_invoice_id',
                                            string='Trans. Bank', copy=False)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('proforma', 'Proforma'),
        ('invoiced', 'Invoiced'),
        ('reopen', 'Reopened'),
        ('canceled', 'Canceled'),
    ], required=True, default='draft', string='State', index=True, copy=False, track_visibility='onchange')
    creditnota_id = fields.Many2one('s2u.account.invoice', string='Creditnota', ondelete='set null', copy=False)
    detailed_ids = fields.One2many('s2u.account.invoice.detailed', 'invoice_id',
                                   string='Details', copy=True, readonly=True, states=_invoice_state)
    project = fields.Char(string='Project', index=True, readonly=True, states=_invoice_state)
    payment_terms = fields.Char(string='Terms', readonly=True, compute='_compute_payment_terms')
    delivery_address = fields.Text(string='Address')
    delivery_country_id = fields.Many2one('res.country', string='Leveringsland')
    delivery_tinno = fields.Char('TIN no.')
    delivery_ref = fields.Char('Shipment ref.')
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_invoice_state)
    paid_state = fields.Selection([
        ('open', 'Open'),
        ('paid', 'Paid')
    ], required=True, default='open', string='Payment state', index=True, copy=False)
    use_email_address = fields.Char(string='Address for mail', readonly=True, compute='_compute_email_address')
    alert_for_send = fields.Boolean(string='Alert for send', default=False, index=True)
    access_token = fields.Char('Security Token', copy=False, default=_get_default_access_token)
    is_expired = fields.Boolean(compute='_compute_is_expired', string="Is expired")
    document_count = fields.Integer(string='# of Docs', compute='_get_document_count', readonly=True)

    @api.model
    def create(self, vals):

        invoice = super(AccountInvoice, self).create(vals)
        invoice.compute_vats()

        return invoice

    @api.multi
    def write(self, vals):

        res = super(AccountInvoice, self).write(vals)
        for invoice in self:
            invoice.compute_vats()

        return res

    @api.one
    def unlink(self):

        if self.state not in ['draft', 'reopen', 'proforma']:
            raise UserError(_('Only a concept invoice can be deleted, you have to cancel the invoice!'))

        olddocs = self.env['ir.attachment'].sudo().search([('res_model', '=', 's2u.account.invoice'),
                                                           ('res_id', '=', self.id)])
        olddocs.unlink()

        if self.creditnota_id:
            amount_open = self.compute_open(self.creditnota_id.amount_gross, self.creditnota_id.id)
            self.creditnota_id.write({
                'amount_open': amount_open
            })

        res = super(AccountInvoice, self).unlink()

        return res

    @api.multi
    def copy(self, default=None):

        new_inv = super(AccountInvoice, self).copy(default=default)

        # trigger onchange to set date_due
        new_inv._onchange_partner_date_invoice()

        return new_inv

    def ubl_add_party(self, ns_cac, ns_cbc, root_element, partner, postal_address, physical_address,
                      add_identification=False, add_taxscheme=False):
        def add_address(adr_elem, address):
            if address.address:
                elem = etree.SubElement(adr_elem, '{%s}StreetName' % ns_cbc)
                elem.text = address.address
            if address.city:
                elem = etree.SubElement(adr_elem, '{%s}CityName' % ns_cbc)
                elem.text = address.city
            if address.zip:
                elem = etree.SubElement(adr_elem, '{%s}PostalZone' % ns_cbc)
                elem.text = address.zip
            if address.country_id:
                country_elem = etree.SubElement(adr_elem, '{%s}Country' % ns_cac)
                elem = etree.SubElement(country_elem, '{%s}IdentificationCode' % ns_cbc)
                elem.text = address.country_id.code

        party_elem = etree.SubElement(root_element, '{%s}Party' % ns_cac)
        if add_identification:
            ident_elem = etree.SubElement(party_elem, '{%s}PartyIdentification' % ns_cac)
            elem = etree.SubElement(ident_elem, '{%s}ID' % ns_cbc)
            if partner.c_of_c:
                elem.text = partner.c_of_c
                # TODO: handle different countries
                elem.set('schemeAgencyID', 'NL')
                elem.set('schemeAgencyName', 'KVK')

        name_elem = etree.SubElement(party_elem, '{%s}PartyName' % ns_cac)
        elem = etree.SubElement(name_elem, '{%s}Name' % ns_cbc)
        if partner.name:
            elem.text = partner.name

        if postal_address:
            postal_elem = etree.SubElement(party_elem, '{%s}PostalAddress' % ns_cac)
            add_address(postal_elem, postal_address)

        if physical_address:
            physical_elem = etree.SubElement(party_elem, '{%s}PhysicalLocation' % ns_cac)
            physical_elem = etree.SubElement(physical_elem, '{%s}Address' % ns_cac)
            add_address(physical_elem, physical_address)

        contact_elem = etree.SubElement(party_elem, '{%s}Contact' % ns_cac)
        elem = etree.SubElement(contact_elem, '{%s}Telephone' % ns_cbc)
        if partner.phone:
            elem.text = partner.phone
        elem = etree.SubElement(contact_elem, '{%s}ElectronicMail' % ns_cbc)
        if partner.email:
            elem.text = partner.email

        if add_taxscheme:
            scheme_elem = etree.SubElement(party_elem, '{%s}PartyTaxScheme' % ns_cac)
            elem = etree.SubElement(scheme_elem, '{%s}RegistrationName' % ns_cbc)
            if partner.name:
                elem.text = partner.name
            elem = etree.SubElement(scheme_elem, '{%s}CompanyID' % ns_cbc)
            if partner.tinno:
                elem.text = partner.tinno
            tax_elem = etree.SubElement(scheme_elem, '{%s}TaxScheme' % ns_cac)
            elem = etree.SubElement(tax_elem, '{%s}ID' % ns_cbc)
            # TODO: get taxscheme name from accounting
            elem.text = 'VAT'
            elem = etree.SubElement(tax_elem, '{%s}TaxTypeCode' % ns_cbc)
            # TODO: get taxscheme name from accounting
            elem.text = 'VAT'


        return True

    def ubl_add_legal(self, ns_cac, ns_cbc, root_element, invoice):
        total_elem = etree.SubElement(root_element, '{%s}LegalMonetaryTotal' % ns_cac)
        elem = etree.SubElement(total_elem, '{%s}LineExtensionAmount' % ns_cbc)
        elem.text = '%0.2f' % invoice.amount_net
        elem.set('currencyID', 'EUR')
        elem = etree.SubElement(total_elem, '{%s}TaxExclusiveAmount' % ns_cbc)
        elem.text = '%0.2f' % invoice.amount_net
        elem.set('currencyID', 'EUR')
        elem = etree.SubElement(total_elem, '{%s}TaxInclusiveAmount' % ns_cbc)
        elem.text = '%0.2f' % invoice.amount_gross
        elem.set('currencyID', 'EUR')
        elem = etree.SubElement(total_elem, '{%s}PayableAmount' % ns_cbc)
        elem.text = '%0.2f' % invoice.amount_gross
        elem.set('currencyID', 'EUR')

    def ubl_add_tax(self, ns_cac, ns_cbc, root_element, invoice):
        total_elem = etree.SubElement(root_element, '{%s}TaxTotal' % ns_cac)
        elem = etree.SubElement(total_elem, '{%s}TaxAmount' % ns_cbc)
        elem.text = '%0.2f' % invoice.amount_vat
        elem.set('currencyID', 'EUR')

        for vat in invoice.vat_ids:
            subtotal_elem = etree.SubElement(total_elem, '{%s}TaxSubtotal' % ns_cac)
            elem = etree.SubElement(subtotal_elem, '{%s}TaxableAmount' % ns_cbc)
            elem.text = '%0.2f' % vat.net_amount
            elem.set('currencyID', 'EUR')
            elem = etree.SubElement(subtotal_elem, '{%s}TaxAmount' % ns_cbc)
            elem.text = '%0.2f' % vat.vat_amount
            elem.set('currencyID', 'EUR')
            elem = etree.SubElement(subtotal_elem, '{%s}Percent' % ns_cbc)
            elem.text = str(vat.vat_id.calc_vat(100.0))
            category_elem = etree.SubElement(subtotal_elem, '{%s}TaxCategory' % ns_cac)
            elem = etree.SubElement(category_elem, '{%s}Percent' % ns_cbc)
            elem.text = str(vat.vat_id.calc_vat(100.0))
            etree.SubElement(category_elem, '{%s}TaxScheme' % ns_cac)

    def ubl_add_inv_line(self, ns_cac, ns_cbc, root_element, line):
        line_elem = etree.SubElement(root_element, '{%s}InvoiceLine' % ns_cac)
        elem = etree.SubElement(line_elem, '{%s}ID' % ns_cbc)
        elem.text = str(line.id)

        # TODO: add qty to invoice lines
        elem = etree.SubElement(line_elem, '{%s}InvoicedQuantity' % ns_cbc)
        elem.text = '1'

        elem = etree.SubElement(line_elem, '{%s}Note' % ns_cbc)
        elem.text = line.descript

        elem = etree.SubElement(line_elem, '{%s}LineExtensionAmount' % ns_cbc)
        elem.text = '%0.2f' % line.net_amount
        elem.set('currencyID', 'EUR')

        total_elem = etree.SubElement(line_elem, '{%s}TaxTotal' % ns_cac)
        elem = etree.SubElement(total_elem, '{%s}TaxAmount' % ns_cbc)
        elem.text = '%0.2f' % line.vat_amount
        elem.set('currencyID', 'EUR')

        if line.vat_id:
            subtotal_elem = etree.SubElement(total_elem, '{%s}TaxSubtotal' % ns_cac)
            elem = etree.SubElement(subtotal_elem, '{%s}TaxableAmount' % ns_cbc)
            elem.text = '%0.2f' % line.net_amount
            elem.set('currencyID', 'EUR')
            elem = etree.SubElement(subtotal_elem, '{%s}TaxAmount' % ns_cbc)
            elem.text = '%0.2f' % line.vat_amount
            elem.set('currencyID', 'EUR')
            elem = etree.SubElement(subtotal_elem, '{%s}Percent' % ns_cbc)
            elem.text = str(line.vat_id.calc_vat(100.0))

            category_elem = etree.SubElement(subtotal_elem, '{%s}TaxCategory' % ns_cac)
            elem = etree.SubElement(category_elem, '{%s}Percent' % ns_cbc)
            elem.text = str(line.vat_id.calc_vat(100.0))
            etree.SubElement(category_elem, '{%s}TaxScheme' % ns_cac)

        item_elem = etree.SubElement(line_elem, '{%s}Item' % ns_cac)
        elem = etree.SubElement(item_elem, '{%s}Description' % ns_cbc)
        elem.text = line.descript
        # TODO: integrate s2u.sale.product
        elem = etree.SubElement(item_elem, '{%s}Name' % ns_cbc)
        elem.text = line.descript
        if line.vat_id:
            class_elem = etree.SubElement(item_elem, '{%s}ClassifiedTaxCategory' % ns_cac)
            elem = etree.SubElement(class_elem, '{%s}Percent' % ns_cbc)
            elem.text = str(line.vat_id.calc_vat(100.0))
            etree.SubElement(class_elem, '{%s}TaxScheme' % ns_cac)

        price_elem = etree.SubElement(line_elem, '{%s}Price' % ns_cac)
        elem = etree.SubElement(price_elem, '{%s}PriceAmount' % ns_cbc)
        # TODO: integrate invoice qty to calculate item price
        elem.text = '%0.2f' % line.net_amount
        elem.set('currencyID', 'EUR')

    @api.multi
    def create_ubl(self):
        ns_cac = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
        ns_cbc = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
        for invoice in self:
            invoice_ns = {
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'xsd': 'http://www.w3.org/2001/XMLSchema',
                'qdt': 'urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2',
                'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
                'udt': 'urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2',
                'cac': ns_cac,
                'cbc': ns_cbc
            }

            root = etree.Element('Invoice', xmlns='urn:oasis:names:specification:ubl:schema:xsd:Invoice-2', nsmap=invoice_ns)

            elem = etree.SubElement(root, '{%s}UBLVersionID' % ns_cbc)
            elem.text = '2.0'
            elem = etree.SubElement(root, '{%s}CustomizationID' % ns_cbc)
            elem.text = 'Solution2use framework for Odoo'
            elem = etree.SubElement(root, '{%s}ID' % ns_cbc)
            elem.text = invoice.name
            elem = etree.SubElement(root, '{%s}IssueDate' % ns_cbc)
            elem.text = invoice.date_invoice
            elem = etree.SubElement(root, '{%s}InvoiceTypeCode' % ns_cbc)
            if invoice.amount_gross >= 0.0:
                elem.text = '380'
            else:
                elem.text = '381'
            elem = etree.SubElement(root, '{%s}DocumentCurrencyCode' % ns_cbc)
            #TODO: multi currency
            elem.text = 'EUR'

            supplier_party = etree.SubElement(root, '{%s}AccountingSupplierParty' % ns_cac)
            postal_address = False
            physical_address = False
            if invoice.company_id.entity_id:
                postal_address = invoice.company_id.entity_id.get_postal()
                physical_address = invoice.company_id.entity_id.get_physical()
            self.ubl_add_party(ns_cac, ns_cbc, supplier_party,
                               invoice.company_id.entity_id, postal_address, physical_address,
                               add_identification=True, add_taxscheme=True)

            customer_party = etree.SubElement(root, '{%s}AccountingCustomerParty' % ns_cac)
            postal_address = False
            physical_address = False
            if invoice.partner_id:
                postal_address = invoice.partner_id.get_postal()
                physical_address = invoice.partner_id.get_physical()
            self.ubl_add_party(ns_cac, ns_cbc, customer_party, invoice.partner_id, postal_address, physical_address)

            self.ubl_add_tax(ns_cac, ns_cbc, root, invoice)
            self.ubl_add_legal(ns_cac, ns_cbc, root, invoice)
            for line in invoice.line_ids:
                self.ubl_add_inv_line(ns_cac, ns_cbc, root, line)

            xml_string = etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True)
            return xml_string

    @api.multi
    def do_validate(self):
        """This method does the same as action_validate, but without returning the pdf. It should be
        used from within other modules when creating and validating invoices automatically."""

        self.ensure_one()

        olddocs = self.env['ir.attachment'].sudo().search([('res_model', '=', 's2u.account.invoice'),
                                                           ('res_id', '=', self.id)])
        olddocs.unlink()

        if self.state in ['draft', 'proforma']:
            self.write({
                'name': self._new_number(),
                'state': 'invoiced'
            })
        else:
            self.write({
                'state': 'invoiced'
            })

        return True

    @api.multi
    def action_validate(self):
        """This method is used within the xml view when button validate is pressed"""

        self.ensure_one()

        # cleanup old docs, not needed here
        attachments = self.env['ir.attachment'].sudo().search([('res_model', '=', 's2u.account.invoice'),
                                                               ('res_id', '=', self.id),
                                                               ('name', '=', 'Invoice-%s.pdf' % self.name.replace('/',''))])
        attachments.unlink()

        if self.state in ['draft', 'proforma']:
            self.write({
                'name': self._new_number(),
                'state': 'invoiced'
            })
        else:
            self.write({
                'state': 'invoiced'
            })

        return self.env.ref('s2uaccount.s2uaccount_so_invoices').report_action(self)

    @api.multi
    def action_proforma(self):
        """This method is used within the xml view when button validate is pressed"""

        self.ensure_one()

        olddocs = self.env['ir.attachment'].sudo().search([('res_model', '=', 's2u.account.invoice'),
                                                           ('res_id', '=', self.id)])
        olddocs.unlink()

        if self.state == 'draft':
            self.write({
                'name': 'Proforma',
                'state': 'proforma'
            })
        else:
            self.write({
                'state': 'proforma'
            })

        return self.env.ref('s2uaccount.s2uaccount_so_invoices').report_action(self)
 
    @api.multi
    def action_cancel(self):

        self.ensure_one()
        self.write({
            'state': 'canceled'
        })

    @api.multi
    def action_creditnota(self):

        self.ensure_one()
        if self.amount_open <= 0.0:
            raise UserError(_('You can not make a creditnota for this invoice!'))
        if self.creditnota_id:
            raise UserError(_('This invoice has already a creditnota, please check!'))

        creditnota = self.copy(default={
            'reference': 'Creditnota voor factuur %s' % self.name,
            'creditnota_id': self.id
        })
        for line in creditnota.line_ids:
            line.write({
                'net_amount': line.net_amount* -1.0,
                'vat_amount': line.vat_amount * -1.0,
                'net_price': line.net_price * -1.0 if line.net_price else False
            })

        # trigger onchange to set date_due
        creditnota._onchange_partner_date_invoice()

        self.write({
            'creditnota_id': creditnota.id
        })

        action_rec = self.env['ir.model.data'].xmlid_to_object('s2uaccount.invoice_form')

        return {
            'type': 'ir.actions.act_window',
            'name': _('Creditnota'),
            'res_model': 's2u.account.invoice',
            'res_id': creditnota.id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': action_rec.id,
            'target': 'current',
            'nodestroy': True,
        }

    @api.multi
    def action_reopen(self):

        self.ensure_one()
        self.write({
            'state': 'reopen'
        })

    @api.multi
    def action_send_by_email(self):
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        self.ensure_one()
        if not self.use_email_address:
            raise UserError(_('There is no mail address present to use!'))

        template = self.env['mail.template'].sudo().search([('model', '=', 's2u.account.invoice')])

        compose_form = self.env.ref('mail.email_compose_message_wizard_form', False)

        ctx = dict(
            default_model='s2u.account.invoice',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
            mark_invoice_as_sent=True,
            custom_layout="account.mail_template_data_notification_email_account_invoice",
            force_email=True
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    def invoice_state_till(self, till_date):

        self.ensure_one()

        bank_accounting_model = self.env['s2u.account.bank.account']
        memorial_accounting_model = self.env['s2u.account.memorial.account']

        amount_paid = 0.0
        amount_writeoff = 0.0
        if self.creditnota_id and self.creditnota_id.date_invoice <= till_date:
            amount_paid -= self.creditnota_id.amount_gross

        transactions = bank_accounting_model.search([('so_invoice_id', '=', self.id),
                                                     ('date_trans', '<=', till_date)])
        for trans in transactions:
            if trans.type == 'nor':
                amount_paid -= trans.debit
                amount_paid += trans.credit
            else:
                amount_writeoff -= trans.debit
                amount_writeoff += trans.credit
        transactions = memorial_accounting_model.search([('so_invoice_id', '=', self.id),
                                                         ('date_trans', '<=', till_date)])
        for trans in transactions:
            if trans.type == 'nor':
                amount_paid -= trans.debit
                amount_paid += trans.credit
            else:
                amount_writeoff -= trans.debit
                amount_writeoff += trans.credit

        res = {
            'invoice': self.amount_gross,
            'paid': amount_paid,
            'writeoff': amount_writeoff,
            'saldo': self.amount_gross - amount_paid - amount_writeoff
        }

        return res

class AccountInvoicePOLine(models.Model):
    _name = "s2u.account.invoice.po.line"
    _description = "Invoice line"

    @api.one
    @api.depends('net_amount', 'vat_amount')
    def _compute_gross_amount(self):
        if self.vat_id:
            self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)
        else:
            self.gross_amount = self.net_amount

    invoice_id = fields.Many2one('s2u.account.invoice.po', string='Invoice', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True)
    gross_amount = fields.Monetary(string='Gross', currency_field='currency_id',
                                   store=True, readonly=True, compute='_compute_gross_amount')
    net_amount = fields.Monetary(string='Net', currency_field='currency_id')
    vat_amount = fields.Monetary(string='VAT', currency_field='currency_id')
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 domain=[('type', 'in', ['expense', 'stock'])])
    vat_id = fields.Many2one('s2u.account.vat', string='VAT', required=True, domain=[('type', '=', 'buy')])
    descript = fields.Char(string='Description', required=True)
    financial_date = fields.Date(related='invoice_id.date_financial', store=True, readonly=True, index=True)
    analytic_id = fields.Many2one('s2u.account.analytic', string='Analytic', ondelete='set null')

    @api.onchange('account_id')
    def _onchange_account_id(self):
        if not self.account_id:
            return False
        if self.account_id.vat_id:
            self.vat_id = self.account_id.vat_id
        return False

    @api.onchange('vat_id')
    def _onchange_vat_id(self):
        if not self.vat_id:
            self.gross_amount = self.net_amount
            self.vat_amount = 0.0
            return False

        self.vat_amount = self.vat_id.calc_vat_from_netto_amount(self.net_amount)
        self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)

    @api.onchange('net_amount')
    def _onchange_net_amount(self):
        if not self.vat_id:
            self.gross_amount = self.net_amount
            self.vat_amount = 0.0
            return False

        self.vat_amount = self.vat_id.calc_vat_from_netto_amount(self.net_amount)
        self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)

    @api.onchange('vat_amount')
    def _onchange_vat_amount(self):
        if not self.vat_id:
            self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)
            return False

        self.gross_amount = self.vat_id.calc_gross_amount(self.net_amount, self.vat_amount)


class AccountInvoicePO(models.Model):
    _name = "s2u.account.invoice.po"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Purchase invoice"

    @api.multi
    @api.constrains('state', 'partner_id')
    def _check_address_entity(self):
        for invoice in self:
            if invoice.partner_id.type != 'b2b' and invoice.state == 'valid':
                raise ValueError(_('Please select a b2b creditor!'))

    @api.model
    def _default_account(self):
        domain = [
            ('type', '=', 'payable'),
        ]
        return self.env['s2u.account.account'].search(domain, limit=1)

    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id

    @api.one
    @api.depends('line_ids.gross_amount', 'line_ids.net_amount', 'line_ids.vat_amount')
    def _compute_amount(self):
        self.amount_net = sum(line.net_amount for line in self.line_ids)
        self.amount_vat = sum(line.vat_amount for line in self.line_ids)
        self.amount_gross = sum(line.gross_amount for line in self.line_ids)

    @api.onchange('date_invoice')
    def _onchange_date_invoice(self):
        if self.date_invoice:
            self.date_financial = self.date_invoice

    def compute_open(self, amount_open, invoice_id):

        bank_accounting_model = self.env['s2u.account.bank.account']
        memorial_accounting_model = self.env['s2u.account.memorial.account']

        transactions = bank_accounting_model.search([('po_invoice_id', '=', invoice_id)])
        for trans in transactions:
            amount_open -= trans.debit
            amount_open += trans.credit
        transactions = memorial_accounting_model.search([('po_invoice_id', '=', invoice_id)])
        for trans in transactions:
            amount_open -= trans.debit
            amount_open += trans.credit

        return amount_open

    @api.one
    @api.depends('amount_gross', 'transactions_bank.debit', 'transactions_bank.credit',
                 'transactions_memorial.debit', 'transactions_memorial.credit')
    def _compute_open(self):

        self.amount_open = self.compute_open(self.amount_gross, self.id)

    @api.multi
    def sync_open(self):

        for inv in self:
            amount_open = inv.compute_open(inv.amount_gross, inv.id)

            inv.write({
                'amount_open': amount_open
            })

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(AccountInvoicePO, self)._track_subtype(init_values)

    def _get_document_count(self):

        for sale in self:
            docs = self.env['s2u.document'].search([('res_model', '=', 's2u.account.invoice.po'),
                                                    ('res_id', '=', sale.id)])
            sale.document_count = len(docs.ids)

    @api.multi
    def action_view_document(self):
        action = self.env.ref('s2udocument.action_document').read()[0]
        action['domain'] = [('res_model', '=', 's2u.account.invoice.po'),
                            ('res_id', '=', self.id)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.partner_id.id,
            'default_doc_context': self._description if self._description else self._name,
            'default_rec_context': self.name,
            'default_res_model': 's2u.account.invoice.po',
            'default_res_id': self.id
        }
        action['context'] = str(context)
        return action

    name = fields.Char(string='Number', index=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Invoice Currency', default=_default_currency,
                                  readonly=True, states={'draft': [('readonly', False)]})
    line_ids = fields.One2many('s2u.account.invoice.po.line', 'invoice_id',
                               string='Lines', readonly=True, states={'draft': [('readonly', False)]})
    date_invoice = fields.Date(string='Invoice Date', index=True, copy=False,
                               default=lambda self: fields.Date.context_today(self),
                               readonly=True, states={'draft': [('readonly', False)]})
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 default=_default_account, domain=[('type', '=', 'payable')],
                                 readonly=True, states={'draft': [('readonly', False)]})
    amount_net = fields.Monetary(string='Amount Net',
                                 store=True, readonly=True, compute='_compute_amount')
    amount_vat = fields.Monetary(string='Amount VAT',
                                 store=True, readonly=True, compute='_compute_amount')
    amount_gross = fields.Monetary(string='Amount Gross',
                                   store=True, readonly=True, compute='_compute_amount')
    partner_id = fields.Many2one('s2u.crm.entity', string='Creditor', index=True,
                                 readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'Concept'),
        ('incoming', 'Incoming'),
        ('convert', 'Converting'),
        ('import', 'Importing'),
        ('wait', 'Waiting'),
        ('valid', 'Accepted'),
        ('reject', 'Rejected'),
        ('failed', 'Failed')
    ], required=True, default='draft', string='State', track_visibility='onchange')
    source_data = fields.Text('Data')
    failed_message = fields.Char(string='Message')
    cloud_task_id = fields.Char(string='Task ID', index=True)
    date_financial = fields.Date(string='Financial Date', index=True, copy=False,
                                 default=lambda self: fields.Date.context_today(self))
    amount_open = fields.Monetary(string='Amount Open',
                                  store=True, readonly=True, compute='_compute_open')
    transactions_bank = fields.One2many('s2u.account.bank.account', 'po_invoice_id',
                                        string='Trans. Bank')
    transactions_memorial = fields.One2many('s2u.account.memorial.account', 'po_invoice_id',
                                            string='Trans. Bank')
    reference = fields.Char(string='Reference', index=True, readonly=True, states={'draft': [('readonly', False)]})
    document_count = fields.Integer(string='# of Docs', compute='_get_document_count', readonly=True)

    @api.multi
    def do_set_valid(self):
        self.ensure_one()
        self.write({'state': 'valid'})

    @api.multi
    def do_set_incoming(self):
        self.ensure_one()
        self.write({'state': 'incoming'})

    @api.multi
    def do_set_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})


class InvoiceAddPayment(models.TransientModel):
    _name = 's2u.account.invoice.payment'

    @api.model
    def default_get(self, fields):

        rec = super(InvoiceAddPayment, self).default_get(fields)

        context = self._context
        active_model = context.get('active_model')
        invoice_id = context.get('active_id', False)

        # Checks on context parameters
        if not active_model or not invoice_id:
            raise UserError(
                _("Programmation error: wizard action executed without active_model or active_id in context."))
        if active_model != 's2u.account.invoice':
            raise UserError(_(
                "Programmation error: the expected model for this action is 's2u.account.invoice'. The provided one is '%d'.") % active_model)

        invoice = self.env['s2u.account.invoice'].browse(invoice_id)
        rec['invoice_id'] = invoice.id
        rec['amount_paid'] = invoice.amount_open
        account = self.env['s2u.account.account'].search([('type', 'in', ['bank', 'cash'])], limit=1)
        if account:
            rec['account_id'] = account.id

        return rec

    @api.multi
    def do_payment(self):

        journal_model = self.env['s2u.account.memorial']

        if self.invoice_id.state != 'invoiced':
            raise ValidationError(_('Please confirm this invoice first, before register a payment for it!'))

        inv = {
            'currency_id': self.currency_id.id,
            'trans_amount': self.amount_paid,
            'invoice_id': self.invoice_id.id
        }

        vals1 = {
            'currency_id': self.currency_id.id,
            'type': 'deb',
            'partner_id': self.invoice_id.partner_id.id,
            'account_id': self.invoice_id.account_id.id,
            'gross_amount': self.amount_paid,
            'vat_amount': 0.0,
            'so_ids': [(0, 0, inv)]
        }

        vals2 = {
            'currency_id': self.currency_id.id,
            'type': 'nor',
            'gross_amount': self.amount_paid * -1.0,
            'vat_amount': 0.0,
            'account_id': self.account_id.id
        }

        journal_vals = {
            'name': 'Payment invoice %s' % self.invoice_id.name,
            'date_trans': self.payment_date,
            'currency_id': self.currency_id.id,
            'memorial_type': 'nor',
            'line_ids': [(0, 0, vals1), (0, 0, vals2)]
        }
        journal_model.with_context({
            'register_payment': True
        }).create(journal_vals)

    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice')
    account_id = fields.Many2one('s2u.account.account', string='Bank',
                                 domain=[('type', 'in', ['bank', 'cash'])], required=True)
    currency_id = fields.Many2one('res.currency', related='invoice_id.currency_id', store=True)
    amount_paid = fields.Monetary(string='Payment', currency_field='currency_id', required=True)
    payment_date = fields.Date(string='Date', copy=False, required=True,
                               default=lambda self: fields.Date.context_today(self))
