{
    'name': 'Solutions2use CRM',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'website': 'https://www.solutions2use.com',
    'version': '0.1',
    'summary': 'Solutions2use CRM',
    'category':  'CRM',
    'images': ['static/description/icon.png'],
    'description':
        """
        """,
    'depends': ['base_setup', 's2ubase', 'mail'],
    'data': [
        'security/rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/entity_view.xml',
        'views/web_template.xml',
        'output/templates/general_crm.xml',
    ],
    'qweb': [
        'static/src/xml/base.xml',
    ],
    'installable': True,
    'auto_install': False,
}
