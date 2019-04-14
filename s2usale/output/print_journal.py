import datetime
from odoo import api, fields, models, _

class PrintJournal(models.AbstractModel):
    _name = 'report.s2usale.report_journal'
    _inherit = 's2uaccount.abstract_report_journal'

    @api.model
    def get_report_values(self, docids, data=None):

        sales = self.env['s2u.sale'].browse(docids)
        pages = []
        for order in sales:
            invlines = self.env['s2u.account.invoice.line'].search([('sale_id', '=', order.id)])
            invoice_ids = [l.invoice_id.id for l in invlines]
            invoice_ids = list(set(invoice_ids))

            moves_invoices = self.moves_for_invoices(invoice_ids)
            moves_bank = self.moves_for_invoices_on_bank(invoice_ids)
            moves_memorial = self.moves_for_invoices_on_memorial(invoice_ids)

            todolines = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', order.id)])
            outgoing_ids = [l.outgoing_id.id for l in todolines]
            outgoing_ids = list(set(outgoing_ids))

            moves_outgoing = self.moves_for_stock_on_outgoing(outgoing_ids)

            todos = self.env['s2u.warehouse.outgoing.todo'].search([('sale_id', '=', order.id)])
            rmas = self.env['s2u.warehouse.rma.line'].search([('todo_id', 'in', todos.ids)])
            rma_ids = [r.rma_id.id for r in rmas]
            rma_ids = list(set(rma_ids))

            move_rma = self.moves_for_stock_on_rma(rma_ids)

            moves = moves_invoices + moves_bank + moves_memorial + moves_outgoing + move_rma

            pages.append({
                'title': _('Journal for Sales Order %s' % order.name),
                'moves': moves
            })

        return {
            'pages': pages
        }

