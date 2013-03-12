import unittest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from stats import Base, Player, Game

db = create_engine('sqlite:///test.db')
Base.metadata.create_all(db)
Session = sessionmaker(bind=db)

class TestStats(unittest.TestCase):
	def setUp(self):
		Base.metadata.drop_all(db)
		Base.metadata.create_all(db)

	def test_players(self):
		session = Session()
		p1 = Player(name='test_user')
		p1.spy_wins = 10
		session.add(p1)
		session.commit()

		g = Game(num_players=2, date=datetime.datetime.utcnow(), resistance_rounds=3, spy_rounds=2)
		p2 = Player(name='test_user2')

		g.players.append(p1)
		g.players.append(p2)

		session.add(g)
		session.add(p2)
		session.commit()

		player_list = session.query(Player).filter_by(name='test_user').all()
		self.assertEqual(len(player_list), 1)
		self.assertIn(p1, player_list)

		player = player_list[0]
		self.assertEqual(len(player.games), 1)
		self.assertIn(g, player.games)


	def test_games(self):
		session = Session()
		p1 = Player(name='test_user')
		p2 = Player(name='test_user2')

		g = Game(num_players=2, date=datetime.datetime.utcnow(), resistance_rounds=3, spy_rounds=2)
		
		g.players.append(p1)
		g.players.append(p2)

		session.add(g)
		session.add(p1)
		session.add(p2)
		session.commit()

		query_game = session.query(Game).first()
		self.assertEqual(query_game, g)

		self.assertEqual(len(query_game.players), 2)
		self.assertIn(p1, query_game.players)

	def test_player_stats(self):
		pass

	def test_game_stats(self):
		session = Session()

		p1 = Player(name='test_user')
		p2 = Player(name='test_user2')

		games = [Game(num_players=2, date=datetime.datetime.utcnow(), resistance_rounds=3, spy_rounds=2),
				 Game(num_players=2, date=datetime.datetime.utcnow(), resistance_rounds=3, spy_rounds=2),
				 Game(num_players=2, date=datetime.datetime.utcnow(), resistance_rounds=3, spy_rounds=2),
				 Game(num_players=2, date=datetime.datetime.utcnow(), resistance_rounds=1, spy_rounds=3)]

		for game in games:
			game.players.append(p1)
			game.players.append(p2)
			session.add(game)

		session.add(p1)
		session.add(p2)
		session.commit()

		total_games = session.query(Game).count()
		resistance_wins = session.query(Game).filter(Game.resistance_rounds >= 3).count()
		spy_wins = session.query(Game).filter(Game.spy_rounds >= 3).count()

		self.assertEqual(resistance_wins/total_games, 3/4)
		self.assertEqual(spy_wins/total_games, 1/4)


if __name__ == '__main__':
	unittest.main()