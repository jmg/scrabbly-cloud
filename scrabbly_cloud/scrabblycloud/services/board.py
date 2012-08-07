from django.db.models import Q
from scrabblycloud.models import Board, Tile

from base import BaseService

class BoardService(BaseService):

    entity = Board

    def save(self, board, word, current_player):

        for tile in word.tiles:

            tile = Tile(x=tile.x, y=tile.y, letter=tile.char)
            tile.save()

            board.tiles.add(tile)

        board.turn = self._get_next_player(board, current_player)
        board.save()
        return board

    def _get_next_player(self, board, current_player):

        players = board.players.filter(~Q(remote_id=current_player.remote_id))
        return players[0]

    def _get_tile(self, x, y, tiles):

        context = {"x": x, "y": y}
        
        x, y = int(x), int(y)
        for tile in tiles:
            if tile.x == x and tile.y == y:
                context["letter"] = tile.letter

        return self.render("board/_tile.html", context)

    def get_tiles(self, board_model):

        tiles = []
        for y in range(board_model.height):
            row = []
            for x in range(board_model.width):
                row.append(self._get_tile(x, y, board_model.tiles.all()))

            tiles.append(row)

        return tiles

    def empty(self, board):

        for tile in board.tiles.all():
            tile.delete()

    def is_player_turn(self, current_player, board):

        return current_player.id == board.turn.id