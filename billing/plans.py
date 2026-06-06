"""Premium plan catalogue.

Plans are defined in code (not the DB) so they're easy to version and price.
Amounts are in the currency's minor unit (e.g. cents).
"""

PLANS = {
    "monthly": {
        "name": "Premium mensual",
        "amount": 499,          # $4.99
        "currency": "usd",
        "interval": "month",    # Stripe recurring interval
        "days": 31,             # local entitlement length per period
    },
    "yearly": {
        "name": "Premium anual",
        "amount": 3999,         # $39.99 (2 months free)
        "currency": "usd",
        "interval": "year",
        "days": 366,
    },
}

DEFAULT_PLAN = "monthly"


def get_plan(code):
    return PLANS.get(code)


def price_display(plan):
    return f"${plan['amount'] / 100:.2f}"
