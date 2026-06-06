from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("game.api_urls")),
    path("", include("billing.urls")),
    path("", include("accounts.urls")),
    path("", include("game.urls")),
]
