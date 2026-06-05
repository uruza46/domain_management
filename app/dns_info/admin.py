from django.contrib import admin

from .models import DnsInfo, DnsRecord

admin.site.register(DnsInfo)
admin.site.register(DnsRecord)
