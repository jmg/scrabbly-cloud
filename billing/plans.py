"""Premium tiers and plan catalogue.

Two paid tiers (Gold, Diamond) à la chess.com. Tiers gate perks; plans are the
purchasable billing periods for a tier. Amounts are in the currency minor unit.
"""

# Perks a tier unlocks. Diamond is a superset of Gold.
TIERS = {
    "gold": {
        "name": "Gold",
        "rank": 1,
        "perks": {"themes", "stats", "unlimited", "badge"},
    },
    "diamond": {
        "name": "Diamond",
        "rank": 2,
        "perks": {"themes", "stats", "unlimited", "badge", "analysis"},
    },
}

PLANS = {
    "gold_monthly":    {"tier": "gold",    "name": "Gold mensual",    "amount": 499,  "currency": "usd", "interval": "month", "days": 31},
    "gold_yearly":     {"tier": "gold",    "name": "Gold anual",      "amount": 3999, "currency": "usd", "interval": "year",  "days": 366},
    "diamond_monthly": {"tier": "diamond", "name": "Diamond mensual", "amount": 999,  "currency": "usd", "interval": "month", "days": 31},
    "diamond_yearly":  {"tier": "diamond", "name": "Diamond anual",   "amount": 7999, "currency": "usd", "interval": "year",  "days": 366},
    "diamond_lifetime": {"tier": "diamond", "name": "Diamond de por vida", "amount": 19999, "currency": "usd", "interval": None, "days": 36500, "lifetime": True},
}

# Plans purchasable as a one-time gift (no recurring billing).
GIFT_PLANS = {
    "gift_gold_year":    {"tier": "gold",    "name": "Gold (1 año, regalo)",    "amount": 3999, "currency": "usd", "days": 366},
    "gift_diamond_year": {"tier": "diamond", "name": "Diamond (1 año, regalo)", "amount": 7999, "currency": "usd", "days": 366},
}

TRIAL_DAYS = 7


def get_plan(code):
    return PLANS.get(code)


def price_display(plan):
    return f"${plan['amount'] / 100:.2f}"


def tier_has_perk(tier, perk):
    return tier in TIERS and perk in TIERS[tier]["perks"]


def tier_rank(tier):
    return TIERS.get(tier, {}).get("rank", 0)
