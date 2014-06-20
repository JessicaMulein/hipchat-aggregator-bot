import sys
import threading
import signal
import os

from optparse import OptionParser
from aggregator import HipchatAggregatorBot


bot = None


def main():

    import logging
    logging.basicConfig()

    parser = OptionParser(usage="""usage: %prog [options]""")

    parser.add_option(
        "-c",
        "--config",
        dest="config_path",
        help="Config file path"
    )
    (options, pos_args) = parser.parse_args()

    if not options.config_path:
        print >> sys.stderr, 'ERROR: Missing config file path'
        return 1

    bot = HipchatAggregatorBot(
        config_file=os.path.abspath(options.config_path)
    )

    # Connect to the XMPP server and start processing XMPP stanzas.
    print "Connecting"
    if bot.connect():
        # If you do not have the dnspython library installed, you will need
        # to manually specify the name of the server if it does not match
        # the one in the JID. For example, to use Google Talk you would
        # need to use:
        #
        # if xmpp.connect(('talk.google.com', 5222)):
        #     ...
        bot.process(block=True)
    else:
        print("Unable to connect.")


def term(signal, frame):
    if bot:
        bot.disconnect()

if __name__ == '__main__':
    # add signal handlers
    signal.signal(signal.SIGTERM, term)
    signal.signal(signal.SIGABRT, term)
    signal.signal(signal.SIGQUIT, term)

    main_thread = threading.Thread(target=main)
    main_thread.start()
    main_thread.join()
    sys.exit(0)
