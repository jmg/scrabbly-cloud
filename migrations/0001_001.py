
import datetime
from flask import current_app
from flask.ext.evolution import BaseMigration
from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy(current_app)
db.metadata.bind = db.engine


class Migration(BaseMigration):
    def up(self):

        # self.execute("ALTER TABLE table_name DROP COLUMN column_name;")
        # self.execute("CREATE INDEX column_name_idx ON table_name (column_name ASC NULLS LAST);")
        # MyModel.__table__.create()
        # MyModel.__table__.drop()
        pass

    def down(self):
        raise IrreversibleMigration("down is not defined")
