import simplejson as json

from flask import render_template, request, session, make_response
from juggernaut import Juggernaut

from app import app
import models

from scrabbly import Dictionary, Board, Player, Tile, Word, InvalidPlayError


@app.route("/", methods=['GET'])
def index():

    boards = models.Board.query.all()

    return render_template('boards.html', boards=boards)


@app.route("/boards/<board_id>/", methods=['GET'])
def board(board_id):

    context = {}
    context["letters"] = sorted([letter.decode("utf-8") for letter in Dictionary.letters.keys()])

    size = (15, 15)
    board = Board(size, [Player("jm")])
    context["width"], context["height"] = size

    board_model = models.Board.query.get_or_404(board_id)

    session["board"] = board
    session["board_model"] = board_model

    return render_template('board.html', **context)


def _save_tiles(board_model, word):

    board_model.save()

    for tile in word.tiles:

        tile_model = models.Tile(x=tile.x, y=tile.y, letter=tile.char)
        tile_model.save()

        board_model.tiles.append(tile_model)


@app.route("/board/play/", methods=['POST'])
def play():

    data = request.form["letters"]
    tiles = json.loads(data)

    word = Word([Tile(tile["letter"], (int(tile["x"]), int(tile["y"]))) for tile in tiles])

    board = session["board"]
    board_model = session["board_model"]

    try:
        board.play(word)

        _save_tiles(board_model, word)

        jug = Juggernaut()
        jug.publish('play', data)

        session["board"] = board

        response = {"status": "ok"}
    except InvalidPlayError, e:
        response = {"status": "error", "message": unicode(e) }

    return json.dumps(response)
