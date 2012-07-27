from django.db import models


class Tile(models.Model):

    x = models.PositiveIntegerField(null=True)
    y = models.PositiveIntegerField(null=True)
    letter = models.CharField(max_length=1)


class Player(models.Model):

    name = models.CharField(max_length=500)


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