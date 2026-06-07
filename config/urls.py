from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

from blog.sitemaps import SITEMAPS
from blog.views import manifest, robots_txt, site_og

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),  # set_language view
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("site.webmanifest", manifest, name="manifest"),
    path("og.png", site_og, name="site_og"),
    path("api/", include("game.api_urls")),
    path("", include("billing.urls")),
    path("", include("accounts.urls")),
    path("", include("blog.urls")),
    path("", include("game.urls")),
]
