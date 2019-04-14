import datetime
from odoo import api, fields, models, _

class AbstractJournal(models.AbstractModel):
    _name = 's2uaccount.abstract_report_journal'

    @api.model
    def convert_rate(self, amount, currency, date_trans=False):

        if not currency:
            return amount

        company_currency = self.env.user.company_id.currency_id
        if company_currency == currency:
            return amount

        if date_trans:
            amount = amount * currency.with_context({'date': date_trans}).rate
        else:
            amount = amount * currency.rate

        return amount

    @api.model
    def currency_amount(self, amount, currency):

        if not currency:
            return False

        company_currency = self.env.user.company_id.currency_id
        if company_currency == currency:
            return False

        return amount

    @api.model
    def moves_for_invoices(self, invoice_ids):

        moves = []
        for invoice in self.env['s2u.account.invoice'].browse(invoice_ids):
            if invoice.state != 'invoiced':
                continue
            lines = []
            debit = 0.0
            credit = 0.0
            if invoice.amount_gross > 0.0:
                lines.append({
                    'date': invoice.date_financial,
                    'account': invoice.account_id.code,
                    'descript': invoice.account_id.name,
                    'debit': self.convert_rate(invoice.amount_gross, invoice.currency_id, invoice.date_financial),
                    'currency_amount': self.currency_amount(invoice.amount_gross, invoice.currency_id),
                    'currency': invoice.currency_id
                })
                debit += self.convert_rate(invoice.amount_gross, invoice.currency_id, invoice.date_financial)
            elif invoice.amount_gross < 0.0:
                lines.append({
                    'date': invoice.date_financial,
                    'account': invoice.account_id.code,
                    'descript': invoice.account_id.name,
                    'credit': self.convert_rate(abs(invoice.amount_gross), invoice.currency_id, invoice.date_financial),
                    'currency_amount': self.currency_amount(invoice.amount_gross, invoice.currency_id),
                    'currency': invoice.currency_id
                })
                credit += self.convert_rate(abs(invoice.amount_gross), invoice.currency_id, invoice.date_financial)
            for invline in invoice.line_ids:
                if invline.net_amount < 0.0:
                    lines.append({
                        'date': '',
                        'account': invline.account_id.code,
                        'descript': invline.account_id.name,
                        'debit': self.convert_rate(abs(invline.net_amount), invoice.currency_id, invoice.date_financial),
                        'currency_amount': self.currency_amount(invline.net_amount, invoice.currency_id),
                        'currency': invoice.currency_id
                    })
                    debit += self.convert_rate(abs(invline.net_amount), invoice.currency_id, invoice.date_financial)
                elif invline.net_amount > 0.0:
                    lines.append({
                        'date': '',
                        'account': invline.account_id.code,
                        'descript': invline.account_id.name,
                        'credit': self.convert_rate(invline.net_amount, invoice.currency_id, invoice.date_financial),
                        'currency_amount': self.currency_amount(invline.net_amount, invoice.currency_id),
                        'currency': invoice.currency_id
                    })
                    credit += self.convert_rate(invline.net_amount, invoice.currency_id, invoice.date_financial)
            for invline in invoice.line_ids:
                for rule in invline.vat_id.rule_ids:
                    if rule.rule_type == 'plus':
                        amount = invline.vat_amount
                    else:
                        amount = invline.vat_amount * -1.0
                    if amount < 0.0:
                        lines.append({
                            'date': '',
                            'account': rule.account_id.code,
                            'descript': rule.account_id.name,
                            'debit': self.convert_rate(abs(amount), invoice.currency_id, invoice.date_financial),
                            'currency_amount': self.currency_amount(amount, invoice.currency_id),
                            'currency': invoice.currency_id
                        })
                        debit += self.convert_rate(abs(amount), invoice.currency_id, invoice.date_financial)
                    elif amount > 0.0:
                        lines.append({
                            'date': '',
                            'account': rule.account_id.code,
                            'descript': rule.account_id.name,
                            'credit': self.convert_rate(amount, invoice.currency_id, invoice.date_financial),
                            'currency_amount': self.currency_amount(amount, invoice.currency_id),
                            'currency': invoice.currency_id
                        })
                        credit += self.convert_rate(amount, invoice.currency_id, invoice.date_financial)

            if lines:
                moves.append({
                    'title': 'Invoice %s %s' % (invoice.name, invoice.reference),
                    'date': invoice.date_financial,
                    'lines': lines,
                    'debit': self.convert_rate(debit, invoice.currency_id, invoice.date_financial),
                    'credit': self.convert_rate(credit, invoice.currency_id, invoice.date_financial),
                    'currency_amount': self.currency_amount(debit - credit, invoice.currency_id),
                    'currency': invoice.currency_id
                })

        return moves

    @api.model
    def moves_for_invoices_on_bank(self, invoice_ids):

        moves = []
        for invoice in self.env['s2u.account.invoice'].browse(invoice_ids):
            banklines_so = self.env['s2u.account.bank.line.invoice.so'].search([('invoice_id', '=', invoice.id)])
            bankline_ids = [b.bankline_id.id for b in banklines_so]
            bankline_ids = list(set(bankline_ids))
            for bankline in self.env['s2u.account.bank.line'].browse(bankline_ids):
                banklines_so = self.env['s2u.account.bank.line.invoice.so'].search([('invoice_id', '=', invoice.id),
                                                                                    ('bankline_id', '=', bankline.id)])
                lines = []
                debit = 0.0
                credit = 0.0
                for bl in banklines_so:
                    amount = bl.trans_amount
                    if bl.type in ['diff', 'disc']:
                        amount += bl.open_amount
                    if amount > 0.0:
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
                                'account': bl.bankline_id.bank_id.account_so_difference_id.code,
                                'descript': bl.bankline_id.bank_id.account_so_difference_id.name,
                                'debit': bl.open_amount
                            })
                            debit += bl.open_amount
                    elif amount < 0.0:
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
                                'account': bl.bankline_id.bank_id.account_so_difference_id.code,
                                'descript': bl.bankline_id.bank_id.account_so_difference_id.name,
                                'credit': abs(bl.open_amount)
                            })
                            credit += abs(bl.open_amount)
                if lines:
                    lines[0]['date'] = bankline.date_trans
                    moves.append({
                        'title': 'Bank/Cash %s' % bankline.bank_id.name,
                        'date': bankline.date_trans,
                        'lines': lines,
                        'debit': debit,
                        'credit': credit
                    })

        return moves

    @api.model
    def moves_for_invoices_on_memorial(self, invoice_ids):

        moves = []
        for invoice in self.env['s2u.account.invoice'].browse(invoice_ids):
            memlines_so = self.env['s2u.account.memorial.line.invoice.so'].search([('invoice_id', '=', invoice.id)])
            memline_ids = [b.mline_id.id for b in memlines_so]
            memline_ids = list(set(memline_ids))
            for memline in self.env['s2u.account.memorial.line'].browse(memline_ids):
                memlines_so = self.env['s2u.account.memorial.line.invoice.so'].search([('invoice_id', '=', invoice.id),
                                                                                       ('mline_id', '=', memline.id)])
                lines = []
                debit = 0.0
                credit = 0.0
                for bl in memlines_so:
                    amount = bl.trans_amount
                    if bl.type in ['diff', 'disc']:
                        amount += bl.open_amount
                    if amount > 0.0:
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
                    elif amount < 0.0:
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
                if lines:
                    lines[0]['date'] = memline.memorial_id.date_trans
                    moves.append({
                        'title': 'Memorial %s' % memline.memorial_id.name,
                        'date': memline.memorial_id.date_trans,
                        'lines': lines,
                        'debit': debit,
                        'credit': credit
                    })

        return moves

    @api.model
    def moves_for_stock_on_outgoing(self, outgoing_ids):

        moves = []
        for outgoing in self.env['s2u.warehouse.outgoing'].browse(outgoing_ids):
            transactions = self.env['s2u.account.move'].search([('res_model', '=', 's2u.warehouse.unit.product.transaction'),
                                                                ('res_id', 'in', outgoing.trans_ids.ids)])
            lines = []
            debit = 0.0
            credit = 0.0
            for trans in transactions:
                lines.append({
                    'date': trans.date_trans,
                    'account': trans.account_id.code,
                    'descript': trans.name,
                    'debit': trans.debit,
                    'credit': trans.credit,
                })
                debit += trans.debit
                credit += trans.credit

            if lines:
                moves.append({
                    'title': 'Outgoing %s %s' % (outgoing.name, outgoing.reference),
                    'date': lines[0]['date'],
                    'lines': lines,
                    'debit': debit,
                    'credit': credit
                })

        return moves

    @api.model
    def moves_for_stock_on_rma(self, rma_ids):

        moves = []

        for rma in self.env['s2u.warehouse.rma'].browse(rma_ids):
            transactions = self.env['s2u.account.move'].search([('res_model', '=', 's2u.warehouse.unit.product.transaction'),
                                                                ('res_id', 'in', rma.trans_ids.ids)])
            lines = []
            debit = 0.0
            credit = 0.0
            for trans in transactions:
                lines.append({
                    'date': trans.date_trans,
                    'account': trans.account_id.code,
                    'descript': trans.name,
                    'debit': trans.debit,
                    'credit': trans.credit,
                })
                debit += trans.debit
                credit += trans.credit

            if lines:
                moves.append({
                    'title': 'RMA %s %s' % (rma.name, rma.reference),
                    'date': lines[0]['date'],
                    'lines': lines,
                    'debit': debit,
                    'credit': credit
                })
        return moves
