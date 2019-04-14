{
    'name': 'Solutions2use Subscription',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use Subscriptions',
    'category':  'Sales',
    'images': ['static/description/icon.png'],
    'description':
        """
        """,
    'depends': ['s2ubaseproduct', 's2ucrm', 's2uproduct', 's2usale', 's2uproject', 's2uwarehouse'],
    'data': [
        # security
        'security/rules.xml',
        'security/ir.model.access.csv',
        # views
        'views/menus.xml',
        'views/subscription_view.xml',
        'views/subscription_portal_templates.xml',
        'views_inherited/sale_view.xml',
        'views_inherited/entity_view.xml',
        'views_inherited/project_view.xml',
        'wizards/views/increase_wizard_view.xml',
        'output/templates/print_sale.xml',
        'data/crons.xml'
    ],
    'installable': True,
    'auto_install': False,
}
