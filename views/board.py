import simplejson as json

from flask import render_template, request, session, make_response

from app import app

from services.board import BoardService
from services.game import ScrabblyService


@app.route("/", methods=['GET'])
def index():

    boards = BoardService().all()
    return render_template('boards.html', boards=boards)


@app.route("/boards/<board_id>/", methods=['GET'])
def board(board_id):

    size = (15, 15)
    board = ScrabblyService().new(size, ["jm"])

    board_model = BoardService().get_or_404(board_id)

    session["board"] = board
    session["board_model"] = board_model

    context = {}
    context["letters"] = ScrabblyService().letters()
    context["width"], context["height"] = size
    return render_template('board.html', **context)


@app.route("/board/play/", methods=['POST'])
def play():

    data = request.form["letters"]
    tiles = json.loads(data)

    board = session["board"]
    board_model = session["board_model"]

    response = ScrabblyService().play(board, board_model, tiles, data, session)

    return json.dumps(response)
