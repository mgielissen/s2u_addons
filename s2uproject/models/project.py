# -*- coding: utf-8 -*-

import datetime
import io
import math
import base64
import xlsxwriter

from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _


class ProjectTaskNote(models.Model):
    _name = 's2u.project.task.note'
    _description = 'Task notes'
    _order = 'date_note desc'

    task_id = fields.Many2one('s2u.project.task', string='Task', required=True, ondelete='cascade')
    date_note = fields.Date(string='Note date', index=True, copy=False, required=True,
                            default=lambda self: fields.Date.context_today(self))
    note = fields.Text(string='Note')
    user_id = fields.Many2one('res.users', string='Author', required=True,
                              default=lambda self: self.env.user)


class ProjectTaskDocument(models.Model):
    _name = 's2u.project.task.document'
    _description = 'Task documents'

    task_id = fields.Many2one('s2u.project.task', string='Task', required=True, ondelete='cascade')
    name = fields.Char(required=True, index=True, string='Title')
    data_file = fields.Binary(string='Document', required=True)
    data_name = fields.Char(string='Filename', required=True)
    descript = fields.Text(string='Description')


class ProjectTask(models.Model):
    _name = "s2u.project.task"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Project task"
    _order = "sequence, id desc"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(ProjectTask, self)._track_subtype(init_values)

    def _read_group_stage_ids(self, cr, uid, ids, domain, read_group_order=None, access_rights_uid=None, context=None):
        if context is None:
            context = {}
        access_rights_uid = access_rights_uid or uid
        stage_obj = self.pool.get('s2u.project.task.stage')
        order = stage_obj._order
        # lame hack to allow reverting search, should just work in the trivial case
        if read_group_order == 'stage_id desc':
            order = "%s desc" % order
        # retrieve team_id from the context, add them to already fetched columns (ids)
        search_domain = [('id', 'in', ids)]
        # perform search
        stage_ids = stage_obj._search(cr, uid, search_domain, order=order, access_rights_uid=access_rights_uid,
                                      context=context)
        result = stage_obj.name_get(cr, access_rights_uid, stage_ids, context=context)
        # restore order of the search
        result.sort(lambda x, y: cmp(stage_ids.index(x[0]), stage_ids.index(y[0])))

        fold = {}
        for stage in stage_obj.browse(cr, access_rights_uid, stage_ids, context=context):
            fold[stage.id] = stage.fold or False
        return result, fold

    _group_by_full = {
        'stage_id': _read_group_stage_ids
    }

    @api.one
    @api.depends('deadline')
    def _compute_alert(self):
        if self.deadline and self.state == 'open':
            d = datetime.datetime.strptime(self.deadline, '%Y-%m-%d')
            if (d - datetime.timedelta(days=2)).strftime('%Y-%m-%d') <= datetime.datetime.now().strftime('%Y-%m-%d'):
                self.deadline_alert = True
            else:
                self.deadline_alert = False
        else:
            self.deadline_alert = False

    @api.one
    def _compute_short(self):
        if self.descript:
            if len(self.descript) > 40:
                self.descript_short = '%s ...' % self.descript[:40]
            else:
                self.descript_short = self.descript
        else:
            self.descript_short = ''

    @api.one
    @api.depends('project_id', 'stage_id', 'rate_id', 'task_forecast')
    def _compute_hours(self):

        self.hours_written = 0.0
        self.hours_offered = 0.0
        self.hours_to_spend = 0.0
        self.rolling_forecast = 0.0
        self.forecast_alert = False

        # hours written on this task
        hours = self.env['s2u.project.hour'].search([('task_id', '=', self.id),
                                                     ('change_request', '=', False)])
        for h in hours:
            self.hours_written += h.hours_zone

        if self.project_id and self.stage_id and self.rate_id:
            tasks = self.env['s2u.project.task'].search([('project_id', '=', self.project_id.id),
                                                         ('stage_id', '=', self.stage_id.id),
                                                         ('rate_id', '=', self.rate_id.id),
                                                         ('state', '=', 'open')])
            for t in tasks:
                self.rolling_forecast += t.task_forecast

            rate = self.env['s2u.project.stage.role'].search([('project_id', '=', self.project_id.id),
                                                              ('stage_id', '=', self.stage_id.id),
                                                              ('rate_id', '=', self.rate_id.id)], limit=1)
            if rate:
                self.hours_offered = rate.hours

        # berekening van beschikbare uren op deze taak
        self.hours_to_spend = self.hours_available - self.hours_written

        if round(self.hours_available, 2) and round(self.task_forecast, 2) > round(self.hours_to_spend, 2):
            self.forecast_alert = True

    @api.multi
    def write_hours(self):

        projectrate = self.env['s2u.project.stage.role'].search([('project_id', '=', self.project_id.id),
                                                                 ('stage_id', '=', self.stage_id.id),
                                                                 ('rate_id', '=', self.rate_id.id)], limit=1)

        return {
            'name': _('Write hours'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2u.project.hour',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': {
                'default_partner_id': self.project_id.partner_id.id if self.project_id else False,
                'default_project_id': self.project_id.id if self.project_id else False,
                'default_projectrate_id': projectrate.id if projectrate else False,
                'default_task_id': self.id,
                'default_locked': True
            }
        }

    def _compute_attachment_ids(self):
        for task in self:
            attachment_ids = self.env['ir.attachment'].search(
                [('res_id', '=', task.id), ('res_model', '=', 's2u.project.task')]).ids
            message_attachment_ids = task.mapped('message_ids.attachment_ids').ids  # from mail_thread
            task.attachment_ids = list(set(attachment_ids) - set(message_attachment_ids))

    def _compute_hours_count(self):
        task_data = self.env['s2u.project.hour'].read_group(
            [('task_id', 'in', self.ids)], ['task_id'], ['task_id'])
        result = dict((data['task_id'][0], data['task_id_count']) for data in task_data)
        for task in self:
            task.hours_count = result.get(task.id, 0)

    @api.multi
    def action_view_hours(self):
        tasks = self.env['s2u.project.hour'].search([('task_id', '=', self.id)])

        action = self.env.ref('s2uproject.action_project_hour').read()[0]
        context = {
            'search_default_open': 1,
            'default_partner_id': self.project_id.partner_id.id,
            'default_project_id': self.project_id.id,
            'default_task_id': self.id
        }
        action['context'] = str(context)

        if len(tasks) >= 1:
            action['domain'] = [('id', 'in', tasks.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.onchange('rate_id')
    def _onchange_rate_id(self):
        if self.project_id and self.stage_id and self.rate_id:
            projectrate = self.env['s2u.project.stage.role'].search([('project_id', '=', self.project_id.id),
                                                                     ('stage_id', '=', self.stage_id.id),
                                                                     ('rate_id', '=', self.rate_id.id)], limit=1)
            if projectrate and projectrate.descript:
                self.descript = projectrate.descript

    @api.depends('stage_id', 'kanban_state')
    def _compute_kanban_state_label(self):
        for task in self:
            if task.kanban_state == 'normal':
                task.kanban_state_label = 'Normal'
            elif task.kanban_state == 'blocked':
                task.kanban_state_label = 'Blocked'
            else:
                task.kanban_state_label = 'Done'

    project_id = fields.Many2one('s2u.project', string='Project', ondelete='restrict')
    project_descript = fields.Char(string='Project descript.', related='project_id.short_descript', readonly=True,
                                   store=True, index=True)
    stage_id = fields.Many2one('s2u.project.task.stage', string='Fase')
    name = fields.Char(required=True, index=True, string='Task')
    deadline = fields.Date(string='Deadline', index=True)
    descript = fields.Text(string='Description')
    responsible_id = fields.Many2one('res.users', string='Responsible', required=True,
                                     default=lambda self: self.env.user)
    manager_id = fields.Many2one('res.users', string='Manager', readonly=True, related='project_id.responsible_id')
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True)
    doc_ids = fields.One2many('s2u.project.task.document', 'task_id', string='Documents')
    deadline_alert = fields.Boolean(string='Alert', store=False, readonly=True, compute='_compute_alert')
    color = fields.Integer(string='Color Index')
    type = fields.Selection([
        ('priv', 'Privat'),
        ('buss', 'Bussiness')
    ], string='Type', index=True, copy=False, related='project_id.type', store=True, readonly=True)
    note_ids = fields.One2many('s2u.project.task.note', 'task_id', string='Notes')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    descript_short = fields.Char(string='Short description', store=False, readonly=True, compute='_compute_short')
    state = fields.Selection([
        ('open', 'Open'),
        ('ready', 'Ready'),
        ('closed', 'Closed')
    ], string='State', index=True, default='open', required=True, copy=False, track_visibility='onchange')
    hours_written = fields.Float(string='Booked',
                                 readonly=True, compute='_compute_hours')
    hours_offered = fields.Float(string='Offered',
                                 readonly=True, compute='_compute_hours')
    hours_to_spend = fields.Float(string='Left over',
                                  readonly=True, compute='_compute_hours')
    rolling_forecast = fields.Float(string='Rolling forecast',
                                    readonly=True, compute='_compute_hours')
    forecast_alert = fields.Boolean(string='Forecast alert',
                                    readonly=True, compute='_compute_hours', store=True)
    rate_id = fields.Many2one('s2u.project.hour.rate.def', string='Role', ondelete='restrict')
    task_forecast = fields.Float(string='Rolling forecast', digits=(16, 2))
    change_request = fields.Boolean(string='SCR', default=False)
    change_request_id = fields.Many2one('s2u.sale.product', string='Request', ondelete='restrict',
                                        domain=[('product_type', '=', 'changerequest')])
    invpartner_id = fields.Many2one('s2u.project.hour.invoicing.partner', string='Invoicing Partner',
                                    ondelete='set null', copy=False)
    internal_description = fields.Text(string='Internal description')
    project_state = fields.Selection([
        ('pending', 'Not started'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('onhold', 'On hold')
    ], string='Project state', related='project_id.state')
    partner_id = fields.Many2one('s2u.crm.entity', string='Customer', related='project_id.partner_id',
                                 store=True, readony=True)
    attachment_ids = fields.One2many('ir.attachment', compute='_compute_attachment_ids', string="Main Attachments",
                                     help="Attachment that don't come from message.")
    hours_count = fields.Integer(compute='_compute_hours_count', string="Hours")
    hours_available = fields.Float(string='Available')
    displayed_image_id = fields.Many2one('ir.attachment',
                                         domain="[('res_model', '=', 's2u.project.task'), "
                                                "('res_id', '=', id), "
                                                "('mimetype', 'ilike', 'image')]",
                                         string='Cover Image')
    active = fields.Boolean(default=True)
    kanban_state = fields.Selection([
        ('normal', 'Grey'),
        ('done', 'Green'),
        ('blocked', 'Red')], string='Kanban State',
        copy=False, default='normal', required=True,
        help="A task's kanban state indicates special situations affecting it:\n"
             " * Grey is the default situation\n"
             " * Red indicates something is preventing the progress of this task\n"
             " * Green indicates the task is ready to be pulled to the next stage")
    kanban_state_label = fields.Char(compute='_compute_kanban_state_label', string='Kanban State',
                                     track_visibility='onchange')
    tag_ids = fields.Many2many('s2u.crm.tag', string='Tags')
    priority = fields.Selection([('0', 'Low'),
                                 ('1', 'Normal')], default='0', index=True, string="Priority")
    sequence = fields.Integer(string='Sequence', index=True, default=10,
                              help="Gives the sequence order when displaying a list of tasks.")


class ProjectTaskStage(models.Model):
    _name = "s2u.project.task.stage"
    _description = "Fase"
    _order = "sequence"

    name = fields.Char(required=True, index=True, string='Fase')
    fold = fields.Boolean(string='Fold')
    sequence = fields.Integer(string='Sequence', index=True, default=10)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)


class ProjectHour(models.Model):
    _name = "s2u.project.hour"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Project hours"
    _order = 'date desc, user_id'
    _rec_name = "short_descript"

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()

        return super(ProjectHour, self)._track_subtype(init_values)

    @api.one
    @api.depends('date')
    def _compute_hour_year(self):
        if not self.date:
            self.year_hour = False
        else:
            hourdat = datetime.datetime.strptime(self.date, '%Y-%m-%d')
            self.year_hour = hourdat.strftime("%Y")

    @api.one
    @api.depends('date')
    def _compute_hour_month(self):
        if not self.date:
            self.month_hour = False
        else:
            hourdat = datetime.datetime.strptime(self.date, '%Y-%m-%d')
            self.month_hour = "%02d (%s)" % (hourdat.month, hourdat.strftime("%B"))

    @api.multi
    @api.constrains('project_id', 'projectrate_id')
    def _check_project_stage_rate(self):
        for hour in self:
            if hour.projectrate_id and hour.projectrate_id.project_id != hour.project_id:
                raise ValueError(_('Role does not belongs to project!'))
            if hour.task_id and hour.task_id.project_id != hour.project_id:
                raise ValueError(_('Task does not belongs to project!'))

    @api.one
    @api.depends('task_id', 'hours')
    def _compute_hours(self):

        self.hours_written = 0.0

        if self.task_id:
            hours = self.env['s2u.project.hour'].search([('task_id', '=', self.task_id.id),
                                                         ('change_request', '=', False)])
            for h in hours:
                if h.id == self.id:
                    continue
                self.hours_written += h.hours_zone
        if self.hours:
            self.hours_written += self.hours_zone

    @api.one
    @api.depends('hours', 'zone', 'projectrate_id')
    def _compute_hours_zone(self):

        self.hours_zone = 0.0

        if self.hours and self.projectrate_id:
            if self.zone == 'zone2':
                surcharge = self.projectrate_id.project_id.zone2
            elif self.zone == 'zone3':
                surcharge = self.projectrate_id.project_id.zone3
            elif self.zone == 'zone4':
                surcharge = self.projectrate_id.project_id.zone4
            else:
                surcharge = self.projectrate_id.project_id.zone1
            if surcharge:
                self.hours_zone = round(self.hours + self.hours / 100.0 * surcharge, 2)
            else:
                self.hours_zone = self.hours
        else:
            self.hours_zone = 0.0

    @api.model
    def create(self, vals):
        if self._context.get('default_locked', False):
            vals['partner_id'] = self._context['default_partner_id']
            vals['project_id'] = self._context['default_project_id']
            vals['projectrate_id'] = self._context['default_projectrate_id']
            vals['task_id'] = self._context['default_task_id']
            vals['locked'] = False
        if vals.get('task_state', False):
            task = self.env['s2u.project.task'].browse(vals['task_id'])
            if task.state == 'closed':
                raise ValueError(
                    _('This task is closed! Please contact your manager if you need to work on this task.'))
            if vals['task_state'] == 'ready':
                vals['task_forecast'] = 0.0
            task.write({
                'state': vals['task_state']
            })

        return super(ProjectHour, self).create(vals)

    @api.multi
    def write(self, vals):

        for hour in self:
            if vals.get('task_state', False):
                task_id = vals.get('task_id', hour.task_id.id if hour.task_id else False)
                task = self.env['s2u.project.task'].browse(task_id)
                if task.state == 'closed':
                    raise ValueError(_('This task is closed! Please contact your manager if you need to work on this task.'))
                if vals['task_state'] == 'ready':
                    vals['task_forecast'] = 0.0

                task.write({
                    'state': vals['task_state']
                })

        return super(ProjectHour, self).write(vals)

    @api.one
    def _compute_short_description(self):

        if self.name and len(self.name) > 50:
            self.short_descript = '%s ...' % self.name[:50]
        else:
            self.short_descript = self.name

    @api.one
    def _compute_zone_short(self):
        if self.zone:
            if self.zone == 'zone1':
                self.zone_short = 'TKT'
            elif self.zone == 'zone2':
                self.zone_short = 'BKT'
            elif self.zone == 'zone3':
                self.zone_short = 'ZZ'
            elif self.zone == 'zone4':
                self.zone_short = 'VA'
        else:
            self.zone_short = ''

    @api.onchange('task_id')
    def _onchange_task(self):
        if self.task_id:
            self.change_request = self.task_id.change_request
            self.change_request_id = self.task_id.change_request_id.id if self.task_id.change_request_id else False
        else:
            self.change_request = False
            self.change_request_id = False

    @api.onchange('hours')
    def _onchange_hours(self):
        if self.hours:
            frac, whole = math.modf(self.hours)
            if frac > 0.75:
                self.hours = whole + 1.0
            elif frac > 0.5:
                self.hours = whole + 0.75
            elif frac > 0.25:
                self.hours = whole + 0.5
            elif frac > 0.0:
                self.hours = whole + 0.25

    project_id = fields.Many2one('s2u.project', string='Project', required=True, ondelete='restrict')
    projectrate_id = fields.Many2one('s2u.project.stage.role', string='Role', ondelete='restrict')
    name = fields.Text(required=True, index=True, string='Description')
    date = fields.Date(string='Date', index=True, default=lambda self: fields.Date.context_today(self), copy=False)
    user_id = fields.Many2one('res.users', string='Employee', required=True,
                              default=lambda self: self.env.user, copy=False)
    hours = fields.Float(string='Hours', digits=(16, 2))
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    year_hour = fields.Char(string='Hour Year',
                            store=True, readonly=True, compute='_compute_hour_year')
    month_hour = fields.Char(string='Hour Month',
                             store=True, readonly=True, compute='_compute_hour_month')
    invpartnerline_id = fields.Many2one('s2u.project.hour.invoicing.partner.hour', string='Invoicing Partner Hour',
                                        ondelete='set null', copy=False)
    zone = fields.Selection([
        ('zone1', 'Office hours'),
        ('zone2', 'After hours'),
        ('zone3', 'Sat. and Sun.'),
        ('zone4', 'Holidays')
    ], string='Zone', index=True, default='zone1', required=True)
    zone_short = fields.Char(string='Zone', compute='_compute_zone_short', readonly=True)
    task_id = fields.Many2one('s2u.project.task', string='Task', ondelete='restrict')
    hours_written = fields.Float(string='Booked',
                                 readonly=True, compute='_compute_hours')
    hours_to_spend = fields.Float(string='Left over',
                                  readonly=True, related='task_id.hours_to_spend')
    task_forecast = fields.Float(string='Task forecast', related='task_id.task_forecast')
    internal_description = fields.Text(string='Internal description', related='task_id.internal_description')
    partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True)
    task_state = fields.Selection([
        ('open', 'Open'),
        ('ready', 'Ready')
    ], string='Task state', copy=False)
    short_descript = fields.Char(string='Description', compute='_compute_short_description')
    hours_zone = fields.Float(string='Hours/zone', digits=(16, 2), readonly=True, store=True, compute='_compute_hours_zone')
    change_request = fields.Boolean(string='SCR', related='task_id.change_request', store=True)
    change_request_id = fields.Many2one('s2u.sale.product', string='Request', related='task_id.change_request_id', store=True)
    locked = fields.Boolean(string='Locked', default=False)


class ProjectStageRole(models.Model):
    _name = "s2u.project.stage.role"
    _description = "Roles with the project fase"
    _rec_name = "rate_id"

    @api.multi
    def name_get(self):
        result = []
        for rate in self:
            name = '%s - %s' % (rate.rate_id.name,
                                rate.stage_id.name)
            result.append((rate.id, name))
        return result

    @api.one
    def _compute_amount(self):

        self.real_hours = 0.0
        self.rolling_forecast = 0.0
        self.forecast_alert = False
        hours = self.env['s2u.project.hour'].search([('projectrate_id', '=', self.id),
                                                     ('change_request', '=', False)])
        for h in hours:
            self.real_hours += h.hours_zone
        tasks = self.env['s2u.project.task'].search([('project_id', '=', self.project_id.id),
                                                     ('stage_id', '=', self.stage_id.id),
                                                     ('rate_id', '=', self.rate_id.id),
                                                     ('state', '=', 'open')])
        for t in tasks:
            self.rolling_forecast += t.task_forecast
        self.real_amount = self.real_hours * self.rate_per_hour
        self.hours_to_spend = self.hours - self.real_hours

        if round(self.hours, 2) and round(self.rolling_forecast, 2) > round(self.hours_to_spend, 2):
            self.forecast_alert = True

    @api.one
    def _compute_state(self):

        tasks = self.env['s2u.project.task'].search([('project_id', '=', self.project_id.id),
                                                     ('stage_id', '=', self.stage_id.id),
                                                     ('rate_id', '=', self.rate_id.id),
                                                     ('state', 'in', ['open', 'ready'])])
        if tasks:
            self.state = 'Open'
        else:
            self.state = 'Closed'

    @api.onchange('rate_id')
    def _onchange_rate(self):
        if self.rate_id:
            partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                search([('rate_id', '=', self.rate_id.id),
                        ('partner_id', '=', self.project_id.partner_id.id)], limit=1)
            if partner_rate:
                if partner_rate.discount_type == 'price':
                    self.rate_per_hour = partner_rate.rate_per_hour
                else:
                    self.rate_per_hour = round(self.rate_id.rate_per_hour - (self.rate_id.rate_per_hour * (partner_rate.rate_per_hour / 100.0)), 2)
            else:
                self.rate_per_hour = self.rate_id.rate_per_hour

    @api.onchange('hours', 'rate_per_hour')
    def _onchange_hours(self):
        if self.rate_id and self.hours and self.rate_per_hour:
            self.amount = self.rate_per_hour * self.hours
        else:
            self.amount = 0.0

    @api.multi
    def new_task(self):

        return {
            'name': _('New task'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2u.project.task',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': {
                'default_project_id': self.project_id.id if self.project_id else False,
                'default_stage_id': self.stage_id.id if self.stage_id else False,
                'default_rate_id': self.rate_id.id if self.rate_id else False,
                'default_descript': self.descript
            },
            'target': 'current'
        }

    project_id = fields.Many2one('s2u.project', string='Project', ondelete='cascade')
    stage_id = fields.Many2one('s2u.project.task.stage', string='Fase', ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    rate_id = fields.Many2one('s2u.project.hour.rate.def', string='Role', required=True, ondelete='restrict')
    rate_per_hour = fields.Monetary(string='Rate p/h', currency_field='currency_id', required=True)
    hours = fields.Float(string='Hours available', digits=(16, 2), required=True)
    amount = fields.Monetary(string='Amount available', required=True)
    real_hours = fields.Float(string='Hours booked',
                              readonly=True, compute='_compute_amount')
    real_amount = fields.Monetary(string='Amount booked',
                                  readonly=True, compute='_compute_amount')
    hours_to_spend = fields.Float(string='Left over',
                                  readonly=True, compute='_compute_amount')
    rolling_forecast = fields.Float(string='Rolling forecast', readonly=True,
                                    compute='_compute_amount')
    descript = fields.Text(string='Description')
    forecast_alert = fields.Boolean(string='Forecast alert',
                                    readonly=True, compute='_compute_amount', store=True)
    state = fields.Char(string='State', readonly=True, compute='_compute_state')

    _sql_constraints = [
        ('rate_uniq', 'unique (rate_id, stage_id, project_id)', _('This role is already present!'))
    ]

class ProjectSale(models.Model):
    _name = "s2u.project.sale"

    project_id = fields.Many2one('s2u.project', string='Project', ondelete='cascade')
    sale_id = fields.Many2one('s2u.sale', string='SO', index=True,
                              ondelete='cascade')

class Project(models.Model):
    _name = "s2u.project"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Project"
    _order = "sequence, name"

    @api.multi
    def _track_subtype(self, init_values):

        return super(Project, self)._track_subtype(init_values)

    @api.multi
    def _compute_is_favorite(self):
        for project in self:
            project.is_favorite = self.env.user in project.favorite_user_ids

    @api.multi
    def _inverse_is_favorite(self):
        favorite_projects = not_fav_projects = self.env['s2u.project'].sudo()
        for project in self:
            if self.env.user in project.favorite_user_ids:
                favorite_projects |= project
            else:
                not_fav_projects |= project

        # Project User has no write access for project.
        not_fav_projects.write({'favorite_user_ids': [(4, self.env.uid)]})
        favorite_projects.write({'favorite_user_ids': [(3, self.env.uid)]})

    @api.multi
    def _get_default_favorite_user_ids(self):
        return [(6, 0, [self.env.uid])]

    @api.multi
    def name_get(self):
        result = []
        for project in self:
            # client = project.partner_id.name
            if project.short_descript:
                name = '%s - %s' % (project.name, project.short_descript)
            else:
                name = project.name
            result.append((project.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', ('short_descript', '=ilike', name + '%'),
                      ('name', operator, name), ('partner_id.name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        projects = self.search(domain + args, limit=limit)
        return projects.name_get()

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id and self.partner_id.use_project_zones:
            self.zone1 = self.partner_id.project_zone1
            self.zone2 = self.partner_id.project_zone2
            self.zone3 = self.partner_id.project_zone3
            self.zone4 = self.partner_id.project_zone4
        else:
            self.zone1 = 0.0
            self.zone2 = 35.0
            self.zone3 = 50.0
            self.zone4 = 100.0

    @api.onchange('projecttype_id')
    def onchange_projecttype_id(self):

        if self.projecttype_id and not self.rate_ids:
            add_rates = []
            for stage in self.projecttype_id.stage_ids:
                if not stage.rate_ids:
                    continue
                for rate in stage.rate_ids:
                    partner_rate = False
                    if self.partner_id:
                        partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                            search([('rate_id', '=', rate.rate_id.id),
                                    ('partner_id', '=', self.partner_id.id)], limit=1)
                    if partner_rate:
                        if partner_rate.discount_type == 'price':
                            rate_per_hour = partner_rate.rate_per_hour
                        else:
                            rate_per_hour = round(rate.rate_id.rate_per_hour - (rate.rate_id.rate_per_hour * (partner_rate.rate_per_hour / 100.0)), 2)
                    else:
                        rate_per_hour = rate.rate_id.rate_per_hour

                    vals = {
                        'stage_id': stage.stage_id.id,
                        'rate_id': rate.rate_id.id,
                        'descript': rate.descript,
                        'rate_per_hour': rate_per_hour,
                        'hours': rate.hours,
                        'amount': rate.hours * rate_per_hour
                    }
                    add_rates.append((0, 0, vals))
            self.rate_ids = add_rates

    @api.model
    def _new_number(self):
        exists = self.env['ir.sequence'].sudo().search([('company_id', '=', self.env.user.company_id.id),
                                                        ('code', '=', 's2u.project')])
        if not exists:
            raise ValueError(_('Sequence for creating project not exists!'))

        sequence = exists[0]
        return sequence.with_context(ir_sequence_date=fields.Date.context_today(self)).next_by_id()

    @api.multi
    def broadcast_teamleaders(self):

        self.ensure_one()
        if not self.responsible_id:
            self.message_post(body=_('Hello teamleaders, who is taken the responsibility for this project?'),
                              subtype='mt_comment')
        return True

    def _get_invoice_count(self):

        for project in self:
            lines = self.env['s2u.account.invoice'].search([('project_id', '=', project.id)])
            invoice_ids = [l.id for l in lines]
            invoice_ids = list(set(invoice_ids))
            project.invoice_count = len(invoice_ids)

    @api.multi
    def action_view_invoice(self):
        lines = self.env['s2u.account.invoice'].search([('project_id', '=', self.id)])
        invoice_ids = [l.id for l in lines]
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

    def _get_sale_count(self):

        for project in self:
            if project.sale_id:
                project.sale_count = 1
            else:
                project.sale_count = 0

    @api.multi
    def action_view_sale(self):
        action = self.env.ref('s2usale.action_sale').read()[0]
        if len(self.sale_id):
            action['views'] = [(self.env.ref('s2usale.sale_form').id, 'form')]
            action['res_id'] = self.sale_id.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.multi
    def write_hours(self):

        return {
            'name': _('Write hours'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2u.project.hour',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': {
                'default_partner_id': self.partner_id.id if self.partner_id else False,
                'default_project_id': self.id
            }
        }

    def _compute_task_count(self):
        task_data = self.env['s2u.project.task'].read_group(
            [('project_id', 'in', self.ids), ('state', '=', 'open')], ['project_id'], ['project_id'])
        result = dict((data['project_id'][0], data['project_id_count']) for data in task_data)
        for project in self:
            project.task_count = result.get(project.id, 0)

    @api.multi
    def action_view_tasks(self):
        tasks = self.env['s2u.project.task'].search([('project_id', '=', self.id),
                                                     ('state', '=', 'open')])

        action = self.env.ref('s2uproject.action_project_task').read()[0]
        context = {
            'search_default_open': 1,
            'default_project_id': self.id
        }
        action['context'] = str(context)

        if len(tasks) >= 1:
            action['domain'] = [('id', 'in', tasks.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def _compute_hours_count(self):
        task_data = self.env['s2u.project.hour'].read_group(
            [('project_id', 'in', self.ids)], ['project_id'], ['project_id'])
        result = dict((data['project_id'][0], data['project_id_count']) for data in task_data)
        for project in self:
            project.hours_count = result.get(project.id, 0)

    @api.multi
    def action_view_hours(self):
        tasks = self.env['s2u.project.hour'].search([('project_id', '=', self.id)])

        action = self.env.ref('s2uproject.action_project_hour').read()[0]
        context = {
            'search_default_open': 1,
            'default_partner_id': self.partner_id.id,
            'default_project_id': self.id
        }
        action['context'] = str(context)

        if len(tasks) >= 1:
            action['domain'] = [('id', 'in', tasks.ids)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.one
    def _compute_hours(self):

        self.planning_hours = 0.0
        self.real_hours = 0.0
        self.hours_to_spend = 0.0
        self.rolling_forecast = 0.0

        for rate in self.rate_ids:
            self.planning_hours += rate.hours
            hours = self.env['s2u.project.hour'].search([('projectrate_id', '=', rate.id),
                                                         ('change_request', '=', False)])
            for h in hours:
                self.real_hours += h.hours_zone

        tasks = self.env['s2u.project.task'].search([('project_id', '=', self.id),
                                                     ('state', '=', 'open')])
        for t in tasks:
            self.rolling_forecast += t.task_forecast

        self.hours_to_spend = self.planning_hours - self.real_hours

    @api.multi
    def write(self, vals):

        if vals.get('state', False):
            if vals['state'] == 'open':

                for project in self:
                    # only responsable needed on normal projects, not support projects
                    if not (project.projecttype_id and project.projecttype_id.classification != 'none'):
                        if not vals.get('responsible_id', project.responsible_id):
                            raise UserError(_('Start project failed! No internal responsible assigned.'))

                for project in self:
                    if project.name == 'New project':
                        project.name = self._new_number()

        return super(Project, self).write(vals)

    @api.one
    def compute_classification(self):

        self.classification_visual = self.projecttype_id.classification \
            if self.projecttype_id and self.projecttype_id.classification != 'none' else ''

    def _get_document_count(self):

        for sale in self:
            docs = self.env['s2u.document'].search([('res_model', '=', 's2u.project'),
                                                    ('res_id', '=', sale.id)])
            sale.document_count = len(docs.ids)

    def _compute_task_needaction_count(self):
        for project in self:
            project.task_needaction_count = 0

    @api.multi
    def action_view_document(self):
        action = self.env.ref('s2udocument.action_document').read()[0]
        action['domain'] = [('res_model', '=', 's2u.project'),
                            ('res_id', '=', self.id)]
        context = {
            'search_default_open': 1,
            'default_entity_id': self.partner_id.id,
            'default_doc_context': self._description if self._description else self._name,
            'default_rec_context': self.name,
            'default_res_model': 's2u.project',
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
        worksheet.write('J1', 'Project', bold)
        worksheet.write('K1', 'Descript', bold)

        if self.type == 'b2b':
            worksheet.write('A2', self.partner_id.name)

            if self.responsible_extern_id and self.responsible_extern_id.address_id:
                worksheet.write('C2', self.responsible_extern_id.address_id.address)
                worksheet.write('D2', self.responsible_extern_id.address_id.zip)
                worksheet.write('E2', self.responsible_extern_id.address_id.city)
                worksheet.write('F2', self.responsible_extern_id.address_id.country_id.name)
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

        if self.responsible_extern_id:
            if self.responsible_extern_id.prefix:
                worksheet.write('B2', self.responsible_extern_id.prefix)
            else:
                worksheet.write('B2', self.responsible_extern_id.name)
            if self.responsible_extern_id.communication:
                worksheet.write('G2', self.responsible_extern_id.communication)
            if self.responsible_extern_id.prefix:
                worksheet.write('H2', self.responsible_extern_id.prefix)

        if self.partner_id.image and self.partner_id.image_fname:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            image_url = '%s/crm/logo/%d/%s' % (base_url, self.partner_id.id, self.partner_id.entity_code)
            worksheet.write('I2', image_url)

        worksheet.write('J2', self.name)
        worksheet.write('K2', self.short_descript if self.short_descript else '')

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

    name = fields.Char(required=True, index=True, string='Project', default='New project', readonly=True)
    reference = fields.Char(index=True, string='Origin')
    partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True, index=True)
    descript = fields.Html(string='Description')
    task_ids = fields.One2many('s2u.project.task', 'project_id', string='Tasks')
    type = fields.Selection([
        ('priv', 'Privat'),
        ('buss', 'Bussiness'),
    ], string='Type', index=True, default='buss', copy=False, required=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    hour_ids = fields.One2many('s2u.project.hour', 'project_id', string='Hours')
    skip_invoicing = fields.Boolean(string='Skip invoicing', default=False, help="Use this option when you do not want this project taken in the invoicing process (project will not be visible on invoice).")
    manual_invoicing = fields.Boolean(string='Manual invoicing', default=False, help="Use this option when you want to invoice this project manually only")
    zone1 = fields.Float(string='Office hours (%)', required=True, default='0.0')
    zone2 = fields.Float(string='After hours (%)', required=True, default='35.0')
    zone3 = fields.Float(string='Sat. and Sun. (%)', required=True, default='50.0')
    zone4 = fields.Float(string='Holidays (%)', required=True, default='100.0')
    sale_id = fields.Many2one('s2u.sale', string='SO', index=True,
                              ondelete='restrict')
    rate_ids = fields.One2many('s2u.project.stage.role', 'project_id', string='Roles')
    responsible_id = fields.Many2one('res.users', string='Resp. intern', track_visibility='onchange')
    active = fields.Boolean('Active', default=True)
    projecttype_id = fields.Many2one('s2u.project.type', string='Project type', ondelete='set null',
                                     readonly=True, states={'pending': [('readonly', False)]})
    date_project = fields.Date(string='Date', index=True, copy=False,
                               default=lambda self: fields.Date.context_today(self))
    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)
    short_descript = fields.Char(string='Short descript.', index=True, copy=False)
    customer_code = fields.Char(string='Your reference', index=True, copy=False)
    state = fields.Selection([
        ('pending', 'Not started'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('onhold', 'On hold')
    ], string='State', index=True, default='pending', required=True, copy=False, track_visibility='onchange')
    other_sale_ids = fields.One2many('s2u.project.sale', 'project_id', string='Other linked SO\'s')
    privacy_visibility = fields.Selection([
        ('employees', 'Visible by all employees'),
        ('portal', 'Visible by following customers')
    ], string='Privacy', required=True, default='employees')
    task_count = fields.Integer(compute='_compute_task_count', string="Tasks")
    task_needaction_count = fields.Integer(compute='_compute_task_needaction_count', string="Tasks")
    responsible_extern_id = fields.Many2one('s2u.crm.entity.contact', string='Resp. extern')
    sale_count = fields.Integer(string='# of Sales', compute='_get_sale_count', readonly=True)
    hours_count = fields.Integer(compute='_compute_hours_count', string="Hours")
    planning_hours = fields.Float(string='Available',
                                  readonly=True, compute='_compute_hours')
    real_hours = fields.Float(string='Booked',
                              readonly=True, compute='_compute_hours')
    hours_to_spend = fields.Float(string='Remaining',
                                  readonly=True, compute='_compute_hours')
    rolling_forecast = fields.Float(string='Rolling forecast', readonly=True,
                                    compute='_compute_hours')
    classification_visual = fields.Char(string='Classification', readonly=True, compute='compute_classification')
    document_count = fields.Integer(string='# of Docs', compute='_get_document_count', readonly=True)
    color = fields.Integer(string='Color Index')
    favorite_user_ids = fields.Many2many('res.users', 'project_favorite_user_rel', 'project_id', 'user_id',
                                         default=_get_default_favorite_user_ids, string='Members')
    is_favorite = fields.Boolean(compute='_compute_is_favorite', inverse='_inverse_is_favorite',
                                 string='Show Project on dashboard', help="Whether this project should be displayed on the dashboard or not")
    label_tasks = fields.Char(string='Use Tasks as', default='Open tasks',
                              help="Gives label to tasks on project's kanban view.")
    sequence = fields.Integer(default=10, help="Gives the sequence order when displaying a list of Projects.")


    @api.multi
    def create_quotation(self):

        self.ensure_one()

        vals = {
            'type': 'b2b' if self.type == 'buss' else 'b2c',
            'partner_id': self.partner_id.id,
            'invoice_type': 'b2b' if self.type == 'buss' else 'b2c',
            'invoice_partner_id': self.partner_id.id,
            'delivery_type': 'b2b' if self.type == 'buss' else 'b2c',
            'delivery_partner_id': self.partner_id.id,
            'invoicing': 'manual',
            'project': self.name
        }
        so = self.env['s2u.sale'].create(vals)

        product = self.env['s2u.sale.product'].search([('code', '=', 'hours')], limit=1)
        if not product:
            raise ValidationError(_('Product [hours] not defined!'))

        product = self.env['s2u.baseproduct.item'].search([('res_model', '=', 's2u.sale.product'),
                                                           ('res_id', '=', product.id)], limit=1)

        for calc in self.calc_ids:
            if calc.block_id:
                detail = '%s / %s' % (calc.block_id.name, calc.rate_id.name)
            else:
                detail = '%s' % (calc.rate_id.name)

            sale_line = {
                'sale_id': so.id,
                'product_id': product.id,
                'product_detail': detail,
                'project': self.name
            }
            sale_line = self.env['s2u.sale.line'].create(sale_line)

            ihours = int(calc.hours)
            qty = "%02d:%02d uur" % (ihours, (calc.hours - ihours) * 60)

            qty_line = {
                'saleline_id': sale_line.id,
                'qty': qty,
                'price': calc.rate_id.rate_per_hour,
                'price_per': 'item',
            }
            sale_line_qty = self.env['s2u.sale.line.qty'].create(qty_line)

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2usale.action_sale')
        list_view_id = imd.xmlid_to_res_id('s2usale.sale_tree')
        form_view_id = imd.xmlid_to_res_id('s2usale.sale_form')

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
            'res_id': so.id
        }

        return result

    @api.multi
    def create_invoice(self):

        invoicing_model = self.env['s2u.project.hour.invoicing']

        if self.skip_invoicing:
            raise UserError(_('This project is marked with \'Skip invoicing\'. Invoice can not be created.'))

        invoicing = invoicing_model.create({
            'hours_till': fields.Date.context_today(self),
            'invoice_contract': False,
            'hours_period': 'Afrekening t/m %s' % fields.Date.context_today(self),
            'project_only_id': self.id
        })
        invoices = invoicing.create_invoices()

        if not invoices:
            return False

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2uaccount.action_invoice')
        list_view_id = imd.xmlid_to_res_id('s2uaccount.invoice_tree')
        form_view_id = imd.xmlid_to_res_id('s2uaccount.invoice_form')

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
            'res_id': invoices[0].id
        }

        return result

    @api.multi
    def action_increase(self):
        self.ensure_one()

        wiz_form = self.env.ref('s2uproject.wizard_action_increase_view', False)
        ctx = dict(
            default_model='s2u.project',
            default_res_id=self.id,
        )
        return {
            'name': _('Increase project'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2uproject.action.increase',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }


class ProjectHourRate(models.Model):
    _name = "s2u.project.hour.rate"
    _description = "Employee costs"
    _order = "user_id"

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one('res.users', string='User', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    cost_per_hour = fields.Monetary(string='Costs p/h', currency_field='currency_id', required=True)
    rate_per_hour = fields.Monetary(string='Rate p/h', currency_field='currency_id', required=True)


class ProjectHourRateDef(models.Model):
    _name = "s2u.project.hour.rate.def"
    _description = "Roles"
    _order = "name"

    def _get_discount_count(self):

        for product in self:
            discounts = self.env['s2u.project.hour.rate.def.partner'].search([('rate_id', '=', product.id)])
            product.discount_count = len(discounts)

    @api.multi
    def action_view_discount(self):
        discounts = self.env['s2u.project.hour.rate.def.partner'].search([('rate_id', '=', self.id)])

        action = self.env.ref('s2uproject.action_sale_rate_discount').read()[0]
        action['domain'] = [('id', 'in', discounts.ids)]
        context = {
            'search_default_open': 1,
            'default_rate_id': self.id
        }
        action['context'] = str(context)
        return action

    name = fields.Char(required=True, index=True, string='Rate')
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    rate_per_hour = fields.Monetary(string='Rate p/h', currency_field='currency_id', required=True)
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 domain=[('type', '=', 'income')])
    discount_count = fields.Integer(string='# of Discounts', compute='_get_discount_count', readonly=True)


class ProjectHourRateDefPartner(models.Model):
    _name = "s2u.project.hour.rate.def.partner"
    _description = "Roles for partner"

    rate_id = fields.Many2one('s2u.project.hour.rate.def', string='Role', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='rate_id.currency_id')
    discount_type = fields.Selection([('price', 'Use this price'),
                                      ('percent', '% discount')], required=True, string='Type', default='price')
    rate_per_hour = fields.Monetary(string='Rate p/h or %', currency_field='currency_id', required=True)
    account_id = fields.Many2one('s2u.account.account', string='Account',
                                 domain=[('type', '=', 'income')])
    partner_id = fields.Many2one('s2u.crm.entity', string='Partner', required=True, index=True, ondelete='cascade')


class ProjectHourInvoicing(models.Model):
    _name = "s2u.project.hour.invoicing"
    _description = "Invoicing"
    _order = "date_invoicing desc"
    _rec_name = "hours_period"

    @api.model
    def _default_hours_till(self):

        tillm = datetime.date.today().month
        tilly = datetime.date.today().year

        return datetime.date(tilly, tillm, 1) - datetime.timedelta(days=1)

    @api.multi
    def do_invoicing(self):

        for invpartner in self.partner_ids:
            if invpartner.invoice_id:
                if invpartner.invoice_id.state == 'draft':
                    invpartner.invoice_id.unlink()
                elif invpartner.invoice_id.state == 'cancel':
                    invpartner.write({
                        'invoice_id': False
                    })

        self.invalidate_cache()

        self._cr.execute("DELETE FROM s2u_project_hour_invoicing_partner "
                         "WHERE invoicing_id=%s and invoice_id is null", (self.id,))
        self.invalidate_cache()

        projects = {}

        if self.project_only_id:
            hours = self.env['s2u.project.hour'].search([('project_id', '=', self.project_only_id.id),
                                                         ('date', '<=', self.hours_till),
                                                         ('invpartnerline_id', '=', False),
                                                         ('change_request', '=', False)])
        else:
            hours = self.env['s2u.project.hour'].search([('date', '<=', self.hours_till),
                                                         ('invpartnerline_id', '=', False),
                                                         ('change_request',  '=', False)])
        for hour in hours:
            if not self.project_only_id and hour.project_id.manual_invoicing:
                # only invoice this hours manually
                continue

            # mag eigenlijk niet voorkomen, maar toch even de check voor zekerheid
            if not hour.project_id or not hour.projectrate_id:
                continue

            if hour.project_id.skip_invoicing:
                continue

            if hour.task_id and hour.task_id.change_request:
                continue

            if hour.projectrate_id.id not in projects:
                projects[hour.projectrate_id.id] = {
                    'partner_id': hour.project_id.partner_id.id,
                    'project_id': hour.project_id.id,
                    'project': hour.project_id,
                    'stage': hour.projectrate_id.stage_id,
                    'rate': hour.projectrate_id,
                    'hours': {
                        'zone1': 0.0,
                        'zone2': 0.0,
                        'zone3': 0.0,
                        'zone4': 0.0,
                    },
                    'lines': []
                }

            projects[hour.projectrate_id.id]['hours'][hour.zone] += hour.hours
            projects[hour.projectrate_id.id]['lines'].append(hour.id)

        partners = {}
        for project_id, data in iter(projects.items()):
            if data['partner_id'] not in partners:
                partners[data['partner_id']] = self.env['s2u.project.hour.invoicing.partner'].create({
                    'invoicing_id': self.id,
                    'partner_id': data['partner_id']
                })
            data['invpartner'] = partners[data['partner_id']]

        tasks = self.env['s2u.project.task'].search([('state', '=', 'closed'),
                                                     ('change_request', '=', True),
                                                     ('invpartner_id', '=', False)])
        for task in tasks:
            if task.project_id.partner_id.id not in partners:
                partners[task.project_id.partner_id.id] = self.env['s2u.project.hour.invoicing.partner'].create({
                    'invoicing_id': self.id,
                    'partner_id': task.project_id.partner_id.id
                })

        self.invalidate_cache()

        for project_id, data in iter(projects.items()):
            for zone in ['zone1', 'zone2', 'zone3', 'zone4']:
                if not data['hours'][zone]:
                    continue
                project = self.env['s2u.project'].browse(data['project_id'])
                if zone == 'zone1':
                    surcharge = project.zone1
                elif zone == 'zone2':
                    surcharge = project.zone2
                elif zone == 'zone3':
                    surcharge = project.zone3
                elif zone == 'zone4':
                    surcharge = project.zone4
                else:
                    surcharge = 0.0

                partner_rate = self.env['s2u.project.hour.rate.def.partner']. \
                    search([('rate_id', '=', data['rate'].rate_id.id),
                            ('partner_id', '=', data['partner_id'])], limit=1)
                if partner_rate and partner_rate.account_id:
                    account = partner_rate.account_id
                else:
                    account = data['rate'].rate_id.account_id

                invpartnerline = self.env['s2u.project.hour.invoicing.partner.hour'].create({
                    'invpartner_id': data['invpartner'].id,
                    'hours': data['hours'][zone],
                    'projectrate_id': data['rate'].id,
                    'rate_per_hour': data['rate'].rate_per_hour,
                    'zone': zone,
                    'zone_surcharge': surcharge,
                    'account_id': account.id
                })

            hours = self.env['s2u.project.hour'].browse(data['lines'])
            hours.write({
                'invpartnerline_id': invpartnerline.id
            })

        self.invalidate_cache()

        if not self.project_only_id:
            if self.invoicing_contract:
                for contract in self.env['s2u.contract'].search([]):
                    invpartner = self.env['s2u.project.hour.invoicing.partner'].search(
                        [('invoicing_id', '=', self.id),
                         ('partner_id', '=', contract.partner_id.id)])
                    if not invpartner:
                        vals = {
                            'invoicing_id': self.id,
                            'partner_id': contract.partner_id.id
                        }
                        if contract.contact_id:
                            vals['contact_id'] = contract.contact_id.id
                        self.env['s2u.project.hour.invoicing.partner'].create(vals)
                    elif contract.contact_id:
                        invpartner[0].write({
                            'contact_id': contract.contact_id.id
                        })
                    self.invalidate_cache()

            self.write({'date_invoicing': fields.Date.context_today(self),
                        'user_id': self.env.user.id})
        return True

    @api.multi
    def create_invoices(self):

        invoice_model = self.env['s2u.account.invoice']
        invline_model = self.env['s2u.account.invoice.line']

        self.do_invoicing()
        self.invalidate_cache()

        for invpartner in self.partner_ids:

            if invpartner.invoice_id:
                continue

            invdata = {
                'type': 'b2b',
                'partner_id': invpartner.partner_id.id,
                'invoicing_id': self.id,
                'date_invoice': fields.Date.context_today(self),
                'date_financial': fields.Date.context_today(self)
            }

            if invpartner.partner_id.payment_term_id:
                due_date = datetime.datetime.strptime(invdata['date_invoice'], "%Y-%m-%d")
                due_date = due_date + datetime.timedelta(days=invpartner.partner_id.payment_term_id.payment_terms)
                invdata['date_due'] = due_date.strftime('%Y-%m-%d')

            if invpartner.contact_id:
                invdata['contact_id'] = invpartner.contact_id.id

            if invpartner.hour_ids:
                invdata['reference'] = self.hours_period

            address = invpartner.partner_id.get_postal()
            if address:
                invdata['address_id'] = address.id

            invoice = invoice_model.create(invdata)
            invoice_model += invoice

            if not self.project_only_id:
                if self.invoicing_contract:
                    contracts = self.env['s2u.contract'].search([('partner_id', '=', invpartner.partner_id.id)])
                    for contract in contracts:
                        contract_descript = contract.name
                        if self.contract_period:
                            contract_descript = '%s %s' % (contract_descript, self.contract_period)

                        invlinedata = {
                            'invoice_id': invoice.id,
                            'net_amount': contract.contract_amount,
                            'account_id': contract.account_id.id,
                            'descript': contract_descript,
                            'qty': '1 stuks',
                            'net_price': contract.contract_amount,
                            'sale_id': contract.sale_id.id if contract.sale_id else False
                        }

                        if invpartner.partner_id.vat_sell_id:
                            invlinedata['vat_id'] = invpartner.partner_id.vat_sell_id.id
                            invlinedata['vat_amount'] = invpartner.partner_id.vat_sell_id.calc_vat_from_netto_amount(
                                contract.contract_amount)
                            invlinedata['gross_amount'] = invpartner.partner_id.vat_sell_id.calc_gross_amount(
                                contract.contract_amount, invlinedata['vat_amount'])
                        elif contract.account_id.vat_id:
                            invlinedata['vat_id'] = contract.account_id.vat_id.id
                            invlinedata['vat_amount'] = contract.account_id.vat_id.calc_vat_from_netto_amount(
                                contract.contract_amount)
                            invlinedata['gross_amount'] = contract.account_id.vat_id.calc_gross_amount(
                                contract.contract_amount, invlinedata['vat_amount'])
                        else:
                            raise UserError(_('No VAT is defined for contract %s!' % contract.name))

                        invline_model.create(invlinedata)

            for line in invpartner.hour_ids:

                ihours = int(line.hours)
                qty = "%02d:%02d" % (ihours, (line.hours - ihours) * 60)

                if line.zone == 'zone1' and line.projectrate_id.project_id.zone1:
                    rate_per_hour = line.rate_per_hour + \
                        round(line.rate_per_hour * (line.projectrate_id.project_id.zone1 / 100.0), 2)
                elif line.zone == 'zone2' and line.projectrate_id.project_id.zone2:
                    rate_per_hour = line.rate_per_hour + \
                        round(line.rate_per_hour * (line.projectrate_id.project_id.zone2 / 100.0), 2)
                elif line.zone == 'zone3' and line.projectrate_id.project_id.zone3:
                    rate_per_hour = line.rate_per_hour + \
                        round(line.rate_per_hour * (line.projectrate_id.project_id.zone3 / 100.0), 2)
                elif line.zone == 'zone4' and line.projectrate_id.project_id.zone4:
                    rate_per_hour = line.rate_per_hour + \
                        round(line.rate_per_hour * (line.projectrate_id.project_id.zone4 / 100.0), 2)
                else:
                    rate_per_hour = line.rate_per_hour

                if line.projectrate_id.project_id.short_descript:
                    descript = '%s (%s), %s - %s (%s)' % (line.projectrate_id.project_id.name,
                                                          line.projectrate_id.project_id.short_descript,
                                                          line.projectrate_id.stage_id.name,
                                                          line.projectrate_id.rate_id.name,
                                                          line.zone)
                else:
                    descript = '%s, %s - %s (%s)' % (line.projectrate_id.project_id.name,
                                                     line.projectrate_id.stage_id.name,
                                                     line.projectrate_id.rate_id.name,
                                                     line.zone)
                invlinedata = {
                    'invoice_id': invoice.id,
                    'net_amount': rate_per_hour * line.hours,
                    'account_id': line.account_id.id,
                    'descript': descript,
                    'qty': qty,
                    'net_price': rate_per_hour,
                    'sale_id': line.projectrate_id.project_id.sale_id.id
                    if line.projectrate_id.project_id.sale_id else False
                }
                if invpartner.partner_id.vat_sell_id:
                    invlinedata['vat_id'] = invpartner.partner_id.vat_sell_id.id
                    invlinedata['vat_amount'] = invpartner.partner_id.vat_sell_id.calc_vat_from_netto_amount(
                        invlinedata['net_amount'])
                    invlinedata['gross_amount'] = invpartner.partner_id.vat_sell_id.calc_gross_amount(
                        invlinedata['net_amount'], invlinedata['vat_amount'])
                elif line.projectrate_id.rate_id.account_id.vat_id:
                    invlinedata['vat_id'] = line.projectrate_id.rate_id.account_id.vat_id.id
                    invlinedata['vat_amount'] = line.projectrate_id.rate_id.account_id.vat_id.calc_vat_from_netto_amount(
                        invlinedata['net_amount'])
                    invlinedata['gross_amount'] = line.projectrate_id.rate_id.account_id.vat_id.calc_gross_amount(
                        invlinedata['net_amount'], invlinedata['vat_amount'])
                else:
                    raise UserError(_('No VAT is defined for hour rate %s!' % line.rate_id.name))
                invline_model.create(invlinedata)

            # check closed tasks with change requests
            projects = self.env['s2u.project'].search([('partner_id', '=', invpartner.partner_id.id)])
            tasks = self.env['s2u.project.task'].search([('project_id', 'in', projects.ids),
                                                         ('state', '=', 'closed'),
                                                         ('change_request', '=', True),
                                                         ('invpartner_id', '=', False)])
            task_doubles = {}
            for task in tasks:
                if task.id in task_doubles:
                    task_doubles[task.id]['qty'] += 1
                else:
                    task_doubles[task.id] = {
                        'task': task,
                        'qty': 1
                    }

            tot_changerequest = 0.0
            for id, task_data in iter(task_doubles.items()):
                task = task_data['task']
                account = task.change_request_id.get_so_account()
                if not account:
                    raise UserError(_('No financial account is defined for change request %s!' % task.change_request_id.name))
                res = task.change_request_id.get_product_price('%d x' % task_data['qty'], False)
                invlinedata = {
                    'invoice_id': invoice.id,
                    'net_amount': res['price'],
                    'account_id': account.id,
                    'descript': task.change_request_id.name,
                    'qty': '%d x' % task_data['qty'],
                    'net_price': res.get('total_amount', res['price']),
                    'sale_id': task.project_id.sale_id.id if task.project_id.sale_id else False
                }
                tot_changerequest += res.get('total_amount', res['price'])
                if invpartner.partner_id.vat_sell_id:
                    invlinedata['vat_id'] = invpartner.partner_id.vat_sell_id.id
                    invlinedata['vat_amount'] = invpartner.partner_id.vat_sell_id.calc_vat_from_netto_amount(
                        invlinedata['net_amount'])
                    invlinedata['gross_amount'] = invpartner.partner_id.vat_sell_id.calc_gross_amount(
                        invlinedata['net_amount'], invlinedata['vat_amount'])
                elif hasattr(task.change_request_id, 'get_so_vat'):
                    invlinedata['vat_id'] = task.change_request_id.get_so_vat().id
                    invlinedata['vat_amount'] = task.change_request_id.get_so_vat().calc_vat_from_netto_amount(invlinedata['net_amount'])
                    invlinedata['gross_amount'] = task.change_request_id.get_so_vat().calc_gross_amount(invlinedata['net_amount'], invlinedata['vat_amount'])
                else:
                    raise UserError(_('No VAT is defined for change request %s!' % task.change_request_id.name))
                invline_model.create(invlinedata)

            tasks.write({
                'invpartner_id': invpartner.id
            })

            invpartner.write({
                'invoice_id': invoice.id,
                'tot_changerequest': tot_changerequest
            })

        self.write({
            'state': 'invoiced'
        })

        return invoice_model

    @api.multi
    def done_invoices(self):

        for invpartner in self.partner_ids:

            if invpartner.invoice_id and invpartner.invoice_id.state == 'draft':
                invpartner.invoice_id.do_validate()

        self.write({
            'state': 'done'
        })


    @api.one
    @api.depends('hours_till')
    def _compute_hour_year(self):
        if not self.hours_till:
            self.year_hour = False
        else:
            hourdat = datetime.datetime.strptime(self.hours_till, '%Y-%m-%d')
            self.year_hour = hourdat.strftime("%Y")

    @api.one
    @api.depends('hours_till')
    def _compute_hour_month(self):
        if not self.hours_till:
            self.month_hour = False
        else:
            hourdat = datetime.datetime.strptime(self.hours_till, '%Y-%m-%d')
            self.month_hour = hourdat.strftime("%B")

    @api.one
    @api.depends('partner_ids.tot_amount', 'partner_ids.tot_contract', 'partner_ids.tot_changerequest',
                 'partner_ids.tot_hours', 'invoicing_contract')
    def _compute_amount(self):
        self.tot_amount = sum((line.tot_amount + line.tot_contract + line.tot_changerequest) for line in self.partner_ids)
        self.tot_hours = sum(line.tot_hours for line in self.partner_ids)

    def _get_invoice_count(self):

        for inv in self:
            invlines = self.env['s2u.project.hour.invoicing.partner'].search([('invoicing_id', '=', inv.id)])
            invoice_ids = [l.invoice_id.id for l in invlines]
            invoice_ids = list(set(invoice_ids))
            inv.invoice_count = len(invoice_ids)

    @api.multi
    def action_view_invoice(self):
        invlines = self.env['s2u.project.hour.invoicing.partner'].search([('invoicing_id', '=', self.id)])
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

    _invoiced_state = {
        'draft': [('readonly', False)],
        'invoiced': [('readonly', False)],
    }

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one('res.users', string='User', copy=False, required=True,
                              default=lambda self: self.env.user, readonly=True, states=_invoiced_state)
    date_invoicing = fields.Date(string='Date', index=True, copy=False,
                                 default=lambda self: fields.Date.context_today(self),
                                 required=True, readonly=True, states=_invoiced_state)
    hours_till = fields.Date(string='Hours till', index=True, copy=False,
                             default=_default_hours_till, required=True, readonly=True, states=_invoiced_state)
    partner_ids = fields.One2many('s2u.project.hour.invoicing.partner', 'invoicing_id',
                                  string='Partners', copy=False, readonly=True, states=_invoiced_state)
    year_hour = fields.Char(string='Hour Year',
                            store=True, readonly=True, compute='_compute_hour_year')
    month_hour = fields.Char(string='Hour Month',
                             store=True, readonly=True, compute='_compute_hour_month')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    tot_amount = fields.Monetary(string='Tot. Amount',
                                 store=True, readonly=True, compute='_compute_amount')
    tot_hours = fields.Float(string='Tot. hours',
                             store=True, readonly=True, compute='_compute_amount')
    invoicing_contract = fields.Boolean(string='Contract', default=True, readonly=True, states=_invoiced_state)
    contract_period = fields.Char(string='Contract period', readonly=True, states=_invoiced_state)
    hours_period = fields.Char(string='Hours period', readonly=True, states=_invoiced_state)
    state = fields.Selection([
        ('draft', 'Concept'),
        ('invoiced', 'Invoiced'),
        ('done', 'Done'),
    ], required=True, default='draft', string='State', index=True, copy=False)
    project_only_id = fields.Many2one('s2u.project', string='This project only')
    invoice_count = fields.Integer(string='# of Invoices', compute='_get_invoice_count', readonly=True)


class ProjectHourInvoicingPartner(models.Model):
    _name = "s2u.project.hour.invoicing.partner"
    _description = "Invoicing Partner"
    _rec_name = "partner_id"

    @api.one
    @api.depends('hour_ids.rate_per_hour', 'hour_ids.hours')
    def _compute_amount(self):
        def make_rate(surcharge, rate):
            if surcharge:
                return rate + round(rate * surcharge / 100.0, 2)
            else:
                return rate
        self.tot_amount = sum((make_rate(line.zone_surcharge, line.rate_per_hour) * line.hours) for line in self.hour_ids)
        self.tot_hours = sum(line.hours for line in self.hour_ids)

    @api.one
    @api.depends('invoicing_id.invoicing_contract')
    def _compute_contract(self):
        contracts = self.env['s2u.contract'].search([('partner_id', '=', self.partner_id.id)])
        if contracts:
            self.tot_contract = sum(contract.contract_amount for contract in contracts)

    invoicing_id = fields.Many2one('s2u.project.hour.invoicing', string='Invoicing', required=True, ondelete='cascade')
    partner_id = fields.Many2one('s2u.crm.entity', string='Partner', required=True, index=True)
    hour_ids = fields.One2many('s2u.project.hour.invoicing.partner.hour', 'invpartner_id',
                               string='Hours', copy=False)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    tot_amount = fields.Monetary(string='Tot. amount',
                                 store=True, readonly=True, compute='_compute_amount')
    tot_hours = fields.Float(string='Tot. hours',
                             store=True, readonly=True, compute='_compute_amount')
    tot_contract = fields.Monetary(string='Tot. contract',
                                   store=True, readonly=True, compute='_compute_contract')
    tot_changerequest = fields.Monetary(string='Tot. change request')
    invoice_id = fields.Many2one('s2u.account.invoice', string='Invoice', ondelete='cascade')
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True)


class ProjectHourInvoicingPartnerHour(models.Model):
    _name = "s2u.project.hour.invoicing.partner.hour"
    _description = "Invoicing Partner Hour"

    invpartner_id = fields.Many2one('s2u.project.hour.invoicing.partner', string='Invoicing Partner', required=True,
                                    ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  related='invpartner_id.currency_id', store=True)
    rate_per_hour = fields.Monetary(string='Rate', currency_field='currency_id', required=True)
    hours = fields.Float(string='Hours', digits=(16, 2), required=True)
    projectrate_id = fields.Many2one('s2u.project.stage.role', string='Role', ondelete='restrict')
    zone = fields.Selection([('zone1', 'Office hours'),
                             ('zone2', 'After hours'),
                             ('zone3', 'Sat. and Sun.'),
                             ('zone4', 'Holidays')], string='Zone')
    zone_surcharge = fields.Float(string='Surcharge', default=0.0)
    account_id = fields.Many2one('s2u.account.account', string='Account')


class Contract(models.Model):
    _name = "s2u.contract"
    _description = "Contract"
    _order = "name"

    name = fields.Char(required=True, index=True, string='Contract')
    partner_id = fields.Many2one('s2u.crm.entity', string='Customer', required=True, index=True)
    descript = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    contract_amount = fields.Monetary(string='Amount', required=True)
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 domain=[('type', '=', 'income')])
    contact_id = fields.Many2one('s2u.crm.entity.contact', string='Contact', index=True)
    sale_id = fields.Many2one('s2u.sale', string='SO', index=True,
                              ondelete='restrict')


class ProjectReportInvoiceHours(models.TransientModel):

    _name = 's2u.project.hour.invoicing.report'

    type = fields.Selection([
        ('partner', 'Partner'),
        ('project', 'Project'),
    ], string='Type', index=True, default='partner', copy=False, required=True)
    invoicing_id = fields.Many2one('s2u.project.hour.invoicing', string='Invoicing', ondelete='cascade')
    invpartner_id = fields.Many2one('s2u.project.hour.invoicing.partner', string='Invoicing Partner', ondelete='cascade')
    project_id = fields.Many2one('s2u.project', string='Project', ondelete='cascade')

    @api.multi
    def do_report(self):
        data = {
            'form': self.read(['invpartner_id', 'type', 'project_id', 'invoicing_id'])[0]
        }

        return self.env.ref('s2uproject.s2uproject_hour_invoicing2').with_context(landscape=True). \
            report_action(self, data=data)


class ProjectReportDateHours(models.TransientModel):

    _name = 's2u.project.hour.date.report'

    type = fields.Selection([
        ('partner', 'Partner'),
        ('project', 'Project'),
    ], string='Type', index=True, default='partner', copy=False, required=True)
    partner_id = fields.Many2one('s2u.crm.entity', string='Partner', ondelete='cascade')
    project_id = fields.Many2one('s2u.project', string='Project', ondelete='cascade')
    date_from = fields.Date(string='Date From', index=True, copy=False, required=True,
                            default=lambda self: fields.Date.context_today(self))
    date_till = fields.Date(string='Date Till', index=True, copy=False, required=True,
                            default=lambda self: fields.Date.context_today(self))

    @api.multi
    def do_report(self):
        self.ensure_one()
        data = {
            'form': self.read(['partner_id', 'type', 'project_id', 'date_from', 'date_till'])[0]
        }
        return self.env.ref('s2uproject.s2uproject_print_hours').with_context(landscape=True).\
            report_action(self, data=data)


class ProjectBlockDef(models.Model):
    _name = "s2u.project.block.def"
    _description = "Blocks"
    _order = "sequence"

    name = fields.Char(required=True, index=True, string='Block')
    sequence = fields.Integer(string='Sequence', required=True, default=10)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)


class ContractTemplate(models.Model):
    _name = "s2u.contract.template"
    _inherit = 's2u.baseproduct.abstract'
    _description = "Contract Template"

    @api.multi
    def get_product_name(self):
        """Inherited from base product"""
        return '%s (%s)' % (self.name, 'Contract')

    @api.multi
    def check_product_detail(self, detail, product_name=False):

        # product details mag voor alle waarden bevatten, geen speciale syntax noodzakelijk
        if not detail:
            detail = ''
        return detail

    @api.multi
    def get_so_account(self):

        self.ensure_one()
        if self.account_id:
            return self.account_id
        else:
            return super(ContractTemplate, self).get_so_account()

    @api.multi
    def get_so_vat(self):

        self.ensure_one()
        return super(ContractTemplate, self).get_so_vat()

    @api.multi
    def get_po_account(self, supplier=False):

        self.ensure_one()
        return super(ContractTemplate, self).get_po_account(supplier=supplier)

    @api.multi
    def get_po_vat(self, supplier=False):

        self.ensure_one()
        return super(ContractTemplate, self).get_po_vat(supplier=supplier)

    @api.multi
    def get_product_price(self, qty, details, ctx=False):
        """"Inherited from base product"""

        if not (isinstance(qty, int) or isinstance(qty, float)):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(qty)
        if not qty:
            return False

        res = {
            'price': self.amount * 12.0,
            'price_per': 'item',
            'total_amount': qty * self.amount * 12.0
        }
        return res

    name = fields.Char(string='Name', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    amount = fields.Monetary(string='Amount monthly', currency_field='currency_id')
    account_id = fields.Many2one('s2u.account.account', string='Account', required=True,
                                 domain=[('type', '=', 'income')])
    product_ids = fields.One2many('s2u.contract.template.product', 'template_id',
                                  string='Products', copy=True)
    descript = fields.Text(string='Description')
    product_type = fields.Selection(default='service')


class ContractTemplateProduct(models.Model):
    _name = "s2u.contract.template.product"
    _inherit = "s2u.baseproduct.transaction.abstract"

    @api.model
    def create(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(ContractTemplateProduct, self).create(vals)

    @api.multi
    def write(self, vals):

        if vals.get('qty', False):
            qty = self.env['s2u.baseproduct.abstract'].parse_qty(vals['qty'])
            vals['product_qty'] = qty

        return super(ContractTemplateProduct, self).write(vals)

    template_id = fields.Many2one('s2u.contract.template', string='Template', required=True, ondelete='cascade')
    qty = fields.Char(string='Qty', required=True, default='1 stuks')
    use_product_detail_so = fields.Boolean(string='Use details SO', default=False)


class ProjectTypeStageRole(models.Model):
    _name = "s2u.project.type.stage.role"
    _description = "Roles with the project type fase"
    _rec_name = "rate_id"

    @api.multi
    def name_get(self):
        result = []
        for rate in self:
            name = '%s [%s - %s]' % (rate.rate_id.name,
                                     rate.projecttypestage_id.projecttype_id.name,
                                     rate.projecttypestage_id.stage_id.name)
            result.append((rate.id, name))
        return result

    @api.onchange('rate_id')
    def _onchange_rate(self):
        if self.rate_id:
            self.rate_per_hour = self.rate_id.rate_per_hour

    projecttypestage_id = fields.Many2one('s2u.project.type.stage', string='Fase', required=True, ondelete='cascade')
    rate_id = fields.Many2one('s2u.project.hour.rate.def', string='Role', required=True, ondelete='restrict')
    hours = fields.Float(string='Hours', digits=(16, 2), required=True)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.user.company_id.currency_id)
    rate_per_hour = fields.Monetary(string='Rate p/h', currency_field='currency_id')
    descript = fields.Text(string='Description')

    _sql_constraints = [
        ('rate_uniq', 'unique (rate_id, projecttypestage_id)', _('This role is already present!'))
    ]


class ProjectTypeStage(models.Model):
    _name = "s2u.project.type.stage"
    _description = "Project type fases"
    _rec_name = "stage_id"
    _order = "projecttype_id, sequence"

    @api.multi
    def name_get(self):
        result = []
        for stage in self:
            name = '%s [%s]' % (stage.stage_id.name, stage.projecttype_id.name)
            result.append((stage.id, name))
        return result

    @api.one
    def _compute_amount(self):

        self.hours = 0.0

        for r in self.rate_ids:
            self.hours += r.hours

    projecttype_id = fields.Many2one('s2u.project.type', string='Project type', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    stage_id = fields.Many2one('s2u.project.task.stage', string='Fase', ondelete='restrict', required=True)
    rate_ids = fields.One2many('s2u.project.type.stage.role', 'projecttypestage_id', string='Roles', copy=True)
    hours = fields.Float(string='Hours', readonly=True, compute='_compute_amount')

    _sql_constraints = [
        ('stage_uniq', 'unique (stage_id, projecttype_id)', _('This fase is already present!'))
    ]


class ProjectType(models.Model):
    _name = "s2u.project.type"
    _description = "Project type"
    _order = "name"

    @api.multi
    def action_create_project(self):
        self.ensure_one()

        wiz_form = self.env.ref('s2uproject.wizard_action_create_project_view', False)
        ctx = dict(
            default_model='s2u.project.type',
            default_res_id=self.id,
        )
        return {
            'name': _('Create project'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 's2uproject.action.create.project',
            'views': [(wiz_form.id, 'form')],
            'view_id': wiz_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update(name=_("%s (copy)") % (self.name or ''))
        return super(ProjectType, self).copy(default)

    @api.one
    def compute_classification(self):
        self.classification_visual = self.classification if self.classification != 'none' else ''

    name = fields.Char(required=True, index=True, string='Type')
    stage_ids = fields.One2many('s2u.project.type.stage', 'projecttype_id', string='Fases', copy=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    classification = fields.Selection([
        ('none', 'None'),
        ('h', 'SH&E'),
        ('b', 'Brons'),
        ('s', 'Silver'),
        ('g', 'Gold'),
        ('p', 'Platinum')
    ], string='Classification', index=True, copy=False, default='none', required=True)
    classification_visual = fields.Char(string='Classification', readonly=True, compute='compute_classification')
    allow_in_so = fields.Boolean(string='Allow in SO', default=True, required=True)

    _sql_constraints = [
        (
        'name_company_uniq', 'unique (name, company_id)', 'The type name should be unique!')
    ]
