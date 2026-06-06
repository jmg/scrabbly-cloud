from django.contrib import admin
from django.urls import include, path
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),  # set_language view
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("api/", include("game.api_urls")),
    path("", include("billing.urls")),
    path("", include("accounts.urls")),
    path("", include("game.urls")),
]
