from flask.ext.admin import Admin
from flask.ext.admin.contrib.sqlamodel import ModelView

from app import app
from models import *

admin = Admin(app)
admin.add_view(ModelView(Board, db.session))
admin.add_view(ModelView(Tile, db.session))
admin.add_view(ModelView(Player, db.session))