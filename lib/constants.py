# -*- coding: utf-8 -*-
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2018 The Electrum developers
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import json


def read_json(filename, default):
    path = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(path, 'r') as f:
            r = json.loads(f.read())
    except:
        r = default
    return r


class BitcoinMainnet:

    TESTNET = False
    WIF_PREFIX = 0x80
    ADDRTYPE_P2PKH = bytes.fromhex('1CB8')
    ADDRTYPE_P2SH = bytes.fromhex('1CBD')
    GENESIS = "00040fe8ec8471911baa1db1266ea15dd06b4a8a5c453883c000b031973dce08"
    DEFAULT_PORTS = {'t': '50021', 's': '50022'}
    DEFAULT_SERVERS = read_json('servers.json', {})
    CHECKPOINTS = read_json('checkpoints.json', [])

    XPRV_HEADERS = {
        'standard':    0x0488ade4,  # xprv
    }
    XPUB_HEADERS = {
        'standard':    0x0488b21e,  # xpub
    }
    OVERWINTER_HEIGHT = 347500


class BitcoinTestnet:

    TESTNET = True
    WIF_PREFIX = 0xEF
    ADDRTYPE_P2PKH = bytes.fromhex('1D25')
    ADDRTYPE_P2SH = bytes.fromhex('1CBA')
    GENESIS = "05a60a92d99d85997cce3b87616c089f6124d7342af37106edc76126334a2c38"
    DEFAULT_PORTS = {'t': '51021', 's': '51022'}
    DEFAULT_SERVERS = read_json('servers_testnet.json', {})
    CHECKPOINTS = read_json('checkpoints_testnet.json', [])

    XPRV_HEADERS = {
        'standard':    0x04358394,  # tprv
    }
    XPUB_HEADERS = {
        'standard':    0x043587cf,  # tpub
    }
    OVERWINTER_HEIGHT = 207500


class BitcoinRegtest(BitcoinTestnet):

    GENESIS = "029f11d80ef9765602235e1bc9727e3eb6ba20839319f761fee920d63401e327"
    DEFAULT_SERVERS = read_json('servers_regtest.json', {})
    CHECKPOINTS = []


# don't import net directly, import the module instead (so that net is singleton)
net = BitcoinMainnet


def set_mainnet():
    global net
    net = BitcoinMainnet


def set_testnet():
    global net
    net = BitcoinTestnet


def set_regtest():
    global net
    net = BitcoinRegtest
