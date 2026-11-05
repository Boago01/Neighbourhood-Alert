from django.contrib import admin
from django.contrib import messages
from .models import (
    Alert,
    AlertAcknowledgment,
    AlertSMSDelivery,
    ApprovalSMSDelivery,
    SafetyResource,
)
from .services import send_alert_sms


class AlertAcknowledgmentInline(admin.TabularInline):
    model = AlertAcknowledgment
    extra = 0
    readonly_fields = ['acknowledged_at']


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'is_active', 'created_by', 'created_at', 'expires_at']
    list_filter = ['priority', 'is_active', 'created_at']
    search_fields = ['title', 'message', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [AlertAcknowledgmentInline]
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('title', 'message', 'priority')
        }),
        ('Location (Optional)', {
            'fields': ('latitude', 'longitude', 'radius'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['deactivate_alerts', 'activate_alerts', 'mark_as_critical']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and (
            request.user.is_police() or request.user.is_admin_user()
        ):
            delivery = send_alert_sms(obj)
            if delivery.status == 'failed':
                self.message_user(
                    request,
                    'The alert was saved, but its SMS notification could not be submitted.',
                    level=messages.WARNING,
                )
            elif delivery.status == 'dry_run':
                self.message_user(
                    request,
                    'SMS notification recorded in dry-run mode; no SMS was sent.',
                    level=messages.INFO,
                )
    
    def deactivate_alerts(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} alerts deactivated.')
    deactivate_alerts.short_description = 'Deactivate selected alerts'
    
    def activate_alerts(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} alerts activated.')
    activate_alerts.short_description = 'Activate selected alerts'
    
    def mark_as_critical(self, request, queryset):
        queryset.update(priority='critical')
        self.message_user(request, f'{queryset.count()} alerts marked as critical.')
    mark_as_critical.short_description = 'Mark selected alerts as critical'


@admin.register(AlertSMSDelivery)
class AlertSMSDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        'alert',
        'status',
        'recipient_count',
        'http_status',
        'provider_submission_id',
        'attempted_at',
        'completed_at',
    ]
    list_filter = ['status', 'attempted_at']
    search_fields = ['alert__title', 'provider_submission_id']
    readonly_fields = [
        'alert',
        'status',
        'provider_submission_id',
        'http_status',
        'error_code',
        'recipient_count',
        'attempted_at',
        'completed_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApprovalSMSDelivery)
class ApprovalSMSDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'status',
        'http_status',
        'provider_submission_id',
        'attempted_at',
        'completed_at',
    ]
    list_filter = ['status', 'attempted_at']
    search_fields = ['user__username', 'provider_submission_id']
    readonly_fields = [
        'user',
        'status',
        'provider_submission_id',
        'http_status',
        'error_code',
        'attempted_at',
        'completed_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AlertAcknowledgment)
class AlertAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = ['alert', 'user', 'acknowledged_at']
    list_filter = ['acknowledged_at']
    search_fields = ['alert__title', 'user__username']
    readonly_fields = ['acknowledged_at']


@admin.register(SafetyResource)
class SafetyResourceAdmin(admin.ModelAdmin):
    list_display = ['title', 'resource_type', 'contact_number', 'is_active', 'created_at']
    list_filter = ['resource_type', 'is_active', 'created_at']
    search_fields = ['title', 'description', 'contact_number']
    readonly_fields = ['created_at']
