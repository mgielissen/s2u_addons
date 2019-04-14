import datetime
from odoo import api, fields, models


class PrintReportVat(models.AbstractModel):
    _name = 'report.s2uaccount.report_vat'

    def _get_accounts(self, company_id, date_till, make_final):
        saved_obj = self.env['report.s2uaccount.vat.saved']
        cy = datetime.date.today().year

        date_from = datetime.date(cy, 1, 1).strftime('%Y-%m-%d')
        accounts = {}
        vat_categories = dict((fn, {'amount': 0.0,
                                    'vat': 0.0}) for fn in ['1a', '1b', '1c', '1d', '1e',
                                                            '2a', '3a', '3b', '3c', '4a', '4b',
                                                            '5a', '5b', '5c'])
        totals = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
        totals_vat = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
        totals_vat_receive = 0.0
        icp_values = {}
        vat_export_import_total = dict((fn, 0.0) for fn in ['15', '16', '17', '18'])
        vat_export_import_till = dict((fn, 0.0) for fn in ['15', '16', '17', '18'])
        vat_export_import_this = dict((fn, 0.0) for fn in ['15', '16', '17', '18'])
        for obj in ['s2u.account.invoice', 's2u.account.invoice.po']:
            invoices = self.env[obj].search([('date_financial', '>=', date_from),
                                             ('date_financial', '<=', date_till)])
            for invoice in invoices:
                for line in invoice.line_ids:
                    if not line.gross_amount and not line.net_amount and not line.vat_amount:
                        continue
                    if line.vat_id:
                        if line.vat_id.vat_report in ['01', '02', '03', '04', '05', '06', '07']:
                            if line.account_id.code not in accounts:
                                res = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
                                res['code'] = line.account_id.code
                                res['name'] = line.account_id.name
                                res['type'] = line.account_id.type
                                accounts[line.account_id.code] = res
                            accounts[line.account_id.code][line.vat_id.vat_report] += line.net_amount
                            accounts[line.account_id.code]['total'] += line.net_amount
                            totals[line.vat_id.vat_report] += line.net_amount
                            totals['total'] += line.net_amount
                            totals_vat[line.vat_id.vat_report] += line.vat_amount
                            totals_vat['total'] += line.vat_amount
                        elif line.vat_id.vat_report == '10':
                            totals_vat_receive += line.vat_amount

                        for rule in line.vat_id.rule_ids:
                            if rule.category_id.code not in vat_categories:
                                vat_categories[rule.category_id.code] = {'amount': 0.0,
                                                                         'vat': 0.0}
                            vat_categories[rule.category_id.code]['amount'] += line.net_amount
                            vat_categories[rule.category_id.code]['vat'] += line.vat_amount

                        if line.vat_id.vat_report in ['15', '16', '17', '18']:
                            vat_export_import_total[line.vat_id.vat_report] += line.net_amount

                        if line.vat_id.tinno_obligatory:
                            if invoice.partner_id.tinno:
                                if invoice.partner_id.tinno not in icp_values:
                                    try:
                                        country = invoice.partner_id.tinno[0:2]
                                        tincode = invoice.partner_id.tinno[2:]
                                    except:
                                        country = 'xx'
                                        tincode = 'xxxxxxxxx'

                                    icp_values[invoice.partner_id.tinno] = {'country': country,
                                                                            'code': tincode,
                                                                            'tinno': invoice.partner_id.tinno,
                                                                            'total_deliveries': 0.0,
                                                                            'total_services': 0.0}

                                if line.vat_id.category == 'ser':
                                    icp_values[invoice.partner_id.tinno]['total_services'] += line.net_amount
                                else:
                                    icp_values[invoice.partner_id.tinno]['total_deliveries'] += line.net_amount
                    else:
                        # BTW geen
                        if line.account_id.type == 'income':
                            if line.account_id.code not in accounts:
                                res = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
                                res['code'] = line.account_id.code
                                res['name'] = line.account_id.name
                                res['type'] = line.account_id.type
                                accounts[line.account_id.code] = res
                            accounts[line.account_id.code]['04'] += line.net_amount
                            accounts[line.account_id.code]['total'] += line.net_amount
                            totals['04'] += line.net_amount
                            totals['total'] += line.net_amount

        vat_categories['5a']['vat'] = 0.0
        for cat in ['1a', '1b', '1c', '1d', '1e', '2a', '3a', '3b', '3c', '4a', '4b']:
            vat_categories['5a']['vat'] += vat_categories[cat]['vat']
        vat_categories['5c']['vat'] = vat_categories['5a']['vat'] - vat_categories['5b']['vat']

        res = []
        for code in sorted(accounts):
            res.append(accounts[code])

        already_saved = saved_obj.search([('company_id', '=', company_id),
                                          ('amount_name', 'in', ['icp_services', 'icp_deliveries']),
                                          ('vat_till', '>=', date_from),
                                          ('vat_till', '<', date_till)])
        for vat_saved in already_saved:
            if vat_saved.vat_report in icp_values:
                if vat_saved.amount_name == 'icp_services':
                    icp_values[vat_saved.vat_report]['total_services'] -= vat_saved.amount
                else:
                    icp_values[vat_saved.vat_report]['total_deliveries'] -= vat_saved.amount

        res_icp = []
        for tinno in sorted(icp_values):
            if icp_values[tinno]['total_services'] or icp_values[tinno]['total_deliveries']:
                res_icp.append(icp_values[tinno])

        totals_till_period = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
        already_saved = saved_obj.search([('company_id', '=', company_id),
                                          ('amount_name', '=', 'accounts'),
                                          ('vat_till', '>=', date_from),
                                          ('vat_till', '<', date_till)])
        for vat_saved in already_saved:
            if vat_saved.vat_report in totals_till_period:
                totals_till_period[vat_saved.vat_report] += vat_saved.amount

        totals_vat_till_period = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
        already_saved = saved_obj.search([('company_id', '=', company_id),
                                          ('amount_name', '=', 'vat_to_pay'),
                                          ('vat_till', '>=', date_from),
                                          ('vat_till', '<', date_till)])
        for vat_saved in already_saved:
            if vat_saved.vat_report in totals_vat_till_period:
                totals_vat_till_period[vat_saved.vat_report] += vat_saved.amount

        totals_vat_receive_till_period = 0.0
        already_saved = saved_obj.search([('company_id', '=', company_id),
                                          ('amount_name', '=', 'vat_to_receive'),
                                          ('vat_till', '>=', date_from),
                                          ('vat_till', '<', date_till)])
        for vat_saved in already_saved:
            totals_vat_receive_till_period += vat_saved.amount

        totals_this_period = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
        totals_vat_this_period = dict((fn, 0.0) for fn in ['01', '02', '03', '04', '05', '06', '07', 'total'])
        for k in list(totals.keys()):
            totals_this_period[k] = totals[k] - totals_till_period[k]
            totals_vat_this_period[k] = totals_vat[k] - totals_vat_till_period[k]

        totals_vat_receive_this_period = totals_vat_receive - totals_vat_receive_till_period

        already_saved = saved_obj.search([('company_id', '=', company_id),
                                          ('amount_name', '=', 'export_import'),
                                          ('vat_till', '>=', date_from),
                                          ('vat_till', '<', date_till)])
        for vat_saved in already_saved:
            if vat_saved.vat_report in vat_export_import_till:
                vat_export_import_till[vat_saved.vat_report] += vat_saved.amount

        for k in list(vat_export_import_total.keys()):
            vat_export_import_this[k] = vat_export_import_total[k] - vat_export_import_till[k]

        for amount_name in ['amount', 'vat']:
            already_saved = saved_obj.search([('company_id', '=', company_id),
                                              ('amount_name', '=', 'categories_%s' % amount_name),
                                              ('vat_till', '>=', date_from),
                                              ('vat_till', '<', date_till)])
            for vat_saved in already_saved:
                if vat_saved.vat_report not in vat_categories:
                    vat_categories[vat_saved.vat_report] = {'amount': 0.0,
                                                            'vat': 0.0}
                vat_categories[vat_saved.vat_report][amount_name] -= vat_saved.amount

        return res, totals, totals_till_period, totals_this_period, \
               totals_vat, totals_vat_till_period, totals_vat_this_period, \
               totals_vat_receive, totals_vat_receive_till_period, totals_vat_receive_this_period, vat_categories, \
               res_icp, vat_export_import_total, vat_export_import_till, vat_export_import_this

    @api.model
    def get_report_values(self, docids, data=None):
        saved_obj = self.env['report.s2uaccount.vat.saved']

        accounts, totals, till_period, this_period, \
        totals_vat, totals_vat_till_period, totals_vat_this_period, \
        totals_vat_receive, totals_vat_receive_till_period, totals_vat_receive_this_period, \
        vat_categories_amounts, icp_values, vat_export_import_total, vat_export_import_till, \
        vat_export_import_this = self._get_accounts(data['form']['company_id'][0], data['form']['vat_till'], data['final'])

        category_obj = self.env['s2u.account.vat.category']
        categories = category_obj.search([])

        if data['final']:
            already_saved = saved_obj.search([('company_id', '=', data['form']['company_id'][0]),
                                              ('vat_till', '=', data['form']['vat_till'])])
            already_saved.unlink()
            for k, v in iter(this_period.items()):
                saved_obj.create({'company_id': data['form']['company_id'][0],
                                  'vat_till': data['form']['vat_till'],
                                  'amount_name': 'accounts',
                                  'vat_report': k,
                                  'amount': v})

            for k, v in iter(totals_vat_this_period.items()):
                saved_obj.create({'company_id': data['form']['company_id'][0],
                                  'vat_till': data['form']['vat_till'],
                                  'amount_name': 'vat_to_pay',
                                  'vat_report': k,
                                  'amount': v})

            saved_obj.create({'company_id': data['form']['company_id'][0],
                              'vat_till': data['form']['vat_till'],
                              'amount_name': 'vat_to_receive',
                              'vat_report': '',
                              'amount': totals_vat_receive_this_period})

            for k, v in iter(vat_categories_amounts.items()):
                saved_obj.create({'company_id': data['form']['company_id'][0],
                                  'vat_till': data['form']['vat_till'],
                                  'amount_name': 'categories_amount',
                                  'vat_report': k,
                                  'amount': v['amount']})
                saved_obj.create({'company_id': data['form']['company_id'][0],
                                  'vat_till': data['form']['vat_till'],
                                  'amount_name': 'categories_vat',
                                  'vat_report': k,
                                  'amount': v['vat']})

            for k, v in iter(vat_export_import_this.items()):
                saved_obj.create({'company_id': data['form']['company_id'][0],
                                  'vat_till': data['form']['vat_till'],
                                  'amount_name': 'export_import',
                                  'vat_report': k,
                                  'amount': v})

            for icp in icp_values:
                if icp['total_deliveries']:
                    saved_obj.create({'company_id': data['form']['company_id'][0],
                                      'vat_till': data['form']['vat_till'],
                                      'amount_name': 'icp_deliveries',
                                      'vat_report': icp['tinno'],
                                      'amount': icp['total_deliveries']})
                if icp['total_services']:
                    saved_obj.create({'company_id': data['form']['company_id'][0],
                                      'vat_till': data['form']['vat_till'],
                                      'amount_name': 'icp_services',
                                      'vat_report': icp['tinno'],
                                      'amount': icp['total_services']})

        try:
            date_obj = datetime.datetime.strptime(data['form']['vat_till'], '%Y-%m-%d')
            lang = self.env['res.lang'].search([('code', '=', self.env.user.lang)])
            date_vat_till = date_obj.strftime(lang.date_format)
        except:
            date_vat_till = data['form']['vat_till']

        docargs = {
            'accounts': accounts,
            'account_totals': totals,
            'account_till_totals': till_period,
            'account_this_totals': this_period,
            'vat_calulated': {'01': totals['01'] * 0.21,
                              '02': totals['02'] * 0.06},
            'vat_is': totals_vat,
            'vat_till': totals_vat_till_period,
            'vat_to_pay': totals_vat_this_period,
            'vat_to_receive': totals_vat_receive,
            'vat_to_receive_till': totals_vat_receive_till_period,
            'vat_to_receive_this': totals_vat_receive_this_period,
            'vat_valid': totals_vat_this_period['total'] - totals_vat_receive_this_period,
            'vat_export_import_total': vat_export_import_total,
            'vat_export_import_till': vat_export_import_till,
            'vat_export_import_this': vat_export_import_this,
            'vat_categories': categories,
            'vat_categories_amounts': vat_categories_amounts,
            'icp_values': icp_values,
            'date_vat_till': date_vat_till
        }

        return docargs


