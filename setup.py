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
    sys.exit("Error: Electrum-Zclassic requires Python version >= 3.4.0...")

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
        (os.path.join(usr_share, 'applications/'), ['electrum-zclassic.desktop']),
        (os.path.join(usr_share, icons_dirname), ['icons/electrum-zclassic.png'])
    ]

setup(
    name="Electrum-Zclassic",
    version=version.ELECTRUM_VERSION,
    install_requires=requirements,
    extras_require={
        'full': requirements_hw + ['pycryptodomex'],
    },
    packages=[
        'electrum_zclassic',
        'electrum_zclassic_gui',
        'electrum_zclassic_gui.qt',
        'electrum_zclassic_plugins',
        'electrum_zclassic_plugins.audio_modem',
        'electrum_zclassic_plugins.cosigner_pool',
        'electrum_zclassic_plugins.email_requests',
        'electrum_zclassic_plugins.hw_wallet',
        'electrum_zclassic_plugins.keepkey',
        'electrum_zclassic_plugins.labels',
        'electrum_zclassic_plugins.ledger',
        'electrum_zclassic_plugins.trezor',
        'electrum_zclassic_plugins.digitalbitbox',
        'electrum_zclassic_plugins.virtualkeyboard',
    ],
    package_dir={
        'electrum_zclassic': 'lib',
        'electrum_zclassic_gui': 'gui',
        'electrum_zclassic_plugins': 'plugins',
    },
    package_data={
        'electrum_zclassic': [
            'servers.json',
            'servers_testnet.json',
            'servers_regtest.json',
            'currencies.json',
            'wordlist/*.txt',
            'locale/*/LC_MESSAGES/electrum.mo',
        ]
    },
    scripts=['electrum-zclassic'],
    data_files=data_files,
    description="Lightweight Zclassic Wallet",
    author="Thomas Voegtlin",
    author_email="thomasv@electrum.org",
    license="MIT License",
    url="https://github.com/ZclassicCommunity/electrum-zclassic",
    long_description="""Lightweight Zclassic Wallet"""
)
