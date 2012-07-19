import os

from flask.ext.sqlalchemy import SQLAlchemy
from flask import render_template
from app import app

app.config.update(SQLALCHEMY_DATABASE_URI="sqlite:////%s/base.sqlite" % os.getcwd())
db = SQLAlchemy(app)

tiles = db.Table('tiles',
    db.Column('tile_id', db.Integer, db.ForeignKey('tile.id')),
    db.Column('board_id', db.Integer, db.ForeignKey('board.id'))
)

players = db.Table('players',
    db.Column('player_id', db.Integer, db.ForeignKey('player.id')),
    db.Column('board_id', db.Integer, db.ForeignKey('board.id'))
)

class Tile(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    x = db.Column(db.Integer)
    y = db.Column(db.Integer)
    letter = db.Column(db.String(1))


class Player(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(500))


class Board(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    tiles = db.relationship('Tile', secondary=tiles, backref=db.backref('tiles', lazy='dynamic'))
    players = db.relationship('Player', secondary=players, backref=db.backref('players', lazy='dynamic'))

    height = db.Column(db.Integer)
    width = db.Column(db.Integer)

    def get_tile(self, x, y):

        x, y = int(x), int(y)
        for tile in self.tiles:
            if tile.x == x and tile.y == y:
                tem = render_template("_tile.html", letter=tile.letter)
                return tem

        return ""
