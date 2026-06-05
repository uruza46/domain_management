from django.urls import path

from . import views

urlpatterns = [
    path("", views.request_list, name="request_list"),
    path("new/", views.request_new, name="request_new"),
    path("<uuid:pk>/", views.request_detail, name="request_detail"),
    path("<uuid:pk>/review/<str:review_type>/", views.review_form, name="review_form"),
    path("<uuid:pk>/approve/", views.final_approval_form, name="final_approval_form"),
]
