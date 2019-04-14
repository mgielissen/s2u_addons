# -*- coding: utf-8 -*-
import datetime

from odoo.exceptions import UserError, ValidationError
from odoo import _, api, fields, models


class ActionCloseTasks(models.TransientModel):
    _name = 's2u.project.action.close.tasks'
    _description = 'Close tasks marked as ready'

    @api.multi
    def do_close_tasks(self):

        self.ensure_one()

        task_ids = self._context['active_ids']
        tasks = self.env['s2u.project.task'].browse(task_ids)
        for task in tasks:
            if task.manager_id.id != self.env.user.id:
                raise ValidationError(_('You can not close task: %s, because you are not the manager of the project: %s.' % (task.name, task.project_id.name)))
            if task.state not in ['ready', 'open']:
                raise ValidationError(_('You can not close task: %s, because it is not ready yet.' % (task.name)))
        tasks.write({
            'state': 'closed'
        })

        return {'type': 'ir.actions.act_window_close'}


class ActionReopenTasks(models.TransientModel):
    _name = 's2u.project.action.reopen.tasks'
    _description = 'Reopen ready and/order closed tasks'

    @api.multi
    def do_reopen_tasks(self):

        self.ensure_one()

        task_ids = self._context['active_ids']
        tasks = self.env['s2u.project.task'].browse(task_ids)
        for task in tasks:
            if task.manager_id.id != self.env.user.id:
                raise ValidationError(_(
                    'You can not reopen task: %s, because you are not the manager of the project: %s.' % (task.name, task.project_id.name)))
            if task.state not in ['ready', 'closed']:
                raise ValidationError(_('You can not reopen task: %s, because it is not ready or closed.' % (task.name)))
        tasks.write({
            'state': 'open'
        })

        return {'type': 'ir.actions.act_window_close'}
