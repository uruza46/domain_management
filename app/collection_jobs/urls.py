from django.urls import path

from . import views

urlpatterns = [
    path("domains/<uuid:pk>/request/", views.request_domain_collection, name="collection_request"),
    path("domains/<uuid:pk>/history/", views.domain_collection_history, name="collection_history"),
    path("results/<uuid:pk>/", views.collection_result_detail, name="collection_result_detail"),
    path("batches/", views.batch_run_list, name="batch_run_list"),
    path("history/", views.collection_history, name="collection_history"),
]
