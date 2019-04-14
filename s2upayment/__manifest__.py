{
    'name': 'Solutions2use Payment Acquirer',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Base object for payment acquirers',
    'category':  'eCommerce',
    'images': ['static/description/icon.png'],
    'description':
        """Base object for payment acquirers
        """,
    'depends': ['s2uaccount', 's2uproduct', 's2usale', 'website'],
    'data': [
         'security/rules.xml',
         'security/ir.model.access.csv',
         'security/res_groups.xml',
         'views/menus.xml',
         'views/payment_acquirer_view.xml',
         'views/payment_transaction_view.xml',
         'views/country_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
