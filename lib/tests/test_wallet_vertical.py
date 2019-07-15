import unittest
from unittest import mock

import lib.bitcoin as bitcoin
import lib.keystore as keystore
import lib.storage as storage
import lib.wallet as wallet
from lib import constants

from . import TestCaseForTestnet


class WalletIntegrityHelper:

    gap_limit = 1  # make tests run faster

    @classmethod
    def check_seeded_keystore_sanity(cls, test_obj, ks):
        test_obj.assertTrue(ks.is_deterministic())
        test_obj.assertFalse(ks.is_watching_only())
        test_obj.assertFalse(ks.can_import())
        test_obj.assertTrue(ks.has_seed())

    @classmethod
    def check_xpub_keystore_sanity(cls, test_obj, ks):
        test_obj.assertTrue(ks.is_deterministic())
        test_obj.assertTrue(ks.is_watching_only())
        test_obj.assertFalse(ks.can_import())
        test_obj.assertFalse(ks.has_seed())

    @classmethod
    def create_standard_wallet(cls, ks):
        store = storage.WalletStorage('if_this_exists_mocking_failed_648151893')
        store.put('keystore', ks.dump())
        store.put('gap_limit', cls.gap_limit)
        w = wallet.Standard_Wallet(store)
        w.synchronize()
        return w

    @classmethod
    def create_multisig_wallet(cls, ks1, ks2, ks3=None):
        """Creates a 2-of-2 or 2-of-3 multisig wallet."""
        store = storage.WalletStorage('if_this_exists_mocking_failed_648151893')
        store.put('x%d/' % 1, ks1.dump())
        store.put('x%d/' % 2, ks2.dump())
        if ks3 is None:
            multisig_type = "%dof%d" % (2, 2)
        else:
            multisig_type = "%dof%d" % (2, 3)
            store.put('x%d/' % 3, ks3.dump())
        store.put('wallet_type', multisig_type)
        store.put('gap_limit', cls.gap_limit)
        w = wallet.Multisig_Wallet(store)
        w.synchronize()
        return w


