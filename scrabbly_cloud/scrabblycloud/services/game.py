from scrabbly import Dictionary, Board, Player, Tile, Word, InvalidPlayError

from scrabblycloud.services.realtime import RealTimeService
from scrabblycloud.services.board import BoardService
from scrabblycloud.services.playerboard import PlayerBoardService


class ScrabblyService(object):

    def letters(self):

        return sorted([letter.decode("utf-8") for letter in Dictionary("spanish").letters.keys()])

    def _add_current_player(self, players_model, board_model, current_player):

        if current_player not in players_model:
            PlayerBoardService.new(board=board_model, player=current_player).save()

        if board_model.turn is None:
            board_model.turn = current_player

    def new(self, board_model, current_player):

        players_model = board_model.players.all()
        self._add_current_player(players_model, board_model, current_player)

        players = [Player(id=player.remote_id, name=player.name) for player in players_model]
        size = (board_model.width, board_model.height)

        return Board(size, players, language="spanish")

    def play(self, board_model, tiles, data, current_player):

        if board_model.turn.id != current_player.id:
            return {"status": "error", "message": "Is not your turn!" }

        board = self.new(board_model, current_player)

        matrix = dict([((tile.x, tile.y), Tile(tile.letter, (tile.x, tile.y))) for tile in board_model.tiles.all()])
        board.matrix.update(matrix)

        word = Word([Tile(tile["letter"], (int(tile["x"]), int(tile["y"]))) for tile in tiles])

        try:
            points = board.play(word)

            total_points = PlayerBoardService().update_board_state(board_model, points, current_player)
            BoardService().save(board_model, word, current_player)
            RealTimeService().publish('play', data)

            return {"status": "ok", "points": total_points }

        except InvalidPlayError, e:

            return {"status": "error", "message": unicode(e) }
