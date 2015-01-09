#!/usr/bin/env python
#
# Copyright 2012 Jacob Meacham (https://github.com/jacob-meacham)
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
# Code based on wolfbot.py (https://code.google.com/p/ircbot-collection/), 
# which itself is based on example bot and irc-bot class from
# Joel Rosdahl <joel@rosdahl.net>, author of included python-irclib.

import string
from ircbot import SingleServerIRCBot
import irclib
from irclib import nm_to_n, irc_lower, parse_channel_modes
from common import OutputManager
import traceback

"""Generic functionality useful for a game moderating IRC bot."""

default_port = 6697
IRC_BOLD = "\x02"
class GameBot(SingleServerIRCBot):
    GAMESTATE_NONE, GAMESTATE_STARTING, GAMESTATE_RUNNING  = range(3)
    
    def __init__(self, channel, nickname, nickpass, server, port=default_port, debug=False, moderation=True):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        
        # self.desired_nickname is the nickname we _want_. The nickname we actually
        # have at any particular time is c.get_nickname().
        self.desired_nickname = nickname
        self.nickpass = nickpass
        self.debug = debug
        self.members_in_room = []
        self.moderation = moderation

        self.queue = OutputManager(self.connection)
        self.queue.start()
        try:
            self.start()
        except KeyboardInterrupt:
            self.connection.quit("Ctrl-C at console")
            print "Quit IRC."
        except Exception, e:
            self.connection.quit("%s: %s" % (e.__class__.__name__, e.args))
            raise
  
    ''' section: IRC functions '''
    _uninteresting_events = {
        'all_raw_messages': None,
        'yourhost': None,
        'created': None,
        'myinfo': None,
        'featurelist': None,
        'luserclient': None,
        'luserop': None,
        'luserchannels': None,
        'luserme': None,
        'n_local': None,
        'n_global': None,
        'luserconns': None,
        'motdstart': None,
        'motd': None,
        'endofmotd': None,
        'topic': None,
        'topicinfo': None,
        'ping': None,
        }
    
    def _dispatcher(self, c, e):
        try:
            if self.debug:
                eventtype = e.eventtype()
                if eventtype not in self._uninteresting_events:
                    source = e.source()
                    if source is not None:
                        source = nm_to_n(source)
                    else:
                        source = ''
                    print "E: %s (%s->%s) %s" % (eventtype, source, e.target(),
                        e.arguments())
            SingleServerIRCBot._dispatcher(self, c, e)
        except:
            self.say_public(_('Oh no, someone made a boo boo!'))
            traceback.print_exc()
  
    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")
  
    def on_join(self, c, e):
        nick = nm_to_n(e.source())
        self.members_in_room.append(nick)
        if nick == c.get_nickname():
            self.connection.mode(self.channel, '')
  
    def on_channelmodeis(self, c, e):
        c._handle_event(
            irclib.Event("mode", e.source(), e.arguments()[0], [e.arguments()[1]]))
        self.fix_modes()
  
    def on_mode(self, c, e):
        if e.target() == self.channel:
            try:
                if parse_channel_modes(e.arguments()[0]) == ['+','o',c.get_nickname()]:
                    self.fix_modes()
            except IndexError:
                pass
        
    def on_quit(self, c, e):
        source = nm_to_n(e.source())
        self._removeUser(source)
        if source in self.members_in_room:
            self.members_in_room.remove(source)
        if source == self.desired_nickname:
            # Our desired nick just quit - take the nick back
            c.nick(self.desired_nickname)
            self.members_in_room.append(source)
  
    def on_nick(self, c, e):
        self._renameUser(nm_to_n(e.source()), e.target())

    def _renameUser(self, old, new):
        self.members_in_room.append(new)
        self.members_in_room.remove(old)
  
    def _removeUser(self, nick):
        pass
        
    def on_namreply(self, c, e):
        for nick in e.arguments()[2].split():
            if nick[0] == "@":
                nick = nick[1:]
            elif nick[0] == "+":
                nick = nick[1:]
            self.members_in_room.append(nick)
  
    def on_welcome(self, c, e):
        c.join(self.channel)
        if c.get_nickname() != self.desired_nickname:
            # Reclaim our desired nickname
            c.privmsg('nickserv', 'ghost %s %s' % (self.desired_nickname, self.nickpass))
  
    def fix_modes(self):
        chobj = self.channels[self.channel]
        is_moderated = chobj.is_moderated()
        should_be_moderated = self.moderation
        if is_moderated and not should_be_moderated:
            self.connection.mode(self.channel, '-m')
        elif not is_moderated and should_be_moderated:
            self.connection.mode(self.channel, '+m')
  
    def multimode(self, mode, nicks):
        max_batch = 4 # FIXME: Get this from features message
        assert len(mode) == 2
        assert mode[0] in ('-', '+')
        while nicks:
            batch_len = len(nicks)
            if batch_len > max_batch:
                batch_len = max_batch
            tokens = [mode[0] + (mode[1]*batch_len)]
            while batch_len:
                tokens.append(nicks.pop(0))
                batch_len -= 1
            self.connection.mode(self.channel, ' '.join(tokens))
  
    def on_privnotice(self, c, e):
        source = e.source()
        if source and irc_lower(nm_to_n(source)) == 'nickserv':
            if e.arguments()[0].find('IDENTIFY') >= 0:
                # Received request to identify
                if self.nickpass and self.desired_nickname == c.get_nickname():
                    self.queue.send('identify %s' % self.nickpass, 'nickserv')
  
    def check_game_control(self, e):
        "Implement a timeout for game controller."
        pass
  
    def on_privmsg(self, c, e):
        self.check_game_control(e)
        self.do_command(e, e.arguments()[0])
  
    def on_part(self, c, e):
        source = nm_to_n(e.source())
        self._removeUser(source)
        if source in self.members_in_room:
            self.members_in_room.remove(source)
  
    def on_kick(self, c, e):
        self._removeUser(nm_to_n(e.arguments()[0]))
  
    def on_pubmsg(self, c, e):
        self.check_game_control(e)
        s = e.arguments()[0]
        a = string.split(s, ":", 1)
        if len(a) > 1 and irc_lower(a[0]) == irc_lower(c.get_nickname()):
            self.do_command(e, string.strip(a[1]))
        if s[0]=='!' and (len(s) > 1) and s[1]!='!':
            self.do_command(e, string.strip(s[1:]))
  
    def say_public(self, text):
        "Print TEXT into public channel, for all to see."
        self.queue.send(IRC_BOLD+text, self.channel)
  
    def say_private(self, nick, text):
        "Send private message of TEXT to NICK."
        self.queue.send(IRC_BOLD+text,nick)
  
    def reply(self, e, text):
        "Send TEXT to public channel or as private msg, in reply to event E."
        if e.eventtype() == "pubmsg":
            self.say_public("%s: %s" % (nm_to_n(e.source()), text))
        else:
            self.say_private(nm_to_n(e.source()), text)
            
    def match_name(self, nick):
        """Match NICK to a username in users(), insensitively.  Return
        matching nick, or None if no match."""
    
        chname, chobj = self.channels.items()[0]
        users = chobj.users()
        if self._nickname in users:
            users.remove(self._nickname)
    
        for user in users:
            if user.upper() == nick.upper():
                return user
        return None