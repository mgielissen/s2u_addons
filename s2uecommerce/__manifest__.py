{
    'name': 'Solutions2use eCommerce',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'eCommerce',
    'category':  'webshop',
    'images': ['static/description/icon.png'],
    'description':
        """eCommerce / webshop
        """,
    'depends': ['auth_signup', 'website', 'portal', 's2ucrm', 's2uaccount', 's2uproduct', 's2upayment'],
    'data': [
         'security/rules.xml',
         'security/ir.model.access.csv',
         'views/menus.xml',
         'views/theme.xml',
         'views/layout.xml',
         'views/website_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
}
