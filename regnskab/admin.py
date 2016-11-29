from django.contrib import admin
from regnskab.models import Alias, Payment, Sheet, EmailTemplate, Session


class AliasAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'profile', 'period', 'start_time', 'end_time')


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('profile', 'time', 'amount', 'note')


class SheetAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False


class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('subject', 'created_time')


class SessionAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False


admin.site.register(Alias, AliasAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Sheet, SheetAdmin)
admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(Session, SessionAdmin)
