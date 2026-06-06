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


def blog_index(request):
    posts = Post.objects.filter(published=True)
    return render(request, "blog/index.html", {"posts": posts})


def blog_post(request, slug):
    post = get_object_or_404(Post, slug=slug, published=True)
    related = Post.objects.filter(published=True).exclude(pk=post.pk)[:4]
    return render(request, "blog/post.html", {"post": post, "related": related})
