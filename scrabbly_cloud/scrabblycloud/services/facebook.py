from base import BaseService
from scrabblycloud.models import Player, User

from pyfb import Pyfb
from settings import FACEBOOK_CONFIG
from django.contrib.auth import logout, login, authenticate


class FacebookService(BaseService):

    entity = Player

    def login(self, user, request):

        user = authenticate(username=user)
        login(request, user)

    def logout(self, request):

        logout(request)

    def save(self, access_token, request):

        pyfb = Pyfb(FACEBOOK_CONFIG["id"], access_token=access_token)
        me = pyfb.get_myself()

        user, created = User.objects.get_or_create(username=me.name, email=me.email)

        if created:
            user.save()
            player = self.new(remote_id=me.id, user=user)
            player.save()

        self.login(user, request)
        return user