{
    'name': 'Solutions2use Sales',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use Sales',
    'category':  'Sales',
    'images': ['static/description/icon.png'],
    'description':
        """
        """,
    'depends': ['base_setup', 'portal', 's2ubase', 's2ubaseproduct', 's2ucrm', 's2uaccount', 's2uwarehouse', 's2udocument'],
    'data': [
        # security
        'security/res_groups.xml',
        'security/rules.xml',
        'security/ir.model.access.csv',
        # views
        'views/menus.xml',
        'views/sale_view.xml',
        'views/purchase_view.xml',
        'views/label_view.xml',
        'views_inherited/shipment_view.xml',
        'views_inherited/entity_view.xml',
        'views_inherited/invoice_view.xml',
        'wizards/views/sale_wizard_view.xml',
        'output/reports.xml',
        'output/templates/print_sale.xml',
        'output/templates/print_purchase.xml',
        'output/templates/print_invoice.xml',
        'views/sale_portal_templates.xml',
        'output/templates/print_delivery.xml',
        'output/templates/print_rma.xml',
        'output/templates/report_journal.xml',
        'data/sale_action_data.xml'
    ],
    'installable': True,
    'auto_install': False,
}
