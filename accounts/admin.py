from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import transaction
from django.utils import timezone
from alerts.models import ApprovalSMSDelivery
from alerts.services import send_approval_welcome_sms
from volunteers.models import Volunteer
from .models import User, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_approved', 'is_active', 'is_removed', 'date_joined']
    list_filter = ['role', 'is_approved', 'is_active', 'is_removed', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    readonly_fields = BaseUserAdmin.readonly_fields + ('is_removed',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': (
                'role',
                'phone_number',
                'address',
                'police_employee_number',
                'police_station',
                'police_unit',
                'profile_picture',
                'is_approved',
                'is_removed',
            )
        }),
    )
    
    actions = ['approve_users', 'retry_failed_welcome_sms', 'reject_users']
    
    def approve_users(self, request, queryset):
        approved_count = 0
        for user in queryset.filter(is_removed=False):
            if user.role == 'police':
                if user.is_approved and user.is_active:
                    continue
                user.is_approved = True
                user.is_active = True
                user.save(update_fields=['is_approved', 'is_active'])
                send_approval_welcome_sms(user)
                approved_count += 1
            elif user.role == 'volunteer':
                try:
                    volunteer = user.volunteer
                except Volunteer.DoesNotExist:
                    if user.is_approved:
                        continue
                    with transaction.atomic():
                        volunteer = Volunteer.objects.create(
                            user=user,
                            motivation=(
                                'Volunteer registration submitted without a '
                                'separate application record.'
                            ),
                            is_approved=True,
                            approved_by=request.user,
                            approved_at=timezone.now(),
                        )
                        user.is_approved = True
                        user.is_active = True
                        user.save(update_fields=['is_approved', 'is_active'])
                    send_approval_welcome_sms(user)
                    approved_count += 1
                    continue
                if volunteer.is_approved:
                    continue
                with transaction.atomic():
                    volunteer.is_approved = True
                    volunteer.approved_by = request.user
                    volunteer.approved_at = timezone.now()
                    volunteer.save(update_fields=[
                        'is_approved',
                        'approved_by',
                        'approved_at',
                    ])
                    user.is_approved = True
                    user.save(update_fields=['is_approved'])
                send_approval_welcome_sms(user)
                approved_count += 1
            elif not user.is_approved:
                user.is_approved = True
                user.save(update_fields=['is_approved'])
                approved_count += 1
        self.message_user(request, f'{approved_count} users have been approved.')
    approve_users.short_description = 'Approve selected users'

    def retry_failed_welcome_sms(self, request, queryset):
        failed_users = queryset.filter(
            is_approved=True,
            is_active=True,
            is_removed=False,
            approval_sms_delivery__status='failed',
            approval_sms_delivery__error_code='missing_public_url',
        ).select_related('approval_sms_delivery')
        submitted_count = 0
        failed_count = 0
        for user in failed_users:
            delivery = send_approval_welcome_sms(user)
            if delivery and delivery.status in ('submitted', 'dry_run'):
                submitted_count += 1
            else:
                failed_count += 1

        self.message_user(
            request,
            f'{submitted_count} welcome SMS message(s) submitted or dry-run; '
            f'{failed_count} could not be submitted.',
        )
    retry_failed_welcome_sms.short_description = (
        'Retry welcome SMS blocked by missing website URL'
    )
    
    def reject_users(self, request, queryset):
        queryset = queryset.filter(is_removed=False)
        queryset.update(is_approved=False)
        self.message_user(request, f'{queryset.count()} users have been rejected.')
    reject_users.short_description = 'Reject selected users'

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_removed:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'emergency_contact_name', 'emergency_contact_phone']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
