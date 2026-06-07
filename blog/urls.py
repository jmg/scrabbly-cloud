from django.urls import path

from . import views
from .feeds import BlogFeed

urlpatterns = [
    path("search/", views.search, name="search"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("healthz", views.healthz, name="healthz"),
    path("blog/", views.blog_index, name="blog"),
    path("blog/feed/", BlogFeed(), name="blog_feed"),
    path("blog/<slug:slug>/", views.blog_post, name="blog_post"),
    path("blog/<slug:slug>/og.png", views.og_image, name="blog_og"),
]
