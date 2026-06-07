"""Deterministic initials avatars rendered as inline SVG.

No uploads or external services: the colour is derived from a hash of the seed
(username) and the glyph is the user's initials, so avatars are stable, legible
and free to generate anywhere.
"""

import hashlib

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def avatar(seed, size=40):
    seed = str(seed)
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    hue = digest[0] * 360 // 256
    bg = f"hsl({hue}, 42%, 45%)"

    letters = [c for c in seed if c.isalnum()]
    initials = ("".join(letters[:2]).upper()) or "?"
    font_size = 46 if len(initials) >= 2 else 54

    svg = (
        f'<svg class="avatar" width="{size}" height="{size}" viewBox="0 0 100 100" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{escape(seed)}">'
        f'<rect width="100" height="100" rx="18" fill="{bg}"/>'
        f'<text x="50" y="50" text-anchor="middle" dominant-baseline="central" '
        f'font-family="Inter, Segoe UI, system-ui, sans-serif" '
        f'font-size="{font_size}" font-weight="700" fill="#fff">{escape(initials)}</text>'
        f'</svg>'
    )
    return mark_safe(svg)
