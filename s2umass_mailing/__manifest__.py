{
    'name': 'Solutions2use Mass Mailing',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use Mass Mailing',
    'category':  'Marketing',
    'description':
        """
        """,
    'depends': ['mass_mailing', 's2ucrm'],
    'data': [
        # security
        'security/ir.model.access.csv',
        # views
        'views_inherited/entity_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}
