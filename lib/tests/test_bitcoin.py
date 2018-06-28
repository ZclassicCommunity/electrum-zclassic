import base64
import unittest
import sys
from ecdsa.util import number_to_string

from lib.bitcoin import (
    generator_secp256k1, point_to_ser, public_key_to_p2pkh, EC_KEY,
    bip32_root, bip32_public_derivation, bip32_private_derivation, pw_encode,
    pw_decode, Hash, public_key_from_private_key, address_from_private_key,
    is_address, is_private_key, xpub_from_xprv, is_new_seed, is_old_seed,
    var_int, op_push, address_to_script, regenerate_key,
    verify_message, deserialize_privkey, serialize_privkey,
    is_b58_address, address_to_scripthash, is_minikey, is_compressed, is_xpub,
    xpub_type, is_xprv, is_bip32_derivation, seed_type, EncodeBase58Check)
from lib.util import bfh
from lib import constants

from . import TestCaseForTestnet


try:
    import ecdsa
except ImportError:
    sys.exit("Error: python-ecdsa does not seem to be installed. Try 'sudo pip install ecdsa'")


class Test_bitcoin(unittest.TestCase):

    def test_crypto(self):
        for message in [b"Chancellor on brink of second bailout for banks", b'\xff'*512]:
            self._do_test_crypto(message)

    def _do_test_crypto(self, message):
        G = generator_secp256k1
        _r  = G.order()
        pvk = ecdsa.util.randrange( pow(2,256) ) %_r

        Pub = pvk*G
        pubkey_c = point_to_ser(Pub,True)
        #pubkey_u = point_to_ser(Pub,False)
        addr_c = public_key_to_p2pkh(pubkey_c)

        #print "Private key            ", '%064x'%pvk
        eck = EC_KEY(number_to_string(pvk,_r))

        #print "Compressed public key  ", pubkey_c.encode('hex')
        enc = EC_KEY.encrypt_message(message, pubkey_c)
        dec = eck.decrypt_message(enc)
        self.assertEqual(message, dec)

        #print "Uncompressed public key", pubkey_u.encode('hex')
        #enc2 = EC_KEY.encrypt_message(message, pubkey_u)
        dec2 = eck.decrypt_message(enc)
        self.assertEqual(message, dec2)

        signature = eck.sign_message(message, True)
        #print signature
        EC_KEY.verify_message(eck, signature, message)

    def test_msg_signing(self):
        msg1 = b'Chancellor on brink of second bailout for banks'
        msg2 = b'Electrum'

        def sign_message_with_wif_privkey(wif_privkey, msg):
            txin_type, privkey, compressed = deserialize_privkey(wif_privkey)
            key = regenerate_key(privkey)
            return key.sign_message(msg, compressed)

        sig1 = sign_message_with_wif_privkey(
            'L1TnU2zbNaAqMoVh65Cyvmcjzbrj41Gs9iTLcWbpJCMynXuap6UN', msg1)
        addr1 = 't1NZqTzJMjwKMcQPxofUEbqRSSotJ7VVJSZ'
        sig2 = sign_message_with_wif_privkey(
            '5Hxn5C4SQuiV6e62A1MtZmbSeQyrLFhu5uYks62pU5VBUygK2KD', msg2)
        addr2 = 't1ZFtVnxGSXwNZjnsKVhiAGeEC8nJPuJDDp'

        sig1_b64 = base64.b64encode(sig1)
        sig2_b64 = base64.b64encode(sig2)

        print('sig1_b64', sig1_b64)
        print('sig2_b64', sig2_b64)
        self.assertEqual(sig1_b64, b'IAcowIh4U6j342ioNfu/jH4OCcy+qtLp9O6P3aoFVk5NbC+UpsCDhBYwlg2R7gsw18TV1QKjDX7JkWaYb9pGdGo=')
        self.assertEqual(sig2_b64, b'HIszHegFNJvGYqJYvzSqrBtfc1PdbR1fai93xIZUeXr6coc3XrEmEvjKvcyas2mermVUnaCVox944itoZg3bwt8=')

        self.assertTrue(verify_message(addr1, sig1, msg1))
        self.assertTrue(verify_message(addr2, sig2, msg2))

        self.assertFalse(verify_message(addr1, b'wrong', msg1))
        self.assertFalse(verify_message(addr1, sig2, msg1))

    def test_aes_homomorphic(self):
        """Make sure AES is homomorphic."""
        payload = u'\u66f4\u7a33\u5b9a\u7684\u4ea4\u6613\u5e73\u53f0'
        password = u'secret'
        enc = pw_encode(payload, password)
        dec = pw_decode(enc, password)
        self.assertEqual(dec, payload)

    def test_aes_encode_without_password(self):
        """When not passed a password, pw_encode is noop on the payload."""
        payload = u'\u66f4\u7a33\u5b9a\u7684\u4ea4\u6613\u5e73\u53f0'
        enc = pw_encode(payload, None)
        self.assertEqual(payload, enc)

    def test_aes_deencode_without_password(self):
        """When not passed a password, pw_decode is noop on the payload."""
        payload = u'\u66f4\u7a33\u5b9a\u7684\u4ea4\u6613\u5e73\u53f0'
        enc = pw_decode(payload, None)
        self.assertEqual(payload, enc)

    def test_aes_decode_with_invalid_password(self):
        """pw_decode raises an Exception when supplied an invalid password."""
        payload = u"blah"
        password = u"uber secret"
        wrong_password = u"not the password"
        enc = pw_encode(payload, password)
        self.assertRaises(Exception, pw_decode, enc, wrong_password)

    def test_hash(self):
        """Make sure the Hash function does sha256 twice"""
        payload = u"test"
        expected = b'\x95MZI\xfdp\xd9\xb8\xbc\xdb5\xd2R&x)\x95\x7f~\xf7\xfalt\xf8\x84\x19\xbd\xc5\xe8"\t\xf4'

        result = Hash(payload)
        self.assertEqual(expected, result)

    def test_var_int(self):
        for i in range(0xfd):
            self.assertEqual(var_int(i), "{:02x}".format(i) )

        self.assertEqual(var_int(0xfd), "fdfd00")
        self.assertEqual(var_int(0xfe), "fdfe00")
        self.assertEqual(var_int(0xff), "fdff00")
        self.assertEqual(var_int(0x1234), "fd3412")
        self.assertEqual(var_int(0xffff), "fdffff")
        self.assertEqual(var_int(0x10000), "fe00000100")
        self.assertEqual(var_int(0x12345678), "fe78563412")
        self.assertEqual(var_int(0xffffffff), "feffffffff")
        self.assertEqual(var_int(0x100000000), "ff0000000001000000")
        self.assertEqual(var_int(0x0123456789abcdef), "ffefcdab8967452301")

    def test_op_push(self):
        self.assertEqual(op_push(0x00), '00')
        self.assertEqual(op_push(0x12), '12')
        self.assertEqual(op_push(0x4b), '4b')
        self.assertEqual(op_push(0x4c), '4c4c')
        self.assertEqual(op_push(0xfe), '4cfe')
        self.assertEqual(op_push(0xff), '4cff')
        self.assertEqual(op_push(0x100), '4d0001')
        self.assertEqual(op_push(0x1234), '4d3412')
        self.assertEqual(op_push(0xfffe), '4dfeff')
        self.assertEqual(op_push(0xffff), '4dffff')
        self.assertEqual(op_push(0x10000), '4e00000100')
        self.assertEqual(op_push(0x12345678), '4e78563412')

    def test_address_to_script(self):
        # base58 P2PKH
        self.assertEqual(address_to_script('t1MZDS9LxiXasLqR5fMDK4kDa8TJjSFsMsq'), '76a91428662c67561b95c79d2257d2a93d9d151c977e9188ac')
        self.assertEqual(address_to_script('t1U7SgL7CWNnawSvZD8k8JgwWUygasy2cp1'), '76a914704f4b81cadb7bf7e68c08cd3657220f680f863c88ac')

        # base58 P2SH
        self.assertEqual(address_to_script('t3NSSQe2KNgLcTWy2WsiRAkr7NTtZ15fhLn'), 'a9142a84cf00d47f699ee7bbc1dea5ec1bdecb4ac15487')
        self.assertEqual(address_to_script('t3grLzdTrjSSiCFXzxV5YCvkYZt2tJjDLau'), 'a914f47c8954e421031ad04ecd8e7752c9479206b9d387')