# TODO passphrase/seed_extension
class TestWalletKeystoreAddressIntegrityForMainnet(unittest.TestCase):

    @mock.patch.object(storage.WalletStorage, '_write')
    def test_electrum_seed_standard(self, mock_write):
        seed_words = 'cycle rocket west magnet parrot shuffle foot correct salt library feed song'
        self.assertEqual(bitcoin.seed_type(seed_words), 'standard')

        ks = keystore.from_seed(seed_words, '', False)

        WalletIntegrityHelper.check_seeded_keystore_sanity(self, ks)
        self.assertTrue(isinstance(ks, keystore.BIP32_KeyStore))

        self.assertEqual(ks.xprv, 'xprv9s21ZrQH143K2ghMCZbyreZcic8NSSuC8AG1gSTVPdvjiXufyQJyEVwUmS7EBtsH1YKdaMC17EBDrSzpe7M4k48FUYtJpzJNNptxbnpHEXL')
        self.assertEqual(ks.xpub, 'xpub661MyMwAqRbcFAmpJb8zDnWMGdxrqud3VPBcUps6wyTibLEpWwdDnJFxchhCazNLf4xNd3SpAEifKJoL4LSy5jBj2iqXdrfBMmxTWevpCQs')

        w = WalletIntegrityHelper.create_standard_wallet(ks)
        self.assertEqual(w.txin_type, 'p2pkh')

        self.assertEqual(w.get_receiving_addresses()[0], 't1WuqhS6byNzoKu3LJrpfv2BGp7oiATxzyn')
        self.assertEqual(w.get_change_addresses()[0], 't1fvzMLWaFGdJnsJ7K5Ju1jMuC3bKexciyL')

    @mock.patch.object(storage.WalletStorage, '_write')
    def test_electrum_seed_old(self, mock_write):
        seed_words = 'powerful random nobody notice nothing important anyway look away hidden message over'
        self.assertEqual(bitcoin.seed_type(seed_words), 'old')

        ks = keystore.from_seed(seed_words, '', False)

        WalletIntegrityHelper.check_seeded_keystore_sanity(self, ks)
        self.assertTrue(isinstance(ks, keystore.Old_KeyStore))

        self.assertEqual(ks.mpk, 'e9d4b7866dd1e91c862aebf62a49548c7dbf7bcc6e4b7b8c9da820c7737968df9c09d5a3e271dc814a29981f81b3faaf2737b551ef5dcc6189cf0f8252c442b3')

        w = WalletIntegrityHelper.create_standard_wallet(ks)
        self.assertEqual(w.txin_type, 'p2pkh')

        self.assertEqual(w.get_receiving_addresses()[0], 't1YAqEWYrfi9CbW5LgmayAvjDE5T5MgaYiD')
        self.assertEqual(w.get_change_addresses()[0], 't1cJ799hEFa5AHmB3ReeDo3Rr2X4quderf4')

    @mock.patch.object(storage.WalletStorage, '_write')
    def test_bip39_seed_bip44_standard(self, mock_write):
        seed_words = 'treat dwarf wealth gasp brass outside high rent blood crowd make initial'
        self.assertEqual(keystore.bip39_is_checksum_valid(seed_words), (True, True))

        ks = keystore.from_bip39_seed(seed_words, '', "m/44'/0'/0'")

        self.assertTrue(isinstance(ks, keystore.BIP32_KeyStore))

        self.assertEqual(ks.xprv, 'xprv9z8mPoJhK3FiPpzM3gPVYxLkaq6QeCYpwLheSgPBHH3RURwnZYaTqxzLWnkyFMtV1vm8hGTkEjrJRoYegJwgFKEg1K9bsdf3UrpcAcnSj6w')
        self.assertEqual(ks.xpub, 'xpub6D87oJqb9Qp1cK4p9hvVv6HV8rvu3fGgJZdFF4nnqcaQMEGw75tiPmJpN3CQrZR9gpHe7zycB78ynLfT3v6451qoC8k3YcGyiuWyWzuXaKN')

        w = WalletIntegrityHelper.create_standard_wallet(ks)
        self.assertEqual(w.txin_type, 'p2pkh')

        self.assertEqual(w.get_receiving_addresses()[0], 't1fiRjRCGirFb2PprWzYdXjukAAuYB89Gzz')
        self.assertEqual(w.get_change_addresses()[0], 't1SVeFNqPq3SzuuzWmbJjj6TX9W8kv7eWJL')

    @mock.patch.object(storage.WalletStorage, '_write')
    def test_electrum_multisig_seed_standard(self, mock_write):
        seed_words = 'blast uniform dragon fiscal ensure vast young utility dinosaur abandon rookie sure'
        self.assertEqual(bitcoin.seed_type(seed_words), 'standard')

        ks1 = keystore.from_seed(seed_words, '', True)
        WalletIntegrityHelper.check_seeded_keystore_sanity(self, ks1)
        self.assertTrue(isinstance(ks1, keystore.BIP32_KeyStore))
        self.assertEqual(ks1.xprv, 'xprv9s21ZrQH143K2qPRVQ1Z66ZqoNSWoyxWdBXKivnt1TCaAoe7Pa74eYxWRtpSnYrZsvoBcxJqM6H2sGrzkQDPcHKUwztcwSpkTYpAz5y3LJh')
        self.assertEqual(ks1.xpub, 'xpub661MyMwAqRbcFKTtbRYZTEWaMQH1DSgMzQSvXKCVZnjZ3byFw7RKCMGzH9G2U7MTTxYuaEhL3suS4HFGHb66QbiDaHPgCZoGNx2678FKe3X')

        # electrum seed: ghost into match ivory badge robot record tackle radar elbow traffic loud
        ks2 = keystore.from_xpub('xpub661MyMwAqRbcGfCPEkkyo5WmcrhTq8mi3xuBS7VEZ3LYvsgY1cCFDbenT33bdD12axvrmXhuX3xkAbKci3yZY9ZEk8vhLic7KNhLjqdh5ec')
        WalletIntegrityHelper.check_xpub_keystore_sanity(self, ks2)
        self.assertTrue(isinstance(ks2, keystore.BIP32_KeyStore))

        w = WalletIntegrityHelper.create_multisig_wallet(ks1, ks2)
        self.assertEqual(w.txin_type, 'p2sh')

        self.assertEqual(w.get_receiving_addresses()[0], 't3eXoCQLLLZnf95PhrrQhoDTsGdR8FwLhXe')
        self.assertEqual(w.get_change_addresses()[0], 't3RoTuEy2FbMgP3urUmYTFpbajjbMpECh9S')

    @mock.patch.object(storage.WalletStorage, '_write')
    def test_bip39_multisig_seed_bip45_standard(self, mock_write):
        seed_words = 'treat dwarf wealth gasp brass outside high rent blood crowd make initial'
        self.assertEqual(keystore.bip39_is_checksum_valid(seed_words), (True, True))

        ks1 = keystore.from_bip39_seed(seed_words, '', "m/45'/0")
        self.assertTrue(isinstance(ks1, keystore.BIP32_KeyStore))
        self.assertEqual(ks1.xprv, 'xprv9w8rAFAEVWArZQjheVqb3wkb2s4LzyCz8crjnsz9Le2hXbsvp6x1vxk1aC7GinLWBGkADbBnCbU9cLe7goagdHAdDYk231FK9uWp6nbVN8a')
        self.assertEqual(ks1.xpub, 'xpub6A8CZkh8Ksj9mtpAkXNbR5hKattqQRvqVqnLbGPktyZgQQD5MeGGUm4VRUxfX8jBebX9bcwK7V234sCqboDBxcmA9qSZpy7gnmysRWGdzoz')

        # bip39 seed: tray machine cook badge night page project uncover ritual toward person enact
        # der: m/45'/0
        ks2 = keystore.from_xpub('xpub6Bco9vrgo8rNUSi8Bjomn8xLA41DwPXeuPcgJamNRhTTyGVHsp8fZXaGzp9ypHoei16J6X3pumMAP1u3Dy4jTSWjm4GZowL7Dcn9u4uZC9W')
        WalletIntegrityHelper.check_xpub_keystore_sanity(self, ks2)
        self.assertTrue(isinstance(ks2, keystore.BIP32_KeyStore))

        w = WalletIntegrityHelper.create_multisig_wallet(ks1, ks2)
        self.assertEqual(w.txin_type, 'p2sh')

        self.assertEqual(w.get_receiving_addresses()[0], 't3YmFV8iPfehb2aVAmod4bEqFVwQTGf4j1i')
        self.assertEqual(w.get_change_addresses()[0], 't3ND13q6EWVnYUme5Ko6VAYxPbP6bae2RcH')

