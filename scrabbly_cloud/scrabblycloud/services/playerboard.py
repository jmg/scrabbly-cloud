from base import BaseService
from scrabblycloud.models import PlayerBoard


class PlayerBoardService(BaseService):

    entity = PlayerBoard

    def update_board_state(self, board, points, current_player):

        player_board = self.get(player=current_player, board=board)
        player_board.points += points
        player_board.save()
        return player_board.points