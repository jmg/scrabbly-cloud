from scrabblycloud.models import Board, Tile

from base import BaseService

class BoardService(BaseService):

    entity = Board

    def save(self, board, word):

        for tile in word.tiles:

            tile = Tile(x=tile.x, y=tile.y, letter=tile.char)
            tile.save()

            board.tiles.add(tile)

        board.save()

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