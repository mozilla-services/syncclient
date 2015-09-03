import argparse
from client import SyncClient, get_browserid_assertion
from pprint import pprint


def main():
    parser = argparse.ArgumentParser(
        description="""CLI to interact with Firefox Sync""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(dest='login',
                        help='Firefox Accounts login.')
    parser.add_argument(dest='password',
                        help='Firefox Accounts password.')
    parser.add_argument(dest='action', help='The action to be executed',
                        default='info_collections', nargs='?',
                        choices=[m for m in dir(SyncClient)
                                 if not m.startswith('_')])

    args, extra = parser.parse_known_args()

    bid_assertion_args = get_browserid_assertion(args.login, args.password)
    client = SyncClient(*bid_assertion_args)
    pprint(getattr(client, args.action)(*extra))

if __name__ == '__main__':
    main()
