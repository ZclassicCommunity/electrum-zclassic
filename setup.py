#!/usr/bin/env python3

# python setup.py sdist --format=zip,gztar

from setuptools import setup
import os
import sys
import platform
import imp
import argparse

version = imp.load_source('version', 'lib/version.py')

if sys.version_info[:3] < (3, 4, 0):
    sys.exit("Error: Electrum-Zcash requires Python version >= 3.4.0...")

data_files = []

if platform.system() in ['Linux', 'FreeBSD', 'DragonFly']:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root=', dest='root_path', metavar='dir', default='/')
    opts, _ = parser.parse_known_args(sys.argv[1:])
    usr_share = os.path.join(sys.prefix, "share")
    if not os.access(opts.root_path + usr_share, os.W_OK) and \
       not os.access(opts.root_path, os.W_OK):
        if 'XDG_DATA_HOME' in os.environ.keys():
            usr_share = os.environ['XDG_DATA_HOME']
        else:
            usr_share = os.path.expanduser('~/.local/share')
    data_files += [
        (os.path.join(usr_share, 'applications/'), ['electrum-zcash.desktop']),
        (os.path.join(usr_share, 'pixmaps/'), ['icons/electrum-zcash.png'])
    ]

setup(
    name="Electrum-Zcash",
    version=version.ELECTRUM_VERSION,
    install_requires=[
        'pyaes>=0.1a1',
        'ecdsa>=0.9',
        'pbkdf2',
        'requests',
        'qrcode',
        'protobuf',
        'dnspython',
        'jsonrpclib-pelix',
        'PySocks>=1.6.6',
    ],
    packages=[
        'electrum_zcash',
        'electrum_zcash_gui',
        'electrum_zcash_gui.qt',
        'electrum_zcash_plugins',
        'electrum_zcash_plugins.audio_modem',
        'electrum_zcash_plugins.cosigner_pool',
        'electrum_zcash_plugins.email_requests',
        'electrum_zcash_plugins.hw_wallet',
        'electrum_zcash_plugins.keepkey',
        'electrum_zcash_plugins.labels',
        'electrum_zcash_plugins.ledger',
        'electrum_zcash_plugins.trezor',
        'electrum_zcash_plugins.digitalbitbox',
        'electrum_zcash_plugins.virtualkeyboard',
    ],
    package_dir={
        'electrum_zcash': 'lib',
        'electrum_zcash_gui': 'gui',
        'electrum_zcash_plugins': 'plugins',
    },
    package_data={
        'electrum_zcash': [
            'servers.json',
            'servers_testnet.json',
            'currencies.json',
            'www/index.html',
            'wordlist/*.txt',
            'locale/*/LC_MESSAGES/electrum.mo',
        ]
    },
    scripts=['electrum-zcash'],
    data_files=data_files,
    description="Lightweight Zcash Wallet",
    author="Thomas Voegtlin",
    author_email="thomasv@electrum.org",
    license="MIT License",
    url="https://electrum-zcash.org",
    long_description="""Lightweight Zcash Wallet"""
)
