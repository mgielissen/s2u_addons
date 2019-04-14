# -*- coding: utf-8 -*-

import xmlrpclib


sysDB = 'db'
sysUID = 'user'
sysPW = 'pw'
urlCommon = 'http://%s:%d/xmlrpc/common' % ('127.0.0.1', 8169)
urlObject = 'http://%s:%d/xmlrpc/object' % ('127.0.0.1', 8169)

sockCommon = xmlrpclib.ServerProxy(urlCommon)
sockObject = xmlrpclib.ServerProxy(urlObject)

uid = sockCommon.login(sysDB, sysUID, sysPW)

print 'test set fav ...'

print sockObject.execute(sysDB, uid, sysPW, 's2u.mobile.proxy', 'contact_favorite', [], 'entity:10', False)

