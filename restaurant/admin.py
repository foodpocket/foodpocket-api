from django.contrib import admin
from .models import Account, Restaurant, VisitRecord, TokenSystem, Pocket


# Register your models here.
class AccountAdmin(admin.ModelAdmin):
    list_display = ['username', 'uid', 'email', 'last_login', 'create_time']
    ordering = ['username']


class TokenSystemAdmin(admin.ModelAdmin):
    list_display = ['owner', 'expire_time', 'create_time', 'token']
    ordering = ['-create_time', '-expire_time']


class PocketAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'status']


class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['name', 'pocket', 'owner', 'uid', 'status']


class VisitRecordAdmin(admin.ModelAdmin):
    list_display = ['restaurant', 'owner', 'visit_date', 'status']


admin.site.register(Account, AccountAdmin)
admin.site.register(TokenSystem, TokenSystemAdmin)
admin.site.register(Pocket, PocketAdmin)
admin.site.register(Restaurant, RestaurantAdmin)
admin.site.register(VisitRecord, VisitRecordAdmin)
