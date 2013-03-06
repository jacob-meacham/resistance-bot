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
# This is an IRC bot to moderate a game of Resistance (http://en.wikipedia.org/wiki/The_Resistance_(game))
#
# Code based on wolfbot.py (https://code.google.com/p/ircbot-collection/), 
# which itself is based on example bot and irc-bot class from
# Joel Rosdahl <joel@rosdahl.net>, author of included python-irclib.
#

"""An IRC bot to moderate a game of "Resistance".

This bot uses the SingleServerIRCBot class from
ircbot.py.  The bot enters a channel and listens for commands in
private messages and channel traffic.  Commands in channel messages
are given by prefixing the text by the bot name followed by a colon."""

import sys, string, random, time, os.path
from irclib.ircbot import SingleServerIRCBot
import irclib.irclib
from irclib.irclib import nm_to_n, nm_to_h, irc_lower, parse_channel_modes
from irclib.botcommon import OutputManager
import random
from random import choice

minUsers=4
defaultPort=6667

mission_size = [
                [2,3,2,3,3], # 5 players
                [2,3,4,3,4], # 6 players
                [2,3,3,4,4], # 7 players
                [3,4,4,5,5], # 8 players
                [3,4,4,5,6], # 9 players
                [3,4,4,5,5] # 10 players
               ]