class Test_bitcoin_testnet(TestCaseForTestnet):

    def test_address_to_script(self):
        # base58 P2PKH
        self.assertEqual(address_to_script('tmQ5vePhZkGVbPhJdFd7J9bQF9p5jmVXGe5'), '76a9149da64e300c5e4eb4aaffc9c2fd465348d5618ad488ac')
        self.assertEqual(address_to_script('tmD3HcYHK21Kypmi3UpSSDEgbSdoTcnduow'), '76a914247d2d5b6334bdfa2038e85b20fc15264f8e5d2788ac')

        # base58 P2SH
        self.assertEqual(address_to_script('t2Ge2v7dx9Q87aDcx9iDr48uxCEe1gBVzCT'), 'a9146eae23d8c4a941316017946fc761a7a6c85561fb87')
        self.assertEqual(address_to_script('t2TN9d3YVzoaZqdwyrqZKjz6289tW3JF78v'), 'a914e4567743d378957cd2ee7072da74b1203c1a7a0b87')


class Test_xprv_xpub(unittest.TestCase):

    xprv_xpub = (
        # Taken from test vectors in https://en.bitcoin.it/wiki/BIP_0032_TestVectors
        {'xprv': 'xprvA41z7zogVVwxVSgdKUHDy1SKmdb533PjDz7J6N6mV6uS3ze1ai8FHa8kmHScGpWmj4WggLyQjgPie1rFSruoUihUZREPSL39UNdE3BBDu76',
         'xpub': 'xpub6H1LXWLaKsWFhvm6RVpEL9P4KfRZSW7abD2ttkWP3SSQvnyA8FSVqNTEcYFgJS2UaFcxupHiYkro49S8yGasTvXEYBVPamhGW6cFJodrTHy',
         'xtype': 'standard'},
    )

    def _do_test_bip32(self, seed, sequence):
        xprv, xpub = bip32_root(bfh(seed), 'standard')
        self.assertEqual("m/", sequence[0:2])
        path = 'm'
        sequence = sequence[2:]
        for n in sequence.split('/'):
            child_path = path + '/' + n
            if n[-1] != "'":
                xpub2 = bip32_public_derivation(xpub, path, child_path)
            xprv, xpub = bip32_private_derivation(xprv, path, child_path)
            if n[-1] != "'":
                self.assertEqual(xpub, xpub2)
            path = child_path

        return xpub, xprv

    def test_bip32(self):
        # see https://en.bitcoin.it/wiki/BIP_0032_TestVectors
        xpub, xprv = self._do_test_bip32("000102030405060708090a0b0c0d0e0f", "m/0'/1/2'/2/1000000000")
        self.assertEqual("xpub6H1LXWLaKsWFhvm6RVpEL9P4KfRZSW7abD2ttkWP3SSQvnyA8FSVqNTEcYFgJS2UaFcxupHiYkro49S8yGasTvXEYBVPamhGW6cFJodrTHy", xpub)
        self.assertEqual("xprvA41z7zogVVwxVSgdKUHDy1SKmdb533PjDz7J6N6mV6uS3ze1ai8FHa8kmHScGpWmj4WggLyQjgPie1rFSruoUihUZREPSL39UNdE3BBDu76", xprv)

        xpub, xprv = self._do_test_bip32("fffcf9f6f3f0edeae7e4e1dedbd8d5d2cfccc9c6c3c0bdbab7b4b1aeaba8a5a29f9c999693908d8a8784817e7b7875726f6c696663605d5a5754514e4b484542","m/0/2147483647'/1/2147483646'/2")
        self.assertEqual("xpub6FnCn6nSzZAw5Tw7cgR9bi15UV96gLZhjDstkXXxvCLsUXBGXPdSnLFbdpq8p9HmGsApME5hQTZ3emM2rnY5agb9rXpVGyy3bdW6EEgAtqt", xpub)
        self.assertEqual("xprvA2nrNbFZABcdryreWet9Ea4LvTJcGsqrMzxHx98MMrotbir7yrKCEXw7nadnHM8Dq38EGfSh6dqA9QWTyefMLEcBYJUuekgW4BYPJcr9E7j", xprv)

    def test_xpub_from_xprv(self):
        """We can derive the xpub key from a xprv."""
        for xprv_details in self.xprv_xpub:
            result = xpub_from_xprv(xprv_details['xprv'])
            self.assertEqual(result, xprv_details['xpub'])

    def test_is_xpub(self):
        for xprv_details in self.xprv_xpub:
            xpub = xprv_details['xpub']
            self.assertTrue(is_xpub(xpub))
        self.assertFalse(is_xpub('xpub1nval1d'))
        self.assertFalse(is_xpub('xpub661MyMwAqRbcFWohJWt7PHsFEJfZAvw9ZxwQoDa4SoMgsDDM1T7WK3u9E4edkC4ugRnZ8E4xDZRpk8Rnts3Nbt97dPwT52WRONGBADWRONG'))

    def test_xpub_type(self):
        for xprv_details in self.xprv_xpub:
            xpub = xprv_details['xpub']
            self.assertEqual(xprv_details['xtype'], xpub_type(xpub))

    def test_is_xprv(self):
        for xprv_details in self.xprv_xpub:
            xprv = xprv_details['xprv']
            self.assertTrue(is_xprv(xprv))
        self.assertFalse(is_xprv('xprv1nval1d'))
        self.assertFalse(is_xprv('xprv661MyMwAqRbcFWohJWt7PHsFEJfZAvw9ZxwQoDa4SoMgsDDM1T7WK3u9E4edkC4ugRnZ8E4xDZRpk8Rnts3Nbt97dPwT52WRONGBADWRONG'))

    def test_is_bip32_derivation(self):
        self.assertTrue(is_bip32_derivation("m/0'/1"))
        self.assertTrue(is_bip32_derivation("m/0'/0'"))
        self.assertTrue(is_bip32_derivation("m/44'/0'/0'/0/0"))
        self.assertTrue(is_bip32_derivation("m/49'/0'/0'/0/0"))
        self.assertFalse(is_bip32_derivation("mmmmmm"))
        self.assertFalse(is_bip32_derivation("n/"))
        self.assertFalse(is_bip32_derivation(""))
        self.assertFalse(is_bip32_derivation("m/q8462"))

    def test_version_bytes(self):
        xprv_headers_b58 = {
            'standard':    'xprv',
        }
        xpub_headers_b58 = {
            'standard':    'xpub',
        }
        for xtype, xkey_header_bytes in constants.net.XPRV_HEADERS.items():
            xkey_header_bytes = bfh("%08x" % xkey_header_bytes)
            xkey_bytes = xkey_header_bytes + bytes([0] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xprv_headers_b58[xtype]))

            xkey_bytes = xkey_header_bytes + bytes([255] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xprv_headers_b58[xtype]))

        for xtype, xkey_header_bytes in constants.net.XPUB_HEADERS.items():
            xkey_header_bytes = bfh("%08x" % xkey_header_bytes)
            xkey_bytes = xkey_header_bytes + bytes([0] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xpub_headers_b58[xtype]))

            xkey_bytes = xkey_header_bytes + bytes([255] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xpub_headers_b58[xtype]))


