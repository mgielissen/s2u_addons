{
    'name': 'Solutions2use ecommerce instance management',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use ecommerce instance management',
    'category':  'eCommerce',
    'description':
        """
        """,
    'depends': ['s2ubase', 's2usubscription', 's2uecommerce', 's2usale', 's2ucrm', 's2umobile'],
    'data': [
        # security
        'security/res_groups.xml',
        'security/rules.xml',
        'security/ir.model.access.csv',
        # views
        'views/menus.xml',
        'views/instance_view.xml',
        'views/website_templates.xml',
        # pdf definitions
        # report views
        # wizard views
        # inital data
    ],
    'installable': True,
    'auto_install': False,
}
