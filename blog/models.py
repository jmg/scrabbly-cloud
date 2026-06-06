from django.db import models
from django.urls import reverse
from django.utils import timezone


class Post(models.Model):
    """An SEO-oriented blog article. Body is trusted HTML authored in the admin."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    excerpt = models.CharField(max_length=300, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    body = models.TextField(help_text="HTML")
    language = models.CharField(max_length=5, default="es")
    published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at"]

    def get_absolute_url(self):
        return reverse("blog_post", args=[self.slug])

    @property
    def description(self):
        return self.meta_description or self.excerpt

    def __str__(self):
        return self.title
