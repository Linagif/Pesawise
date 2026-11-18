from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts import forms as af

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(authentication_form=af.StyledAuthForm,
                                                          redirect_authenticated_user=True), name="login"),
    path("accounts/password_change/", auth_views.PasswordChangeView.as_view(form_class=af.StyledPasswordChangeForm),
         name="password_change"),
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(form_class=af.StyledPasswordResetForm),
         name="password_reset"),
    path("accounts/reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(form_class=af.StyledSetPasswordForm),
         name="password_reset_confirm"),
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),   # logout, *_done views
    path("", include("dashboard.urls")),
    path("income/", include("income.urls")),
    path("budgets/", include("budgets.urls")),
    path("expenses/", include("expenses.urls")),
    path("savings/", include("savings.urls")),
    path("tips/", include("advisor.urls")),
    path("categories/", include("core.urls")),
    path("import/", include("imports.urls")),
]
