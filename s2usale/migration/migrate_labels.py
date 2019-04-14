# -*- coding: utf-8 -*-
import xmlrpclib
import sys

#  1     2     3      4     5     6      7     8            9
#server port uidold pwold dbold uidnew pwnew dbnew company_id_server_new
#Beispiel
#127.0.0.1 8169 admin kennwort s2utest admin kennwort s2utest9 1

def migrieren(server, portold, servernew, portnew, user_old, pw_old, db_old,  user_new, pw_new, db_new, company_id, tabelle, query):
    if portold == 'ssl':
        urlCommon_old = 'https://%s/xmlrpc/common' % (server)
        urlObject_old = 'https://%s/xmlrpc/object' % (server)
    else:
        urlCommon_old = 'http://%s:%s/xmlrpc/common' % (server, portold)
        urlObject_old = 'http://%s:%s/xmlrpc/object' % (server, portold)
    sysDB_old = db_old
    sysUID_old = user_old
    sysPW_old = pw_old
    if portnew == 'ssl':
        urlCommon_new = 'https://%s/xmlrpc/common' % (servernew)
        urlObject_new = 'https://%s/xmlrpc/object' % (servernew)
    else:
        urlCommon_new = 'http://%s:%s/xmlrpc/common' % (servernew, portnew)
        urlObject_new = 'http://%s:%s/xmlrpc/object' % (servernew, portnew)
    sysDB_new = db_new
    sysUID_new = user_new
    sysPW_new = pw_new

    sockCommon_old = xmlrpclib.ServerProxy(urlCommon_old)
    sockObject_old = xmlrpclib.ServerProxy(urlObject_old)

    uid_old = sockCommon_old.login(sysDB_old, sysUID_old, sysPW_old)
    if not uid_old:
        print "login failed!"
        exit(1)

    sockCommon_new = xmlrpclib.ServerProxy(urlCommon_new)
    sockObject_new = xmlrpclib.ServerProxy(urlObject_new)

    uid_new = sockCommon_new.login(sysDB_new, sysUID_new, sysPW_new)
    if not uid_new:
        print "login failed!"
        exit(1)

    records = sockObject_old.execute(sysDB_old, uid_old, sysPW_old, tabelle, 'search', query)
    print 'start %s' % tabelle
    count = 0
    relogin_counter = 0

    found = sockObject_new.execute(sysDB_new, uid_new, sysPW_new, tabelle, 'search', [])
    if found:
        # records present, also abort
        return False

    for rec_id in records:
        rec = sockObject_old.execute(sysDB_old, uid_old, sysPW_old, tabelle, 'read', rec_id, [])

        vals = {}
        for field in rec:
            if field == 'id':
                pass
            elif field == 'company_id':
                if rec[field]:
                    vals[field] = company_id
            elif field not in ['create_uid', 'write_uid']:
                vals[field] = rec[field]
        try:
            sockObject_new.execute(sysDB_new, uid_new, sysPW_new, tabelle, 'create', vals)
        except:
            print 'Fehler %s %s' % (tabelle, rec_id)

        count += 1
        relogin_counter += 1
        if relogin_counter >= 500:
            print "Make a re-login ..."
            uid_old = sockCommon_old.login(sysDB_old, sysUID_old, sysPW_old)
            uid_new = sockCommon_new.login(sysDB_new, sysUID_new, sysPW_new)
            relogin_counter = 0

    print 'Finished %s' % tabelle

    return 'ok'


def main():
    if len(sys.argv) < 11:
        print 'error zu wenig elemente übergeben'
        print 'Reihenfolge'
        print 'serverold portold servernew portnew uidold pwold dbold uidnew pwnew dbnew company_id_server_new'
        sys.exit()

    server = sys.argv[1]
    port = sys.argv[2]
    servernew = sys.argv[3]
    portnew = sys.argv[4]
    user_old = sys.argv[5]
    pw_old = sys.argv[6]
    db_old = sys.argv[7]
    user_new = sys.argv[8]
    pw_new = sys.argv[9]
    db_new = sys.argv[10]
    company_id = sys.argv[11]

    print migrieren(server, port, servernew, portnew, user_old, pw_old, db_old, user_new, pw_new, db_new, company_id,
                    tabelle='s2u.label', query=[])


if __name__ == '__main__':
    main()
