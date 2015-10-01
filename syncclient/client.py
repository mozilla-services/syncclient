from hashlib import sha256
from binascii import hexlify
import sys

import requests
from requests_hawk import HawkAuth
from fxa.core import Client as FxAClient

# This is a proof of concept, in python, to get some data of some collections.
# The data stays encrypted and because we don't have the keys to decrypt it
# it just stays like that for now. The goal is simply to prove that it's
# possible to get the data out of the API"""

TOKENSERVER_URL = "https://token.services.mozilla.com/"
FXA_SERVER_URL = "https://api.accounts.firefox.com"


def encode_header(value):
    if isinstance(value, str):
        return value
    # Python3, it must be bytes
    if sys.version_info[0] > 2:  # pragma: no cover
        return value.decode('utf-8')
    # Python2, it must be unicode
    else:  # pragma: no cover
        return value.encode('utf-8')


def get_browserid_assertion(login, password, fxa_server_url=FXA_SERVER_URL,
                            tokenserver_url=TOKENSERVER_URL):
    """Trade a user and password for a BrowserID assertion and the client
    state.
    """
    client = FxAClient(server_url=fxa_server_url)
    session = client.login(login, password, keys=True)
    bid_assertion = session.get_identity_assertion(tokenserver_url)
    _, keyB = session.fetch_keys()
    return bid_assertion, hexlify(sha256(keyB.encode('utf-8')).digest()[0:16])


class SyncClientError(Exception):
    """An error occured in SyncClient."""


class TokenserverClient(object):
    """Client for the Firefox Sync Token Server.
    """
    def __init__(self, bid_assertion, client_state,
                 server_url=TOKENSERVER_URL):
        self.bid_assertion = bid_assertion
        self.client_state = client_state
        self.server_url = server_url

    def get_hawk_credentials(self, duration=None):
        """Asks for new temporary token given a BrowserID assertion"""
        authorization = 'BrowserID %s' % encode_header(self.bid_assertion)
        headers = {
            'Authorization': authorization,
            'X-Client-State': self.client_state
        }
        params = {}

        if duration is not None:
            params['duration'] = int(duration)

        url = self.server_url.rstrip('/') + '/1.0/sync/1.5'
        raw_resp = requests.get(url, headers=headers, params=params)
        raw_resp.raise_for_status()
        return raw_resp.json()


