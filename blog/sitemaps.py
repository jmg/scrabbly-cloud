from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Post


class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return Post.objects.filter(published=True)

    def lastmod(self, obj):
        return obj.updated_at


class StaticSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return ["lobby", "pricing", "puzzles", "arenas", "blog"]

    def location(self, name):
        return reverse(name)


SITEMAPS = {"posts": PostSitemap, "static": StaticSitemap}
