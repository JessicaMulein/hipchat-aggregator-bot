import hypchat
import sleekxmpp
import json
import md5
import dateutil
from collections import deque
from datetime import datetime, timedelta
from ConfigParser import ConfigParser


class HipchatAggregator:
    hipchat = None
    config = None
    session = None
    me = None
    rooms = {}
    room_map = {}

    def __init__(self, config_file='config.ini'):
        parser = ConfigParser()
        parser.read(config_file)
        self.config = {}
        for section in parser.sections():
            self.config[section] = {}
            for key, val in parser.items(section):
                if section == "Aggregations":
                    try:
                        val = json.loads(val)
                    except:
                        raise Exception(
                            "Could not parse aggregation {}:\n{}".format(
                                key,
                                val
                            )
                        )

                self.config[section][key] = val

        if not 'Authentication' in self.config:
            raise Exception("Configuration missing Authentication section")

        elif not 'auth_token' in self.config['Authentication']:
            raise Exception("Authentication section missing auth_token")

        elif len(str(self.config['Authentication']['auth_token'])) < 30:
            raise Exception("Invalid auth_token")

        self.hipchat = hypchat.HypChat(
            self.config['Authentication']['auth_token']
        )
        self.get_self()
        self.make_rooms()

    def get_self(self):
        try:
            resp = self.hipchat._requests.get(
                'https://api.hipchat.com/v2/oauth/token/{}'.format(
                    self.config['Authentication']['auth_token']
                )
            )
            self.session = json.loads(resp.content)
            self.me = self.hipchat.get_user(self.session['owner']['id'])
        except:
            self.session = False
            self.me = False
            raise Exception("Unable to fetch own information")

    def send_message(self, hc_room, message, background='yellow', message_type='html'):
        return self.hipchat._requests.post(
            'https://api.hipchat.com/v2/room/{}/notification'.format(
                hc_room['id']
            ),
            {
                'color': background,
                'message': message,
                'notify': False,
                'message_format': message_type
            }
        )

    def get_room(self, room):
        retval = False
        try:
            retval = self.hipchat.get_room(room)

        except hypchat.requests.HttpNotFound:
            retval = None

        except:
            raise

        return retval

    def make_room(self, room):
        return self.hipchat.create_room(
            room,
            owner=self.me,
            privacy='private',
            guest_access=False
        )

    def is_owner(self, hc_room):
        return hc_room['owner']['id'] == self.me['id']

    def make_rooms(self):
        for room, data in self.config['Aggregations'].iteritems():
            print "Aggregating {}".format(room)
            hc_room = self.get_room(room)
            if hc_room is None:
                print "Creating room"
                hc_room = self.make_room(room)
            elif hc_room and not self.is_owner(hc_room):
                print "Room already exists, not owner: SKIPPING"
                continue
            else:
                print "Room already exists"

            room_jid = hc_room['xmpp_jid']
            ag_rooms = []
            for ag_room in data['rooms']:
                hc_ag_room = self.hipchat.get_room(ag_room)

                ag_rooms.append(hc_ag_room)

                ag_room_jid = unicode(hc_ag_room['xmpp_jid'])
                if not ag_room_jid in self.room_map:
                    self.room_map[ag_room_jid] = []

                if not room_jid in self.room_map[ag_room_jid]:
                    self.room_map[ag_room_jid].append(
                        room_jid
                    )
                    self.rooms[ag_room_jid] = {
                        'name': hc_ag_room['name'],
                        'hc_room': hc_ag_room
                    }

            self.rooms[room_jid] = {
                'name': hc_room['name'],
                'hc_room': hc_room,
                'ag_rooms': ag_rooms
            }

    def get_color(self, room_jid):
        if room_jid not in self.rooms:
            return 'yellow'
        elif 'Colorization' not in self.config:
            return 'yellow'

        room_name = self.rooms[room_jid]['hc_room']['name']

        if room_name.lower() not in self.config['Colorization']:
            return 'yellow'

        return self.config['Colorization'][room_name.lower()]


class HipchatAggregatorBot(sleekxmpp.ClientXMPP):
    aggregator = None
    config = None
    signon = None
    replay_queue_size = None
    seen_messages = None

    def __init__(self, config_file='config.ini'):
        self.signon = datetime.now(dateutil.tz.tzutc())
        self.aggregator = HipchatAggregator(
            config_file=config_file
        )

        sleekxmpp.ClientXMPP.__init__(
            self,
            self.aggregator.me['xmpp_jid'],
            self.aggregator.config['Authentication']['xmpp_password']
        )
        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("groupchat_message", self.groupchat_message)

        self.replay_queue_size = int(
            self.aggregator.config['Buffer']['replay_queue_size']
        )
        self.replay_cutoff = int(
            self.aggregator.config['Buffer']['replay_cutoff']
        )
        self.seen_messages = deque(maxlen=self.replay_queue_size)

    def session_start(self, event):
        print "Connected to HipChat"
        self.get_roster()
        self.send_presence()

        self.register_plugin('xep_0045')
        for room, ag_room in self.aggregator.room_map.iteritems():
            print "Joining {}".format(room)

            self.plugin['xep_0045'].joinMUC(
                room,
                self.aggregator.me['name'],
                wait=True
            )

    def parse_delay(self, msg):
        for ele in msg.get_payload():
            if 'stamp' in ele.attrib.keys():
                stamp = ele.attrib.get('stamp')
                return dateutil.parser.parse(stamp).replace(
                    tzinfo=dateutil.tz.tzutc()
                )
        return None

    def filter_replay(self, msg):
        m = md5.new()
        m.update(msg['from'].bare)
        m.update(chr(0))
        m.update(str(msg['mucnick']))
        m.update(chr(0))
        m.update(str(msg['body']))
        m.update(chr(0))
        msg_digest = m.hexdigest()
        if msg_digest in self.seen_messages:
            return True
        else:
            self.seen_messages.append(msg_digest)
        return False

    def groupchat_message(self, msg):
        delay_stamp = self.parse_delay(msg)

        if delay_stamp is not None and delay_stamp < self.signon:
            return

        elif self.filter_replay(msg):
            return

        source_room_jid = msg['from'].bare
        if source_room_jid not in self.aggregator.room_map:
            print "Ignoring message from {}".format(
                msg['from']
            )
            return
        source_room = self.aggregator.rooms[source_room_jid]
        source_room_name = source_room['name']

        # send to requested aggregation rooms
        for dest_room_jid in self.aggregator.room_map[source_room_jid]:
            body = msg['body']
            if msg['mucnick'] != 'JIRA':
                # special handling for jira
                # don't translate JIRA newlines
                body = body.replace("\n", "<br />")

            html = '[{}] &lt;{}&gt; {}'.format(
                source_room_name,
                msg['mucnick'],
                body
            )

            color = self.aggregator.get_color(source_room_jid)

            self.aggregator.send_message(
                self.aggregator.rooms[dest_room_jid]['hc_room'],
                html,
                background=color,
                message_type='html'
            )

        # move up the ignore bar (minus specified seconds)
        self.signon = datetime.now(dateutil.tz.tzutc()) - timedelta(0,self.replay_cutoff)
