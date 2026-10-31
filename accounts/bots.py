"""The computer opponents: one bot account per difficulty level.

A bot is recognised by its flags (``is_bot`` plus ``bot_level``), never by
its username: a person who registered "IA-Experta" must not become the
computer in everyone's games. The name players see comes from the level, so
a bot whose preferred username was already taken keeps an internal one
("IA-Experta-bot") and still shows as "IA-Experta".

Usernames starting with "IA-" are reserved for these accounts.
"""

import unicodedata

from django.db import IntegrityError, transaction

# level -> (name shown to players, starting rating)
BOT_LEVELS = {
    "beginner": ("IA-Principiante", 700),
    "easy": ("IA-Fácil", 1000),
    "medium": ("IA-Media", 1400),
    "hard": ("IA-Difícil", 1800),
    "expert": ("IA-Experta", 2100),
}
DEFAULT_LEVEL = "medium"

RESERVED_PREFIX = "ia-"

# Look-alikes of "I" and "A" (Cyrillic, Greek) that would let someone show up
# as "IA-…" while dodging a plain prefix check.
_CONFUSABLES = str.maketrans({
    "І": "i", "і": "i",  # Cyrillic І і
    "Ι": "i", "ι": "i",  # Greek Ι ι
    "А": "a", "а": "a",  # Cyrillic А а
    "Α": "a", "α": "a",  # Greek Α α
})


def is_reserved_username(name):
    """True for names that look like a bot's ("IA-…", any case or width)."""
    norm = unicodedata.normalize("NFKC", name or "").strip().casefold()
    return norm.translate(_CONFUSABLES).startswith(RESERVED_PREFIX)


def bot_display_name(level):
    return BOT_LEVELS.get(level, BOT_LEVELS[DEFAULT_LEVEL])[0]


def free_bot_username(user_model, name):
    """``name`` if nobody has it (in any case), else ``name-bot``, ``name-bot-2``…"""
    candidates = [name, f"{name}-bot"] + [f"{name}-bot-{i}" for i in range(2, 100)]
    for candidate in candidates:
        if not user_model.objects.filter(username__iexact=candidate).exists():
            return candidate
    raise RuntimeError(f"no free username for bot {name!r}")


def get_bot(level):
    """The bot account for ``level`` (created if it is missing)."""
    from .models import User

    if level not in BOT_LEVELS:
        level = DEFAULT_LEVEL
    bot = User.objects.filter(is_bot=True, bot_level=level).first()
    if bot is not None:
        return bot
    name, rating = BOT_LEVELS[level]
    try:
        with transaction.atomic():
            bot = User(
                username=free_bot_username(User, name),
                is_bot=True, bot_level=level, rating=rating,
            )
            bot.set_unusable_password()
            bot.save()
    except IntegrityError:  # created concurrently: bot_level is unique
        bot = User.objects.get(is_bot=True, bot_level=level)
    return bot
