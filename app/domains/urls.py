from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="domain_dashboard"),
    path("import/", views.import_form, name="import_form"),
    path("import/preview/", views.import_preview, name="import_preview"),
    path("import/commit/", views.import_commit, name="import_commit"),
]
