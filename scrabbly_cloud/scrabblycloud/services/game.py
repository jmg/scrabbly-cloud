from scrabbly import Dictionary, Board, Player, Tile, Word, InvalidPlayError

from scrabblycloud.services.realtime import RealTimeService
from scrabblycloud.services.board import BoardService
from scrabblycloud.services.playerboard import PlayerBoardService
from scrabblycloud.services.tile import TileService

from settings import SCRABBLE_RULES


class ScrabblyService(object):

    def letters(self):

        return sorted([letter.decode("utf-8") for letter in Dictionary("spanish").letters.keys()])

    def _add_current_player(self, players_model, board_model, current_player):

        if current_player not in players_model:
            PlayerBoardService.new(board=board_model, player=current_player).save()

        if board_model.turn is None:
            board_model.turn = current_player

    def reload_tiles(self, current_player, board_model, board):

        player_board = PlayerBoardService().get(board=board_model, player=current_player)
        tiles_count = player_board.tiles.count()

        if tiles_count < SCRABBLE_RULES["max_tiles_per_player"]:

            letters = board.get_random_tiles(SCRABBLE_RULES["max_tiles_per_player"] - tiles_count)

            for letter in letters:
                tile = TileService().new(letter=letter, x=0, y=0)
                tile.save()
                player_board.tiles.add(tile)

            player_board.save()

        return player_board

    def new(self, board_model, current_player):

        players_model = board_model.players.all()
        self._add_current_player(players_model, board_model, current_player)

        players = [Player(id=player.remote_id, name=player.name) for player in players_model]
        size = (board_model.width, board_model.height)

        board = Board(size, players, language="spanish")
        player_board = self.reload_tiles(current_player, board_model, board)

        return board, player_board

    def play(self, board_model, tiles, current_player):

        if board_model.turn.id != current_player.id:
            return {"status": "error", "message": "Is not your turn!" }

        board, player_board = self.new(board_model, current_player)

        matrix = dict([((tile.x, tile.y), Tile(tile.letter, (tile.x, tile.y))) for tile in board_model.tiles.all()])
        board.matrix.update(matrix)

        word_tiles = []
        tiles_model = []

        for tile in tiles:
                    
            tile_model = TileService().get(id=tile["id"])
            tiles_model.append(tile_model)
            word_tiles.append(Tile(tile_model.letter, (int(tile["x"]), int(tile["y"]))))
        
        word = Word(word_tiles)

        try:
            points = board.play(word)

            total_points = PlayerBoardService().update_board_state(board_model, points, current_player)
            board_model = BoardService().save(board_model, word, current_player)

            for tile, tile_model in zip(tiles, tiles_model):
                tile["letter"] = tile_model.letter
                tile_model.delete()

            RealTimeService().publish('play', tiles=tiles, player=current_player.remote_id, points=total_points)

            return {"status": "ok", "points": total_points, "next_player": board_model.turn.user.username}

        except InvalidPlayError, e:

            return {"status": "error", "message": unicode(e) }
