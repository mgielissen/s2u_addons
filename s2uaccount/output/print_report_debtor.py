import datetime
import time
from odoo import api, fields, models

class PrintReportDebtor(models.AbstractModel):
    _name = 'report.s2uaccount.report_debtor'

    def get_days(self, inv_date, till_date):

        if till_date:
            till_date = datetime.datetime.strptime(till_date, '%Y-%m-%d')
        else:
            till_date = datetime.datetime.strptime(time.strftime('%Y-%m-%d'), '%Y-%m-%d')
        if datetime.datetime.strptime(inv_date, '%Y-%m-%d') < till_date:
            days = till_date - datetime.datetime.strptime(inv_date, '%Y-%m-%d')
            days = days.days
        else:
            days = 0

        return days

    def format_date(self, toformat):

        if not toformat:
            return False

        formatted_date = datetime.datetime.strptime(toformat, '%Y-%m-%d')
        formatted_date = formatted_date.strftime('%d-%m-%Y')

        return formatted_date

    @api.model
    def get_report_values(self, docids, data=None):

        def days_to_index(days):
            if days <= 30:
                return 0
            if days <= 60:
                return 1
            if days <= 90:
                return 2
            if days <= 120:
                return 3
            return 4

        company_id = data['form']['company_id'][0]
        date_till = data['form']['date_till']

        sql = """SELECT inv.id,
                        inv.name,
                        entity.id,
                        entity.name,
                        inv.date_invoice, 
                        inv.reference,
                        inv.amount_gross AS amount,
                        COALESCE(SUM(bank.credit - bank.debit), 0) + COALESCE(SUM(memorial.credit - memorial.debit), 0) - COALESCE(creditnota.amount_gross, 0) AS paid,
                        COALESCE(SUM(bank2.credit - bank2.debit), 0) + COALESCE(SUM(memorial2.credit - memorial2.debit), 0) AS accepted,
                        inv.amount_gross - COALESCE(SUM(bank.credit - bank.debit), 0) - COALESCE(SUM(memorial.credit - memorial.debit), 0) + COALESCE(creditnota.amount_gross, 0) AS saldo
                 FROM s2u_account_invoice inv
                     LEFT JOIN s2u_crm_entity entity ON inv.partner_id = entity.id
                     LEFT OUTER JOIN s2u_account_bank_account bank ON (inv.id = bank.so_invoice_id AND bank.date_trans <= '%s' AND bank.type = 'nor')
                     LEFT OUTER JOIN s2u_account_memorial_account memorial ON (inv.id = memorial.so_invoice_id AND memorial.date_trans <= '%s' AND memorial.type = 'nor')
                     LEFT OUTER JOIN s2u_account_bank_account bank2 ON (inv.id = bank2.so_invoice_id AND bank2.date_trans <= '%s' AND bank2.type <> 'nor')
                     LEFT OUTER JOIN s2u_account_memorial_account memorial2 ON (inv.id = memorial2.so_invoice_id AND memorial2.date_trans <= '%s' AND memorial2.type <> 'nor')
                     LEFT OUTER JOIN s2u_account_invoice creditnota ON (inv.creditnota_id = creditnota.id AND creditnota.date_invoice <= '%s')
                         WHERE inv.date_invoice <= '%s' AND inv.company_id = %d AND inv.state = 'invoiced'                              
                                    GROUP BY inv.id, entity.id, creditnota.amount_gross 
                                    HAVING inv.amount_gross - COALESCE(SUM(bank.credit - bank.debit), 0) - COALESCE(SUM(memorial.credit - memorial.debit), 0) + COALESCE(creditnota.amount_gross, 0) <> 0
                                    ORDER BY entity.name, inv.date_invoice""" % (date_till, date_till, date_till, date_till, date_till, date_till, company_id)
        self.env.cr.execute(sql)
        res = self.env.cr.fetchall()
        debtors = []
        invoices = False
        debtor_id = False
        debtor_name = False

        # 0 - 30 dagen, 31 - 60 dagen, 61 - 90 dagen, 91 - 120 dagen, > 120 dagen
        endtotal_open = [0.0, 0.0, 0.0, 0.0, 0.0]
        total_open = 0.0

        for inv in res:
            # filter out noice: 0,000000001 etc.
            if round(inv[9], 2) == 0.0:
                continue
            if debtor_id != inv[2]:
                if debtor_id and invoices:
                    debtors.append({
                        'debtor': debtor_name,
                        'amount': sum([i['amount'] for i in invoices]),
                        'paid': sum([i['paid'] for i in invoices]),
                        'accepted': sum([i['accepted'] for i in invoices]),
                        'saldo': sum([i['saldo'] for i in invoices]),
                        'invoices': invoices
                    })
                debtor_id = inv[2]
                debtor_name = inv[3]
                invoices = []
            data = {
                'number': inv[1],
                'date': self.format_date(inv[4]),
                'descript': inv[5],
                'amount': inv[6],
                'paid': inv[7],
                'accepted': inv[8],
                'saldo': inv[9],
                'days': self.get_days(inv[4], date_till)
            }
            invoices.append(data)
            endtotal_open[days_to_index(data['days'])] += data['saldo']
            total_open += data['saldo']

        if debtor_id and invoices:
            debtors.append({
                'debtor': debtor_name,
                'amount': sum([i['amount'] for i in invoices]),
                'paid': sum([i['paid'] for i in invoices]),
                'accepted': sum([i['accepted'] for i in invoices]),
                'saldo': sum([i['saldo'] for i in invoices]),
                'invoices': invoices
            })

        return {
            'debtors': debtors,
            'date_till': self.format_date(date_till),
            'endtotal': endtotal_open,
            'total': total_open
        }


