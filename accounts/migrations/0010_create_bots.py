"""Give every difficulty level its bot account, identified by bot_level.

Bots used to be looked up by username, so whoever registered "IA-Experta"
became the computer. Here each level gets a flagged account:

* an existing bot (is_bot) with the level's name is tagged with its level;
* otherwise a new bot is created under that name, or, when a person already
  holds the name, under "<name>-bot" (the shown name comes from the level).

A person's account is never turned into a bot. Values are copied here, not
imported from accounts.bots, so this migration keeps working if they change.
"""

from django.contrib.auth.hashers import make_password
from django.db import migrations

BOT_LEVELS = {
    "beginner": ("IA-Principiante", 700),
    "easy": ("IA-Fácil", 1000),
    "medium": ("IA-Media", 1400),
    "hard": ("IA-Difícil", 1800),
    "expert": ("IA-Experta", 2100),
}


def _free_username(User, name):
    candidates = [name, f"{name}-bot"] + [f"{name}-bot-{i}" for i in range(2, 100)]
    for candidate in candidates:
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
    raise RuntimeError(f"no free username for bot {name!r}")


def create_bots(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for level, (name, rating) in BOT_LEVELS.items():
        if User.objects.filter(is_bot=True, bot_level=level).exists():
            continue
        legacy = User.objects.filter(is_bot=True, bot_level="", username=name).first()
        if legacy is not None:
            legacy.bot_level = level
            legacy.save(update_fields=["bot_level"])
            continue
        User.objects.create(
            username=_free_username(User, name), password=make_password(None),
            is_bot=True, bot_level=level, rating=rating,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_user_bot_level"),
    ]

    operations = [
        migrations.RunPython(create_bots, migrations.RunPython.noop),
    ]
