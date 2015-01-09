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

from resistance.bot import ResistanceBot
import config
import gettext
import locale
import logging
 
def init_localization(localization_filename):
  if localization_filename is not None:
    filename = localization_filename
  else:
    locale.setlocale(locale.LC_ALL, '') # use user's preferred locale

    # take first two characters of country code
    filename = "i18n/messages_%s.mo" % locale.getlocale()[0][0:2]
  
  try:
    logging.debug('Opening message file %s' % filename)
    trans = gettext.GNUTranslations(open(filename, "rb"))
  except IOError:
    logging.debug('Using default messages')
    trans = gettext.NullTranslations()
 
  trans.install(names=['ngettext'])
  logging.debug('localization initialized!')

def main():
    init_localization(config.localization_filename)
    ResistanceBot(config.channel, config.nickname, config.nickpass, config.host, config.port, config.debug, moderation=config.moderation)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Caught Ctrl-C during initialization."