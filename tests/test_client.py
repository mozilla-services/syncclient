# -*- coding: utf-8 -*-
import mock
from hashlib import sha256

from sync.client import SyncClient, get_browserid_assertion, encode_header
from .support import unittest, patch


class ClientRequestIssuanceTest(unittest.TestCase):
    def setUp(self):
        super(ClientRequestIssuanceTest, self).setUp()
        # Mock the _authenticate method in order to avoid issuance of
        # requests when we start the client.
        patched = patch(self, 'sync.client.requests',
                        'sync.client.SyncClient._authenticate')

        self.requests = patched[0].request

    def _get_client(self, api_endpoint='http://example.org/'):
        client = SyncClient("bid_assertion", "client_state")
        client.api_endpoint = api_endpoint
        client.auth = mock.sentinel.auth
        return client

    def test_client_add_serverurl_to_requests(self):
        client = self._get_client()
        client._request('get', '/test')

        self.requests.assert_called_with(
            'get', 'http://example.org/test',
            auth=client.auth)

    def test_request_raise_on_error(self):
        # Patch requests to raise an exception.
        resp = mock.MagicMock()
        resp.raise_for_status.side_effect = Exception
        self.requests.return_value = resp

        client = self._get_client()
        self.assertRaises(Exception, client._request, 'get', '/')


class ClientAuthenticationTest(unittest.TestCase):
    def setUp(self):
        super(ClientAuthenticationTest, self).setUp()
        patched = patch(self, 'sync.client.requests',
                        'sync.client.HawkAuth')
        self.requests = patched[0]
        self.hawk_auth = patched[1]

    def test_authenticate_requests_the_tokenserver_with_proper_headers(self):
        SyncClient(u"bid_assertion", "client_state")
        self.requests.get.assert_called_with(
            'https://token.services.mozilla.com/1.0/sync/1.5',
            headers={
                'X-Client-State': 'client_state',
                'Authorization': 'BrowserID bid_assertion'
            })

    def test_error_with_tokenserver_is_raised(self):
        resp = mock.MagicMock()
        resp.raise_for_status.side_effect = Exception
        self.requests.get.return_value = resp
        self.assertRaises(Exception, SyncClient, "bid_assertion",
                          "client_state")

    def test_credentials_from_tokenserver_are_passed_to_hawkauth(self):
        resp = mock.MagicMock()
        resp.json.return_value = {
            'hashalg': mock.sentinel.hashalg,
            'id': mock.sentinel.id,
            'key': mock.sentinel.key,
            'uid': mock.sentinel.uid,
            'api_endpoint': mock.sentinel.api_endpoint
        }
        self.requests.get.return_value = resp
        client = SyncClient("bid_assertion", "client_state")

        self.hawk_auth.assert_called_with(credentials={
            'algorithm': mock.sentinel.hashalg,
            'id': mock.sentinel.id,
            'key': mock.sentinel.key
        })

        assert client.user_id == mock.sentinel.uid
        assert client.api_endpoint == mock.sentinel.api_endpoint


class BrowserIDAssertionTest(unittest.TestCase):

    @mock.patch('sync.client.FxAClient')
    @mock.patch('sync.client.hexlify')
    def test_trade_works_as_expected(self, hexlify, fxa_client):
        # mock the calls to PyFxA.
        fake_keyB = "fake key b"
        session = mock.MagicMock()
        session.fetch_keys.return_value = None, fake_keyB
        fxa_client().login.return_value = session
        get_browserid_assertion('login', 'password')

        digest = sha256(fake_keyB.encode('utf-8')).digest()[0:16]
        hexlify.return_value = mock.sentinel.hexlified
        hexlify.assert_called_with(digest)


