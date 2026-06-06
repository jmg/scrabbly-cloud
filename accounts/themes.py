"""Board themes. Only "classic" is free; the rest require Premium."""

THEMES = [
    {"code": "classic", "name": "Clásico", "premium": False},
    {"code": "wood", "name": "Madera", "premium": True},
    {"code": "midnight", "name": "Medianoche", "premium": True},
    {"code": "forest", "name": "Bosque", "premium": True},
    {"code": "contrast", "name": "Alto contraste", "premium": True},
]

THEME_CODES = {t["code"] for t in THEMES}
PREMIUM_THEMES = {t["code"] for t in THEMES if t["premium"]}
