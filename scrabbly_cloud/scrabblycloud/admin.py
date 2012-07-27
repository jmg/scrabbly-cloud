from django.contrib import admin
from models import Tile, Board, Player, PlayerBoard

admin.site.register(Player)
admin.site.register(Board)
admin.site.register(PlayerBoard)
admin.site.register(Tile)