class Test_xprv_xpub_testnet(TestCaseForTestnet):

    def test_version_bytes(self):
        xprv_headers_b58 = {
            'standard':    'tprv',
        }
        xpub_headers_b58 = {
            'standard':    'tpub',
        }
        for xtype, xkey_header_bytes in constants.net.XPRV_HEADERS.items():
            xkey_header_bytes = bfh("%08x" % xkey_header_bytes)
            xkey_bytes = xkey_header_bytes + bytes([0] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xprv_headers_b58[xtype]))

            xkey_bytes = xkey_header_bytes + bytes([255] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xprv_headers_b58[xtype]))

        for xtype, xkey_header_bytes in constants.net.XPUB_HEADERS.items():
            xkey_header_bytes = bfh("%08x" % xkey_header_bytes)
            xkey_bytes = xkey_header_bytes + bytes([0] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xpub_headers_b58[xtype]))

            xkey_bytes = xkey_header_bytes + bytes([255] * 74)
            xkey_b58 = EncodeBase58Check(xkey_bytes)
            self.assertTrue(xkey_b58.startswith(xpub_headers_b58[xtype]))


class Test_keyImport(unittest.TestCase):

    priv_pub_addr = (
           {'priv': 'KzMFjMC2MPadjvX5Cd7b8AKKjjpBSoRKUTpoAtN6B3J9ezWYyXS6',
            'exported_privkey': 'p2pkh:KzMFjMC2MPadjvX5Cd7b8AKKjjpBSoRKUTpoAtN6B3J9ezWYyXS6',
            'pub': '02c6467b7e621144105ed3e4835b0b4ab7e35266a2ae1c4f8baa19e9ca93452997',
            'address': 't1QTbqnYayRQQ2QZDUgYAcZ6EAcuddyRMbu',
            'minikey' : False,
            'txin_type': 'p2pkh',
            'compressed': True,
            'addr_encoding': 'base58',
            'scripthash': 'c9aecd1fef8d661a42c560bf75c8163e337099800b8face5ca3d1393a30508a7'},
           {'priv': 'p2pkh:Kzj8VjwpZ99bQqVeUiRXrKuX9mLr1o6sWxFMCBJn1umC38BMiQTD',
            'exported_privkey': 'p2pkh:Kzj8VjwpZ99bQqVeUiRXrKuX9mLr1o6sWxFMCBJn1umC38BMiQTD',
            'pub': '0352d78b4b37e0f6d4e164423436f2925fa57817467178eca550a88f2821973c41',
            'address': 't1ZQHZQpr51Z83vYLkuCgUnA7xgygSNEL8E',
            'minikey': False,
            'txin_type': 'p2pkh',
            'compressed': True,
            'addr_encoding': 'base58',
            'scripthash': 'a9b2a76fc196c553b352186dfcca81fcf323a721cd8431328f8e9d54216818c1'},
           {'priv': '5Hxn5C4SQuiV6e62A1MtZmbSeQyrLFhu5uYks62pU5VBUygK2KD',
            'exported_privkey': 'p2pkh:5Hxn5C4SQuiV6e62A1MtZmbSeQyrLFhu5uYks62pU5VBUygK2KD',
            'pub': '04e5fe91a20fac945845a5518450d23405ff3e3e1ce39827b47ee6d5db020a9075422d56a59195ada0035e4a52a238849f68e7a325ba5b2247013e0481c5c7cb3f',
            'address': 't1ZFtVnxGSXwNZjnsKVhiAGeEC8nJPuJDDp',
            'minikey': False,
            'txin_type': 'p2pkh',
            'compressed': False,
            'addr_encoding': 'base58',
            'scripthash': 'f5914651408417e1166f725a5829ff9576d0dbf05237055bf13abd2af7f79473'},
           {'priv': 'p2pkh:5KhYQCe1xd5g2tqpmmGpUWDpDuTbA8vnpbiCNDwMPAx29WNQYfN',
            'exported_privkey': 'p2pkh:5KhYQCe1xd5g2tqpmmGpUWDpDuTbA8vnpbiCNDwMPAx29WNQYfN',
            'pub': '048f0431b0776e8210376c81280011c2b68be43194cb00bd47b7e9aa66284b713ce09556cde3fee606051a07613f3c159ef3953b8927c96ae3dae94a6ba4182e0e',
            'address': 't1LzMikhRjUTSEzTLdGUBsrBTFZhR9hwffh',
            'minikey': False,
            'txin_type': 'p2pkh',
            'compressed': False,
            'addr_encoding': 'base58',
            'scripthash': '6dd2e07ad2de9ba8eec4bbe8467eb53f8845acff0d9e6f5627391acc22ff62df'},
           # from http://bitscan.com/articles/security/spotlight-on-mini-private-keys
           {'priv': 'SzavMBLoXU6kDrqtUVmffv',
            'exported_privkey': 'p2pkh:L53fCHmQhbNp1B4JipfBtfeHZH7cAibzG9oK19XfiFzxHgAkz6JK',
            'pub': '02588d202afcc1ee4ab5254c7847ec25b9a135bbda0f2bc69ee1a714749fd77dc9',
            'address': 't1S9WvZLVKoLjXUAxssvGojtqx1pABJMJUU',
            'minikey': True,
            'txin_type': 'p2pkh',
            'compressed': True,  # this is actually ambiguous... issue #2748
            'addr_encoding': 'base58',
            'scripthash': '60ad5a8b922f758cd7884403e90ee7e6f093f8d21a0ff24c9a865e695ccefdf1'},
    )

    def test_public_key_from_private_key(self):
        for priv_details in self.priv_pub_addr:
            txin_type, privkey, compressed = deserialize_privkey(priv_details['priv'])
            result = public_key_from_private_key(privkey, compressed)
            self.assertEqual(priv_details['pub'], result)
            self.assertEqual(priv_details['txin_type'], txin_type)
            self.assertEqual(priv_details['compressed'], compressed)

    def test_address_from_private_key(self):
        for priv_details in self.priv_pub_addr:
            addr2 = address_from_private_key(priv_details['priv'])
            self.assertEqual(priv_details['address'], addr2)

    def test_is_valid_address(self):
        for priv_details in self.priv_pub_addr:
            addr = priv_details['address']
            self.assertFalse(is_address(priv_details['priv']))
            self.assertFalse(is_address(priv_details['pub']))
            self.assertTrue(is_address(addr))

            is_enc_b58 = priv_details['addr_encoding'] == 'base58'
            self.assertEqual(is_enc_b58, is_b58_address(addr))

        self.assertFalse(is_address("not an address"))

    def test_is_private_key(self):
        for priv_details in self.priv_pub_addr:
            self.assertTrue(is_private_key(priv_details['priv']))
            self.assertTrue(is_private_key(priv_details['exported_privkey']))
            self.assertFalse(is_private_key(priv_details['pub']))
            self.assertFalse(is_private_key(priv_details['address']))
        self.assertFalse(is_private_key("not a privkey"))

    def test_serialize_privkey(self):
        for priv_details in self.priv_pub_addr:
            txin_type, privkey, compressed = deserialize_privkey(priv_details['priv'])
            priv2 = serialize_privkey(privkey, compressed, txin_type)
            self.assertEqual(priv_details['exported_privkey'], priv2)

    def test_address_to_scripthash(self):
        for priv_details in self.priv_pub_addr:
            sh = address_to_scripthash(priv_details['address'])
            self.assertEqual(priv_details['scripthash'], sh)

    def test_is_minikey(self):
        for priv_details in self.priv_pub_addr:
            minikey = priv_details['minikey']
            priv = priv_details['priv']
            self.assertEqual(minikey, is_minikey(priv))

    def test_is_compressed(self):
        for priv_details in self.priv_pub_addr:
            self.assertEqual(priv_details['compressed'],
                             is_compressed(priv_details['priv']))


