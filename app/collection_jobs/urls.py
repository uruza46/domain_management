from django.urls import path

from . import views

urlpatterns = [
    path("domains/<uuid:pk>/request/", views.request_domain_collection, name="collection_request"),
    path("domains/<uuid:pk>/history/", views.domain_collection_history, name="collection_history"),
]
