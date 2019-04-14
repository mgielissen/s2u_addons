# -*- coding: utf-8 -*-

import time
import math

from openerp.osv import expression
from openerp.tools.float_utils import float_round as round
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.exceptions import UserError, ValidationError
from openerp import api, fields, models, _


class ProductionUsedMaterials(models.Model):
    _inherit = "s2u.warehouse.production.used.materials"

    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string="Project", ondelete='restrict')
