import datetime
import re

from odoo.tools.misc import formatLang
from odoo.osv import expression
from odoo import api, fields, models, _


class Label(models.Model):
    _name = "s2u.label"
    _order = 'sequence,id'

    @api.multi
    @api.depends('name', 'code')
    def name_get(self):
        result = []
        for label in self:
            if label.code:
                name = label.name + ' (' + label.code + ')'
            else:
                name = label.name
            result.append((label.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=ilike', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        labels = self.search(domain + args, limit=limit)
        return labels.name_get()

    name = fields.Char(required=True, index=True, string='Label', translate=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    code = fields.Char(index=True, string='Code')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    default_value = fields.Text(string='Default value')
    bold = fields.Boolean(string='Bold', default=False)


# TODO: kan worden verwijdered
class LayoutLabel(models.Model):
    _name = "s2u.layout.label"
    _order = "sequence, label_id"

    @api.onchange('label_id')
    def _onchange_label_id(self):

        if self.label_id:
            self.sequence = self.label_id.sequence

        if self.label_id and self.label_id.default_value:
            self.default_value = self.label_id.default_value

    layout_id = fields.Many2one('s2u.layout', string='Layout', required=True, ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    default_value = fields.Char(string='Default')


# TODO: kan worden verwijdered
class LayoutLabelPORequest(models.Model):
    _name = "s2u.layout.label.po.request"
    _order = "sequence, label_id"

    @api.onchange('label_id')
    def _onchange_label_id(self):
        if self.label_id and self.label_id.default_value:
            self.default_value = self.label_id.default_value
            self.sequence = self.label_id.sequence

    layout_id = fields.Many2one('s2u.layout', string='Layout', required=True, ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    default_value = fields.Char(string='Default')


# TODO: kan worden verwijdered
class LayoutLabelPOOrder(models.Model):
    _name = "s2u.layout.label.po.order"
    _order = "sequence, label_id"

    @api.onchange('label_id')
    def _onchange_label_id(self):
        if self.label_id and self.label_id.default_value:
            self.default_value = self.label_id.default_value
            self.sequence = self.label_id.sequence

    layout_id = fields.Many2one('s2u.layout', string='Layout', required=True, ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    default_value = fields.Char(string='Default')


class LayoutLabelSO(models.Model):
    _name = "s2u.layout.label.so"
    _order = "sequence, label_id"

    @api.onchange('label_id')
    def _onchange_label_id(self):

        if self.label_id and self.label_id.default_value:
            self.default_value = self.label_id.default_value
            self.sequence = self.label_id.sequence

    layout_id = fields.Many2one('s2u.layout', string='Layout', required=True, ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    default_value = fields.Char(string='Default')
    display = fields.Selection([
        ('both', 'Quotation and Order'),
        ('quotation', 'Quotation only'),
        ('order', 'Order only')
    ], required=True, default='both', string='Sale')
    on_invoice = fields.Boolean(string='On invoice')


class LayoutLabelPO(models.Model):
    _name = "s2u.layout.label.po"
    _order = "sequence, label_id"

    @api.onchange('label_id')
    def _onchange_label_id(self):

        if self.label_id and self.label_id.default_value:
            self.default_value = self.label_id.default_value
            self.sequence = self.label_id.sequence

    layout_id = fields.Many2one('s2u.layout', string='Layout', required=True, ondelete='cascade')
    label_id = fields.Many2one('s2u.label', string='Label', ondelete='restrict', required=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    default_value = fields.Char(string='Default')
    display = fields.Selection([
        ('both', 'Request and Order'),
        ('request', 'Request only'),
        ('order', 'Order only')
    ], required=True, default='both', string='Display')


class Layout(models.Model):
    _name = "s2u.layout"
    _order = "name"

    name = fields.Char(string='Layout', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    use_as_default = fields.Boolean(string='Use as default', default=False)
    label_so_ids = fields.One2many('s2u.layout.label.so', 'layout_id',
                                    string='SO', copy=True)
    label_po_ids = fields.One2many('s2u.layout.label.po', 'layout_id',
                                   string='PO', copy=True)
