#-*- coding:utf-8 -*-

from . import ubl

import sys
import platform
import os
import __main__
import psutil
import logging
from logging.handlers import RotatingFileHandler

DEF_LOG_DIR = '.'
if platform.system() == 'Linux':
    DEF_LOG_DIR = '/var/log/odoo'


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
