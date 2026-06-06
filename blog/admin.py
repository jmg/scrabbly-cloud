from django.contrib import admin

from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "language", "published", "published_at")
    list_filter = ("published", "language")
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}
