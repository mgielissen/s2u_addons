#-*- coding:utf-8 -*-

import time
import math
import datetime
import sys
import re
import platform
import os
import __main__
import psutil
import logging
from logging.handlers import RotatingFileHandler

DEF_LOG_DIR = '.'
if platform.system() == 'Linux':
    DEF_LOG_DIR = '/var/log/odoo'

def get_android_appid():

    return "AIzaSyDKVZo4sk-zVzmjbv0pRhlBEH40vWLMwQY"


def valid_email(string):
            if not re.match('^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', string.rstrip()):
                return False
            return True


def format_date(d):

    dagen = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag']
    maanden = ['januari', 'februari', 'maart',
               'april', 'mei', 'juni', 'juli',
               'augustus', 'september', 'oktober',
               'november', 'december']

    datum = datetime.datetime.strptime(d, '%Y-%m-%d')
    nu = datetime.datetime.strptime(time.strftime('%Y-%m-%d'), '%Y-%m-%d')

    if nu.year == datum.year:
        return '%s, %d %s' % (dagen[datum.weekday()], datum.day, maanden[datum.month - 1])
    else:
        return '%s, %d %s %d' % (dagen[datum.weekday()], datum.day, maanden[datum.month - 1], datum.year)


def format_datetime(dt):

    try:
        d = dt[:10]
        t = dt[11:19]
        return '%s %s' % (format_date(d), t)
    except:
        return dt


def format_time(t):
    m, h = math.modf(t)

    return '%d:%02d' % (int(h), int(m * 60.0))


def encode_list(l, encoding):
    for idx, item in enumerate(l):
        if isinstance(item, basestring):
            l[idx] = item.encode(encoding)
    return l


def decode_list(l, decoding):
    for idx, item in enumerate(l):
        if isinstance(item, basestring):
            l[idx] = item.decode(decoding)
    return l


def check_encoding(iterable, encoding):
    """
    Check for values inside iterable object
    :param iterable: list of dict with strings
    :param encoding: target encodig
    :return: modified inpu list
    """
    if isinstance(iterable, dict):
        for key, val in iter(iterable.items()):
            if isinstance(val, str):
                try:
                    iterable[key] = val.encode(encoding)
                except:
                    res = ''
                    for c in val:
                        try:
                            res += c.encode(encoding, 'replace')
                        except:
                            res += '?'

                    iterable[key] = res
    elif isinstance(iterable, list):
        for idx, val in enumerate(iterable):
            if isinstance(val, basestring):
                try:
                    iterable[idx] = val.encode(encoding)
                except:
                    res = ''
                    for c in val:
                        try:
                            res += c.encode(encoding, 'replace')
                        except:
                            res += '?'

                    iterable[idx] = res

    return iterable


def get_configured_logger(filename=None, level='debug'):
    """
    Configures logger with Rolling file Console output handlers.
    :param filename: log file name
    :return: logger object
    """
    if not filename:
        filename = os.path.basename(__main__.__file__)
        filename = filename.replace('.py', '.log')

    # concatenate to Default log directory
    filename = os.path.join(DEF_LOG_DIR, filename)

    logger = logging.getLogger(__main__.__name__)
    if level == 'debug':
        logger.setLevel(logging.DEBUG)
    elif level == 'info':
        logger.setLevel(logging.INFO)
    elif level == 'warn':
        logger.setLevel(logging.WARN)
    elif level == 'error':
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    rf_handler = RotatingFileHandler(filename=filename, maxBytes=1000000, backupCount=3, encoding='utf8')
    console_handler = logging.StreamHandler(sys.stdout)
    rf_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(rf_handler)
    logger.addHandler(console_handler)

    return logger


def is_running():
    """
    Checks if calling process is already running
    :return: True is running, False otherwise
    """
    process_name = os.path.basename(__main__.__file__)
    this_pid = os.getpid()

    for p in psutil.process_iter():
        # check for process with same name but different pid
        if len(p.cmdline()) > 0 and 'python' in p.cmdline() and this_pid != p.pid:
            if any(process_name in cmd for cmd in p.cmdline()):
                return True

    return False
