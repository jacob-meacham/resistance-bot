from sqlalchemy import *
from migrate import *


from migrate.changeset import schema
pre_meta = MetaData()
post_meta = MetaData()
player = Table('player', post_meta,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('name', String(length=80)),
    Column('spy_wins', Integer),
    Column('spy_losses', Integer),
    Column('resistance_wins', Integer),
    Column('resistance_losses', Integer),
)

game = Table('game', post_meta,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('num_players', Integer),
    Column('date', Date),
    Column('resistance_rounds', Integer),
    Column('spy_rounds', Integer),
)


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    pre_meta.bind = migrate_engine
    post_meta.bind = migrate_engine
    post_meta.tables['player'].columns['name'].create()
    post_meta.tables['player'].columns['resistance_losses'].create()
    post_meta.tables['player'].columns['resistance_wins'].create()
    post_meta.tables['player'].columns['spy_losses'].create()
    post_meta.tables['player'].columns['spy_wins'].create()
    post_meta.tables['game'].columns['date'].create()
    post_meta.tables['game'].columns['num_players'].create()
    post_meta.tables['game'].columns['resistance_rounds'].create()
    post_meta.tables['game'].columns['spy_rounds'].create()


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pre_meta.bind = migrate_engine
    post_meta.bind = migrate_engine
    post_meta.tables['player'].columns['name'].drop()
    post_meta.tables['player'].columns['resistance_losses'].drop()
    post_meta.tables['player'].columns['resistance_wins'].drop()
    post_meta.tables['player'].columns['spy_losses'].drop()
    post_meta.tables['player'].columns['spy_wins'].drop()
    post_meta.tables['game'].columns['date'].drop()
    post_meta.tables['game'].columns['num_players'].drop()
    post_meta.tables['game'].columns['resistance_rounds'].drop()
    post_meta.tables['game'].columns['spy_rounds'].drop()
