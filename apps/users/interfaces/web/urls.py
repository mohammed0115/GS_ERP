"""Server-rendered user/auth routes (HTML, session-based).

JWT/API routes live in apps.users.interfaces.http.urls.
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from apps.users.interfaces.web import views as web_views

app_name = "users"
urlpatterns = [
    path("login/",          web_views.OTPLoginView.as_view(),   name="login"),
    path("otp/verify/",    web_views.OTPVerifyView.as_view(),  name="otp_verify"),
    path("otp/resend/",    web_views.OTPResendView.as_view(),  name="otp_resend"),
    path("logout/",     auth_views.LogoutView.as_view(),   name="logout"),
    path("register/",   web_views.RegisterView.as_view(),  name="register"),

    path("password/change/", auth_views.PasswordChangeView.as_view(
        template_name="auth/change_password.html",
        success_url="/accounts/password/change/done/",
    ), name="change_password"),
    path("password/change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="auth/change_password.html",
    ), name="change_password_done"),

    path("password/reset/", auth_views.PasswordResetView.as_view(
        template_name="auth/password_reset.html",
        email_template_name="auth/password_reset_email.txt",
        success_url="/accounts/password/reset/done/",
    ), name="password_reset"),
    path("password/reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="auth/password_reset_done.html",
    ), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="auth/password_reset_confirm.html",
        success_url="/accounts/password/reset/complete/",
    ), name="password_reset_confirm"),
    path("password/reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="auth/password_reset_complete.html",
    ), name="password_reset_complete"),

    # Self-service profile
    path("profile/", web_views.ProfileView.as_view(), name="profile"),

    # Notifications
    path("notifications/",          web_views.NotificationListView.as_view(),       name="notifications"),
    path("notifications/mark-read/", web_views.NotificationMarkAllReadView.as_view(), name="notifications_mark_all_read"),

    # Admin: users
    path("users/",                  web_views.UserListView.as_view(),   name="user_list"),
    path("users/create/",           web_views.UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/",    web_views.UserUpdateView.as_view(), name="user_edit"),

    # Admin: roles (Django groups)
    path("roles/",                  web_views.RoleListView.as_view(),   name="role_list"),
    path("roles/create/",           web_views.RoleCreateView.as_view(), name="role_create"),
    path("roles/<int:pk>/edit/",    web_views.RoleUpdateView.as_view(), name="role_edit"),
]
