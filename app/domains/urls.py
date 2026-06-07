from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="domain_dashboard"),
    path("import/", views.import_form, name="import_form"),
    path("import/preview/", views.import_preview, name="import_preview"),
    path("import/commit/", views.import_commit, name="import_commit"),
    path("ledger/", views.domain_ledger, name="domain_ledger"),
    path("ledger/<uuid:pk>/panel/", views.domain_panel, name="domain_panel"),
    path("ledger/<uuid:pk>/children/", views.domain_tree_children, name="domain_tree_children"),
]
