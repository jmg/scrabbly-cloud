from django.db import models
from django.contrib.auth.models import User


class Tile(models.Model):

    x = models.PositiveIntegerField(null=True)
    y = models.PositiveIntegerField(null=True)
    letter = models.CharField(max_length=1)


class Player(models.Model):

    user = models.ForeignKey(User)

    name = models.CharField(max_length=500)
    remote_id = models.CharField(max_length=100)

    def picture(self):

        return "https://graph.facebook.com/%s/picture" % self.remote_id


class PlayerBoard(models.Model):

    player = models.ForeignKey("Player")
    Board = models.ForeignKey("Board")

    points = models.PositiveIntegerField()
    tiles = models.ManyToManyField("Tile")


class Board(models.Model):

    tiles = models.ManyToManyField('Tile')
    players = models.ManyToManyField('Player', through="PlayerBoard")

    height = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
