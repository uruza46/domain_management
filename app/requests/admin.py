from django.contrib import admin

from .models import DomainRequest, DomainRequestReview

admin.site.register(DomainRequest)
admin.site.register(DomainRequestReview)
