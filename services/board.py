from models import db, Board, Tile
from base import BaseService

class BoardService(BaseService):

    entity = Board

    def save(self, board, word):

        db.session.add(board)

        for tile in word.tiles:

            tile_model = Tile(x=tile.x, y=tile.y, letter=tile.char)
            db.session.add(tile_model)

            board.tiles.append(tile_model)

        db.session.commit()

    def empty(self, board):

        db.session.add(board)

        for tile in board.tiles:
            db.session.delete(tile)

        db.session.commit()
