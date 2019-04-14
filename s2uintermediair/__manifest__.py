{
    'name': 'Solutions2use Intermediair',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use Intermediair',
    'category':  'Sales',
    'images': ['static/description/icon.png'],
    'description':
        """
        """,
    'depends': ['base_setup', 's2ubase', 's2ubaseproduct', 's2ucrm', 's2uaccount', 's2uwarehouse', 's2usale', 's2uproduct'],
    'data': [
        # security
        'security/rules.xml',
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        # views
        'views/menus.xml',
        'views/calculation_view.xml',
        'wizards/views/add_purchase_view.xml',
        'views_inherited/purchase_view.xml',
        'output/templates/print_sale.xml',
        'output/templates/print_purchase.xml',
        'output/templates/print_invoice.xml'
    ],
    'installable': True,
    'auto_install': False,
}
