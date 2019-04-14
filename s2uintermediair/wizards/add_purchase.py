# -*- coding: utf-8 -*-

from openerp.exceptions import UserError, ValidationError
from openerp import _, api, fields, models


class AddPurchase(models.TransientModel):
    """
    """
    _name = 's2u.intermediair.add.purchase'
    _description = 'Add purchase'

    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 default=lambda self: self.env.user.company_id)
    project = fields.Char(string='Project', required=True)
    reference = fields.Char(string='Reference')
    supplier_ids = fields.Many2many('s2u.crm.entity', 'intermediair_add_purchase_rel', 'add_id', 'entity_id',
                                    string='Suppliers', required=True)
    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string="Project", ondelete='set null')
    line_ids = fields.One2many('s2u.intermediair.add.purchase.line', 'create_id', string='Purchase')

    @api.model
    def default_get(self, fields):

        result = super(AddPurchase, self).default_get(fields)

        context = self._context
        active_ids = context.get('active_ids')
        project = self.env['s2u.intermediair.calc'].browse(active_ids[0])
        result['project'] = project.name
        result['reference'] = project.reference
        result['intermediair_calc_id'] = project.id

        lines = []
        sequence = 10
        for project in self.env['s2u.intermediair.calc'].browse(active_ids):
            for line in project.calc_po_ids:
                product = self.env[line.product_id.res_model].browse(line.product_id.res_id)
                if hasattr(product, 'layout_id'):
                    layout_id = product.layout_id.id
                else:
                    layout_id = False

                lines.append((0, 0, {
                    'intermediair_calc_id': project.id,
                    'pos': line.pos,
                    'qty': line.qty,
                    'distribution': line.distribution,
                    'product_id': line.product_id.id,
                    'product_detail': line.product_detail,
                    'sequence': sequence,
                    'calcpurchase_id': line.id,
                    'layout_id': layout_id
                }))
                sequence += 10
            result['line_ids'] = lines

        return result

    @api.multi
    def do_purchase(self):
        self.ensure_one()

        purchase_ids = []
        project = self.intermediair_calc_id

        to_purchase = False
        for line in self.line_ids:
            if line.purchase:
                to_purchase = True
                break
        if not to_purchase:
            raise UserError(_('Please select products to purchase!'))

        for supplier in self.supplier_ids:
            delivery = project.delivery_partner_id.prepare_delivery()
            vals = {
                'partner_id': supplier.id,
                'delivery_type': 'dropshipping',
                'dropshipping_type': project.delivery_type,
                'dropshipping_partner_id': project.delivery_partner_id.id,
                'dropshipping_address': delivery,
                'project': self.project if self.project else project.name,
                'reference': self.reference if self.reference else project.reference,
                'date_delivery': project.date_delivery,
                'date_artwork': project.date_artwork,
            }

            if project.delivery_contact_id:
                vals['dropshipping_contact_id'] = project.delivery_contact_id.id
            if project.delivery_address:
                vals['dropshipping_address'] = project.delivery_address

            purchase = self.env['s2u.purchase'].create(vals)
            purchase_ids.append(purchase.id)

            for line in self.line_ids:
                if not line.purchase:
                    continue

                exists = self.env['s2u.purchase.line'].search([('purchase_id', '=', purchase.id),
                                                               ('product_id', '=', line.product_id.id),
                                                               ('product_detail', '=', line.product_detail)], limit=1)
                if exists:
                    purchase_line = exists
                else:
                    po_line = {
                        'purchase_id': purchase.id,
                        'intermediair_calc_id': line.intermediair_calc_id.id,
                        'product_id': line.product_id.id,
                        'product_detail': line.product_detail,
                    }
                    if line.intermediair_calc_id.analytic_id:
                        po_line['analytic_id'] = line.intermediair_calc_id.analytic_id.id
                    purchase_line = self.env['s2u.purchase.line'].create(po_line)

                so_present = self.env['s2u.sale.line'].search([('intermediair_calc_id', '=', line.intermediair_calc_id.id)])

                line.calcpurchase_id.write({
                    'purchaseline_id': purchase_line.id,
                    'po_amount_locked': True if so_present else False
                })

                exists = self.env['s2u.purchase.line.qty'].search([('purchaseline_id', '=', purchase_line.id),
                                                                   ('qty', '=', line.qty)], limit=1)
                if not exists:
                    if line.distribution == '{{distribution}}':
                        distribution = self.env['s2u.intermediair.calc.totals'].search([('calc_id', '=', project.id),
                                                                                        ('pos', '=', line.pos)], limit=1)
                        if not distribution:
                            raise UserError(_('Can not match distribution! Position [%s] is not defined.' % line.pos))
                        distribution = distribution.distribution
                    else:
                        distribution = line.distribution

                    qty_line = {
                        'purchaseline_id': purchase_line.id,
                        'qty': line.qty,
                        'distribution': distribution,
                        'intermediair_calc_id': line.intermediair_calc_id.id,
                    }

                    if line.intermediair_calc_id.analytic_id:
                        qty_line['analytic_id'] = line.intermediair_calc_id.analytic_id.id

                    product = self.env[line.product_id.res_model].browse(line.product_id.res_id)
                    purchase_info = product.get_purchase_price(line.qty,
                                                               line.product_detail,
                                                               ctx={
                                                                   'supplier_id': supplier.id
                                                               })
                    if purchase_info:
                        qty_line['price'] = purchase_info['price']
                        qty_line['price_per'] = 'total'

                    self.env['s2u.purchase.line.qty'].create(qty_line)

                if line.layout_id:
                    if not purchase_line.label_ids:
                        for label in line.layout_id.label_po_ids:
                            find_label = self.env['s2u.intermediair.calc.detail'].search([('calc_id', '=', project.id),
                                                                                          ('label_id', '=', label.label_id.id)], limit=1)
                            if find_label and find_label.value:
                                value = find_label.value
                            else:
                                value = label.default_value

                            vals = {
                                'purchaseline_id': purchase_line.id,
                                'label_id': label.label_id.id,
                                'value': value,
                                'sequence': label.sequence,
                                'display': label.display
                            }
                            self.env['s2u.purchase.line.label'].create(vals)

        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('s2usale.action_purchase')
        list_view_id = imd.xmlid_to_res_id('s2usale.purchase_tree')
        form_view_id = imd.xmlid_to_res_id('s2usale.purchase_form')

        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form'], [False, 'graph'], [False, 'kanban'],
                      [False, 'calendar'], [False, 'pivot']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }

        if len(purchase_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % purchase_ids
        elif len(purchase_ids) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = purchase_ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}

        return result


class AddPurchaseLine(models.TransientModel):
    _name = 's2u.intermediair.add.purchase.line'
    _order = 'sequence'

    create_id = fields.Many2one('s2u.intermediair.add.purchase', string='Create', ondelete='set null')
    pos = fields.Selection([
        ('pos1', 'Staffel 1.'),
        ('pos2', 'Staffel 2.'),
        ('pos3', 'Staffel 3.'),
        ('pos4', 'Staffel 4.'),
        ('pos5', 'Staffel 5.'),
        ('once', 'Label')
    ], required=True, default='pos1', string='Pos')
    qty = fields.Char(string='Qty', required=True)
    distribution = fields.Char(string='Distribution')
    product_id = fields.Many2one('s2u.baseproduct.item', string='Product', required=True)
    product_detail = fields.Char(string='Details')
    sequence = fields.Integer(string='Sequence', default=10)
    purchase = fields.Boolean(string='Purchase')
    layout_id = fields.Many2one('s2u.layout', string='PO Layout', ondelete='set null')
    calcpurchase_id = fields.Many2one('s2u.intermediair.calc.purchase', string="Calc. purchase", ondelete='set null')
    intermediair_calc_id = fields.Many2one('s2u.intermediair.calc', string="Project", ondelete='set null')

