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
