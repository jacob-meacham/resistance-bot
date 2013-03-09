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

import sys, string, random, time, os.path
from irclib.gamebot import GameBot
from irclib.irclib import nm_to_n
from game import ResistanceGame
import settings
import random
from random import choice


class ResistanceBot(GameBot):    
    def __init__(self, channel, nickname, nickpass, server, port=settings.default_port, debug=False, moderation=True):
        self.game = ResistanceGame(self, debug)
        self.game_starter = None

        GameBot.__init__(self, channel, nickname, nickpass, server, port, debug, moderation=moderation)

    def _renameUser(self, old, new):
        GameBot._renameUser(self, old, new)
        self.game.rename_user(old, new)
  
    def _removeUser(self, nick):
        GameBot._removeUser(self, nick)

        if nick == self.game_starter:
            self.game_starter = None

        self.game.remove_user(nick)

    def end_game(self, game_ender):
        if self.game.state == self.game.GAMESTATE_NONE:
            self.say_public("No game is in progress.  Use 'start' to begin a game.")
        elif self.game_starter and game_ender != self.game_starter:
            self.say_public(\
                        ("Sorry, only the starter of the game (%s) may end it." %\
                        self.game_starter))
        else:
            self.game.end()
            self.fix_modes()

    def handle_nonplayers(self, e):
        player = nm_to_n(e.source())
        if player not in self.game.players:
            self.reply(e, "Hush, you're not playing this game.")
            return False
        return True

    def cmd_team(self, args, e):
        if self.game.cur_phase != "ChooseTeam":
            self.reply(e, "Now isn't the time for choosing a mission team. We'll tell you when we've found a target.")
            return
        
        player = nm_to_n(e.source())
        if player != self.game.leader:
            self.reply(e, "Only the leader can decide who is on the mission team.")
            return
        
        if not self.handle_nonplayers(e):
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
                self.game.on_team_choice(e, member, add)
            else:
                raise ValueError
            
        except ValueError:
            self.reply(e, "Command should be in the form of 'team [add|remove] [user]'")
    
    def cmd_unvote(self, args, e):
        if self.game.cur_phase != "Vote":
            self.reply(e, "No election is currently being held.")
            return
        
        if not self.handle_nonplayers(e):
            return
        
        player = nm_to_n(e.source())
        self.game.on_unvote(e, player)

    def cmd_say(self, args, e):
        if len(args) == 0:
            return
        sayString = ""
        for word in args:
            sayString += word
            sayString +=" "
        self.say_public(sayString)
        
    def cmd_accept(self, args, e):
        if self.game.cur_phase != "Vote":
            self.reply(e, "No election is currently being held.")
            return
        
        if not self.handle_nonplayers(e):
            return
        
        player = nm_to_n(e.source())
        self.game.on_vote(e, player, True)
        
    def cmd_decline(self, args, e):
        if self.game.cur_phase != "Vote":
            self.reply(e, "No election is currently being held.")
            return
        
        if not self.handle_nonplayers(e):
            return
        
        player = nm_to_n(e.source())
        self.game.on_vote(e, player, False)
        
    def cmd_sabotage(self, args, e):
        player = nm_to_n(e.source())
        if self.game.state != self.game.GAMESTATE_RUNNING:
            self.reply(e, "You cannot sabotage before the game starts!")
            return

        if player not in self.game.mission_team:
            self.reply(e, "You're not on any mission team!")
            return
        
        if self.game.cur_phase != "Mission":
            self.reply(e, "Hold your horses, the mission hasn't started yet.")
            return
            
        if e.eventtype() == "pubmsg":
            self.reply(e, "You cannot public finish a mission!  Send me your choice in private.")
            return
                
        if player not in self.game.spies:
            self.reply(e, "You can't sabotage that.")
            return
        
        self.game.on_mission(e, player, False)
        
    def cmd_finish(self, args, e):
        player = nm_to_n(e.source())
        if self.game.state != self.game.GAMESTATE_RUNNING:
            self.reply(e, "You cannot sabotage before the game starts!")
            return
        
        if player not in self.game.mission_team:
            self.reply(e, "You're not on any mission team!")
            return
        
        if self.game.cur_phase != "Mission":
            self.reply(e, "Hold your horses, the mission hasn't started yet.")
            return
            
        if e.eventtype() == "pubmsg":
            self.reply(e, "You cannot public finish a mission!  Send me your choice in private.")
            return
        
        self.game.on_mission(e, player, True)
    
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
        if self.game.state == self.game.GAMESTATE_RUNNING:
            self.game.print_stats()
        elif self.game.state == self.game.GAMESTATE_STARTING:
            self.reply(e, "A new game is starting, current players are %s" % (self.game.players,))
        else:
            self.reply(e, "No game is in progress.")
  
    def cmd_status(self, args, e):
        self.cmd_stats(args, e)
        
    def cmd_score(self, args, e):
        if self.game.state == self.game.GAMESTATE_RUNNING:
            self.game.print_score()
        else:
            self.reply(e, "No game is in progress.")

    def cmd_votes(self, args, e):
        if self.game.state == self.game.GAMESTATE_RUNNING and self.game.cur_phase == "Vote":
            self.game.print_votes()
        else:
            self.reply(e, "No election is currently being held.")
  
    def cmd_start(self, args, e):
        "Initialize a resistance game."
        game_starter = nm_to_n(e.source())        
        chname, chobj = self.channels.items()[0]

        if self.game.state == self.game.GAMESTATE_RUNNING:
            self.say_public("A game started by %s is in progress; "
            "that person must end it." % self.game_starter)
        
        elif self.game.state == self.game.GAMESTATE_NONE:
            self.game.reset_game()
            self.game.state = self.game.GAMESTATE_STARTING
            self.game_starter = game_starter
            self.game_starter_last_seen = time.time()
            self.game.players.append(game_starter)

            self.say_public("A new game has been started by %s; "
                "say '%s: join' to join the game."
                % (self.game_starter, self.connection.get_nickname()))
            self.say_public("%s: Say '%s: start' when everyone has joined."
                % (self.game_starter, self.connection.get_nickname()))
            self.fix_modes()

        elif self.game.state == self.game.GAMESTATE_STARTING:
            if self.game_starter and game_starter != self.game_starter:
                self.say_public("Game startup was begun by %s; "
                "that person must finish starting it." % self.game_starter)
                return
      
            self.game_starter = game_starter
            self.game_starter_last_seen = time.time()

            if len(self.game.players) < settings.min_users:
                self.say_public("Sorry, to start a game, there must be at least active %d players." % (settings.min_users))
            else:
                self.fix_modes()
                self.game.start()

    def cmd_join(self, args, e):
        player = nm_to_n(e.source())
            
        if self.game.state == self.game.GAMESTATE_NONE:
            # Start the game
            self.cmd_start(args, e)
            return
      
        if self.game.state == self.game.GAMESTATE_RUNNING:
            self.reply(e, 'Game is in progress; please wait for the next game.')
            return
      
        player = nm_to_n(e.source())
        if player in self.game.players:
            self.reply(e, 'You are already in the game.')
        elif len(self.game.players) >= 10:
            self.reply(e, 'Only 10 players are allowed to play. You\'ll have to wait')
        else:
            self.game.players.append(player)

            self.reply(e, 'You are now in the game.')
            self.fix_modes()
  
    def cmd_bring(self, args, e):        
        if self.game.state == self.game.GAMESTATE_RUNNING:
            self.reply(e, 'You can\'t bring someone into a game that\'s in progress!')
            return
      
        player = nm_to_n(e.source())
        if player not in self.game.players:
            self.reply(e, 'You can\'t bring someone into a game that you haven\'t even joined!')
            return
        
        # Get the player that they're trying to bring:
        if len(args) != 1:
            self.reply(e, 'Usage: bring <nick>')
            return
        
        if args[0] in self.game.players:
            self.reply(e, 'That player is are already in the game.')
        elif len(self.game.players) >= 10:
            self.reply(e, 'Only 10 players are allowed to play. You\'ll have to wait')
        elif args[0] not in self.members_in_room:
            self.reply(e, 'You can\'t bring someone who isn\'t in the room!')
            return
        else:
            self.game.players.append(args[0])

            self.reply(e, 'Nice job, you just brought ' + args[0] + ' into the game, even though they\'re probably AFK.')
            self.fix_modes()
    
    # TODO
    # def cmd_rank(self, args, e):
    #     if len(args) != 1:
    #         player = nm_to_n(e.source())
    #     else:
    #         player = args[0]
    #         if not os.path.exists(player + ".dat"):
    #             self.say_public("Stats file not found for " + player + ".")
    #             return
                
    #     if player == "overall":
    #         if not os.path.exists(player + ".dat"):
    #             stats = open(player + ".dat", "w")
    #             stats.write("0" + "\n")
    #             stats.write("0" + "\n")
    #             stats.close()
    #             self.say_public("New stats file created for " + player + ".")

    #     stats = open(player + ".dat", "r")
    #     srwins = stats.readline()
    #     sewins = stats.readline()

    #     irwins = int(srwins)
    #     iewins = int(sewins)

    #     totalgames = irwins + iewins

    #     if totalgames == 0:
    #         self.say_public("No games played!")
    #         return

    #     resistancewinpercentage = float(irwins*100.0/(totalgames))
    #     sresistancewinpercentage = str(round(resistancewinpercentage, 2))

    #     empirewinpercentage = float(iewins*100.0/(totalgames))
    #     sempirewinpercentage = str(round(empirewinpercentage, 2))

    #     stotalgames = str(totalgames)

    #     self.say_public('There have been a total of\x033 ' + stotalgames + ' \x0f\x02\x02games played. There is an \x032overall resistance win percentage\x0f\x02\x02 of\x032 ' + sresistancewinpercentage + ' \x0f\x02\x02and an \x034overall empire win percentage\x0f\x02\x02 of\x034 ' + sempirewinpercentage + '\x0f\x02\x02.')
    #     stats.close()
    #     else:
    #         if not os.path.exists(player + ".dat"):
    #             stats = open(player + ".dat", "w")
    #             stats.write("0" + "\n")
    #             stats.write("0" + "\n")
    #             stats.write("0" + "\n")
    #             stats.write("0" + "\n")
    #             stats.close()
    #             self.say_public("New stats file created for " + player + ".")

    #     stats = open(player + ".dat", "r")
    #     srwins = stats.readline()
    #     srlosses = stats.readline()
    #     sewins = stats.readline()
    #     selosses = stats.readline()

    #     irwins = int(srwins)
    #     irlosses = int(srlosses)
    #     iewins = int(sewins)
    #     ielosses = int(selosses)

    #     totalwins = irwins + iewins
    #     totalgames = irwins + iewins + irlosses + ielosses
    #     totalresistancegames = irwins + irlosses
    #     totalempiregames = iewins + ielosses

    #     if totalresistancegames == 0:
    #         resistancewinpercentage = float(0.0)
    #         sresistancewinpercentage = "NA"
    #     else:
    #         resistancewinpercentage = float(irwins*100.0/(totalresistancegames))
    #         sresistancewinpercentage = str(round(resistancewinpercentage, 2))

    #     if totalempiregames == 0:
    #         empirewinpercentage = float(0.0)
    #         sempirewinpercentage = "NA"
    #     else:
    #         empirewinpercentage = float(iewins*100.0/(totalempiregames))
    #         sempirewinpercentage = str(round(empirewinpercentage, 2))

    #     if totalgames == 0:
    #         totalwinpercentage = float(0.0)
    #         stotalwinpercentage = "NA"
    #     else:
    #         totalwinpercentage = float(totalwins*100.0/totalgames)
    #         stotalwinpercentage = str(round(totalwinpercentage, 2))

    #     stotalwins = str(totalwins)
    #     stotalgames = str(totalgames)
    #     stotalresistancegames = str(totalresistancegames)
    #     stotalempiregames = str(totalempiregames)

    #     self.say_public(player + ': you have played\x032 ' + stotalresistancegames + ' \x0f\x02\x02games as resistance and\x034 ' + stotalempiregames + ' \x0f\x02\x02as empire, with an \x033overall win percentage\x0f\x02\x02 of\x033 ' + stotalwinpercentage + '\x0f\x02\x02. You have a \x032resistance win percentage\x0f\x02\x02 of\x032 ' + sresistancewinpercentage + ' \x0f\x02\x02and an \x034empire win percentage\x0f\x02\x02 of\x034 ' + sempirewinpercentage + '\x0f\x02\x02.')
    #     stats.close()
        
    def cmd_end(self, args, e):
        game_ender = nm_to_n(e.source())
        self.end_game(game_ender)
  
    def cmd_del(self, args, e):
        for nick in args:
            if nick not in self.game.players:
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
            if self.game.blind_spies:
                self.reply(e, "Spies are currently blind.")
            else:
                self.reply(e, "Spies are currently not blind.")
        elif self.game.state == self.game.GAMESTATE_RUNNING:
            self.reply(e, "You can't toggle blind spies during a game!")
            return
        elif args[0] == 'on':
            self.reply(e, "Blinding spies.")
            self.game.blind_spies = True
        elif args[0] == 'off':
            self.reply(e, "Unblinding spies.")
            self.game.blind_spies = False
            if self.game.instawin == True:
                self.reply(e, "You cannot have blind turned off while instawin is on.")
                self.reply(e, "Turning off instawin mode.")
                self.game.instawin = False
        else:
            self.reply(e, "Usage: blind on|off")
            
    def cmd_ranked(self, args, e):
        if len(args) != 1:
            if self.game.ranked:
                self.reply(e, "Game mode is currently set to ranked.")
            else:
                self.reply(e, "Game mode is currently set to unranked.")
        elif self.game.state == self.game.GAMESTATE_RUNNING:
            self.reply(e, "You can't toggle game ranking during a game!")
            return
        elif args[0] == 'on':
            self.reply(e, "Turning on ranked mode.")
            self.game.ranked = True
        elif args[0] == 'off':
            self.reply(e, "Turning on unranked mode.")
            self.game.ranked = False
        else:
            self.reply(e, "Usage: ranked on|off")
            
    def cmd_instawin(self, args, e):
        if len(args) != 1:
            if self.game.instawin:
                self.reply(e, "Instawin is currently set to on for 5 man games.  When there are two spies on a team and only one of them sabotages, the spies will automatically win.")
            else:
                self.reply(e, "Instawin is currently set to off.")
        elif self.game.state == self.game.GAMESTATE_RUNNING:
            self.reply(e, "You can't toggle instawin mode during a game!")
            return
        elif args[0] == 'on':
            self.reply(e, "Turning on instawin mode. When there are two spies on a team and only one of them sabotages, the spies will automatically win.")
            self.game.instawin = True
            if self.game.blind_spies == False:
                self.reply(e, "You cannot have instawin turned off while spies are not blind.")
                self.reply(e, "Blinding spies.")
                self.game.blind_spies = True
        elif args[0] == 'off':
            self.reply(e, "Turning off instawin mode.")
            self.game.instawin = False
        else:
            self.reply(e, "Usage: instawin on|off")

    def cmd_settings(self, args, e):
        if len(args) != 1:
            stringify = lambda start, on: start + "On\n" if on else "Off\n"

            self.say_public(stringify("Blind: ", self.game.blind_spies))
            self.say_public(stringify("Instawin: ", self.game.instawin))
            self.say_public(stringify("Ranked: ", self.game.ranked))
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