class ClientHTTPCallsTest(unittest.TestCase):
    def setUp(self):
        super(ClientHTTPCallsTest, self).setUp()
        # Mock the _authenticate method in order to avoid issuance of
        # requests when we start the client.
        p = mock.patch('sync.client.SyncClient._authenticate')
        p.start()
        self.addCleanup(p.stop)

        self.client = SyncClient('fake-bid-assertion', 'fake-client-state')

        # Mock the request method of the client, since we'll use
        # it to make sure the correct requests are made.
        self.client._request = mock.MagicMock()

    def test_info_collection(self):
        self.client.info_collections()
        self.client._request.assert_called_with('get', '/info/collections')

    def test_info_quota(self):
        self.client.info_quota()
        self.client._request.assert_called_with('get', '/info/quota')

    def test_collection_usage(self):
        self.client.get_collection_usage()
        self.client._request.assert_called_with(
            'get',
            '/info/collection_usage')

    def test_collection_counts(self):
        self.client.get_collection_counts()
        self.client._request.assert_called_with(
            'get',
            '/info/collection_counts')

    def test_delete_all_records(self):
        self.client.delete_all_records()
        self.client._request.assert_called_with(
            'delete', '/')

    def test_get_records_sets_full_by_default(self):
        self.client.get_records('mycollection')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'full': True})

    def test_get_records_lowers_the_collection_name(self):
        self.client.get_records('myCollection')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'full': True})

    def test_get_records_handles_ids(self):
        self.client.get_records('myCollection', ids=(1, 3))
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'full': True, 'ids': '1,3'})

    def test_get_records_handles_full(self):
        self.client.get_records('mycollection', full=False)
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={})

    def test_get_records_handles_newer(self):
        self.client.get_records('mycollection', newer='newer')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'newer': 'newer', 'full': True})

    def test_get_records_handles_limit(self):
        self.client.get_records('mycollection', limit='limit')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'limit': 'limit', 'full': True})

    def test_get_records_handles_offset(self):
        self.client.get_records('mycollection', offset='offset')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'offset': 'offset', 'full': True})

    def test_get_records_handles_sort_by_newest(self):
        self.client.get_records('mycollection', sort='newest')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'sort': 'newest', 'full': True})

    def test_get_records_handles_sort_by_index(self):
        self.client.get_records('mycollection', sort='index')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'sort': 'index', 'full': True})

    def test_get_records_ignore_sort_by_invalid(self):
        self.client.get_records('mycollection', sort='invalid')
        self.client._request.assert_called_with(
            'get', '/storage/mycollection',
            params={'full': True})

    def test_get_record(self):
        self.client.get_record('myCollection', 1234)
        self.client._request.assert_called_with(
            'get', '/storage/mycollection/1234')

    def test_delete_record(self):
        self.client.delete_record('myCollection', 1234)
        self.client._request.assert_called_with(
            'delete', '/storage/mycollection/1234')

    def test_put_record(self):
        record = {'id': 1234, 'foo': 'bar'}
        self.client.put_record('myCollection', record)
        self.client._request.assert_called_with(
            'put', '/storage/mycollection/1234',
            json={'foo': 'bar'})

    def test_put_record_doesnt_modify_the_passed_object(self):
        record = {'id': 1234, 'foo': 'bar'}
        self.client.put_record('myCollection', record)
        assert 'id' in record.keys()

    def test_post_records(self):
        # For now, this does nothing.
        records = [{'id': idx, 'foo': 'foo'} for idx in range(1, 10)]
        self.client.post_records("myCollection", records)


class EncodeHeaderTest(unittest.TestCase):
    def test_encode_str_return_str(self):
        value = 'Toto'
        self.assertEqual(type(value), str)
        value = encode_header(value)
        self.assertEqual(type(value), str)

    def test_returns_a_string_if_passed_bytes(self):
        entry = 'Toto'.encode('utf-8')
        value = encode_header(entry)
        self.assertEqual(type(value), str)

    def test_returns_a_string_if_passed_unicode(self):
        entry = u'Rémy'
        value = encode_header(entry)
        self.assertEqual(type(value), str)
