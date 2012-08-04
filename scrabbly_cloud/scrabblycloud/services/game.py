from scrabbly import Dictionary, Board, Player, Tile, Word, InvalidPlayError

from scrabblycloud.services.realtime import RealTimeService
from scrabblycloud.services.board import BoardService

from scrabblycloud.models import PlayerBoard


class ScrabblyService(object):

    def letters(self):

        return sorted([letter.decode("utf-8") for letter in Dictionary("spanish").letters.keys()])

    def _add_current_player(self, players_model, board_model, request):

        current_player = request.user.get_profile()

        if current_player not in players_model:
            PlayerBoard(board=board_model, player=current_player).save()

    def new(self, board_model, request):

        players_model = board_model.players.all()
        self._add_current_player(players_model, board_model, request)

        players = [Player(id=player.remote_id ,name=player.name) for player in players_model]
        size = (board_model.width, board_model.height)

        return Board(size, players, language="spanish")

    def play(self, board_model, tiles, data, request):

        board = self.new(board_model, request)

        matrix = dict([((tile.x, tile.y), Tile(tile.letter, (tile.x, tile.y))) for tile in board_model.tiles.all()])
        board.matrix.update(matrix)

        word = Word([Tile(tile["letter"], (int(tile["x"]), int(tile["y"]))) for tile in tiles])

        try:
            points = board.play(word)

            current_player = request.user.get_profile()
            player_board = PlayerBoard.objects.get(player=current_player, board=board_model)
            player_board.points += points
            player_board.save()

            BoardService().save(board_model, word)
            RealTimeService().publish('play', data)

            return {"status": "ok", "points": player_board.points}

        except InvalidPlayError, e:

            return {"status": "error", "message": unicode(e) }
