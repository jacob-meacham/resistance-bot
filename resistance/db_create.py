from migrate.versioning import api
from settings import SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO
from stats import db, Base
import os.path

print SQLALCHEMY_DB_URI
Base.metadata.create_all(db)
if not os.path.exists(SQLALCHEMY_MIGRATE_REPO):
	api.create(SQLALCHEMY_MIGRATE_REPO, 'migration repository')
	api.version_control(SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO)
else:
	api.version_control(SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO, api.version(SQLALCHEMY_MIGRATE_REPO))