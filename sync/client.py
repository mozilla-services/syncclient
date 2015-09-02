from hashlib import sha256
from binascii import hexlify
import urlparse

import requests
from requests_hawk import HawkAuth
from fxa.core import Client as FxAClient

# This is a proof of concept, in python, to get some data of some collections.
# The data stays encrypted and because we don't have the keys to decrypt it
# it just stays like that for now. The goal is simply to prove that it's
# possible to get the data out of the API"""

TOKENSERVER_URL = "https://token.services.mozilla.com/"
FXA_SERVER_URL = "https://api.accounts.firefox.com"


def get_browserid_assertion(login, password, fxa_server_url=FXA_SERVER_URL,
                            tokenserver_url=TOKENSERVER_URL):
    """Trade a user and password for a BrowserID assertion and the client
    state.
    """
    client = FxAClient(server_url=fxa_server_url)
    session = client.login(login, password, keys=True)
    bid_assertion = session.get_identity_assertion(tokenserver_url)
    _, keyB = session.fetch_keys()
    return bid_assertion, hexlify(sha256(keyB).digest()[0:16])


class SyncClient(object):
    """Client for the Firefox Sync server.
    """

    def __init__(self, bid_assertion, client_state,
                 tokenserver_url=TOKENSERVER_URL,
                 fxa_server_url=FXA_SERVER_URL):
        self._authenticate(bid_assertion, client_state, tokenserver_url)

    def _request(self, method, url, *args, **kwargs):
        """Utility to request an endpoint with the correct authentication
        setup, raises on errors and returns the JSON.
        """
        url = urlparse.urljoin(self.api_endpoint, url)
        self.raw_resp = requests.request(method, url,
                                         auth=self.auth, *args, **kwargs)
        self.raw_resp.raise_for_status()
        return self.raw_resp.json()

    def _authenticate(self, bid_assertion, client_state, tokenserver_url):
        """Asks for new temporary token given a BrowserID assertion"""
        headers = {
            'Authorization': 'BrowserID %s' % bid_assertion.encode(),
            'X-Client-State': client_state
        }
        raw_resp = requests.get(tokenserver_url + '/1.0/sync/1.5',
                                headers=headers)
        raw_resp.raise_for_status()
        resp = raw_resp.json()

        self.auth = HawkAuth(credentials={
            'algorithm': resp['hashalg'],
            'id': resp['id'],
            'key': resp['key']
        })
        self.user_id = resp['uid']
        self.api_endpoint = resp['api_endpoint']

    def info_collections(self, if_modified_since=None,
                         if_unmodified_since=None):
        """
        Returns an object mapping collection names associated with the account
        to the last-modified time for each collection.

        The server may allow requests to this endpoint to be authenticated
        with an expired token, so that clients can check for server-side
        changes before fetching an updated token from the Token Server.
        """
        return self._request('get', '/info/collections')

    def info_quota(self):
        """
        Returns a two-item list giving the user's current usage and quota
        (in KB). The second item will be null if the server does not enforce
        quotas.

        Note that usage numbers may be approximate.
        """
        return self._request('get', '/info/quota')

    def get_collection_usage(self):
        """
        Returns an object mapping collection names associated with the account
        to the data volume used for each collection (in KB).

        Note that these results may be very expensive as it calculates more
        detailed and accurate usage information than the info_quota method.
        """
        return self._request('get', '/info/collection_usage')

    def get_collection_counts(self):
        """
        Returns an object mapping collection names associated with the
        account to the total number of items in each collection.
        """
        return self._request('get', '/info/collection_counts')

    def delete_all_records(self):
        """Deletes all records for the user."""
        return self._request('delete', '/')

    def get_records(self, collection, full=True, ids=None, newer=None,
                    limit=None, offset=None, sort=None, if_modified_since=None,
                    if_unmodified_since=None):
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
        params = {}
        if full:
            params['full'] = True
        if ids is not None:
            params['ids'] = ','.join(ids)
        if newer is not None:
            params['newer'] = newer
        if limit is not None:
            params['limit'] = limit
        if offset is not None:
            params['offset'] = offset
        if sort is not None and sort in ('newest', 'index'):
            params['sort'] = sort

        return self._request('get', '/storage/%s' % collection.lower(),
                             params=params)

    def get_record(self, collection, record_id):
        """Returns the BSO in the collection corresponding to the requested id.
        """
        return self._request('get', '/storage/%s/%s' % (collection.lower(),
                                                        record_id))

    def delete_record(self, collection, record_id):
        """Deletes the BSO at the given location.
        """
        return self._request('delete', '/storage/%s/%s' % (collection.lower(),
                                                           record_id))

    def put_record(self, collection, record, if_unmodified_since=None):
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

        :param if_unmodified_since:
            Avoid overwriting the data if it has been changed since the client
            fetched it.

        Successful responses will return the new last-modified time for the
        collection.

        Note that the server may impose a limit on the amount of data
        submitted for storage in a single BSO.
        """
        record = record.copy()
        record_id = record.pop('id')
        return self._request('put', '/storage/%s/%s' % (
            collection.lower(), record_id), json=record)

    def post_records(self, collection, records):
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
