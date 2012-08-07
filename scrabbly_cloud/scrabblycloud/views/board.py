import simplejson as json
from base import BaseView

from scrabblycloud.services.board import BoardService
from scrabblycloud.services.game import ScrabblyService


class BaseBoardView(BaseView):

    service = BoardService()


class BoardsView(BaseBoardView):    

    url = "^boards$"

    def render_to_response(self, context):
        
        context["boards"] = self.service.all()
        return BaseView.render_to_response(self, context)


class BoardView(BaseBoardView):

    url = "^boards/(?P<board_id>\d+)/$"

    def render_to_response(self, context):

        board_model = self.service.get_object_or_404(id=self.kwargs["board_id"])
        board, player_board = ScrabblyService().new(board_model, self.get_current_player())

        context = {"board": board_model, "player_board": player_board }
        context["tiles"] = BoardService().get_tiles(board_model)
        context["is_player_turn"] = self.service.is_player_turn(self.get_current_player(), board_model)

        return BaseView.render_to_response(self, context)


class PlayView(BaseBoardView):
    
    def post(self, *args, **kwargs):

        data = self.request.POST["letters"]
        tiles = json.loads(data)

        board = self.service.get(id=self.request.POST["board_id"])
        response = ScrabblyService().play(board, tiles, data, self.get_current_player())

        return self.json_response(response)


class RestartView(BaseBoardView):

    def post(self, *args, **kwargs):

        board_model = self.service.get(id=self.request.POST["board_id"])
        self.service.empty(board_model)

        return self.response("ok")
