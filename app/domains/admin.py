from django.contrib import admin

from .models import Brand, Company, Domain, DomainHistory

admin.site.register(Company)
admin.site.register(Brand)
admin.site.register(Domain)
admin.site.register(DomainHistory)
