from scrabbly import Dictionary, Board, Player, Tile, Word, InvalidPlayError

from services.realtime import RealTimeService
from services.board import BoardService


class ScrabblyService(object):

    def letters(self):

        return sorted([letter.decode("utf-8") for letter in Dictionary.letters.keys()])

    def new(self, size, players, session):

        board = Board(size, [Player(player) for player in players])
        session["board"] = board
        return board

    def play(self, board, board_model, tiles, data, session):

        word = Word([Tile(tile["letter"], (int(tile["x"]), int(tile["y"]))) for tile in tiles])

        try:
            board.play(word)

            BoardService().save(board_model, word)
            RealTimeService().publish('play', data)

            session["board"] = board
            session["board_model"] = board_model

            return {"status": "ok"}

        except InvalidPlayError, e:

            return {"status": "error", "message": unicode(e) }
