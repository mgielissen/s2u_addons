{
    'name': 'Solutions2use Accounting',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use Accounting',
    'category':  'Accounting',
    'images': ['static/description/icon.png'],
    'description':
        """
        """,
    'depends': ['base_setup', 's2ubase', 's2ucrm', 's2ubaseproduct', 's2udocument'],
    'data': [
        # security
        'security/rules.xml',
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        # data
        'data/account_data.xml',
        # views
        'views/menus.xml',
        'views/vat_view.xml',
        'views/account_view.xml',
        'views/invoice_view.xml',
        'views/memorial_view.xml',
        'views/bank_view.xml',
        'views/account_portal_templates.xml',
        'views/entity_view.xml',
        # pdf definitions
        'output/reports.xml',
        'output/templates/print_invoice.xml',
        'output/templates/report_vat_view.xml',
        'output/templates/report_trial_balance_view.xml',
        'output/templates/report_debtor_view.xml',
        'output/templates/report_creditor_view.xml',
        'output/templates/report_ledger_view.xml',
        # report views
        'reports/views/report_vat_view.xml',
        'reports/views/report_trial_balance_view.xml',
        'reports/views/report_debtor_view.xml',
        'reports/views/report_creditor_view.xml',
        'reports/views/report_ledger_view.xml',
        # wizard views
        'wizards/views/template_view.xml',
        'wizards/views/import_ubl_view.xml',
        'wizards/views/import_mt940_view.xml',
        # inital data
        'data/templates.xml',
        'data/invoice_action_data.xml',
    ],
    'installable': True,
    'auto_install': False,
}