class SyncClient(object):
    """Client for the Firefox Sync server.
    """

    def __init__(self, bid_assertion=None, client_state=None,
                 tokenserver_url=TOKENSERVER_URL, **credentials):

        if bid_assertion is not None and client_state is not None:
            ts_client = TokenserverClient(bid_assertion, client_state,
                                          tokenserver_url)
            credentials = ts_client.get_hawk_credentials()

        else:
            # Make sure if the user wants to use credentials that they
            # give all the needed information.
            credentials_complete = set(credentials.keys()).issuperset({
                'uid', 'api_endpoint', 'hashalg', 'id', 'key'})

            if not credentials_complete:
                raise SyncClientError(
                    "You should either provide a BID assertion and a client "
                    "state or complete Sync credentials (uid, api_endpoint, "
                    "hashalg, id, key)")

        self.user_id = credentials['uid']
        self.api_endpoint = credentials['api_endpoint']
        self.auth = HawkAuth(credentials={
            'algorithm': credentials['hashalg'],
            'id': credentials['id'],
            'key': credentials['key']
        })

    def _request(self, method, url, **kwargs):
        """Utility to request an endpoint with the correct authentication
        setup, raises on errors and returns the JSON.

        """
        url = self.api_endpoint.rstrip('/') + '/' + url.lstrip('/')
        self.raw_resp = requests.request(method, url, auth=self.auth, **kwargs)
        self.raw_resp.raise_for_status()

        if self.raw_resp.status_code == 304:
            http_error_msg = '%s Client Error: %s for url: %s' % (
                self.raw_resp.status_code,
                self.raw_resp.reason,
                self.raw_resp.url)
            raise requests.exceptions.HTTPError(http_error_msg,
                                                response=self.raw_resp)
        return self.raw_resp.json()

    def info_collections(self, **kwargs):
        """
        Returns an object mapping collection names associated with the account
        to the last-modified time for each collection.

        The server may allow requests to this endpoint to be authenticated
        with an expired token, so that clients can check for server-side
        changes before fetching an updated token from the Token Server.
        """
        return self._request('get', '/info/collections', **kwargs)

    def info_quota(self, **kwargs):
        """
        Returns a two-item list giving the user's current usage and quota
        (in KB). The second item will be null if the server does not enforce
        quotas.

        Note that usage numbers may be approximate.
        """
        return self._request('get', '/info/quota', **kwargs)

    def get_collection_usage(self, **kwargs):
        """
        Returns an object mapping collection names associated with the account
        to the data volume used for each collection (in KB).

        Note that these results may be very expensive as it calculates more
        detailed and accurate usage information than the info_quota method.
        """
        return self._request('get', '/info/collection_usage', **kwargs)

    def get_collection_counts(self, **kwargs):
        """
        Returns an object mapping collection names associated with the
        account to the total number of items in each collection.
        """
        return self._request('get', '/info/collection_counts', **kwargs)

    def delete_all_records(self, **kwargs):
        """Deletes all records for the user."""
        return self._request('delete', '/', **kwargs)

    def get_records(self, collection, full=True, ids=None, newer=None,
                    limit=None, offset=None, sort=None, **kwargs):
        """
        Returns a list of the BSOs contained in a collection. For example:

        >>> ["GXS58IDC_12", "GXS58IDC_13", "GXS58IDC_15"]

        By default only the BSO ids are returned, but full objects can be
        requested using the full parameter. If the collection does not exist,
        an empty list is returned.

        :param ids:
            a comma-separated list of ids. Only objects whose id is in
            this list will be returned. A maximum of 100 ids may be provided.

        :param newer:
            a timestamp. Only objects whose last-modified time is strictly
            greater than this value will be returned.

        :param full:
            any value. If provided then the response will be a list of full
            BSO objects rather than a list of ids.

        :param limit:
            a positive integer. At most that many objects will be returned.
            If more than that many objects matched the query,
            an X-Weave-Next-Offset header will be returned.

        :param offset:
            a string, as returned in the X-Weave-Next-Offset header of a
            previous request using the limit parameter.

        :param sort:
            sorts the output:
            "newest" - orders by last-modified time, largest first
            "index" - orders by the sortindex, highest weight first
        """
        params = kwargs.pop('params', {})
        if full:
            params['full'] = True
        if ids is not None:
            params['ids'] = ','.join(map(str, ids))
        if newer is not None:
            params['newer'] = newer
        if limit is not None:
            params['limit'] = limit
        if offset is not None:
            params['offset'] = offset
        if sort is not None and sort in ('newest', 'index'):
            params['sort'] = sort

        return self._request('get', '/storage/%s' % collection.lower(),
                             params=params, **kwargs)

    def get_record(self, collection, record_id, **kwargs):
        """Returns the BSO in the collection corresponding to the requested id.
        """
        return self._request('get', '/storage/%s/%s' % (collection.lower(),
                                                        record_id), **kwargs)

    def delete_record(self, collection, record_id, **kwargs):
        """Deletes the BSO at the given location.
        """
        return self._request('delete', '/storage/%s/%s' % (
            collection.lower(), record_id), **kwargs)

    def put_record(self, collection, record, **kwargs):
        """
        Creates or updates a specific BSO within a collection.
        The passed record must be a python object containing new data for the
        BSO.

        If the target BSO already exists then it will be updated with the
        data from the request body. Fields that are not provided will not be
        overwritten, so it is possible to e.g. update the ttl field of a
        BSO without re-submitting its payload. Fields that are explicitly set
        to null in the request body will be set to their default value by the
        server.

        If the target BSO does not exist, then fields that are not provided in
        the python object will be set to their default value by the server.

        Successful responses will return the new last-modified time for the
        collection.

        Note that the server may impose a limit on the amount of data
        submitted for storage in a single BSO.
        """
        record = record.copy()
        record_id = record.pop('id')
        return self._request('put', '/storage/%s/%s' % (
            collection.lower(), record_id), json=record, **kwargs)

    def post_records(self, collection, records, **kwargs):
        """
        Takes a list of BSOs in the request body and iterates over them,
        effectively doing a series of individual PUTs with the same timestamp.

        Each BSO record must include an "id" field, and the corresponding BSO
        will be created or updated according to the semantics of a PUT request
        targeting that specific record.

        In particular, this means that fields not provided will not be
        overwritten on BSOs that already exist.

        Successful responses will contain a JSON object with details of
        success or failure for each BSO. It will have the following keys:

            modified: the new last-modified time for the updated items.
            success: a (possibly empty) list of ids of BSOs that were
                     successfully stored.
            failed: a (possibly empty) object whose keys are the ids of BSOs
                    that were not stored successfully, and whose values are
                    lists of strings describing possible reasons for the
                    failure.

        For example:

        {
         "modified": 1233702554.25,
         "success": ["GXS58IDC_12", "GXS58IDC_13", "GXS58IDC_15",
                     "GXS58IDC_16", "GXS58IDC_18", "GXS58IDC_19"],
         "failed": {"GXS58IDC_11": ["invalid ttl"],
                    "GXS58IDC_14": ["invalid sortindex"]}
        }

        Posted BSOs whose ids do not appear in either "success" or "failed"
        should be treated as having failed for an unspecified reason.

        Note that the server may impose a limit on the total amount of data
        included in the request, and/or may decline to process more than a
        certain number of BSOs in a single request. The default limit on the
        number of BSOs per request is 100.
        """
        pass
