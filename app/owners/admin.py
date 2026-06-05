from django.contrib import admin

from .models import Department, Employee, Employee2Department, Inventory, ManagementUnit

admin.site.register(Department)
admin.site.register(Employee)
admin.site.register(Employee2Department)
admin.site.register(ManagementUnit)
admin.site.register(Inventory)