class PrintJournalPO(models.AbstractModel):
    _name = 'report.s2usale.report_journal_po'

    @api.model
    def get_report_values(self, docids, data=None):

        purchases = self.env['s2u.purchase'].browse(docids)
        pages = []
        for order in purchases:
            moves = []

            invlines = self.env['s2u.account.invoice.po.line'].search([('purchaseline_id', 'in', order.line_ids.ids)])
            invoice_ids = [l.invoice_id.id for l in invlines]
            invoice_ids = list(set(invoice_ids))

            for invoice in self.env['s2u.account.invoice.po'].browse(invoice_ids):
                if invoice.state != 'valid':
                    continue
                lines = []
                debit = 0.0
                credit = 0.0
                if invoice.amount_gross > 0.0:
                    lines.append({
                        'date': invoice.date_financial,
                        'account': invoice.account_id.code,
                        'descript': invoice.account_id.name,
                        'credit': invoice.amount_gross
                    })
                    credit += invoice.amount_gross
                elif invoice.amount_gross < 0.0:
                    lines.append({
                        'date': invoice.date_financial,
                        'account': invoice.account_id.code,
                        'descript': invoice.account_id.name,
                        'debit': abs(invoice.amount_gross)
                    })
                    debit += abs(invoice.amount_gross)
                for invline in invoice.line_ids:
                    if invline.net_amount > 0.0:
                        lines.append({
                            'date': '',
                            'account': invline.account_id.code,
                            'descript': invline.account_id.name,
                            'debit': invline.net_amount
                        })
                        debit += invline.net_amount
                    elif invline.net_amount < 0.0:
                        lines.append({
                            'date': '',
                            'account': invline.account_id.code,
                            'descript': invline.account_id.name,
                            'credit': abs(invline.net_amount)
                        })
                        credit += abs(invline.net_amount)

                for invline in invoice.line_ids:
                    for rule in invline.vat_id.rule_ids:
                        if rule.rule_type == 'plus':
                            amount = invline.vat_amount
                        else:
                            amount = invline.vat_amount * -1.0
                        if amount > 0.0:
                            lines.append({
                                'date': '',
                                'account': rule.account_id.code,
                                'descript': rule.account_id.name,
                                'debit': amount
                            })
                            debit += amount
                        elif amount < 0.0:
                            lines.append({
                                'date': '',
                                'account': rule.account_id.code,
                                'descript': rule.account_id.name,
                                'credit': abs(amount)
                            })
                            credit += abs(amount)
                if lines:
                    moves.append({
                        'title': 'PO Invoice %s %s' % (invoice.name, invoice.reference),
                        'date': invoice.date_financial,
                        'lines': lines,
                        'debit': debit,
                        'credit': credit
                    })

                banklines_so = self.env['s2u.account.bank.line.invoice.po'].search([('invoice_id', '=', invoice.id)])
                bankline_ids = [b.bankline_id.id for b in banklines_so]
                bankline_ids = list(set(bankline_ids))
                for bankline in self.env['s2u.account.bank.line'].browse(bankline_ids):
                    banklines_po = self.env['s2u.account.bank.line.invoice.po'].search([('invoice_id', '=', invoice.id),
                                                                                        ('bankline_id', '=',bankline.id)])
                    lines = []
                    debit = 0.0
                    credit = 0.0
                    for bl in banklines_po:
                        amount = bl.trans_amount
                        if bl.type in ['diff', 'disc']:
                            amount += bl.open_amount
                        if amount < 0.0:
                            lines.append({
                                'date': '',
                                'account': invoice.account_id.code,
                                'descript': invoice.account_id.name,
                                'debit': abs(amount)
                            })
                            debit += abs(amount)

                            lines.append({
                                'date': '',
                                'account': bl.bankline_id.bank_id.account_id.code,
                                'descript': bl.bankline_id.bank_id.account_id.name,
                                'credit': abs(bl.trans_amount)
                            })
                            credit += abs(bl.trans_amount)

                            if bl.type == 'diff':
                                lines.append({
                                    'date': '',
                                    'account': bl.bankline_id.bank_id.account_accepted_id.code,
                                    'descript': bl.bankline_id.bank_id.account_accepted_id.name,
                                    'credit': abs(bl.open_amount)
                                })
                                credit += abs(bl.open_amount)
                            elif bl.type == 'disc':
                                lines.append({
                                    'date': '',
                                    'account': bl.bankline_id.bank_id.account_po_difference_id.code,
                                    'descript': bl.bankline_id.bank_id.account_po_difference_id.name,
                                    'credit': abs(bl.open_amount)
                                })
                                credit += abs(bl.open_amount)
                        elif amount > 0.0:
                            lines.append({
                                'date': '',
                                'account': invoice.account_id.code,
                                'descript': invoice.account_id.name,
                                'credit': amount
                            })
                            credit += amount

                            lines.append({
                                'date': '',
                                'account': bl.bankline_id.bank_id.account_id.code,
                                'descript': bl.bankline_id.bank_id.account_id.name,
                                'debit': bl.trans_amount
                            })
                            debit += bl.trans_amount

                            if bl.type == 'diff':
                                lines.append({
                                    'date': '',
                                    'account': bl.bankline_id.bank_id.account_accepted_id.code,
                                    'descript': bl.bankline_id.bank_id.account_accepted_id.name,
                                    'debit': bl.open_amount
                                })
                                debit += bl.open_amount
                            elif bl.type == 'disc':
                                lines.append({
                                    'date': '',
                                    'account': bl.bankline_id.bank_id.account_po_difference_id.code,
                                    'descript': bl.bankline_id.bank_id.account_po_difference_id.name,
                                    'debit': bl.open_amount
                                })
                                debit += bl.open_amount
                    if lines:
                        lines[0]['date'] = bankline.date_trans
                        moves.append({
                            'title': 'Bank/Cash %s' % bankline.bank_id.name,
                            'date': bankline.date_trans,
                            'lines': lines,
                            'credit': debit,
                            'debit': credit
                        })

                memlines_so = self.env['s2u.account.memorial.line.invoice.po'].search([('invoice_id', '=', invoice.id)])
                memline_ids = [b.mline_id.id for b in memlines_so]
                memline_ids = list(set(memline_ids))
                for memline in self.env['s2u.account.memorial.line'].browse(memline_ids):
                    memlines_po = self.env['s2u.account.memorial.line.invoice.po'].search(
                        [('invoice_id', '=', invoice.id),
                         ('mline_id', '=', memline.id)])
                    lines = []
                    debit = 0.0
                    credit = 0.0
                    for bl in memlines_po:
                        amount = bl.trans_amount
                        if bl.type in ['diff', 'disc']:
                            amount += bl.open_amount
                        if amount < 0.0:
                            lines.append({
                                'date': '',
                                'account': invoice.account_id.code,
                                'descript': invoice.account_id.name,
                                'debit': abs(amount)
                            })
                            debit += abs(amount)

                            lines.append({
                                'date': '',
                                'account': bl.mline_id.account_id.code,
                                'descript': bl.mline_id.account_id.name,
                                'credit': abs(bl.trans_amount)
                            })
                            credit += abs(bl.trans_amount)

                            if bl.type == 'diff':
                                lines.append({
                                    'date': '',
                                    'account': bl.mline_id.memorial_id.account_accepted_id.code,
                                    'descript': bl.mline_id.memorial_id.account_accepted_id.name,
                                    'credit': abs(bl.open_amount)
                                })
                                credit += abs(bl.open_amount)
                            elif bl.type == 'disc':
                                lines.append({
                                    'date': '',
                                    'account': bl.mline_id.memorial_id.account_so_difference_id.code,
                                    'descript': bl.mline_id.memorial_id.account_so_difference_id.name,
                                    'credit': abs(bl.open_amount)
                                })
                                credit += abs(bl.open_amount)
                        elif amount > 0.0:
                            lines.append({
                                'date': '',
                                'account': invoice.account_id.code,
                                'descript': invoice.account_id.name,
                                'credit': amount
                            })
                            credit += amount

                            lines.append({
                                'date': '',
                                'account': bl.mline_id.account_id.code,
                                'descript': bl.mline_id.account_id.name,
                                'debit': bl.trans_amount
                            })
                            debit += bl.trans_amount

                            if bl.type == 'diff':
                                lines.append({
                                    'date': '',
                                    'account': bl.mline_id.memorial_id.account_accepted_id.code,
                                    'descript': bl.mline_id.memorial_id.account_accepted_id.name,
                                    'debit': bl.open_amount
                                })
                                debit += bl.open_amount
                            elif bl.type == 'disc':
                                lines.append({
                                    'date': '',
                                    'account': bl.mline_id.memorial_id.account_so_difference_id.code,
                                    'descript': bl.mline_id.memorial_id.account_so_difference_id.name,
                                    'debit': bl.open_amount
                                })
                                debit += bl.open_amount
                    if lines:
                        lines[0]['date'] = memline.memorial_id.date_trans
                        moves.append({
                            'title': 'Memorial %s' % memline.memorial_id.name,
                            'date': memline.memorial_id.date_trans,
                            'lines': lines,
                            'debit': credit,
                            'credit': debit
                        })

            pages.append({
                'title': _('Journal for Purchase Order %s' % order.name),
                'moves': moves
            })

        return {
            'pages': pages
        }
