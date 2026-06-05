from django.contrib import admin

from .models import Risk, SecurityStatus

admin.site.register(SecurityStatus)
admin.site.register(Risk)
