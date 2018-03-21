import unittest
from lib.util import format_satoshis, parse_URI

class TestUtil(unittest.TestCase):

    def test_format_satoshis(self):
        result = format_satoshis(1234)
        expected = "0.00001234"
        self.assertEqual(expected, result)

    def test_format_satoshis_diff_positive(self):
        result = format_satoshis(1234, is_diff=True)
        expected = "+0.00001234"
        self.assertEqual(expected, result)

    def test_format_satoshis_diff_negative(self):
        result = format_satoshis(-1234, is_diff=True)
        expected = "-0.00001234"
        self.assertEqual(expected, result)

    def _do_test_parse_URI(self, uri, expected):
        result = parse_URI(uri)
        self.assertEqual(expected, result)

    def test_parse_URI_address(self):
        self._do_test_parse_URI('zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S'})

    def test_parse_URI_only_address(self):
        self._do_test_parse_URI('t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S'})


    def test_parse_URI_address_label(self):
        self._do_test_parse_URI('zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S?label=electrum%20test',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S', 'label': 'electrum test'})

    def test_parse_URI_address_message(self):
        self._do_test_parse_URI('zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S?message=electrum%20test',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S', 'message': 'electrum test', 'memo': 'electrum test'})

    def test_parse_URI_address_amount(self):
        self._do_test_parse_URI('zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S?amount=0.0003',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S', 'amount': 30000})

    def test_parse_URI_address_request_url(self):
        self._do_test_parse_URI('zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S?r=http://domain.tld/page?h%3D2a8628fc2fbe',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S', 'r': 'http://domain.tld/page?h=2a8628fc2fbe'})

    def test_parse_URI_ignore_args(self):
        self._do_test_parse_URI('zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S?test=test',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S', 'test': 'test'})

    def test_parse_URI_multiple_args(self):
        self._do_test_parse_URI('zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S?amount=0.00004&label=electrum-test&message=electrum%20test&test=none&r=http://domain.tld/page',
                                {'address': 't1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S', 'amount': 4000, 'label': 'electrum-test', 'message': u'electrum test', 'memo': u'electrum test', 'r': 'http://domain.tld/page', 'test': 'none'})

    def test_parse_URI_no_address_request_url(self):
        self._do_test_parse_URI('zcash:?r=http://domain.tld/page?h%3D2a8628fc2fbe',
                                {'r': 'http://domain.tld/page?h=2a8628fc2fbe'})

    def test_parse_URI_invalid_address(self):
        self.assertRaises(BaseException, parse_URI, 'zcash:invalidaddress')

    def test_parse_URI_invalid(self):
        self.assertRaises(BaseException, parse_URI, 'notzcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S')

    def test_parse_URI_parameter_polution(self):
        self.assertRaises(Exception, parse_URI, 'zcash:t1NdvKvSnnBoJ7D9nfJSX5kK7GEGNs1bY4S?amount=0.0003&label=test&amount=30.0')

