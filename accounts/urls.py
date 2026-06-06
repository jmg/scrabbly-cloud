from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/theme/", views.set_theme, name="set_theme"),
    path("friends/", views.friends, name="friends"),
    path("friends/request/", views.friend_request, name="friend_request"),
    path("friends/respond/", views.friend_respond, name="friend_respond"),
    path("friends/remove/", views.friend_remove, name="friend_remove"),
    path("@/<str:username>/", views.profile, name="profile"),
]
