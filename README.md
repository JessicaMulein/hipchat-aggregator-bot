hipchat-aggregator-bot
======================
The HipChat Aggregator Bot will listen to a set of channels and aggregate all of the chatter
into one designated channel and color code them for you. The idea is to only need to watch
once place.

You can define any number of aggregation groups and they can have overlapping channel lists.

By default, if the destination channel doesn't exist, it is created as private, but you can
release it or invite people to it using the normal HipChat client.

The HypChat API client (using v2 API) is used to translate HipChat room names into XMPP jids
and to post the notifications, and SleekXMPP is used to listen on the defined channels (the
XMPP connection is essentially read-only).

You'll need an API token from HipChat as well as your password to facilitate both of these
mechanisms.

All messages will show up as the user whose credentials are given. At the moment, it assumes
that the OAuth user and the XMPP User are one and the same, but this chould be changed.

Author(s) take(s) no responsibility for the secure transit of your credentials as passed by the
underlying libraries. Author(s) can only guarantee This code uses the underlying libraries
without modification or override.

Another note: Currently, messages are being posted as notifications in HTML format which causes
@Mentions to be ignored as well as auto-linking and [show more] being disabled. In my opinion,
this is a good thing since this is intended to be an overview, but the behavior can be changed
by changing it to 'text' instead.

To-Do
===========
* Refactor aggregator/\_\_init\_\_.py into separate class files
* Possibly switch from .ini to plain .py file for config
* Add documentation
* Investigate determining original message being HTML or not and htmlencoding <, >, etc on text messages.
* Add more options to aggregated rooms such as moving the color to the definition, and setting options for the notify property.
