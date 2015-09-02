try:
    import unittest2 as unittest
except ImportError:
    import unittest  # NOQA

import mock


def patch(test_case, *to_mock):
    """Patch the given positional arguments, return the patched version.

    :param test_case:
        The test case to use, in order to unpatch at the end of the test.
    """
    patched = []
    for m in to_mock:
        p = mock.patch(m)
        patched.append(p.start())
        test_case.addCleanup(p.stop)
    return patched
