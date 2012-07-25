from scrabbly import Dictionary, Board, Player, Tile, Word, InvalidPlayError

from scrabblycloud.services.realtime import RealTimeService
from scrabblycloud.services.board import BoardService


class ScrabblyService(object):

    def letters(self):

        return sorted([letter.decode("utf-8") for letter in Dictionary.letters.keys()])

    def new(self, board_model):

        players = [Player(player.name) for player in board_model.players.all()]
        size = (board_model.width, board_model.height)

        return Board(size, players)

    def play(self, board_model, tiles, data):

        board = self.new(board_model)

        matrix = dict([((tile.x, tile.y), Tile(tile.letter, (tile.x, tile.y))) for tile in board_model.tiles.all()])
        board.matrix.update(matrix)

        word = Word([Tile(tile["letter"], (int(tile["x"]), int(tile["y"]))) for tile in tiles])

        try:
            board.play(word)

            BoardService().save(board_model, word)
            RealTimeService().publish('play', data)

            return {"status": "ok"}

        except InvalidPlayError, e:

            return {"status": "error", "message": unicode(e) }
