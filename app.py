from juggernaut import Juggernaut

from flask import Flask, render_template, request, session
app = Flask(__name__)
app.config.update(SECRET_KEY="fhdsjfhsdkjfhsk432853487")

import simplejson as json
from scrabbly import Dictionary, Board, Player, Tile, Word, InvalidPlayError


@app.route("/", methods=['GET'])
def index():

    context = {}
    context["letters"] = sorted([letter.decode("utf-8") for letter in Dictionary.letters.keys()])

    size = (15, 15)
    board = Board(size, [Player("jm")])
    context["width"], context["height"] = size

    session["board"] = board

    return render_template('index.html', **context)


@app.route("/board/play/", methods=['POST'])
def play():

    data = request.form["letters"]
    tiles = json.loads(data)

    word = Word([Tile(tile["letter"], (int(tile["x"]), int(tile["y"]))) for tile in tiles])
    board = session["board"]

    try:
        board.play(word)

        jug = Juggernaut()
        jug.publish('play', data)

        response = {"status": "ok"}
    except InvalidPlayError, e:
        response = {"status": "error", "message": unicode(e) }

    return json.dumps(response)


if __name__ == '__main__':
    app.run(debug=True)


