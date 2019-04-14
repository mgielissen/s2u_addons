{
    'name': 'Solutions2use Document Management',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use Document Management',
    'category':  'Document Management',
    'description':
        """
        """,
    'depends': ['base', 's2ubase', 'mail', 's2ucrm'],
    'data': [
        # security
        'security/rules.xml',
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        # views
        'views/menus.xml',
        'views/document_view.xml',
        'views_inherited/entity_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}
