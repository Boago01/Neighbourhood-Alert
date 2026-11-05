from django.contrib import admin
from django.db import transaction
from django.utils import timezone
from alerts.services import send_approval_welcome_sms
from .models import Volunteer, VolunteerResponse, VolunteerReview


class VolunteerResponseInline(admin.TabularInline):
    model = VolunteerResponse
    extra = 0
    readonly_fields = ['responded_at']


class VolunteerReviewInline(admin.TabularInline):
    model = VolunteerReview
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ['user', 'availability', 'is_approved', 'is_active', 'total_responses', 'rating', 'created_at']
    list_filter = ['is_approved', 'is_active', 'availability', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'skills']
    readonly_fields = ['created_at', 'updated_at', 'approved_at']
    inlines = [VolunteerResponseInline, VolunteerReviewInline]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Application Details', {
            'fields': ('motivation', 'experience', 'skills', 'availability')
        }),
        ('Approval Status', {
            'fields': ('is_approved', 'is_active', 'approved_by', 'approved_at')
        }),
        ('Statistics', {
            'fields': ('total_responses', 'rating')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_volunteers', 'deactivate_volunteers', 'activate_volunteers']
    
    def approve_volunteers(self, request, queryset):
        approved_count = 0
        for volunteer in queryset.filter(
            is_approved=False,
            user__is_removed=False,
        ).select_related('user'):
            with transaction.atomic():
                volunteer.is_approved = True
                volunteer.approved_by = request.user
                volunteer.approved_at = timezone.now()
                volunteer.save(update_fields=[
                    'is_approved',
                    'approved_by',
                    'approved_at',
                ])
                volunteer.user.is_approved = True
                volunteer.user.save(update_fields=['is_approved'])
            send_approval_welcome_sms(volunteer.user)
            approved_count += 1
        self.message_user(request, f'{approved_count} volunteers have been approved.')
    approve_volunteers.short_description = 'Approve selected volunteers'
    
    def deactivate_volunteers(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} volunteers have been deactivated.')
    deactivate_volunteers.short_description = 'Deactivate selected volunteers'
    
    def activate_volunteers(self, request, queryset):
        count = queryset.filter(user__is_removed=False).update(is_active=True)
        self.message_user(request, f'{count} volunteers have been activated.')
    activate_volunteers.short_description = 'Activate selected volunteers'


@admin.register(VolunteerResponse)
class VolunteerResponseAdmin(admin.ModelAdmin):
    list_display = ['volunteer', 'incident', 'status', 'responded_at', 'arrived_at', 'completed_at']
    list_filter = ['status', 'responded_at']
    search_fields = ['volunteer__user__username', 'incident__title']
    readonly_fields = ['responded_at']


@admin.register(VolunteerReview)
class VolunteerReviewAdmin(admin.ModelAdmin):
    list_display = ['volunteer', 'reviewer', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['volunteer__user__username', 'reviewer__username']
    readonly_fields = ['created_at']
