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

print 'test fetch_cockpit ...'

print sockObject.execute(sysDB, uid, sysPW, 's2u.mobile.proxy', 'fetch_cockpit', [])
