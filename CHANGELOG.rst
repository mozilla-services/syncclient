CHANGELOG
#########

This document describes changes between each past release.


0.6.0 (2015-10-12)
==================

- Circumvent a limitation present in requests-hawk 0.2.0. (#17)
- Add support for sorting by oldest when retrieving records. (#18)


0.5.0 (2015-10-01)
==================

- Handle HTTP 304 Not Modified Firefox Sync respones (#14)


0.4.0 (2015-09-23)
==================

- Forward additionnal client keyword arguments to requests (#12)


0.3.0 (2015-09-21)
==================

- Separate SyncClient and TokenserverClient code.
- Add a parameter to configure the expiration of the TokenServer returned credentials.
- Add a parameter to create a SyncClient with already fetched TokenServer credentials.
- Handle TokenServer served from a prefixed path.


0.2.0 (2015-09-03)
==================

**Bug Fixes**

- Handle API Server URL version prefix.


0.1.0 (2015-09-03)
==================

**Initial version**

- A client to synchroneously call a Firefox Sync server.
