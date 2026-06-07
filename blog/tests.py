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

    def test_more_posts_seeded(self):
        self.assertGreaterEqual(Post.objects.filter(published=True).count(), 9)

    def test_og_image_is_png(self):
        post = Post.objects.first()
        r = self.c.get(f"{post.get_absolute_url()}og.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertTrue(r.content[:8] == b"\x89PNG\r\n\x1a\n")

    def test_post_has_og_image_and_hreflang(self):
        post = Post.objects.first()
        html = self.c.get(post.get_absolute_url()).content.decode()
        self.assertIn("/og.png", html)
        self.assertIn('hreflang="es"', html)
        self.assertIn('hreflang="en"', html)
        self.assertIn('twitter:card" content="summary_large_image"', html)

    def test_rss_feed(self):
        r = self.c.get("/blog/feed/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/rss+xml", r["Content-Type"])
        self.assertContains(r, "Scrabbly")

    def test_hl_query_switches_language(self):
        r = self.c.get("/blog/?hl=en")
        self.assertContains(r, "Scrabble Blog")

    def test_english_posts_exist_and_paired(self):
        es = Post.objects.get(slug="como-jugar-scrabble-online")
        en = Post.objects.get(slug="how-to-play-scrabble-online")
        self.assertEqual(es.translation_group, en.translation_group)
        self.assertEqual(en.language, "en")

    def test_index_filters_by_language(self):
        en_html = self.c.get("/blog/?hl=en").content.decode()
        self.assertIn("How to play Scrabble online", en_html)
        self.assertNotIn("Cómo jugar al Scrabble online", en_html)

    def test_post_hreflang_points_to_translation(self):
        html = self.c.get("/blog/como-jugar-scrabble-online/").content.decode()
        self.assertIn('hreflang="en"', html)
        self.assertIn("/blog/how-to-play-scrabble-online/", html)
        self.assertIn("BreadcrumbList", html)

    def test_site_og_image(self):
        r = self.c.get("/og.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "image/png")
        self.assertTrue(r.content[:8] == b"\x89PNG\r\n\x1a\n")

    def test_default_og_image_on_pages(self):
        # A non-blog page advertises the site OG image.
        html = Client().get("/").content.decode()
        self.assertIn("/og.png", html)
        self.assertIn('twitter:card" content="summary_large_image"', html)

    def test_post_overrides_og_image(self):
        post = Post.objects.first()
        html = self.c.get(post.get_absolute_url()).content.decode()
        self.assertIn("/og.png", html)        # the post's own og.png
        self.assertNotIn('content="http://testserver/og.png"', html)  # not the site default

    def test_manifest(self):
        r = self.c.get("/site.webmanifest")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/manifest+json", r["Content-Type"])
        self.assertContains(r, "Scrabbly")

    def test_landing_for_new_guest(self):
        html = Client().get("/").content.decode()
        self.assertIn("hero", html)
        self.assertIn("FAQPage", html)

    def test_website_searchaction_present(self):
        html = self.c.get("/blog/").content.decode()
        self.assertIn('"WebSite"', html)
        self.assertIn("/search/?q={search_term_string}", html)
        self.assertIn('"Organization"', html)

    def test_search_finds_player_and_post(self):
        from django.contrib.auth import get_user_model
        get_user_model().objects.create_user("findme", password="x")
        self.assertContains(self.c.get("/search/?q=findme"), "findme")
        self.assertContains(self.c.get("/search/?q=Scrabble"), "Scrabble")

    def test_healthz(self):
        r = self.c.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"ok")

    def test_legal_pages(self):
        self.assertContains(self.c.get("/terms/"), "Scrabbly")
        self.assertContains(self.c.get("/privacy/"), "Stripe")

    def test_footer_legal_links(self):
        html = self.c.get("/blog/").content.decode()
        self.assertIn("/terms/", html)
        self.assertIn("/privacy/", html)

    def test_favicon_and_manifest_linked(self):
        html = self.c.get("/blog/").content.decode()
        self.assertIn("favicon.svg", html)
        self.assertIn("/site.webmanifest", html)
        self.assertIn('name="theme-color"', html)
