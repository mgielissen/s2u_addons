from odoo import api, models

class PrintInvoice(models.AbstractModel):
    _name = 'report.s2uaccount.print_invoice_so'

    @api.model
    def get_report_values(self, docids, data=None):

        return {
            'doc_ids': docids,
            'doc_model': self.env['s2u.account.invoice'],
            'data': data,
            'docs': self.env['s2u.account.invoice'].browse(docids)
        }
