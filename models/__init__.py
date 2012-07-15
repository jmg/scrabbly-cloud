import os

from flask.ext.sqlalchemy import SQLAlchemy
from app import app

app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:////%s/base.sqlite" % os.getcwd())
db = SQLAlchemy(app)

tiles = db.Table('tiles',
    db.Column('tile_id', db.Integer, db.ForeignKey('tile.id')),
    db.Column('board_id', db.Integer, db.ForeignKey('board.id'))
)


def save(self):
    db.session.add(self)
    db.session.commit()

db.Model.save = save


class Tile(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    x = db.Column(db.Integer)
    y = db.Column(db.Integer)
    letter = db.Column(db.String(1))

class Board(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    tiles = db.relationship('Tile', secondary=tiles, backref=db.backref('tiles', lazy='dynamic'))


