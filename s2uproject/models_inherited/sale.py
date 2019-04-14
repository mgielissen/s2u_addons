# -*- coding: utf-8 -*-

from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class SaleTemplate(models.Model):
    _inherit = "s2u.sale.template"

    @api.multi
    def render_template(self, template, entity=False, address=False, contact=False, user=False, date=False,
                        other=False):

        template = super(SaleTemplate, self).render_template(template, entity=entity, address=address, contact=contact,
                                                             user=user, date=date, other=other)
        if template and other and other.get('so'):
            so = other['so']
            if '[[zone1]]' in template:
                zone = round(so.zone1 + 100.0, 2)
                zone = '%02.f%%' % zone
                template = template.replace('[[zone1]]', zone)
            if '[[zone2]]' in template:
                zone = round(so.zone2 + 100.0, 2)
                zone = '%02.f%%' % zone
                template = template.replace('[[zone2]]', zone)
            if '[[zone3]]' in template:
                zone = round(so.zone3 + 100.0, 2)
                zone = '%02.f%%' % zone
                template = template.replace('[[zone3]]', zone)
            if '[[zone4]]' in template:
                zone = round(so.zone4 + 100.0, 2)
                zone = '%02.f%%' % zone
                template = template.replace('[[zone4]]', zone)
            if '[[project_method]]' in template:
                if so.project_method == 'fix':
                    template = template.replace('[[project_method]]', _('Vast'))
                elif so.project_method == 'calc':
                    template = template.replace('[[project_method]]', _('Nacalculatie'))

        if template:
            template = template.replace('[[zone1]]', '')
            template = template.replace('[[zone2]]', '')
            template = template.replace('[[zone3]]', '')
            template = template.replace('[[zone4]]', '')
            template = template.replace('[[project_method]]', '')

        return template


