from base import BaseView
from scrabblycloud.services.facebook import FacebookService


class BaseUserView(BaseView):

    service = FacebookService()


class IndexView(BaseUserView):

    url = r"^$"

    def get(self, *args, **kwargs):

        return self.render_to_response({})


class FacebookLoginSuccessView(BaseUserView):

    template_name = "board/_user.html"

    def post(self, *args, **kwargs):

        user = self.service.save(self.request.POST["accessToken"], self.request)
        return self.json_response({"url": "/boards"});


class LogoutView(BaseUserView):

    def get(self, *args, **kwargs):

        self.service.logout(self.request)
        return self.redirect("/")