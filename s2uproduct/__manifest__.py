{
    'name': 'Solutions2use Product',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Product management',
    'category':  'Sales en Purchases',
    'images': ['static/description/icon.png'],
    'description':
        """Product management for sales and purchases
        """,
    'depends': ['s2ucrm', 's2uaccount', 's2uwarehouse', 's2usale'],
    'data': [
         'security/rules.xml',
         'security/ir.model.access.csv',
         'views/menus.xml',
         'views/product_view.xml',
         'views_inherited/entity_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}
