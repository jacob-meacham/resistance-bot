import imp
from migrate.versioning import api
from settings import SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO
from stats import db, Base

migration = SQLALCHEMY_MIGRATE_REPO + '/versions/%03d_migration.py' % (api.db_version(SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO) + 1)

tmp_module = imp.new_module('old_model')
old_model = api.create_model(SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO)

exec old_model in tmp_module.__dict__

script = api.make_update_script_for_model(SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO, tmp_module.meta, Base.metadata)
open(migration, "wt").write(script)
a = api.upgrade(SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO)

print 'New migration saved as ' + migration
print 'Current DB version: ' + str(api.db_version(SQLALCHEMY_DB_URI, SQLALCHEMY_MIGRATE_REPO))