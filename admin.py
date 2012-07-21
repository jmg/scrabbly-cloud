from flask.ext.admin import Admin
from flask.ext.admin.contrib.sqlamodel import ModelView
from flask.ext import wtf

from app import app
from models import *

admin = Admin(app)

class BoardAdmin(ModelView):

	form_args = dict(	
        players=dict(validators=[wtf.Optional()]),
        tiles=dict(validators=[wtf.Optional()])
    )

class PlayerAdmin(ModelView):

	form_args = dict(
        players=dict(validators=[wtf.Optional()])
    )

class TileAdmin(ModelView):

	form_args = dict(
        tiles=dict(validators=[wtf.Optional()])
    )

admin.add_view(BoardAdmin(Board, db.session))
admin.add_view(PlayerAdmin(Player, db.session))
admin.add_view(TileAdmin(Tile, db.session))