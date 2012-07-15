from models import Board, Tile

class BoardService(object):

    entity = Board

    def all(self):

        return self.entity.query.all()

    def get_or_404(self, board_id):

        return self.entity.query.get_or_404(board_id)

    def save(self, board_model, word):

        board_model.save()

        for tile in word.tiles:

            tile_model = Tile(x=tile.x, y=tile.y, letter=tile.char)
            tile_model.save()

            board_model.tiles.append(tile_model)
