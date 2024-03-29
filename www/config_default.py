# !usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Jackly'

'''
Default configurations.
'''

configs = {
    'debug': True,
    'db': {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'www-data',
        'password': 'password',
        'db': 'awesome'
    },
    'session': {
        'secret': 'Awesome'
    }
}