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
    board = models.ForeignKey("Board")    

    points = models.PositiveIntegerField(default=0)
    tiles = models.ManyToManyField("Tile", null=True, blank=True)


class Board(models.Model):

    tiles = models.ManyToManyField('Tile', null=True, blank=True)
    players = models.ManyToManyField('Player', through="PlayerBoard")

    height = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    turn = models.ForeignKey("Player", null=True, blank=True, related_name="player_turn")
