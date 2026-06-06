from django.urls import path

from . import views

urlpatterns = [
    path("blog/", views.blog_index, name="blog"),
    path("blog/<slug:slug>/", views.blog_post, name="blog_post"),
]
