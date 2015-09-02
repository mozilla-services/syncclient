from .support import unittest
from sync.client import SyncClient

import mock


class ClientInstantiationTest(unittest.TestCase):
    pass


class ClientRequestIssuanceTest(unittest.TestCase):
    pass


class ClientAuthenticationTest(unittest.TestCase):
    pass


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
            'delete', '')

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