class SaleHour(models.Model):
    _name = "s2u.sale.hour"
    _description = "Hour definitions for project"
    _order = "sale_id, sequence"

    @api.multi
    def name_get(self):
        result = []
        for line in self:
            name = '%s' % line.sale_id.name
            result.append((line.id, name))
        return result

    @api.onchange('hours', 'rate_per_hour')
    def _onchange_hours(self):
        if self.hours and self.rate_per_hour:
            self.amount = self.rate_per_hour * self.hours
        else:
            self.amount = 0.0

    @api.onchange('rate_id')
    def _onchange_rate(self):
        if self.rate_id:
            partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                search([('rate_id', '=', self.rate_id.id),
                        ('partner_id', '=', self.sale_id.partner_id.id)], limit=1)
            if partner_rate:
                if partner_rate.discount_type == 'price':
                    self.rate_per_hour = partner_rate.rate_per_hour
                else:
                    self.rate_per_hour = round(self.rate_id.rate_per_hour - (
                                self.rate_id.rate_per_hour * (partner_rate.rate_per_hour / 100.0)), 2)
            else:
                self.rate_per_hour = self.rate_id.rate_per_hour

    sale_id = fields.Many2one('s2u.sale', string='Sale', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    currency_id = fields.Many2one('res.currency', related='sale_id.currency_id', store=True)
    stage_id = fields.Many2one('s2u.project.task.stage', string='Fase', ondelete='restrict', required=True)
    rate_id = fields.Many2one('s2u.project.hour.rate.def', string='Role', required=True, ondelete='restrict')
    rate_per_hour = fields.Monetary(string='Rate p/h', currency_field='currency_id', required=True)
    hours = fields.Float(string='Hours', digits=(16, 2), required=True)
    amount = fields.Monetary(string='Amount', required=True)
    descript = fields.Text(string='Description')


class Sale(models.Model):
    _inherit = "s2u.sale"

    def _get_project_count(self):

        for sale in self:
            projects = self.env['s2u.project'].search([('sale_id', '=', sale.id)])
            project_ids = [p.id for p in projects]
            project_ids = list(set(project_ids))
            sale.project_count = len(project_ids)

    @api.multi
    def action_view_project(self):
        projects = self.env['s2u.project'].search([('sale_id', '=', self.id)])
        project_ids = [p.id for p in projects]
        project_ids = list(set(project_ids))

        action = self.env.ref('s2uproject.action_project').read()[0]
        if len(project_ids) > 1:
            action['domain'] = [('id', 'in', project_ids)]
        elif len(project_ids) == 1:
            action['views'] = [(self.env.ref('s2uproject.project_form').id, 'form')]
            action['res_id'] = project_ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def skip_for_invoice(self, line):

        if line.product_id and line.product_id.res_model == 's2u.contract.template':
            return True

        return super(Sale, self).skip_for_invoice(line)

    @api.multi
    def manage_invoice_lines(self, lines, condition):

        self.ensure_one()

        if self.project_method not in ['fix']:
            return super(Sale, self).manage_invoice_lines(lines, condition)

        for hour in self.hour_ids:

            ihours = int(hour.hours)
            qty = "%02d:%02d" % (ihours, (hour.hours - ihours) * 60)
            descript = '%s - %s' % (hour.stage_id.name, hour.rate_id.name)

            vals = {
                'net_amount': round(hour.amount * float(condition) / 100.0, 2),
                'account_id': hour.rate_id.account_id.id,
                'descript': descript,
                'qty': qty,
                'net_price': hour.rate_per_hour,
                'sale_id': self.id,
                'price_per': 'item'
            }
            if self.invoice_partner_id.vat_sell_id:
                vals['vat_id'] = self.invoice_partner_id.vat_sell_id.id
                vals['vat_amount'] = self.invoice_partner_id.vat_sell_id.calc_vat_from_netto_amount(
                    vals['net_amount'])
                vals['gross_amount'] = self.invoice_partner_id.vat_sell_id.calc_gross_amount(
                    vals['net_amount'], vals['vat_amount'])
            else:
                if hour.rate_id.account_id.vat_id:
                    vals['vat_id'] = hour.rate_id.account_id.vat_id.id
                    vals['vat_amount'] = hour.rate_id.account_id.vat_id.calc_vat_from_netto_amount(
                        vals['net_amount'])
                    vals['gross_amount'] = hour.rate_id.account_id.vat_id.calc_gross_amount(
                        vals['net_amount'], vals['vat_amount'])
                else:
                    raise UserError(_('No VAT is defined for role %s!' % hour.rate_id.name))

            lines.append((0, 0, vals))

        return super(Sale, self).manage_invoice_lines(lines, condition)

    @api.multi
    def add_outgoing_line(self, line, devider):

        if line.product_id.res_model == 's2u.contract.template':
            contract = self.env['s2u.contract.template'].browse(line.product_id.res_id)
            if not contract.product_ids:
                return False
            vals = []
            for p in contract.product_ids:
                if not p.product_id.is_stockable():
                    continue
                if line.price_per == 'item':
                    product_value = line.price
                else:
                    product_value = line.amount / line.product_qty
                v = {
                    'sale_id': self.id,
                    'saleline_id': line.id,
                    'product_id': p.product_id.id,
                    'product_value': product_value
                }
                if devider > 1:
                    # wordt gebruikt als er meerdere adressen zijn om te leveren, b.v. 2 adressen is 50/50 verdelen
                    v['product_qty'] = round(line.product_qty / float(devider), 0)
                else:
                    v['product_qty'] = line.product_qty
                if p.use_product_detail_so:
                    if line.product_detail:
                        v['product_detail'] = line.product_detail
                    else:
                        v['product_detail'] = p.product_detail
                else:
                    v['product_detail'] = p.product_detail
                vals.append(v)
            return vals

        return super(Sale, self).add_outgoing_line(line, devider)

    @api.onchange('partner_id', 'project_method')
    def onchange_project_zones(self):

        if self.partner_id and self.project_method in ['fix', 'calc']:
            if self.partner_id.use_project_zones:
                self.zone1 = self.partner_id.project_zone1
                self.zone2 = self.partner_id.project_zone2
                self.zone3 = self.partner_id.project_zone3
                self.zone4 = self.partner_id.project_zone4

    @api.onchange('projecttype_id')
    def onchange_projecttype_id(self):

        if self.projecttype_id and self.project_method in ['fix', 'calc']:
            add_rates = []
            for stage in self.projecttype_id.stage_ids:
                if not stage.rate_ids:
                    continue
                for rate in stage.rate_ids:
                    rate_per_hour = False
                    # first check if selected partner as special conditions
                    if self.partner_id:
                        partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                            search([('rate_id', '=', rate.rate_id.id),
                                    ('partner_id', '=', self.partner_id.id)], limit=1)
                        if partner_rate:
                            if partner_rate.discount_type == 'price':
                                rate_per_hour = partner_rate.rate_per_hour
                            else:
                                rate_per_hour = rate.rate_per_hour if rate.rate_per_hour else rate.rate_id.rate_per_hour
                                rate_per_hour = round(rate_per_hour - (rate_per_hour * (partner_rate.rate_per_hour / 100.0)), 2)
                    if not rate_per_hour:
                        rate_per_hour = rate.rate_per_hour if rate.rate_per_hour else rate.rate_id.rate_per_hour
                    vals = {
                        'sequence': stage.sequence,
                        'stage_id': stage.stage_id.id,
                        'rate_id': rate.rate_id.id,
                        'hours': rate.hours,
                        'amount': rate.hours * rate_per_hour,
                        'rate_per_hour': rate_per_hour,
                        'descript': rate.descript
                    }
                    add_rates.append((0, 0, vals))
            self.hour_ids = add_rates

    @api.one
    def customized_compute_amount(self):

        if not self.project_method in ['fix', 'calc']:
            return super(Sale, self).customized_compute_amount()

        for h in self.hour_ids:
            if self.partner_id.vat_sell_id:
                vat = self.partner_id.vat_sell_id
            else:
                partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                    search([('rate_id', '=', h.rate_id.id),
                            ('partner_id', '=', self.partner_id.id)], limit=1)
                if partner_rate and partner_rate.account_id:
                    account = partner_rate.account_id
                else:
                    account = h.rate_id.account_id

                if account.vat_id:
                    vat = account.vat_id
                else:
                    raise UserError(_('No VAT is defined for account %s (%s)!' % (account.name, account.code)))

            vat_amount = vat.calc_vat_from_netto_amount(h.amount)
            gross_amount = vat.calc_gross_amount(h.amount, vat_amount)

            self.net_amount += h.amount
            self.vat_amount += vat_amount
            self.gross_amount += gross_amount

        return super(Sale, self).customized_compute_amount()

    @api.one
    def customized_compute_amount_quot(self):

        if not self.project_method in ['fix', 'calc']:
            return super(Sale, self).customized_compute_amount_quot()

        for h in self.hour_ids:

            if self.partner_id.vat_sell_id:
                vat = self.partner_id.vat_sell_id
            else:
                partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                    search([('rate_id', '=', h.rate_id.id),
                            ('partner_id', '=', self.partner_id.id)], limit=1)
                if partner_rate and partner_rate.account_id:
                    account = partner_rate.account_id
                else:
                    account = h.rate_id.account_id

                if account.vat_id:
                    vat = account.vat_id
                else:
                    raise UserError(_('No VAT is defined for account %s (%s)!' % (account.name, account.code)))

            vat_amount = vat.calc_vat_from_netto_amount(h.amount)
            gross_amount = vat.calc_gross_amount(h.amount, vat_amount)

            self.quot_net_amount += h.amount
            self.quot_vat_amount += vat_amount
            self.quot_gross_amount += gross_amount

        return super(Sale, self).customized_compute_amount()

    @api.one
    @api.depends('line_ids', 'hour_ids')
    def _compute_amount(self):

        return super(Sale, self)._compute_amount()

    @api.one
    @api.depends('line_ids', 'hour_ids')
    def _compute_amount_quot(self):

        return super(Sale, self)._compute_amount_quot()

    @api.multi
    def do_undo_other_stuff(self):

        self.ensure_one()

        projects = self.env['s2u.project'].search([('sale_id', '=', self.id)])
        projects.unlink()

        return True

    @api.one
    def _compute_amount_quot_hours(self):

        net_amount_hours = 0.0
        vat_amount_hours = 0.0
        gross_amount_hours = 0.0
        for line in self.hour_ids:
            net_amount_hours += line.amount
            if self.partner_id.vat_sell_id:
                use_vat = self.partner_id.vat_sell_id
            else:
                partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                    search([('rate_id', '=', line.rate_id.id),
                            ('partner_id', '=', self.partner_id.id)], limit=1)
                if partner_rate and partner_rate.account_id:
                    account = partner_rate.account_id
                else:
                    account = line.rate_id.account_id

                if account.vat_id:
                    use_vat = account.vat_id
                else:
                    raise UserError(_('No VAT is defined for account %s (%s)!' % (account.name, account.code)))

            if use_vat:
                vat = use_vat.calc_vat_from_netto_amount(line.amount)
                gross = use_vat.calc_gross_amount(line.amount, vat)
                vat_amount_hours += vat
                gross_amount_hours += gross
            else:
                gross_amount_hours += line.amount

        self.quot_net_amount_hours = net_amount_hours
        self.quot_vat_amount_hours = vat_amount_hours
        self.quot_gross_amount_hours = gross_amount_hours

    @api.one
    def _compute_amount_hours(self):

        net_amount_hours = 0.0
        vat_amount_hours = 0.0
        gross_amount_hours = 0.0
        for line in self.hour_ids:
            net_amount_hours += line.amount
            if self.partner_id.vat_sell_id:
                use_vat = self.partner_id.vat_sell_id
            else:
                partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                    search([('rate_id', '=', line.rate_id.id),
                            ('partner_id', '=', self.partner_id.id)], limit=1)
                if partner_rate and partner_rate.account_id:
                    account = partner_rate.account_id
                else:
                    account = line.rate_id.account_id

                if account.vat_id:
                    use_vat = account.vat_id
                else:
                    raise UserError(_('No VAT is defined for account %s (%s)!' % (account.name, account.code)))

            if use_vat:
                vat = use_vat.calc_vat_from_netto_amount(line.amount)
                gross = use_vat.calc_gross_amount(line.amount, vat)
                vat_amount_hours += vat
                gross_amount_hours += gross
            else:
                gross_amount_hours += line.amount

        self.net_amount_hours = net_amount_hours
        self.vat_amount_hours = vat_amount_hours
        self.gross_amount_hours = gross_amount_hours

    project_count = fields.Integer(string='# of Projects', compute='_get_project_count', readonly=True)
    project_id = fields.Many2one('s2u.project', string='Project', ondelete='set null')
    project_method = fields.Selection([
        ('none', 'None'),
        ('fix', 'Fix'),
        ('calc', 'Actual costs'),
    ], required=True, default='none', string='Project hours', index=True, readonly=True, states={
        'draft': [('readonly', False)],
        'quot': [('readonly', False)],
        'order': [('readonly', False)]
    })
    zone1 = fields.Float(string='Office hours (%)', default='0.0')
    zone2 = fields.Float(string='After hours (%)', default='35.0')
    zone3 = fields.Float(string='Sat. and Sun. (%)', default='50.0')
    zone4 = fields.Float(string='Holidays (%)', default='100.0')
    hour_ids = fields.One2many('s2u.sale.hour', 'sale_id', string='Hours', copy=True, readonly=True, states={
        'draft': [('readonly', False)],
        'quot': [('readonly', False)],
        'order': [('readonly', False)],
    })
    projecttype_id = fields.Many2one('s2u.project.type', string='Type', ondelete='set null')
    quot_net_amount_hours = fields.Monetary(string='Net amount', currency_field='currency_id',
                                            compute=_compute_amount_quot_hours,
                                            readonly=True)
    quot_vat_amount_hours = fields.Monetary(string='VAT', currency_field='currency_id',
                                            compute=_compute_amount_quot_hours,
                                            readonly=True)
    quot_gross_amount_hours = fields.Monetary(string='Gross amount', currency_field='currency_id',
                                              compute=_compute_amount_quot_hours, readonly=True)
    net_amount_hours = fields.Monetary(string='Net amount', currency_field='currency_id',
                                       compute=_compute_amount_hours,
                                       readonly=True)
    vat_amount_hours = fields.Monetary(string='VAT', currency_field='currency_id',
                                       compute=_compute_amount_hours,
                                       readonly=True)
    gross_amount_hours = fields.Monetary(string='Gross amount', currency_field='currency_id',
                                         compute=_compute_amount_hours, readonly=True)
    net_amount = fields.Monetary(compute=_compute_amount)
    vat_amount = fields.Monetary(compute=_compute_amount)
    gross_amount = fields.Monetary(compute=_compute_amount)
    quot_net_amount = fields.Monetary(compute=_compute_amount_quot)
    quot_vat_amount = fields.Monetary(compute=_compute_amount_quot)
    quot_gross_amount = fields.Monetary(compute=_compute_amount_quot)

    @api.multi
    def overrule_action_order(self):

        self.ensure_one()

        if self.project_method in ['fix', 'calc'] and self.hour_ids:
            return True

        return super(Sale, self).overrule_action_order()

    @api.multi
    def before_confirm(self):

        self.ensure_one()

        def stage_present(stage_id, calc):
            for c in calc:
                if c[2]['stage_id'] == stage_id:
                    return c[2]
            return False

        rates = []
        if self.project_method in ['fix', 'calc']:
            # init project on basis of sales info if possible
            for hour in self.hour_ids:
                if not hour.hours:
                    continue
                vals_rate = {
                    'stage_id': hour.stage_id.id,
                    'rate_id': hour.rate_id.id,
                    'rate_per_hour': hour.rate_per_hour,
                    'hours': hour.hours,
                    'amount': hour.amount,
                    'descript': hour.descript
                }
                rates.append((0, 0, vals_rate))

            if self.project_id:
                rate_lines = self.env['s2u.project.stage.role'].search([('project_id', '=', self.project_id.id)])
                rate_lines.unlink()

            short_descript = self.reference
            if self.projecttype_id:
                short_descript = '%s - %s' % (short_descript, self.projecttype_id.name)
            project_vals = {
                'short_descript': short_descript,
                'customer_code': self.customer_code,
                'reference': self.name,
                'partner_id': self.partner_id.id,
                'rate_ids': rates,
                'skip_invoicing': True if self.project_method == 'fix' else False,
                'zone1': self.partner_id.project_zone1 if self.partner_id.use_project_zones else self.zone1,
                'zone2': self.partner_id.project_zone2 if self.partner_id.use_project_zones else self.zone2,
                'zone3': self.partner_id.project_zone3 if self.partner_id.use_project_zones else self.zone3,
                'zone4': self.partner_id.project_zone4 if self.partner_id.use_project_zones else self.zone4,
                'projecttype_id': self.projecttype_id.id if self.projecttype_id else False,
                'sale_id': self.id
            }
            if self.project_id:
                self.project_id.write(project_vals)
            else:
                project = self.env['s2u.project'].create(project_vals)
                self.write({
                    'project_id': project.id
                })

        return super(Sale, self).before_confirm()
