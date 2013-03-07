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
#
from random import choice

def mission_fiction():
    fiction = ["of an Imperial base with narcoleptic guards.",
               "of a chance to steal the Emperor's prized " + choice(["underwear", "teddy bear", "pony", "son", "lager"]) + '.',
               "of a nuclear power plant looking to recruit shady workers.",
               "of a way to infiltrate a secret Imperial " + choice(["base", "mission", "karaoke party", "surprise party", "March"]) + '.',
               "of a " + choice(["Death Star", "karaoke bar", "Hydroplant", "Core FX 9000", "tractor"]) + " which is not fully operational.",
               "of a high ranking Imperial official who is " + choice(["lactose intolerant", "scared of heights", "balding", "Zac's brother"]) + '.'
               ]
    return choice(fiction)