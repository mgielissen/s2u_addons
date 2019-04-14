{
    'name': 'Solutions2use Payment Acquirer Mollie',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Extension payment acquirer for mollie integration',
    'category':  'eCommerce',
    'description':
        """Extension payment acquirer for mollie integration
        """,
    'depends': ['s2upayment'],
    'data': [
        'security/rules.xml',
        'security/ir.model.access.csv',
        'views/payment_acquirer_view.xml',
        'views/website_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
}
