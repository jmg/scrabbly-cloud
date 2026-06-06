from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed

from .models import Post


class BlogFeed(Feed):
    feed_type = Rss201rev2Feed
    title = "Scrabbly — Blog de Scrabble"
    description = "Estrategias, trucos y guías de Scrabble."

    def link(self):
        return reverse("blog")

    def items(self):
        return Post.objects.filter(published=True)[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.description or item.excerpt

    def item_link(self, item):
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.published_at
