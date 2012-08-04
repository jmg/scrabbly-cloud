import simplejson as json
from base import BaseView

from scrabblycloud.services.board import BoardService
from scrabblycloud.services.game import ScrabblyService


class BoardsView(BaseView):    

    url = "^boards$"

    def render_to_response(self, context):
        
        context["boards"] = BoardService().all()
        return BaseView.render_to_response(self, context)


class BoardView(BaseView):

    url = "^boards/(?P<board_id>\d+)/$"

    def render_to_response(self, context):

        board_model = BoardService().get_object_or_404(id=self.kwargs["board_id"])
        board = ScrabblyService().new(board_model, self.request)

        context = {}
        context["letters"] = ScrabblyService().letters()
        context["board"] = board_model
        context["tiles"] = BoardService().get_tiles(board_model)

        return BaseView.render_to_response(self, context)


class PlayView(BaseView):
    
    def post(self, *args, **kwargs):

        data = self.request.POST["letters"]
        tiles = json.loads(data)

        board = BoardService().get(id=self.request.POST["board_id"])
        response = ScrabblyService().play(board, tiles, data, self.request)

        return self.json_response(response)


class RestartView(BaseView):

    def post(self, *args, **kwargs):

        board_model = BoardService().get(id=self.request.POST["board_id"])
        BoardService().empty(board_model)

        return self.response("ok")
