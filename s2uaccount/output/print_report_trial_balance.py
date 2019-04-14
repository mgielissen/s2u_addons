import datetime
from odoo import api, fields, models

class PrintReportTrialBalance(models.AbstractModel):
    _name = 'report.s2uaccount.report_trial_balance'

    @api.model
    def get_report_values(self, docids, data=None):

        category_obj = self.env['s2u.account.category']
        account_obj = self.env['s2u.account.account']

        company_id = data['form']['company_id'][0]

        assets_liabilities = []
        end_totals = {
            'start_saldo': 0.0,
            'end_saldo': 0.0,
            'left_debit': 0.0,
            'left_credit': 0.0,
            'right_debit': 0.0,
            'right_credit': 0.0
        }

        for cat in category_obj.search([('company_id', '=', company_id),
                                        ('type', 'in', ['asset', 'liability'])]):
            item_cat = {'name': cat.name,
                        'accounts': [],
                        'start_saldo': 0.0,
                        'end_saldo': 0.0,
                        'left_debit': 0.0,
                        'left_credit': 0.0,
                        'right_debit': 0.0,
                        'right_credit': 0.0
                        }
            for account in account_obj.search([('category_id', '=', cat.id)]):
                item_acc = {'code': account.code,
                            'name': account.name,
                            'start_saldo': account.saldo_per_date(False,
                                                                  openingbalance_only=True,
                                                                  fiscalyear=int(data['form']['fiscal_year'])),
                            'end_saldo': 0.0,
                            'left_debit': account.saldo_per_date(data['form']['left_till'],
                                                                 from_date=data['form']['left_from'],
                                                                 result='debit',
                                                                 skip_openingalance=True),
                            'left_credit': account.saldo_per_date(data['form']['left_till'],
                                                                  from_date=data['form']['left_from'],
                                                                  result='credit',
                                                                  skip_openingalance=True),
                            'right_debit': account.saldo_per_date(data['form']['right_till'],
                                                                  from_date=data['form']['right_from'],
                                                                  result='debit',
                                                                  skip_openingalance=True),
                            'right_credit': account.saldo_per_date(data['form']['right_till'],
                                                                   from_date=data['form']['right_from'],
                                                                   result='credit',
                                                                   skip_openingalance=True)}
                if item_acc['start_saldo'] or item_acc['left_debit'] or item_acc['left_credit'] \
                        or item_acc['right_debit'] or item_acc['right_credit']:
                    item_cat['accounts'].append(item_acc)
            for a in item_cat['accounts']:
                a['end_saldo'] = a['start_saldo'] + a['right_debit'] - a['right_credit']
                item_cat['start_saldo'] += a['start_saldo']
                item_cat['end_saldo'] += a['end_saldo']
                item_cat['left_debit'] += a['left_debit']
                item_cat['left_credit'] += a['left_credit']
                item_cat['right_debit'] += a['right_debit']
                item_cat['right_credit'] += a['right_credit']
                end_totals['start_saldo'] += a['start_saldo']
                end_totals['end_saldo'] += a['end_saldo']
                end_totals['left_debit'] += a['left_debit']
                end_totals['left_credit'] += a['left_credit']
                end_totals['right_debit'] += a['right_debit']
                end_totals['right_credit'] += a['right_credit']
            if item_cat['accounts']:
                assets_liabilities.append(item_cat)

        expenses_income = []
        profit_loss = {
            'left_debit': 0.0,
            'left_credit': 0.0,
            'right_debit': 0.0,
            'right_credit': 0.0,
            'profit_loss': 0.0
        }
        for cat in category_obj.search([('company_id', '=', company_id),
                                        ('type', 'in', ['income', 'expense'])]):
            item_cat = {'name': cat.name,
                        'accounts': [],
                        'start_saldo': 0.0,
                        'end_saldo': 0.0,
                        'left_debit': 0.0,
                        'left_credit': 0.0,
                        'right_debit': 0.0,
                        'right_credit': 0.0
                        }
            for account in account_obj.search([('category_id', '=', cat.id)]):
                item_acc = {'code': account.code,
                            'name': account.name,
                            'start_saldo': account.saldo_per_date(False,
                                                                  openingbalance_only=True,
                                                                  fiscalyear=int(data['form']['fiscal_year'])),
                            'end_saldo': 0.0,
                            'left_debit': account.saldo_per_date(data['form']['left_till'],
                                                                 from_date=data['form']['left_from'],
                                                                 result='debit',
                                                                 skip_openingalance=True),
                            'left_credit': account.saldo_per_date(data['form']['left_till'],
                                                                  from_date=data['form']['left_from'],
                                                                  result='credit',
                                                                  skip_openingalance=True),
                            'right_debit': account.saldo_per_date(data['form']['right_till'],
                                                                  from_date=data['form']['right_from'],
                                                                  result='debit',
                                                                  skip_openingalance=True),
                            'right_credit': account.saldo_per_date(data['form']['right_till'],
                                                                   from_date=data['form']['right_from'],
                                                                   result='credit',
                                                                   skip_openingalance=True)}
                if item_acc['start_saldo'] or item_acc['left_debit'] or item_acc['left_credit'] \
                        or item_acc['right_debit'] or item_acc['right_credit']:
                    item_cat['accounts'].append(item_acc)
            for a in item_cat['accounts']:
                a['end_saldo'] = a['start_saldo'] + a['right_debit'] - a['right_credit']
                item_cat['start_saldo'] += a['start_saldo']
                item_cat['end_saldo'] += a['end_saldo']
                item_cat['left_debit'] += a['left_debit']
                item_cat['left_credit'] += a['left_credit']
                item_cat['right_debit'] += a['right_debit']
                item_cat['right_credit'] += a['right_credit']
                end_totals['start_saldo'] += a['start_saldo']
                end_totals['end_saldo'] += a['end_saldo']
                end_totals['left_debit'] += a['left_debit']
                end_totals['left_credit'] += a['left_credit']
                end_totals['right_debit'] += a['right_debit']
                end_totals['right_credit'] += a['right_credit']
                profit_loss['left_debit'] += a['left_debit']
                profit_loss['left_credit'] += a['left_credit']
                profit_loss['right_debit'] += a['right_debit']
                profit_loss['right_credit'] += a['right_credit']
                profit_loss['profit_loss'] += a['right_debit'] - a['right_credit']
            if item_cat['accounts']:
                expenses_income.append(item_cat)

        if data['form']['compare_left'] == 'year':
            label_left = '1-1 / 31-12'
        else:
            dt = datetime.datetime.strptime(data['form']['left_from'], '%Y-%m-%d')
            from_date = '%d-%d' % (dt.day, dt.month)
            dt = datetime.datetime.strptime(data['form']['left_till'], '%Y-%m-%d')
            till_date = '%d-%d' % (dt.day, dt.month)
            label_left = '%s / %s' % (from_date, till_date)
        if data['form']['compare_right'] == 'year':
            label_right = '1-1 / 31-12'
        else:
            dt = datetime.datetime.strptime(data['form']['right_from'], '%Y-%m-%d')
            from_date = '%d-%d' % (dt.day, dt.month)
            dt = datetime.datetime.strptime(data['form']['right_till'], '%Y-%m-%d')
            till_date = '%d-%d' % (dt.day, dt.month)
            label_right = '%s / %s' % (from_date, till_date)

        return {
            'assets_liabilities': assets_liabilities,
            'expenses_income': expenses_income,
            'profit_loss': profit_loss,
            'end_totals': end_totals,
            'label_left': label_left,
            'label_right': label_right,
            'fiscal_year': data['form']['fiscal_year']
        }


