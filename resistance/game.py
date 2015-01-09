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
from random import choice, randrange
from mission import mission_fiction
import datetime
import settings
import logging
from stats import Session, Player, Game

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
    
    def __init__(self, messenger):
    	self.messenger = messenger

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
            self.messenger.say_public(_("%s disappeared in some sort of strange wormhole.") % nick)
            self.players.remove(nick)
        
        if self.state == self.GAMESTATE_STARTING:
            # No more to do
            return

        if nick in self.spies:
            self.spies.remove(nick)
            self.messenger.say_public(_("We've just received word that %s was an Imperial spy! They were summarily and messily executed.") % nick)
            if len(self.spies) == 0:
                self.end(self.game_starter)
                return
        elif nick in self.players:
            self.messenger.say_public(_("%s's loyalty is beyond doubt now. Of course, we had to torture them to death to discover that fact...") % nick)
                  
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
            self.spies.append(_players.pop(randrange(len(_players))))
            num_spies = num_spies + 1
        
        # Save off the original spies, in case one or more of them is deleted.
        self.original_spies = self.spies
        
        self.leader = choice(self.players)
        
        self.messenger.say_public(_("A new game of Resistance has started!"))

        for spy in self.spies:
          self.messenger.say_private(spy, _("You're a sneaky Imperial spy."))
        for player in _players:
          self.messenger.say_private(player, _("You're an upstanding member of the Resistance."))

        if not self.blind_spies:
            # inform the spies of their comrades.
            for spy in self.spies:
                other_spies = [x for x in self.spies if x != spy]
                message = ngettext('The other spy is %(spy_list)s', 'The other spies are %(spy_list)s', 
                    len(other_spies)) % {'spy_list': self.build_list_string(other_spies)}
                self.messenger.say_private(spy, message)
        
        logging.debug(_("SPIES: %s") % ' '.join(self.spies))
                
        self.cur_phase = "ChooseTeam"
        self.phase[self.cur_phase]()    

    def end(self):
        self.messenger.say_public(_("The game has ended."))
        if self.state == self.GAMESTATE_RUNNING:
            self.messenger.say_public(_("*** The spies were %s. "
                            "Everyone else was a member of the Resistance.")
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
        
        self.messenger.say_public(_("\x033 %s \x0f\x02\x02, you're the leader now.") % self.leader)
        self.messenger.say_public(mission_fiction() + " " + _("You should put together a team to take advantage of this opportunity!"\
                        "\x032 %d \x0f\x02\x02 operatives may go on this mission.") % self.cur_team_size)
        
        self.messenger.say_private(self.leader, _("You're now the leader, and should put together your team."))
        
    def calc_team_size(self):
        # Team size changes based on round and number of players.
        idx = len(self.players) - 5
        if idx < 0:
            idx = 0

        return mission_size[idx][self.cur_round]
    
    def begin_voting_phase(self):
        msg = _("As a group, we must now \x036Vote\x0f\x02\x02 on the proposed team. "\
              "The team consists of %s. "\
              "You can either \x034accept\x0f\x02\x02 or \x034decline\x0f\x02\x02 this team. You can change your vote at any time "\
              "but once all of the votes are in, the results are final.") % self.build_list_string(self.mission_team)
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
        
        self.messenger.say_public(_("The mission team consisting of %s will now \x032commence their Mission\x0f\x02\x02") % self.build_list_string(self.mission_team))
        
        for member in self.mission_team:
            self.messenger.say_private(member, _("You have been chosen to complete this daring and deadly mission!"))
            if member in self.spies:
                self.messenger.say_private(member, _("You may choose to either \x034finish\x0f\x02\x02 or \x034sabotage\x0f\x02\x02 this mission."))
            else:
                self.messenger.say_private(member, _("You must attempt to \x034finish\x0f\x02\x02 this mission."))
            
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
            self.messenger.say_public(_("The mission was sabotaged by %s operatives!") % str(sabotages))
            self.spy_rounds = self.spy_rounds + 1
        else:
            self.messenger.say_public(_("The mission was a success!"))
            self.resistance_rounds = self.resistance_rounds + 1
        
        self.cur_round = self.cur_round + 1
        self.print_score()
        
        if self.check_game_over():
            self.end()
     	elif spy_count > 1 and len(self.players) == 5:
     	    self.messenger.say_public(_("There were two sneaky spies on that mission, and only 1 sabotaged. The spies instantly win!"))
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
        game_over = False
        if self.resistance_rounds >= 3:
            self.messenger.say_public(_('\x034The Resistance\x0f\x02\x02 has successfully \x034destroyed\x0f\x02\x02 the Empire!'))
            game_over = True
        elif self.spy_rounds >= 3:
            self.messenger.say_public(_('The \x034Imperial Spies\x0f\x02\x02 have successfully \x034sabotaged\x0f\x02\x02 the Resistance!'))
            game_over = True

        if game_over and self.ranked:
            self.write_stats(self.spy_rounds >= 3)

        return game_over
        
    def print_score(self):
        self.messenger.say_public(_("Score on Mission %d:") % self.cur_round)
        self.messenger.say_public(_("Resistance: %d/3") % self.resistance_rounds)
        self.messenger.say_public(_("Spies: %d/3") % self.spy_rounds)

    def print_votes(self):
        voters = [key for key in self.votes.iterkeys()]
        if len(voters) == 0:
            msg = _("No players have voted yet.")
        else:
            msg = _("The following players have voted: %s") % self.build_list_string(voters)
            
        self.messenger.say_public(msg)
        
    def print_stats(self):
        """ Prints stats that are relevant to the current phase """
        if self.cur_phase == "ChooseTeam":
            msg = _("The current phase is \x033Team Building")
        elif self.cur_phase == "Vote":
            msg = _("The current phase is \x036Voting")
        elif self.cur_phase == "Mission":
            msg = _("The current phase is \x032Mission Duty")
            
        self.messenger.say_public(msg)
        
        self.messenger.say_public(_("The current leader is \x034%s") % self.leader)
        self.messenger.say_public(_("Game order is %s") % ' '.join(self.players))
        self.messenger.say_public(_("It's been \x034 %d \x0f\x02\x02 vote rounds since the last mission.") % self.no_vote_rounds)
        
        if len(self.mission_team) > 0:
            self.messenger.say_public(_("The mission team consists of %s") % self.build_list_string(self.mission_team))
            
        if self.cur_phase == "ChooseTeam":
            self.messenger.say_public(_("The team needs to have %d members.") % self.cur_team_size)
        
        if self.cur_phase == "Vote":
            self.print_votes()
    
    # TODO
    def build_list_string(self, list):
        if len(list) == 0:
            return "no one"
        elif len(list) == 1:
            return str(list[0])
        
        return ', '.join(list[:-1]) + " and " + str(list[-1])
        
    def on_team_choice(self, e, member, add):
        if member not in self.players:
            self.messenger.reply(e, _("You can't add someone who isn't even playing!"))
            return
        
        if add:
            if member in self.mission_team:
                self.messenger.reply(e, _("You can't add someone who is already in the team!"))
            else:
                self.messenger.reply(e, _("Added %s to the mission team") % member)
                self.mission_team.append(member)
        else:
            if member in self.mission_team:
                self.mission_team.remove(member)
                self.messenger.reply(e, _("Removed %s from the mission team") % member)
            else:
                self.messenger.reply(e, _("They're not on the mission team."))
                
        if len(self.mission_team) >= self.cur_team_size:
            # Finished picking the team
            self.cur_phase = "Vote"
            self.phase[self.cur_phase]()
            
    def on_vote(self, e, player, vote):
        self.votes[player] = vote            
        self.messenger.reply(e, _("Your vote has been tallied."))
                
        if self.check_votes():
            t = self.tally_votes()
            for_team = [k for k,v in self.votes.iteritems() if v is True]
            against_team = [k for k,v in self.votes.iteritems() if v is False]

            self.messenger.say_public(_("%s voted \x033for the team\x0f\x02\x02 and") % self.build_list_string(for_team))
            self.messenger.say_public(_("%s voted \x034against the team\x0f\x02\x02.") % self.build_list_string(against_team))
            
            if t:
                self.no_vote_rounds = 0
                self.cur_phase = "Mission"
                self.messenger.say_public(_("Therefore, the mission team was \x033accepted!\x0f\x02\x02"))
            else:
                self.no_vote_rounds = self.no_vote_rounds + 1
                if self.no_vote_rounds >= 5:
                    self.spy_rounds = 3
                    self.messenger.say_public(_("Unfortunately, you all spent so much time bickering, that the Empire discovered your based and destroyed you all."))
                    if self.check_game_over():
                        self.end()
                        return

                self.cur_phase = "ChooseTeam"
                self.messenger.say_public(_("Therefore, the mission team was \x034not accepted!\x0f\x02\x02"))
            
            self.phase[self.cur_phase]()
            
    def on_unvote(self, e, player):
        if player in self.votes.keys():
            del self.votes[player]
            self.messenger.reply(e, _("Your vote has been retracted."))
        else:
            self.messenger.reply(e, _("You haven't voted yet."))
    
    def on_mission(self, e, player, action):
        self.mission_votes[player] = action
        self.messenger.reply(e, _("Your contribution to the mission is acknowledged."))
        
        if self.check_mission():
            self.mission_results()
        
    def write_stats(self, spies_won):
        session = Session()

        game = Game(num_players=len(self.players), date=datetime.datetime.utcnow(), resistance_rounds=self.resistance_rounds, spy_rounds=self.spy_rounds)

        for player_name in self.players:
            player = Player.query.filter_by(name=player_name)
            if player is None:
                player = Player(name=player_name)

            if player in self.spies:
                if spies_won:
                    player.spy_wins = player.spy_wins + 1
                    player.total_wins = player.total_wins + 1
                else:
                    player.spy_losses = player.spy_losses + 1
            else:
                if not spies_won: 
                    player.resistance_wins = player.resistance_wins + 1
                    player.total_wins = player.total_wins + 1
                else:
                    player.resistance_losses = player.resistance_losses + 1

            player.total_games = player.total_games + 1
            player.win_percent = player.total_wins / player.total_games
            game.players.append(player)
            session.add(player)

        session.add(game)
        session.commit()