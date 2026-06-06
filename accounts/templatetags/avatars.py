"""Deterministic identicon avatars rendered as inline SVG.

No uploads or external services: an avatar is derived purely from a seed
(username or id), so it is stable and free to generate anywhere.
"""

import hashlib

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

GRID = 5  # 5x5, horizontally symmetric


@register.filter
def avatar(seed, size=40):
    seed = str(seed)
    digest = hashlib.md5(seed.encode("utf-8")).digest()
    hue = digest[0] * 360 // 256
    fg = f"hsl({hue}, 55%, 58%)"
    bg = "#2e2c28"

    cells = set()
    for row in range(GRID):
        for col in range((GRID + 1) // 2):
            if digest[row * 3 + col] & 1:
                cells.add((row, col))
                cells.add((row, GRID - 1 - col))

    unit = 100 / GRID
    rects = "".join(
        f'<rect x="{c * unit:.1f}" y="{r * unit:.1f}" '
        f'width="{unit:.1f}" height="{unit:.1f}"/>'
        for r, c in cells
    )
    svg = (
        f'<svg class="avatar" width="{size}" height="{size}" viewBox="0 0 100 100" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        f'<rect width="100" height="100" rx="14" fill="{bg}"/>'
        f'<g fill="{fg}">{rects}</g></svg>'
    )
    return mark_safe(svg)