IRC_BOLD = "\x02"
class ResistanceBot(SingleServerIRCBot):
    GAMESTATE_NONE, GAMESTATE_STARTING, GAMESTATE_RUNNING  = range(3)
    
    def __init__(self, channel, nickname, nickpass, server, port=defaultPort,
        debug=False):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        
        # self.desired_nickname is the nickname we _want_. The nickname we actually
        # have at any particular time is c.get_nickname().
        self.desired_nickname = nickname
        self.nickpass = nickpass
        self.debug = debug
        self.moderation = True

        self.members_in_room = []
        self.blind_spies = True
        self.ranked = True
        self.instawin = True
        self.game_starter = None
        self.phase = {}
        self.phase["ChooseTeam"] = self.begin_team_choice_phase
        self.phase["Vote"] = self.begin_voting_phase
        self.phase["Mission"] = self.begin_mission_phase
        self.reset_game()
        
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
  
    def on_nicknameinuse(self, c, e):
        c.nick(c.get_nickname() + "_")
  
    def _renameUser(self, old, new):
    	self.members_in_room.append(new)
    	self.members_in_room.remove(old)
    	
        if self.gamestate == self.GAMESTATE_NONE:
            # don't need to do anything.
            return
 
        if self.gamestate == self.GAMESTATE_STARTING:
            for player in (self.players):
            	if new == "overall":
            	    self.players.remove(old)
            	    self.say_public("%s disappeared in some sort of strange wormhole." % old)
	    	    self.say_public('You cannot play with that name. Please rename and join again.')
		if old in self.players:
	            self.players.append(new)
	            self.players.remove(old)
	    return
            
        for list in (self.players, self.spies, self.original_spies, self.mission_team):
            if old in list:
                list.append(new)
                list.remove(old)
        for map in (self.votes, self.mission_votes):
            if map.has_key(new):
                map[new] = map[old]
                del map[old]
        
        if getattr(self, 'leader') == old:
            setattr(self, 'leader', new)
  
    def _removeUser(self, nick):
        if self.gamestate == self.GAMESTATE_NONE:
            # don't need to do anything.
            return
        
        if nick == self.game_starter:
            self.game_starter = None
        if nick in self.players:
            self.say_public("%s disappeared in some sort of strange wormhole." % nick)
            self.players.remove(nick)
        if self.gamestate == self.GAMESTATE_STARTING:
            # No more to do
            return

        if nick in self.spies:
            self.spies.remove(nick)
            self.say_public("We've just received word that %s was an Imperial spy! They were summarily and messily executed." % nick)
            if len(self.spies) == 0:
                self.end_game(self.game_starter)
                return
        elif nick in self.players:
            self.say_public("%s's loyalty is beyond doubt now. Of course, we had to torture them to death to discover that fact..." % nick)
                  
        # TODO: Check the mission
        if nick in self.mission_team:
            self.mission_team.remove(nick)
        
        # TODO: Check the mission/votes.
        for map in (self.votes, self.mission_votes):
            if map.has_key(nick):
                del map[nick]
                
        if nick == self.leader:
            self.leader = choice(self.players)
            if self.cur_phase == "ChooseTeam":
                # Need to start team choice over.
                # This isn't quite right, since leader is now random.
                self.begin_team_choice_phase()
  
    def on_join(self, c, e):
        nick = nm_to_n(e.source())
        self.members_in_room.append(nick)
        if nick == c.get_nickname():
            chan = e.target()
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
    
        voice = []
        devoice = []
        for user in chobj.users():
            is_live = user in self.players
            is_voiced = chobj.is_voiced(user)
            if is_live and not is_voiced:
               voice.append(user)
            elif not is_live and is_voiced:
              devoice.append(user)
        
        self.multimode('+v', voice)
        self.multimode('-v', devoice)
  
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
  
    ''' section: Game Logic '''
    def reset_game(self):
        self.gamestate = self.GAMESTATE_NONE
        self.players = []
        self.votes = {}
        self.mission_votes = {}
        self.original_spies = []
        self.cur_phase = None
        
    def start_game(self):
        self.gamestate = self.GAMESTATE_RUNNING
        self.mission_team = []
        self.spies = []
        self.cur_team_size = 0
        self.spy_rounds = 0
        self.resistance_rounds = 0
        self.cur_round = 0
        self.no_vote_rounds = 0
        self.votes = {}
        
        # choose the leader and assign spies
        _players = self.players[:]

        total_spies = [2, 2, 3, 3, 3, 4]
        num_spies = 0

        idx = len(self.players) - 5
        if idx < 0:
            idx = 0

        while num_spies < total_spies[idx]:
            self.spies.append(_players.pop(random.randrange(len(_players))))
            num_spies = num_spies + 1
        
        # Save off the original spies, in case one or more of them is deleted.
        self.original_spies = self.spies
        
        self.leader = choice(self.players)
        self.fix_modes()
        
        self.say_public("A new game of Resistance has started!")

        for spy in self.spies:
          self.say_private(spy, "You're a sneaky Imperial spy.")
        for player in _players:
          self.say_private(player, "You're an upstanding member of the Resistance.")

        if not self.blind_spies:
            # inform the spies of their comrades.
            for spy in self.spies:
                other_spies = [x for x in self.spies if x != spy]
                if len(other_spies) == 1:
                    plurality = "spy is "
                else:
                    plurality = "spies are "
                self.say_private(spy, "The other " + plurality + self.build_list_string(other_spies))
        
        if self.debug:
            print "SPIES: %s" % ' '.join(self.spies)
                
        self.cur_phase = "ChooseTeam"
        self.phase[self.cur_phase]()
        
    def end_game(self, game_ender):
        if self.gamestate == self.GAMESTATE_NONE:
            self.say_public("No game is in progress.  Use 'start' to begin a game.")
        elif self.game_starter and game_ender != self.game_starter:
            self.say_public(\
                        ("Sorry, only the starter of the game (%s) may end it." %\
                        self.game_starter))
        else:
            self.say_public("The game has ended.")
            if self.gamestate == self.GAMESTATE_RUNNING:
                self.say_public("*** The spies were %s. "
                                "Everyone else was a member of the Resistance."
                                % self.build_list_string(self.original_spies))
                self.reset_game()
                self.fix_modes()
        
        
    def begin_team_choice_phase(self):
        # pick a new leader
        new_leader = self.players.index(self.leader) + 1
        if new_leader >= len(self.players):
            new_leader = 0
        
        self.leader = self.players[new_leader]
        self.mission_team = []    
        self.cur_team_size = self.calc_team_size()
        
        self.say_public("\x033" + self.leader + "\x0f\x02\x02, you're the leader now.")
        self.say_public("We've just received word " + self.mission_fiction() + " You should put together a team to take advantage of this opportunity!"\
                        "\x032 " + str(self.cur_team_size) + " \x0f\x02\x02 operatives may go on this mission.")
        
        self.say_private(self.leader, "You're now the leader, and should put together your team.")
    
    def mission_fiction(self):
        fiction = ["of an Imperial base with narcoleptic guards.",
                   "of a chance to steal the Emperor's prized " + choice(["underwear", "teddy bear", "pony", "son", "lager"]) + '.',
                   "of a nuclear power plant looking to recruit shady workers.",
                   "of a way to infiltrate a secret Imperial " + choice(["base", "mission", "karaoke party", "surprise party", "March"]) + '.',
                   "of a " + choice(["Death Star", "karaoke bar", "Hydroplant", "Core FX 9000", "tractor"]) + " which is not fully operational.",
                   "of a high ranking Imperial official who is " + choice(["lactose intolerant", "scared of heights", "balding", "Zac's brother"]) + '.'
                   ]
        return choice(fiction)
        
    def calc_team_size(self):
        # Team size changes based on round and number of players.
        idx = len(self.players) - 5
        if idx < 0:
            idx = 0

        return mission_size[idx][self.cur_round]
    
    def begin_voting_phase(self):
        msg = "As a group, we must now \x036Vote\x0f\x02\x02 on the proposed team. "\
              "The team consists of " + self.build_list_string(self.mission_team) + ". "\
              "You can either \x034accept\x0f\x02\x02 or \x034decline\x0f\x02\x02 this team. You can change your vote at any time "\
              "but once all of the votes are in, the results are final."
        self.say_public(msg)
        self.votes = {}
          
    def check_votes(self):
        if len(self.votes) == len(self.players):
            return True
        return False
    
    def tally_votes(self):        
        votes = 0
        for v in self.votes.itervalues():
            if v == True:
                votes = votes + 1
        
        if votes >= len(self.players)/2 + 1:
            return True
        return False
    
    def begin_mission_phase(self):
        self.mission_votes = {}
        
        self.say_public("The mission team consisting of " + self.build_list_string(self.mission_team) + " will now \x032commence their Mission\x0f\x02\x02")
        
        for member in self.mission_team:
            self.say_private(member, "You have been chosen to complete this daring and deadly mission!")
            if member in self.spies:
                self.say_private(member, "You may choose to either \x034finish\x0f\x02\x02 or \x034sabotage\x0f\x02\x02 this mission.")
            else:
                self.say_private(member, "You must attempt to \x034finish\x0f\x02\x02 this mission.")
            
    def check_mission(self):
        if len(self.mission_votes) >= len(self.mission_team):
            return True
        return False
                
    def mission_results(self):
        sabotages = 0
        spy_count = 0
        for v in self.mission_votes.itervalues():
            if v == False:
                sabotages = sabotages + 1
                
        if self.instawin and sabotages == 1:
	        for member in self.mission_team:
		      if member in self.spies:
		          spy_count = spy_count + 1
        
        if sabotages > 0:
            self.say_public("The mission was sabotaged by " + str(sabotages) + " operatives!")
            self.spy_rounds = self.spy_rounds + 1
        else:
            self.say_public("The mission was a success!")
            self.resistance_rounds = self.resistance_rounds + 1
        
        self.cur_round = self.cur_round + 1
        self.print_score()
        
        if self.check_game_over():
            self.end_game(self.game_starter)
     	elif spy_count > 1 and len(self.players) == 5:
     	    self.say_public("There were two sneaky spies on that mission, and only 1 sabotaged. The spies instantly win!")
            self.record_stats(True)
    	    if self.ranked:
                self.recordoverallempirewin()
                for member in self.players:
                    if member in self.spies:
                        self.recordempirewin(member)
    	            else:
                        self.recordresistanceloss(member)
    	    self.end_game(self.game_starter)
        else:
            self.cur_phase = "ChooseTeam"
            self.phase[self.cur_phase]()
    
    def check_game_over(self):
        if self.resistance_rounds >= 3:
            self.say_public('\x034The Resistance\x0f\x02\x02 has successfully \x034destroyed\x0f\x02\x02 the Empire!')
	    if self.ranked:
	        self.recordoverallresistancewin()
	        for member in self.players:
		    if member in self.spies:
		        self.recordempireloss(member)
		    else:
		        self.recordresistancewin(member)
            return True
        elif self.spy_rounds >= 3:
            self.say_public('The \x034Imperial Spies\x0f\x02\x02 have successfully \x034sabotaged\x0f\x02\x02 the Resistance!')
            if self.ranked:
                self.recordoverallempirewin()
	        for member in self.players:
	    	    if member in self.spies:
	      	    	self.recordempirewin(member)
	   	    else:
  		    	self.recordresistanceloss(member)
            return True
        return False
        
    def print_score(self):
        self.say_public("Score on Mission " + str(self.cur_round) + ":")
        self.say_public("Resistance: " + str(self.resistance_rounds) + "/3")
        self.say_public("Spies: " + str(self.spy_rounds) + "/3")

    def print_votes(self):
        voters = [key for key in self.votes.iterkeys()]
        if len(voters) == 0:
            msg = "No players have voted yet."
        else:
            msg = "The following players have voted: " \
              + self.build_list_string(voters)
            
        self.say_public(msg)
        
    def print_stats(self):
        """ Prints stats that are relevant to the current phase """
        msg = ""
        msg += "The current phase is "
        if self.cur_phase == "ChooseTeam":
            msg += "\x033Team Building"
        elif self.cur_phase == "Vote":
            msg += "\x036Voting"
        elif self.cur_phase == "Mission":
            msg += "\x032Mission Duty"
            
        self.say_public(msg)
        
        self.say_public("The current leader is \x034" + self.leader)
        self.say_public("Game order is " + ' '.join(self.players))
        self.say_public("It's been \x034 " + str(self.no_vote_rounds) + " \x0f\x02\x02since the last mission.")
        
        if len(self.mission_team) > 0:
            self.say_public("The mission team consists of " + self.build_list_string(self.mission_team))
            
        if self.cur_phase == "ChooseTeam":
            self.say_public("The team needs to have " + str(self.cur_team_size) + " members.")
        
        if self.cur_phase == "Vote":
            self.print_votes()
    
    def build_list_string(self, list):
        if len(list) == 0:
            return ""
        elif len(list) == 1:
            return str(list[0])
        
        return ', '.join(list[:-1]) + " and " + str(list[-1])
        
    def on_team_choice(self, e, member, add):
        if member not in self.players:
            self.reply(e, "You can't add someone who isn't even playing!")
            return
        
        if add:
            if member in self.mission_team:
                self.reply(e, "You can't add someone who is already in the team!")
            else:
                self.reply(e, "Added %s to the mission team" % member)
                self.mission_team.append(member)
        else:
            if member in self.mission_team:
                self.mission_team.remove(member)
                self.reply(e, "Removed %s from the mission team" % member)
            else:
                self.reply(e, "They're not on the mission team.")
                
        if len(self.mission_team) >= self.cur_team_size:
            # Finished picking the team
            self.cur_phase = "Vote"
            self.phase[self.cur_phase]()
            
    def on_vote(self, e, player, vote):
        self.votes[player] = vote            
        self.reply(e, "Your vote has been tallied.")
                
        if self.check_votes():
            t = self.tally_votes()
            for_team = [k for k,v in self.votes.iteritems() if v is True]
            against_team = [k for k,v in self.votes.iteritems() if v is False]

            self.say_public(self.build_list_string(for_team) + " voted \x033for the team\x0f\x02\x02 and")
            self.say_public(self.build_list_string(against_team) + " voted \x034against the team\x0f\x02\x02.")
            
            if t:
                self.no_vote_rounds = 0
                self.cur_phase = "Mission"
                self.say_public("Therefore, the mission team was \x033accepted!\x0f\x02\x02")
            else:
                self.no_vote_rounds = self.no_vote_rounds + 1
                if self.no_vote_rounds >= 5:
                    self.spy_rounds = 3
                    self.say_public("Unfortunately, you all spent so much time bickering, that the Empire discovered your based and destroyed you all.")
                    if self.check_game_over():
                        self.end_game(self.game_starter)
                        return

                self.cur_phase = "ChooseTeam"
                self.say_public("Therefore, the mission team was \x034not accepted!\x0f\x02\x02")
            
            self.phase[self.cur_phase]()
            
    def on_unvote(self, e, player):
        if player in self.votes.keys():
            del self.votes[player]
            self.reply(e, "Your vote has been retracted.")
        else:
            self.reply(e, "You haven't voted yet.")
    
    def on_mission(self, e, player, action):
        self.mission_votes[player] = action
        self.reply(e, "Your contribution to the mission is acknowledged.")
        
        if self.check_mission():
            self.mission_results()
            

    def handle_nonplayers(self, e):
        player = nm_to_n(e.source())
        if player not in self.players:
            self.reply(e, "Hush, you're not playing this game.")
            return False
        return True


    def recordoverallresistancewin(self):
        if not os.path.exists("overall.dat"):
            stats = open("overall.dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()

        self.say_public("New stats file created for overall.")
            
        stats = open("overall.dat", "r")
        srwins = stats.readline()
        sewins = stats.readline()
        
        irwins = int(srwins)
        iewins = int(sewins)
        
        srwins = str(irwins)
        sewins = str(iewins)
        
        irwins = irwins + 1
        srwins = str(irwins)
        stats.close()

        stats = open("overall.dat", "w")
        stats.write(srwins + "\n")
        stats.write(sewins + "\n")
        stats.close()
        self.say_public("Stats written for overall.")

    def recordoverallempirewin(self):
        if not os.path.exists("overall.dat"):
            stats = open("overall.dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
        self.say_public("New stats file created for overall.")
                
        stats = open("overall.dat", "r")
        srwins = stats.readline()
        sewins = stats.readline()
        
        irwins = int(srwins)
        iewins = int(sewins)
        
        srwins = str(irwins)
        sewins = str(iewins)
        
        iewins = iewins + 1
        sewins = str(iewins)
        stats.close()

        stats = open("overall.dat", "w")
        stats.write(srwins + "\n")
        stats.write(sewins + "\n")
        stats.close()
        self.say_public("Stats written for overall.")
        
    def recordresistancewin(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.say_public("New stats file created for " + player + ".")

        stats = open(player + ".dat", "r")
        srwins = stats.readline()
        srlosses = stats.readline()
        sewins = stats.readline()
        selosses = stats.readline()
        
        irwins = int(srwins)
        irlosses = int(srlosses)
        iewins = int(sewins)
        ielosses = int(selosses)
        
        srwins = str(irwins)
        srlosses = str(irlosses)
        sewins = str(iewins)
        selosses = str(ielosses)
        
        irwins = irwins + 1
        srwins = str(irwins)
        stats.close()

        stats = open(player + ".dat", "w")
        stats.write(srwins + "\n")
        stats.write(srlosses + "\n")
        stats.write(sewins + "\n")
        stats.write(selosses + "\n")
        stats.close()
        self.say_public("Stats written for " + player + ".")

    def recordresistanceloss(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.say_public("New stats file created for " + player + ".")

        stats = open(player + ".dat", "r")
        srwins = stats.readline()
        srlosses = stats.readline()
        sewins = stats.readline()
        selosses = stats.readline()
        
        irwins = int(srwins)
        irlosses = int(srlosses)
        iewins = int(sewins)
        ielosses = int(selosses)
        
        srwins = str(irwins)
        srlosses = str(irlosses)
        sewins = str(iewins)
        selosses = str(ielosses)
        
        irlosses = irlosses + 1
        srlosses = str(irlosses)
        stats.close()

        stats = open(player + ".dat", "w")
        stats.write(srwins + "\n")
        stats.write(srlosses + "\n")
        stats.write(sewins + "\n")
        stats.write(selosses + "\n")
        stats.close()
        self.say_public("Stats written for " + player + ".")
        
    def recordempirewin(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.say_public("New stats file created for " + player + ".")

        stats = open(player + ".dat", "r")
        srwins = stats.readline()
        srlosses = stats.readline()
        sewins = stats.readline()
        selosses = stats.readline()
        
        irwins = int(srwins)
        irlosses = int(srlosses)
        iewins = int(sewins)
        ielosses = int(selosses)

        srwins = str(irwins)
        srlosses = str(irlosses)
        sewins = str(iewins)
        selosses = str(ielosses)
        
        iewins = iewins + 1
        sewins = str(iewins)
        stats.close()

        stats = open(player + ".dat", "w")
        stats.write(srwins + "\n")
        stats.write(srlosses + "\n")
        stats.write(sewins + "\n")
        stats.write(selosses + "\n")
        stats.close()
        self.say_public("Stats written for " + player + ".")

    def recordempireloss(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.say_public("New stats file created for " + player + ".")

        stats = open(player + ".dat", "r")
        srwins = stats.readline()
        srlosses = stats.readline()
        sewins = stats.readline()
        selosses = stats.readline()
        
        irwins = int(srwins)
        irlosses = int(srlosses)
        iewins = int(sewins)
        ielosses = int(selosses)

        srwins = str(irwins)
        srlosses = str(irlosses)
        sewins = str(iewins)
        selosses = str(ielosses)
        
        ielosses = ielosses + 1
        selosses = str(ielosses)
        stats.close()

        stats = open(player + ".dat", "w")
        stats.write(srwins + "\n")
        stats.write(srlosses + "\n")
        stats.write(sewins + "\n")
        stats.write(selosses + "\n")
        stats.close()
        self.say_public("Stats written for " + player + ".")
    
    ''' section: Commands '''
    def cmd_team(self, args, e):
        if self.cur_phase != "ChooseTeam":
            self.reply(e, "Now isn't the time for choosing a mission team. We'll tell you when we've found a target.")
            return
        
        player = nm_to_n(e.source())
        if player != self.leader:
            self.reply(e, "Only the leader can decide who is on the mission team.")
            return
        
        if player not in self.players:
            self.reply(e, "Hush, you're not playing this game.")
            return
        
        try:
            if len(args) != 2:
                raise ValueError
            
            if args[0].strip() == 'add':
                add = True
            elif args[0].strip() == 'remove':
                add = False
            else:
                raise ValueError
            
            member = self.match_name(args[1].strip())
            if member is not None:
                self.on_team_choice(e, member, add)
            else:
                raise ValueError
            
        except ValueError:
            self.reply(e, "Command should be in the form of 'team [add|remove] [user]'")
    
    def cmd_unvote(self, args, e):
        if self.cur_phase != "Vote":
            self.reply(e, "No election is currently being held.")
            return
        
        if not self.handle_nonplayers(e):
            return
        
        player = nm_to_n(e.source())
        self.on_unvote(e, player)

    def cmd_say(self, args, e):
    	if len(args) == 0:
    	    return
    	sayString = ""
    	for word in args:
    	    sayString += word
    	    sayString +=" "
	self.say_public(sayString)
        
    def cmd_accept(self, args, e):
        if self.cur_phase != "Vote":
            self.reply(e, "No election is currently being held.")
            return
        
        if not self.handle_nonplayers(e):
            return
        
        player = nm_to_n(e.source())
        self.on_vote(e, player, True)
		
    def cmd_forceaccept(self, args, e):
        for nick in args:
            if self.cur_phase != "Vote":
	        self.reply(e, "No election is currently being held.")
		return
            if nick not in self.players:
                self.reply(e, "There's nobody playing by the name %s" % nick)
                return
	    if len(args) != 1:
	        self.reply(e, 'Usage: forceaccept <nick>')
	        return

	    if not self.handle_nonplayers(e):
		return

            self.reply(e, "You have forced %s to accept this vote." % nick)
	    self.on_vote(e, args[0], True)
        
    def cmd_decline(self, args, e):
        if self.cur_phase != "Vote":
            self.reply(e, "No election is currently being held.")
            return
        
        if not self.handle_nonplayers(e):
            return
        
        player = nm_to_n(e.source())
        self.on_vote(e, player, False)
        
    def cmd_forcedecline(self, args, e):
        for nick in args:
            if self.cur_phase != "Vote":
	        self.reply(e, "No election is currently being held.")
		return
            if nick not in self.players:
                self.reply(e, "There's nobody playing by the name %s" % nick)
                return
	    if len(args) != 1:
	        self.reply(e, 'Usage: forceaccept <nick>')
	        return

	    if not self.handle_nonplayers(e):
		return

	    self.reply(e, "You have forced %s to decline this vote." % nick)
	    self.on_vote(e, args[0], False)
        
    def cmd_sabotage(self, args, e):
        player = nm_to_n(e.source())
	if self.gamestate != self.GAMESTATE_RUNNING:
		self.reply(e, "You cannot sabotage before the game starts!")
		return

        if player not in self.mission_team:
            self.reply(e, "You're not on any mission team!")
            return
        
        if self.cur_phase != "Mission":
            self.reply(e, "Hold your horses, the mission hasn't started yet.")
            return
            
        if e.eventtype() == "pubmsg":
	    self.reply(e, "You cannot public finish a mission!  Send me your choice in private.")
	    return
                
        if player not in self.spies:
            self.reply(e, "You can't sabotage that.")
            return
        
        self.on_mission(e, player, False)
        
    def cmd_finish(self, args, e):
        player = nm_to_n(e.source())
	if self.gamestate != self.GAMESTATE_RUNNING:
		self.reply(e, "You cannot sabotage before the game starts!")
		return
        
        if player not in self.mission_team:
            self.reply(e, "You're not on any mission team!")
            return
        
        if self.cur_phase != "Mission":
            self.reply(e, "Hold your horses, the mission hasn't started yet.")
            return
            
        if e.eventtype() == "pubmsg":
	    self.reply(e, "You cannot public finish a mission!  Send me your choice in private.")
	    return
	    
        self.on_mission(e, player, True)
    
    def cmd_help(self, args, e):
        cmds = [i[4:] for i in dir(self) if i.startswith('cmd_')]
        self.reply(e, "Valid commands: '%s'" % "', '".join(cmds))

    def cmd_slap(self, args, e):
    	if args[0] == "all":
            slapped_players = [m for m in self.members_in_room if m != self.desired_nickname and m != nm_to_n(e.source())]
            for slapped in slapped_players:
                self.reply(e, "You slap " + member + " around a bit with a large trout.")
        else:
            self.reply(e, "You slap " + args[0] + " around a bit with a large trout.")
  
    def cmd_stats(self, args, e):
        if self.gamestate == self.GAMESTATE_RUNNING:
            self.print_stats()
        elif self.gamestate == self.GAMESTATE_STARTING:
            self.reply(e, "A new game is starting, current players are %s"
            % (self.players,))
        else:
            self.reply(e, "No game is in progress.")
  
    def cmd_status(self, args, e):
        self.cmd_stats(args, e)
        
    def cmd_score(self, args, e):
        if self.gamestate == self.GAMESTATE_RUNNING:
            self.print_score()
        else:
            self.reply(e, "No game is in progress.")

    def cmd_votes(self, args, e):
        if self.gamestate == self.GAMESTATE_RUNNING and self.cur_phase == "Vote":
            self.print_votes()
        else:
            self.reply(e, "No election is currently being held.")
  
    def cmd_start(self, args, e):
        print str(self.gamestate)
        "Initialize a resistance game."
        game_starter = nm_to_n(e.source())
	if game_starter == "overall":
	    self.reply(e, 'You cannot join with that name. Please rename and try again.')
            return
        
        chname, chobj = self.channels.items()[0]

        if self.gamestate == self.GAMESTATE_RUNNING:
            self.say_public("A game started by %s is in progress; "
            "that person must end it." % self.game_starter)
        
        elif self.gamestate == self.GAMESTATE_NONE:
            self.reset_game()
            self.gamestate = self.GAMESTATE_STARTING
            self.game_starter = game_starter
            self.game_starter_last_seen = time.time()
            self.players.append(game_starter)
            self.say_public("A new game has been started by %s; "
                "say '%s: join' to join the game."
                % (self.game_starter, self.connection.get_nickname()))
            self.say_public("%s: Say '%s: start' when everyone has joined."
                % (self.game_starter, self.connection.get_nickname()))
            self.fix_modes()

        elif self.gamestate == self.GAMESTATE_STARTING:
            if self.game_starter and game_starter != self.game_starter:
                self.say_public("Game startup was begun by %s; "
                "that person must finish starting it." % self.game_starter)
                return
      
            self.game_starter = game_starter
            self.game_starter_last_seen = time.time()

            minUsers = 5
            if len(self.players) < minUsers:
                self.say_public("Sorry, to start a game, there must be " + \
                                "at least active %d players."%(minUsers))
            else:
                self.start_game()

    def cmd_join(self, args, e):
        player = nm_to_n(e.source())
	if player == "overall":
	    self.reply(e, 'You cannot join with that name. Please rename and try again.')
            return
            
        if self.gamestate == self.GAMESTATE_NONE:
            # Start the game
            self.cmd_start(args, e)
            return
      
        if self.gamestate == self.GAMESTATE_RUNNING:
            self.reply(e, 'Game is in progress; please wait for the next game.')
            return
      
        player = nm_to_n(e.source())
        if player in self.players:
            self.reply(e, 'You are already in the game.')
        elif len(self.players) >= 10:
            self.reply(e, 'Only 10 players are allowed to play. You\'ll have to wait')
        else:
            self.players.append(player)
            self.reply(e, 'You are now in the game.')
            self.fix_modes()
  
    def cmd_bring(self, args, e):        
        if self.gamestate == self.GAMESTATE_RUNNING:
            self.reply(e, 'You can\'t bring someone into a game that\'s in progress!')
            return
      
        player = nm_to_n(e.source())
        if player not in self.players:
            self.reply(e, 'You can\'t bring someone into a game that you haven\'t even joined!')
            return
        
        if player == "overall":
            self.reply(e, 'You cannot bring overall into the game. Stop trying to break resbot!')
            return
        
        # Get the player that they're trying to bring:
        if len(args) != 1:
            self.reply(e, 'Usage: bring <nick>')
            return
        
        if args[0] in self.players:
            self.reply(e, 'That player is are already in the game.')
        elif len(self.players) >= 10:
            self.reply(e, 'Only 10 players are allowed to play. You\'ll have to wait')
        elif args[0] not in self.members_in_room:
            self.reply(e, 'You can\'t bring someone who isn\'t in the room!')
            return
        else:
            self.players.append(args[0])
            self.reply(e, 'Nice job, you just brought ' + args[0] + ' into the game, even though they\'re probably AFK.')
            self.fix_modes()
	
    # TODO
    def cmd_rank(self, args, e):
	if len(args) != 1:
        	player = nm_to_n(e.source())
        else:
        	player = args[0]
        	if not os.path.exists(player + ".dat"):
        		self.say_public("Stats file not found for " + player + ".")
        		return
        		
        if player == "overall":
		if not os.path.exists(player + ".dat"):
			stats = open(player + ".dat", "w")
			stats.write("0" + "\n")
			stats.write("0" + "\n")
			stats.close()
			self.say_public("New stats file created for " + player + ".")

		stats = open(player + ".dat", "r")
		srwins = stats.readline()
		sewins = stats.readline()

		irwins = int(srwins)
		iewins = int(sewins)

		totalgames = irwins + iewins

		if totalgames == 0:
			self.say_public("No games played!")
			return

		resistancewinpercentage = float(irwins*100.0/(totalgames))
		sresistancewinpercentage = str(round(resistancewinpercentage, 2))

		empirewinpercentage = float(iewins*100.0/(totalgames))
		sempirewinpercentage = str(round(empirewinpercentage, 2))

		stotalgames = str(totalgames)

		self.say_public('There have been a total of\x033 ' + stotalgames + ' \x0f\x02\x02games played. There is an \x032overall resistance win percentage\x0f\x02\x02 of\x032 ' + sresistancewinpercentage + ' \x0f\x02\x02and an \x034overall empire win percentage\x0f\x02\x02 of\x034 ' + sempirewinpercentage + '\x0f\x02\x02.')
		stats.close()
        else:
		if not os.path.exists(player + ".dat"):
			stats = open(player + ".dat", "w")
			stats.write("0" + "\n")
			stats.write("0" + "\n")
			stats.write("0" + "\n")
			stats.write("0" + "\n")
			stats.close()
			self.say_public("New stats file created for " + player + ".")

		stats = open(player + ".dat", "r")
		srwins = stats.readline()
		srlosses = stats.readline()
		sewins = stats.readline()
		selosses = stats.readline()

		irwins = int(srwins)
		irlosses = int(srlosses)
		iewins = int(sewins)
		ielosses = int(selosses)

		totalwins = irwins + iewins
		totalgames = irwins + iewins + irlosses + ielosses
		totalresistancegames = irwins + irlosses
		totalempiregames = iewins + ielosses

		if totalresistancegames == 0:
			resistancewinpercentage = float(0.0)
			sresistancewinpercentage = "NA"
		else:
			resistancewinpercentage = float(irwins*100.0/(totalresistancegames))
			sresistancewinpercentage = str(round(resistancewinpercentage, 2))

		if totalempiregames == 0:
			empirewinpercentage = float(0.0)
			sempirewinpercentage = "NA"
		else:
			empirewinpercentage = float(iewins*100.0/(totalempiregames))
			sempirewinpercentage = str(round(empirewinpercentage, 2))

		if totalgames == 0:
			totalwinpercentage = float(0.0)
			stotalwinpercentage = "NA"
		else:
			totalwinpercentage = float(totalwins*100.0/totalgames)
			stotalwinpercentage = str(round(totalwinpercentage, 2))

		stotalwins = str(totalwins)
		stotalgames = str(totalgames)
		stotalresistancegames = str(totalresistancegames)
		stotalempiregames = str(totalempiregames)

		self.say_public(player + ': you have played\x032 ' + stotalresistancegames + ' \x0f\x02\x02games as resistance and\x034 ' + stotalempiregames + ' \x0f\x02\x02as empire, with an \x033overall win percentage\x0f\x02\x02 of\x033 ' + stotalwinpercentage + '\x0f\x02\x02. You have a \x032resistance win percentage\x0f\x02\x02 of\x032 ' + sresistancewinpercentage + ' \x0f\x02\x02and an \x034empire win percentage\x0f\x02\x02 of\x034 ' + sempirewinpercentage + '\x0f\x02\x02.')
		stats.close()
        
    def cmd_end(self, args, e):
        game_ender = nm_to_n(e.source())
        self.end_game(game_ender)
  
    def cmd_del(self, args, e):
        for nick in args:
            if nick not in self.players:
                self.reply(e, "There's nobody playing by the name %s" % nick)
            self._removeUser(nick)
  
    def cmd_renick(self, args, e):
        if len(args) != 1:
            self.reply(e, "Usage: renick <nick>")
        else:
            self.connection.nick(args[0])
  
    def cmd_aboutbot(self, args, e):
        self.reply(e, "I am a bot written in Python "
            "using the python-irclib library")

    def cmd_blind(self, args, e):
        if len(args) != 1:
            if self.blind_spies:
                self.reply(e, "Spies are currently blind.")
            else:
                self.reply(e, "Spies are currently not blind.")
        elif self.gamestate == self.GAMESTATE_RUNNING:
            self.reply(e, "You can't toggle blind spies during a game!")
            return
        elif args[0] == 'on':
            self.reply(e, "Blinding spies.")
            self.blind_spies = True
        elif args[0] == 'off':
            self.reply(e, "Unblinding spies.")
            self.blind_spies = False
            if self.instawin == True:
                self.reply(e, "You cannot have blind turned off while instawin is on.")
                self.reply(e, "Turning off instawin mode.")
                self.instawin = False
        else:
            self.reply(e, "Usage: blind on|off")
            
    def cmd_ranked(self, args, e):
        if len(args) != 1:
            if self.ranked:
                self.reply(e, "Game mode is currently set to ranked.")
            else:
                self.reply(e, "Game mode is currently set to unranked.")
        elif self.gamestate == self.GAMESTATE_RUNNING:
            self.reply(e, "You can't toggle game ranking during a game!")
            return
        elif args[0] == 'on':
            self.reply(e, "Turning on ranked mode.")
            self.ranked = True
        elif args[0] == 'off':
            self.reply(e, "Turning on unranked mode.")
            self.ranked = False
        else:
            self.reply(e, "Usage: ranked on|off")
            
    def cmd_instawin(self, args, e):
        if len(args) != 1:
            if self.instawin:
                self.reply(e, "Instawin is currently set to on for 5 man games.  When there are two spies on a team and only one of them sabotages, the spies will automatically win.")
            else:
                self.reply(e, "Instawin is currently set to off.")
        elif self.gamestate == self.GAMESTATE_RUNNING:
            self.reply(e, "You can't toggle instawin mode during a game!")
            return
        elif args[0] == 'on':
            self.reply(e, "Turning on instawin mode. When there are two spies on a team and only one of them sabotages, the spies will automatically win.")
            self.instawin = True
            if self.blind_spies == False:
 	        self.reply(e, "You cannot have instawin turned off while spies are not blind.")
	        self.reply(e, "Blinding spies.")
                self.blind_spies = True
        elif args[0] == 'off':
            self.reply(e, "Turning off instawin mode.")
            self.instawin = False
        else:
            self.reply(e, "Usage: instawin on|off")

    def cmd_settings(self, args, e):
    	if len(args) != 1:
            stringify = lambda start, on: start + "On\n" if on else "Off\n"

            self.say_public(stringify("Blind: ", self.blind_spies))
            self.say_public(stringify("Instawin: ", self.instawin))
            self.say_public(stringify("Ranked: ", self.ranked))
        else:
            self.reply(e, "Usage: settings on|off")
             
    def cmd_moderation(self, args, e):
        if self.game_starter and self.game_starter != nm_to_n(e.source()):
            self.reply(e, "%s started the game, and so has administrative control. "
            "Request denied." % self.game_starter)
            return
        if len(args) != 1:
            self.reply(e, "Usage: moderation on|off")
            return
        if args[0] == 'on':
            self.moderation = True
        elif args[0] == 'off':
            self.moderation = False
        else:
            self.reply(e, "Usage: moderation on|off")
            return
        self.say_public('Moderation turned %s by %s'
            % (args[0], nm_to_n(e.source())))
        self.fix_modes()
  
    def do_command(self, e, cmd):
        """This is the function called whenever someone sends a public or
        private message addressed to the bot. (e.g. "bot: blah").  Parse
        the CMD, execute it, then reply either to public channel or via
        /msg, based on how the command was received.  E is the original
        event, and FROM_PRIVATE is the nick that sent the message."""
        if cmd=='':
            return
        
        cmds = cmd.strip().split(" ")
        cmds[0] = cmds[0].lower()
        if self.debug and e.eventtype() == "pubmsg":
            if cmds[0][0] == '!':
                e._source = cmds[0][1:] + '!fakeuser@fakehost'
                cmds = cmds[1:]
                
        try:
            cmd_handler = getattr(self, "cmd_" + cmds[0])
        except AttributeError:
            cmd_handler = None
    
        if cmd_handler:
            cmd_handler(cmds[1:], e)
            return
    
        # unknown command:  respond appropriately.
        # reply either to public channel, or to person who /msg'd
        self.reply(e, "That command makes no sense.")

def main():
    import optparse

    parser = optparse.OptionParser(description='IRC bot to moderate games of Resistance.')
    parser.add_option('-d', '--debug', action='store_true', help='run the bot with debug info turned on')
    parser.add_option('-c', '--config', help='optional config file for IRC info.', default=None)
  
    (options, args) = parser.parse_args()
  
    if options.config == None:
        options.config = 'resistancebot.conf'
    
    import ConfigParser
    c = ConfigParser.ConfigParser()
    c.read(options.config)
    
    cfgsect = 'resistancebot'    
    host = c.get(cfgsect, 'host')
    channel = c.get(cfgsect, 'channel')
    nickname = c.get(cfgsect, 'nickname')
    nickpass = c.get(cfgsect, 'nickpass')
  
    s = string.split(host, ":", 1)
    server = s[0]
    port = defaultPort
    if len(s) == 2:
      try:
          port = int(s[1])
      except ValueError:
          print "Error: Erroneous port."
          sys.exit(1)        
    
    bot = ResistanceBot(channel, nickname, nickpass, server, port, options.debug)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Caught Ctrl-C during initialization."
