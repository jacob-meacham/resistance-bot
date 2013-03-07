Resistance Bot
==============

An unofficial IRC bot version of [The Resistance](http://boardgamegeek.com/boardgame/41114/the-resistance).

Buy the hard copy of the game, and support the developers! The art is really awesome, and the hard copy of the game includes some fun mechanics that aren't represented here. It's also much better balanced than Werewolf/Mafia for IRC-based games.

License
=======
ReistanceBot uses the great irclib by Joel Rosdahl <joel@rosdahl.net>, and is loosely based on [WolfBot](https://code.google.com/p/ircbot-collection/). irclib is licensed under LGPL. ResistanceBot itself is licensed under Apache 2.0.

Using
=====
Rename config.py.example to config.py, and put in the appropriate settings. Then, just run resistancebot.py!

Commands
--------
The bot accepts commands in the following form: As a PM, with no decorators, in public chat with <botname>: prefixed, or in public chat with ! prefixed (ex !help).

Quick Start
-------
to start a game use !start. Then, people can join using !join. Once you have enough players (5-10), the game leader can start the game using !start.

When the team leader is adding team members, use !team (add|remove) <nick>

When voting, use !accept or !decline -- this can be done in either public or private.

When on a mission, if you are a spy, you can either use *sabotage* or *finish*. As a member of the resistance, you can only choose to *finish*. These commands must be PM'ed to the bot.
