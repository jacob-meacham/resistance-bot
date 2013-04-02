from sqlalchemy import *
from migrate import *

from migrate.changeset import schema
pre_meta = MetaData()
post_meta = MetaData()
player = Table('player', post_meta,
    Column('id', Integer, primary_key=True, nullable=False),
    Column('name', String(length=80)),
    Column('win_percent', Float),
    Column('total_wins', Integer),
    Column('total_losses', Integer),
    Column('spy_wins', Integer),
    Column('spy_losses', Integer),
    Column('resistance_wins', Integer),
    Column('resistance_losses', Integer),
)


def upgrade(migrate_engine):
    # Upgrade operations go here. Don't create your own engine; bind
    # migrate_engine to your metadata
    pre_meta.bind = migrate_engine
    post_meta.bind = migrate_engine
    post_meta.tables['player'].columns['total_wins'].create()
    post_meta.tables['player'].columns['total_losses'].create()
    post_meta.tables['player'].columns['win_percent'].create()


def downgrade(migrate_engine):
    # Operations to reverse the above upgrade go here.
    pre_meta.bind = migrate_engine
    post_meta.bind = migrate_engine
    post_meta.tables['player'].columns['total_wins'].drop()
    post_meta.tables['player'].columns['total_losses'].drop()
    post_meta.tables['player'].columns['win_percent'].drop()
