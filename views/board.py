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

    board_model = BoardService().get_or_404(board_id)
    board = ScrabblyService().new((15, 15), ["jm"])

    context = {}
    context["letters"] = ScrabblyService().letters()
    context["board"] = board_model
    context["width"], context["height"] = board.height, board.width
    return render_template('board.html', **context)


@app.route("/board/play/", methods=['POST'])
def play():

    data = request.form["letters"]
    tiles = json.loads(data)

    board = BoardService().get(request.form["board_id"])
    response = ScrabblyService().play(board, tiles, data)

    return json.dumps(response)


@app.route("/board/restart/", methods=['POST'])
def restart():

    board_model = BoardService().get(request.form["board_id"])
    BoardService().empty(board_model)

    return "ok"
