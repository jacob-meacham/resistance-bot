import datetime
import random
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from stats import Base, Player, Game

class GenerateTestStats:
	def __init__(self, db_path):
		print db_path
		self.db = create_engine(db_path)
		Base.metadata.create_all(self.db)
		self.Session = sessionmaker(bind=self.db)
		self.players = []

		self.generate_test_players(15)
		self.generate_test_games(num=1000, 
			start_time=datetime.datetime.now() - datetime.timedelta(days=45), 
			end_time=datetime.datetime.now())

	def generate_test_players(self, num):
		session = self.Session()
		for x in xrange(num):
			p = Player(name=str(x))
			self.players.append(p)

	def generate_test_games(self, num, start_time, end_time):
		session = self.Session()
		cur_time = start_time
		total_delta = end_time-start_time
		delta = datetime.timedelta(seconds=total_delta.total_seconds()/num)
		for x in xrange(num):
			# pick a random group of players
			num_players = random.randint(4, len(self.players))
			cur_players = random.sample(self.players, num_players)
			spies = random.sample(cur_players, random.randint(2, 3))
			resistance = [p for p in cur_players if p not in spies]

			resistance_rounds = random.randint(0, 3)
			spy_rounds = min(3, random.randint(0, 5 - resistance_rounds))
			g = Game(num_players=num_players, date=cur_time, 
				resistance_rounds=resistance_rounds, 
				spy_rounds=spy_rounds)

			cur_time = cur_time + delta

			for p in cur_players:
				g.players.append(p)

			if resistance_rounds >= 3:
				for spy in spies:
					spy.spy_losses = spy.spy_losses + 1

				for res in resistance:
					res.resistance_wins = res.resistance_wins + 1
			else:
				for spy in spies:
					spy.spy_wins = spy.spy_wins + 1

				for res in resistance:
					res.resistance_wins = res.resistance_wins + 1

			# Add the players to the session, and then commit.
			session.add(g)
			for p in cur_players:
				session.add(p)

		session.commit()

if __name__ == '__main__':
	GenerateTestStats('sqlite:///' + sys.argv[1])