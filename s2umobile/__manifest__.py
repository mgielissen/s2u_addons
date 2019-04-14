# -*- coding: utf-8 -*-
{
    'name': 'Solutions2use Mobile',
    'version': '1.0',
    'author': 'Solutions2use',
    'license': 'AGPL-3',
    'category': 'Mobile',
    'images': ['static/description/icon.png'],
    'description': """
    """,
    'website': 'https://www.solutions2use.com',
    'depends': ['base', 'mail', 's2ucrm', 's2uaccount', 's2usale'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_view.xml',
        'views/res_company_view.xml',
    ],
    'qweb': [
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
