from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class DummyAuthBackend(ModelBackend):

    def authenticate(self, username=None, password=None):

        return username