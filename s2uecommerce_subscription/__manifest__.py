{
    'name': 'Solutions2use ecommerce for Subscriptions',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use ecommerce for Subscriptions',
    'category':  'eCommerce',
    'description':
        """
        """,
    'depends': ['s2usubscription', 's2uecommerce', 's2uproduct'],
    'data': [
        # security
        # views
        'views/website_templates.xml',
        'views_inherited/subscription_view.xml',
        # pdf definitions
        # report views
        # wizard views
        # inital data
    ],
    'installable': True,
    'auto_install': False,
}
