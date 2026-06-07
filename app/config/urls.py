from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from domains import views as domain_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", domain_views.dashboard, name="dashboard"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("domains/", include("domains.urls")),
    path("owners/", include("owners.urls")),
    path("requests/", include("requests.urls")),
    path("collections/", include("collection_jobs.urls")),
]
