from django.test import Client, TestCase

from .models import Post


class BlogTests(TestCase):
    def setUp(self):
        self.c = Client()
        self.c.get("/")  # provision a guest so nav renders

    def test_seed_posts_exist(self):
        self.assertGreaterEqual(Post.objects.filter(published=True).count(), 4)

    def test_index_lists_posts(self):
        r = self.c.get("/blog/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Cómo jugar al Scrabble online")

    def test_post_detail_has_seo(self):
        post = Post.objects.first()
        r = self.c.get(post.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, post.title)
        self.assertContains(r, 'property="og:type" content="article"')
        self.assertContains(r, "application/ld+json")
        self.assertContains(r, post.description)

    def test_unpublished_is_404(self):
        p = Post.objects.create(slug="secreto", title="X", body="x", published=False)
        self.assertEqual(self.c.get(p.get_absolute_url()).status_code, 404)

    def test_sitemap_includes_posts(self):
        r = self.c.get("/sitemap.xml")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "/blog/como-jugar-scrabble-online/")
        self.assertContains(r, "/puzzles/")

    def test_robots_txt(self):
        r = self.c.get("/robots.txt")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Sitemap:")
        self.assertEqual(r["Content-Type"], "text/plain")
