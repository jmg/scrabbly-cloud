from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Post


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /premium/manage/",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size):
    from PIL import ImageFont
    for path in _FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def og_image(request, slug):
    """A 1200×630 social share card rendered per post."""
    post = get_object_or_404(Post, slug=slug, published=True)
    from PIL import Image, ImageDraw
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (22, 21, 18))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 14], fill=(98, 153, 36))
    d.text((60, 56), "♟ Scrabbly", font=_font(40), fill=(240, 180, 40))
    big = _font(66)
    y = 200
    for line in _wrap(d, post.title, big, W - 120)[:4]:
        d.text((60, y), line, font=big, fill=(245, 245, 245))
        y += 84
    d.text((60, H - 72), "scrabblycloud.com", font=_font(34), fill=(150, 150, 150))
    resp = HttpResponse(content_type="image/png")
    img.save(resp, "PNG")
    resp["Cache-Control"] = "public, max-age=86400"
    return resp


def blog_index(request):
    posts = Post.objects.filter(published=True)
    return render(request, "blog/index.html", {"posts": posts})


def blog_post(request, slug):
    post = get_object_or_404(Post, slug=slug, published=True)
    related = Post.objects.filter(published=True).exclude(pk=post.pk)[:4]
    return render(request, "blog/post.html", {"post": post, "related": related})
