from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Password reset (email-based), using Django's built-in views.
    path("password/reset/", auth_views.PasswordResetView.as_view(
        success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(),
         name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        success_url=reverse_lazy("password_reset_complete")),
        name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(),
         name="password_reset_complete"),

    path("settings/", views.settings_view, name="settings"),
    path("settings/account/", views.update_account, name="update_account"),
    path("settings/password/", views.change_password, name="change_password"),
    path("settings/delete/", views.delete_account, name="delete_account"),
    path("settings/theme/", views.set_theme, name="set_theme"),
    path("notifications/", views.notifications, name="notifications"),
    path("friends/", views.friends, name="friends"),
    path("friends/request/", views.friend_request, name="friend_request"),
    path("friends/respond/", views.friend_respond, name="friend_respond"),
    path("friends/remove/", views.friend_remove, name="friend_remove"),
    path("@/<str:username>/", views.profile, name="profile"),
]
