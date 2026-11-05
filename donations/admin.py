from django.contrib import admin
from .models import DonationCampaign, Donation, Payout


class DonationInline(admin.TabularInline):
    model = Donation
    extra = 0
    readonly_fields = ['created_at', 'paid_at']


@admin.register(DonationCampaign)
class DonationCampaignAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'goal_amount', 'current_amount', 'status', 'created_at', 'get_progress']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DonationInline]
    
    def get_progress(self, obj):
        return f"{obj.get_progress_percentage()}%"
    get_progress.short_description = 'Progress'
    
    actions = ['complete_campaigns', 'cancel_campaigns', 'activate_campaigns']
    
    def complete_campaigns(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f'{queryset.count()} campaigns marked as completed.')
    complete_campaigns.short_description = 'Mark selected campaigns as completed'
    
    def cancel_campaigns(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f'{queryset.count()} campaigns cancelled.')
    cancel_campaigns.short_description = 'Cancel selected campaigns'
    
    def activate_campaigns(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f'{queryset.count()} campaigns activated.')
    activate_campaigns.short_description = 'Activate selected campaigns'


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ['get_donor', 'recipient', 'amount', 'campaign', 'is_paid', 'created_at']
    list_filter = ['is_paid', 'is_anonymous', 'created_at']
    search_fields = ['donor__username', 'recipient__username', 'donor_name', 'message']
    readonly_fields = ['created_at', 'paid_at']
    
    def get_donor(self, obj):
        return obj.get_donor_display()
    get_donor.short_description = 'Donor'
    
    actions = ['mark_as_paid']
    
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_paid=True, paid_at=timezone.now())
        self.message_user(request, f'{queryset.count()} donations marked as paid.')
    mark_as_paid.short_description = 'Mark selected donations as paid'


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['volunteer', 'amount', 'status', 'requested_at', 'processed_at']
    list_filter = ['status', 'requested_at']
    search_fields = ['volunteer__username', 'bank_name', 'account_number']
    readonly_fields = ['requested_at', 'processed_at']
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='completed', processed_at=timezone.now(), processed_by=request.user)
        self.message_user(request, f'{queryset.count()} payouts marked as completed.')
    mark_as_completed.short_description = 'Mark selected payouts as completed'
    
    def mark_as_failed(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='failed', processed_at=timezone.now(), processed_by=request.user)
        self.message_user(request, f'{queryset.count()} payouts marked as failed.')
    mark_as_failed.short_description = 'Mark selected payouts as failed'
