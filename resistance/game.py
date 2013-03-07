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
import sys, string, random, time, os.path
from random import choice
from mission import mission_fiction
import settings

mission_size = [
                [2,3,2,3,3], # 5 players
                [2,3,4,3,4], # 6 players
                [2,3,3,4,4], # 7 players
                [3,4,4,5,5], # 8 players
                [3,4,4,5,6], # 9 players
                [3,4,4,5,5] # 10 players
               ]

IRC_BOLD = "\x02"
class ResistanceGame:
    GAMESTATE_NONE, GAMESTATE_STARTING, GAMESTATE_RUNNING  = range(3)
    
    def __init__(self, messenger, debug):
    	self.messenger = messenger
        self.debug = debug

        self.ranked = settings.ranked_default
    	self.blind_spies = settings.blind_default
        self.instawin = settings.instawin_default
        self.phase = {}
        self.phase["ChooseTeam"] = self.begin_team_choice_phase
        self.phase["Vote"] = self.begin_voting_phase
        self.phase["Mission"] = self.begin_mission_phase
        self.reset_game()

    ''' section: Game Logic '''
    def reset_game(self):
        self.state = self.GAMESTATE_NONE
        self.players = []
        self.votes = {}
        self.mission_votes = {}
        self.mission_team = []
        self.spies = []
        self.original_spies = []
        self.cur_phase = None

    def rename_user(self, old, new):
        if self.state == self.GAMESTATE_NONE:
            # don't need to do anything.
            return
 
        if old in self.players:
            self.players.append(new)
            self.players.remove(old)

        for list in (self.players, self.spies, self.original_spies, self.mission_team):
            if old in list:
                list.append(new)
                list.remove(old)
        for map in (self.votes, self.mission_votes):
            if map.has_key(new):
                map[new] = map[old]
                del map[old]
        
        if self.leader == old:
            self.leader = new

    def remove_user(self, nick):
        if self.state == self.GAMESTATE_NONE:
            # don't need to do anything.
            return

        if nick in self.players:
            self.messenger.say_public("%s disappeared in some sort of strange wormhole." % nick)
            self.players.remove(nick)
        
        if self.state == self.GAMESTATE_STARTING:
            # No more to do
            return

        if nick in self.spies:
            self.spies.remove(nick)
            self.messenger.say_public("We've just received word that %s was an Imperial spy! They were summarily and messily executed." % nick)
            if len(self.spies) == 0:
                self.end(self.game_starter)
                return
        elif nick in self.players:
            self.messenger.say_public("%s's loyalty is beyond doubt now. Of course, we had to torture them to death to discover that fact..." % nick)
                  
        if nick in self.mission_team:
            self.mission_team.remove(nick)
        
        for map in (self.votes, self.mission_votes):
            if map.has_key(nick):
                del map[nick]
                
        if nick == self.leader:
            self.leader = choice(self.players)
            if self.cur_phase == "ChooseTeam":
                # Need to start team choice over.
                # This isn't quite right, since leader is now random.
                self.begin_team_choice_phase()
        
    def start(self):
        self.state = self.GAMESTATE_RUNNING
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
        
        self.messenger.say_public("A new game of Resistance has started!")

        for spy in self.spies:
          self.messenger.say_private(spy, "You're a sneaky Imperial spy.")
        for player in _players:
          self.messenger.say_private(player, "You're an upstanding member of the Resistance.")

        if not self.blind_spies:
            # inform the spies of their comrades.
            for spy in self.spies:
                other_spies = [x for x in self.spies if x != spy]
                if len(other_spies) == 1:
                    plurality = "spy is "
                else:
                    plurality = "spies are "
                self.messenger.say_private(spy, "The other " + plurality + self.build_list_string(other_spies))
        
        if self.debug:
            print "SPIES: %s" % ' '.join(self.spies)
                
        self.cur_phase = "ChooseTeam"
        self.phase[self.cur_phase]()    

    def end(self):
        self.messenger.say_public("The game has ended.")
        if self.state == self.GAMESTATE_RUNNING:
            self.messenger.say_public("*** The spies were %s. "
                            "Everyone else was a member of the Resistance."
                            % self.build_list_string(self.original_spies))
            self.reset_game()
        
    def begin_team_choice_phase(self):
        # pick a new leader
        new_leader = self.players.index(self.leader) + 1
        if new_leader >= len(self.players):
            new_leader = 0
        
        self.leader = self.players[new_leader]
        self.mission_team = []    
        self.cur_team_size = self.calc_team_size()
        
        self.messenger.say_public("\x033" + self.leader + "\x0f\x02\x02, you're the leader now.")
        self.messenger.say_public("We've just received word " + mission_fiction() + " You should put together a team to take advantage of this opportunity!"\
                        "\x032 " + str(self.cur_team_size) + "\x0f\x02\x02 operatives may go on this mission.")
        
        self.messenger.say_private(self.leader, "You're now the leader, and should put together your team.")
        
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
        self.messenger.say_public(msg)
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
        
        self.messenger.say_public("The mission team consisting of " + self.build_list_string(self.mission_team) + " will now \x032commence their Mission\x0f\x02\x02")
        
        for member in self.mission_team:
            self.messenger.say_private(member, "You have been chosen to complete this daring and deadly mission!")
            if member in self.spies:
                self.messenger.say_private(member, "You may choose to either \x034finish\x0f\x02\x02 or \x034sabotage\x0f\x02\x02 this mission.")
            else:
                self.messenger.say_private(member, "You must attempt to \x034finish\x0f\x02\x02 this mission.")
            
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
            self.messenger.say_public("The mission was sabotaged by " + str(sabotages) + " operatives!")
            self.spy_rounds = self.spy_rounds + 1
        else:
            self.messenger.say_public("The mission was a success!")
            self.resistance_rounds = self.resistance_rounds + 1
        
        self.cur_round = self.cur_round + 1
        self.print_score()
        
        if self.check_game_over():
            self.end()
     	elif spy_count > 1 and len(self.players) == 5:
     	    self.messenger.say_public("There were two sneaky spies on that mission, and only 1 sabotaged. The spies instantly win!")
            self.record_stats(True)
    	    if self.ranked:
                self.recordoverallempirewin()
                for member in self.players:
                    if member in self.spies:
                        self.recordempirewin(member)
    	            else:
                        self.recordresistanceloss(member)
    	    self.end()
        else:
            self.cur_phase = "ChooseTeam"
            self.phase[self.cur_phase]()
    
    def check_game_over(self):
        if self.resistance_rounds >= 3:
            self.messenger.say_public('\x034The Resistance\x0f\x02\x02 has successfully \x034destroyed\x0f\x02\x02 the Empire!')
	    if self.ranked:
	        self.recordoverallresistancewin()
	        for member in self.players:
		    if member in self.spies:
		        self.recordempireloss(member)
		    else:
		        self.recordresistancewin(member)
            return True
        elif self.spy_rounds >= 3:
            self.messenger.say_public('The \x034Imperial Spies\x0f\x02\x02 have successfully \x034sabotaged\x0f\x02\x02 the Resistance!')
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
        self.messenger.say_public("Score on Mission " + str(self.cur_round) + ":")
        self.messenger.say_public("Resistance: " + str(self.resistance_rounds) + "/3")
        self.messenger.say_public("Spies: " + str(self.spy_rounds) + "/3")

    def print_votes(self):
        voters = [key for key in self.votes.iterkeys()]
        if len(voters) == 0:
            msg = "No players have voted yet."
        else:
            msg = "The following players have voted: " \
              + self.build_list_string(voters)
            
        self.messenger.say_public(msg)
        
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
            
        self.messenger.say_public(msg)
        
        self.messenger.say_public("The current leader is \x034" + self.leader)
        self.messenger.say_public("Game order is " + ' '.join(self.players))
        self.messenger.say_public("It's been \x034 " + str(self.no_vote_rounds) + " \x0f\x02\x02no vote rounds since the last mission.")
        
        if len(self.mission_team) > 0:
            self.messenger.say_public("The mission team consists of " + self.build_list_string(self.mission_team))
            
        if self.cur_phase == "ChooseTeam":
            self.messenger.say_public("The team needs to have " + str(self.cur_team_size) + " members.")
        
        if self.cur_phase == "Vote":
            self.print_votes()
    
    def build_list_string(self, list):
        if len(list) == 0:
            return "no one"
        elif len(list) == 1:
            return str(list[0])
        
        return ', '.join(list[:-1]) + " and " + str(list[-1])
        
    def on_team_choice(self, e, member, add):
        if member not in self.players:
            self.messenger.reply(e, "You can't add someone who isn't even playing!")
            return
        
        if add:
            if member in self.mission_team:
                self.messenger.reply(e, "You can't add someone who is already in the team!")
            else:
                self.messenger.reply(e, "Added %s to the mission team" % member)
                self.mission_team.append(member)
        else:
            if member in self.mission_team:
                self.mission_team.remove(member)
                self.messenger.reply(e, "Removed %s from the mission team" % member)
            else:
                self.messenger.reply(e, "They're not on the mission team.")
                
        if len(self.mission_team) >= self.cur_team_size:
            # Finished picking the team
            self.cur_phase = "Vote"
            self.phase[self.cur_phase]()
            
    def on_vote(self, e, player, vote):
        self.votes[player] = vote            
        self.messenger.reply(e, "Your vote has been tallied.")
                
        if self.check_votes():
            t = self.tally_votes()
            for_team = [k for k,v in self.votes.iteritems() if v is True]
            against_team = [k for k,v in self.votes.iteritems() if v is False]

            self.messenger.say_public(self.build_list_string(for_team) + " voted \x033for the team\x0f\x02\x02 and")
            self.messenger.say_public(self.build_list_string(against_team) + " voted \x034against the team\x0f\x02\x02.")
            
            if t:
                self.no_vote_rounds = 0
                self.cur_phase = "Mission"
                self.messenger.say_public("Therefore, the mission team was \x033accepted!\x0f\x02\x02")
            else:
                self.no_vote_rounds = self.no_vote_rounds + 1
                if self.no_vote_rounds >= 5:
                    self.spy_rounds = 3
                    self.messenger.say_public("Unfortunately, you all spent so much time bickering, that the Empire discovered your based and destroyed you all.")
                    if self.check_game_over():
                        self.end()
                        return

                self.cur_phase = "ChooseTeam"
                self.messenger.say_public("Therefore, the mission team was \x034not accepted!\x0f\x02\x02")
            
            self.phase[self.cur_phase]()
            
    def on_unvote(self, e, player):
        if player in self.votes.keys():
            del self.votes[player]
            self.messenger.reply(e, "Your vote has been retracted.")
        else:
            self.messenger.reply(e, "You haven't voted yet.")
    
    def on_mission(self, e, player, action):
        self.mission_votes[player] = action
        self.messenger.reply(e, "Your contribution to the mission is acknowledged.")
        
        if self.check_mission():
            self.mission_results()
        
    def recordoverallresistancewin(self):
        if not os.path.exists("overall.dat"):
            stats = open("overall.dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()

        self.messenger.say_public("New stats file created for overall.")
            
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
        self.messenger.say_public("Stats written for overall.")

    def recordoverallempirewin(self):
        if not os.path.exists("overall.dat"):
            stats = open("overall.dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
        self.messenger.say_public("New stats file created for overall.")
                
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
        self.messenger.say_public("Stats written for overall.")
        
    def recordresistancewin(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.messenger.say_public("New stats file created for " + player + ".")

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
        self.messenger.say_public("Stats written for " + player + ".")

    def recordresistanceloss(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.messenger.say_public("New stats file created for " + player + ".")

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
        self.messenger.say_public("Stats written for " + player + ".")
        
    def recordempirewin(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.messenger.say_public("New stats file created for " + player + ".")

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
        self.messenger.say_public("Stats written for " + player + ".")

    def recordempireloss(self, player):
        if not os.path.exists(player + ".dat"):
            stats = open(player + ".dat", "w")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.write("0" + "\n")
            stats.close()
            self.messenger.say_public("New stats file created for " + player + ".")

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
        self.messenger.say_public("Stats written for " + player + ".")