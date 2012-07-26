from django.db import models


class Tile(models.Model):

    x = models.PositiveIntegerField()
    y = models.PositiveIntegerField()
    letter = models.CharField(max_length=1)


class Player(models.Model):

    name = models.CharField(max_length=500)


class Board(models.Model):

    tiles = models.ManyToManyField('Tile')
    players = models.ManyToManyField('Player')

    height = models.PositiveIntegerField()
    width = models.PositiveIntegerField()