class Test_seeds(unittest.TestCase):
    """ Test old and new seeds. """

    mnemonics = {
        ('cell dumb heartbeat north boom tease ship baby bright kingdom rare squeeze', 'old'),
        ('cell dumb heartbeat north boom tease ' * 4, 'old'),
        ('cell dumb heartbeat north boom tease ship baby bright kingdom rare badword', ''),
        ('cElL DuMb hEaRtBeAt nOrTh bOoM TeAsE ShIp bAbY BrIgHt kInGdOm rArE SqUeEzE', 'old'),
        ('   cElL  DuMb hEaRtBeAt nOrTh bOoM  TeAsE ShIp    bAbY BrIgHt kInGdOm rArE SqUeEzE   ', 'old'),
        # below seed is actually 'invalid old' as it maps to 33 hex chars
        ('hurry idiot prefer sunset mention mist jaw inhale impossible kingdom rare squeeze', 'old'),
        ('cram swing cover prefer miss modify ritual silly deliver chunk behind inform able', 'standard'),
        ('cram swing cover prefer miss modify ritual silly deliver chunk behind inform', ''),
        ('ostrich security deer aunt climb inner alpha arm mutual marble solid task', 'standard'),
        ('OSTRICH SECURITY DEER AUNT CLIMB INNER ALPHA ARM MUTUAL MARBLE SOLID TASK', 'standard'),
        ('   oStRiCh sEcUrItY DeEr aUnT ClImB       InNeR AlPhA ArM MuTuAl mArBlE   SoLiD TaSk  ', 'standard'),
        ('x8', 'standard'),
        ('science dawn member doll dutch real ca brick knife deny drive list', ''),
    }
    
    def test_new_seed(self):
        seed = "cram swing cover prefer miss modify ritual silly deliver chunk behind inform able"
        self.assertTrue(is_new_seed(seed))

        seed = "cram swing cover prefer miss modify ritual silly deliver chunk behind inform"
        self.assertFalse(is_new_seed(seed))

    def test_old_seed(self):
        self.assertTrue(is_old_seed(" ".join(["like"] * 12)))
        self.assertFalse(is_old_seed(" ".join(["like"] * 18)))
        self.assertTrue(is_old_seed(" ".join(["like"] * 24)))
        self.assertFalse(is_old_seed("not a seed"))

        self.assertTrue(is_old_seed("0123456789ABCDEF" * 2))
        self.assertTrue(is_old_seed("0123456789ABCDEF" * 4))

    def test_seed_type(self):
        for seed_words, _type in self.mnemonics:
            self.assertEqual(_type, seed_type(seed_words), msg=seed_words)
