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
    fiction = [_("We've just received word of an Imperial base with narcoleptic guards."),
               _("We've just received word of a chance to steal the Emperor's prized %s.") % choice([_("underwear"), _("teddy bear"), _("pony"), _("son"), _("lager")]),
               _("We've just received word of a nuclear power plant looking to recruit shady workers."),
               _("We've just received word of a way to infiltrate a secret Imperial %s.") % choice([_("base"), _("mission"), _("karaoke party"), _("surprise party"), _("March")]),
               _("We've just received word  of a %s which is not fully operational.") % choice([_("Death Star"), _("karaoke bar"), _("Hydroplant"), _("Core FX 9000"), _("tractor")]),
               _("We've just received word of a high ranking Imperial official who is %s.") % choice([_("lactose intolerant"), _("scared of heights"), _("balding")])
               ]
    return choice(fiction)