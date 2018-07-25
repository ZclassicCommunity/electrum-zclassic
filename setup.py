#!/usr/bin/env python3

# python setup.py sdist --format=zip,gztar

from setuptools import setup
import os
import sys
import platform
import imp
import argparse

with open('contrib/requirements/requirements.txt') as f:
    requirements = f.read().splitlines()

with open('contrib/requirements/requirements-hw.txt') as f:
    requirements_hw = f.read().splitlines()

version = imp.load_source('version', 'lib/version.py')

if sys.version_info[:3] < (3, 4, 0):
    sys.exit("Error: Electrum-Zcash requires Python version >= 3.4.0...")

data_files = []

if platform.system() in ['Linux', 'FreeBSD', 'DragonFly']:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root=', dest='root_path', metavar='dir', default='/')
    opts, _ = parser.parse_known_args(sys.argv[1:])
    usr_share = os.path.join(sys.prefix, "share")
    icons_dirname = 'pixmaps'
    if not os.access(opts.root_path + usr_share, os.W_OK) and \
       not os.access(opts.root_path, os.W_OK):
        icons_dirname = 'icons'
        if 'XDG_DATA_HOME' in os.environ.keys():
            usr_share = os.environ['XDG_DATA_HOME']
        else:
            usr_share = os.path.expanduser('~/.local/share')
    data_files += [
        (os.path.join(usr_share, 'applications/'), ['electrum-zcash.desktop']),
        (os.path.join(usr_share, icons_dirname), ['icons/electrum-zcash.png'])
    ]

setup(
    name="Electrum-Zcash",
    version=version.ELECTRUM_VERSION,
    install_requires=requirements,
    extras_require={
        'full': requirements_hw + ['pycryptodomex'],
    },
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
            'servers_regtest.json',
            'currencies.json',
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
    url="https://github.com/zebra-lucky/electrum-zcash",
    long_description="""Lightweight Zcash Wallet"""
)
