import hashlib
import logging
from smtplib import SMTPException

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import send_mail
from django.contrib import messages
from django.db.models import Count, Q
from django.db import transaction
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_http_methods, require_POST
from datetime import timedelta
from uuid import uuid4

from .forms import (
    PoliceRegistrationForm,
    UserRegistrationForm,
    UserLoginForm,
    UserProfileForm,
    UserProfileExtendedForm,
    PasswordResetRequestForm,
)
from .models import User, UserProfile
from alerts.services import (
    approval_sms_failure_message,
    send_approval_welcome_sms,
)
from incidents.models import Incident
from alerts.models import Alert
from volunteers.models import Volunteer

logger = logging.getLogger(__name__)


def home_view(request):
    """Home page view"""
    try:
        context = {
            'total_incidents': Incident.objects.count(),
            'resolved_incidents': Incident.objects.filter(status='resolved').count(),
            'active_volunteers': Volunteer.objects.filter(is_approved=True, is_active=True).count(),
            'recent_alerts': Alert.objects.filter(is_active=True).order_by('-created_at')[:3],
        }
    except:
        # Database tables don't exist yet
        context = {
            'total_incidents': 0,
            'resolved_incidents': 0,
            'active_volunteers': 0,
            'recent_alerts': [],
        }
    return render(request, 'accounts/home.html', context)


def register_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful! Please log in.')
            if user.role == 'volunteer':
                messages.info(request, 'Your volunteer application is pending approval.')
            return redirect('login')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def police_register_view(request):
    """Allow police applicants to submit an account for administrator approval."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = PoliceRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Police application submitted successfully. Your account is '
                'pending verification and you can log in after an administrator '
                'approves it.',
            )
            return redirect('login')
    else:
        form = PoliceRegistrationForm()

    return render(request, 'accounts/police_register.html', {'form': form})


def password_reset_request_view(request):
    """Email a reset link to a matching active account, if one exists."""
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().casefold()
        client_ip = request.META.get('REMOTE_ADDR', '')
        digest = hashlib.sha256(
            f'{client_ip}:{email}'.encode('utf-8')
        ).hexdigest()
        may_attempt = cache.add(
            f'password-reset-request:{digest}',
            True,
            timeout=60,
        )

        if may_attempt:
            matching_users = list(
                User.objects.filter(
                    email__iexact=email,
                    is_active=True,
                    is_removed=False,
                ).order_by('pk')[:2]
            )
            if len(matching_users) == 1:
                user = matching_users[0]
                may_send_to_user = cache.add(
                    f'password-reset-user:{user.pk}',
                    True,
                    timeout=60,
                )
                if may_send_to_user:
                    uid = urlsafe_base64_encode(force_bytes(user.pk))
                    token = default_token_generator.make_token(user)
                    reset_path = reverse(
                        'password_reset_confirm',
                        kwargs={'uidb64': uid, 'token': token},
                    )
                    reset_url = request.build_absolute_uri(reset_path)
                    message = (
                        'A password reset was requested for your Neighbourhood '
                        'Alert account.\n\n'
                        f'Reset your password using this link:\n{reset_url}\n\n'
                        'If you did not request a password reset, you can '
                        'ignore this email.'
                    )
                    try:
                        sent_count = send_mail(
                            'Reset your Neighbourhood Alert password',
                            message,
                            settings.DEFAULT_FROM_EMAIL,
                            [user.email],
                            fail_silently=False,
                        )
                    except (OSError, SMTPException) as error:
                        logger.warning(
                            'Password reset email could not be submitted (%s)',
                            type(error).__name__,
                        )
                    else:
                        if sent_count != 1:
                            logger.warning(
                                'Password reset email was not submitted '
                                '(no message sent)'
                            )

        return redirect('password_reset_done')

    return render(
        request,
        'registration/password_reset_form.html',
        {'form': form},
    )


def password_reset_done_view(request):
    return render(request, 'registration/password_reset_done.html')


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                if user.role == 'volunteer' and not user.is_approved:
                    messages.info(
                        request,
                        'Your volunteer application is pending approval.',
                    )
                    return redirect('login')
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                redirect_to = request.POST.get('next') or request.GET.get('next', '')
                if redirect_to and url_has_allowed_host_and_scheme(
                    redirect_to,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(redirect_to)
                return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = UserLoginForm()
    
    redirect_to = request.POST.get('next') or request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_to = ''
    return render(
        request,
        'accounts/login.html',
        {'form': form, 'next': redirect_to},
    )


@login_required
@require_POST
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')


@login_required
def dashboard_view(request):
    """Dashboard view based on user role"""
    user = request.user
    
    # Common context for all users
    context = {
        'user': user,
        'recent_incidents': Incident.objects.all().order_by('-created_at')[:5],
        'active_alerts': Alert.objects.filter(is_active=True).order_by('-created_at')[:3],
    }
    
    # Role-specific context
    if user.is_admin_user():
        # Admin dashboard
        context.update({
            'total_users': User.objects.count(),
            'total_incidents': Incident.objects.count(),
            'pending_volunteers': Volunteer.objects.filter(is_approved=False).count(),
            'pending_police': User.objects.filter(
                role='police',
                is_approved=False,
                is_active=False,
            ).count(),
            'incidents_by_status': {
                'active': Incident.objects.filter(status='active').count(),
                'investigating': Incident.objects.filter(status='investigating').count(),
                'resolved': Incident.objects.filter(status='resolved').count(),
            },
            'incidents_by_severity': {
                'low': Incident.objects.filter(severity='low').count(),
                'medium': Incident.objects.filter(severity='medium').count(),
                'high': Incident.objects.filter(severity='high').count(),
                'critical': Incident.objects.filter(severity='critical').count(),
            },
            'recent_users': User.objects.all().order_by('-date_joined')[:5],
            'pending_approvals': Volunteer.objects.filter(is_approved=False),
        })
    
    elif user.is_police():
        # Police dashboard
        context.update({
            'assigned_incidents': Incident.objects.filter(assigned_officer=user).order_by('-created_at')[:5],
            'active_cases': Incident.objects.filter(status='investigating').count(),
            'high_priority_incidents': Incident.objects.filter(severity__in=['high', 'critical'], status='active').order_by('-created_at')[:5],
            'resolved_by_me': Incident.objects.filter(resolved_by=user).count(),
        })
    
    elif user.is_volunteer():
        # Volunteer dashboard
        try:
            volunteer = Volunteer.objects.get(user=user)
            context.update({
                'volunteer': volunteer,
                'responses_count': volunteer.responses.count(),
                'nearby_incidents': Incident.objects.filter(
                    status='active'
                ).exclude(volunteer_responses__volunteer=volunteer).order_by('-created_at')[:5],
            })
        except Volunteer.DoesNotExist:
            context.update({
                'volunteer': None,
                'pending_approval': True,
            })
    
    else:
        # Resident dashboard
        context.update({
            'my_incidents': Incident.objects.filter(reported_by=user).order_by('-created_at')[:5],
            'my_reports_count': Incident.objects.filter(reported_by=user).count(),
        })
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
def profile_view(request):
    """User profile view"""
    user = request.user
    
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    if request.method == 'POST':
        user_form = UserProfileForm(request.POST, request.FILES, instance=user)
        profile_form = UserProfileExtendedForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserProfileForm(instance=user)
        profile_form = UserProfileExtendedForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user,
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def user_management_view(request):
    """Admin user management view"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    users = User.objects.all().order_by('-date_joined')
    
    # Filter by role
    role_filter = request.GET.get('role')
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Search
    search_query = request.GET.get('q')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    context = {
        'users': users,
        'role_filter': role_filter,
        'search_query': search_query,
    }
    
    return render(request, 'accounts/user_management.html', context)


@login_required
def pending_police_applications_view(request):
    """List pending police applications for administrator review."""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    applications = User.objects.filter(
        role='police',
        is_approved=False,
        is_active=False,
        is_removed=False,
    ).order_by('date_joined')
    return render(
        request,
        'accounts/pending_police_applications.html',
        {'applications': applications},
    )


@login_required
def review_police_application_view(request, user_id):
    """Approve or reject a pending police application."""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard')
    if request.method != 'POST':
        return redirect('pending_police_applications')

    applicant = get_object_or_404(
        User,
        id=user_id,
        role='police',
        is_approved=False,
        is_active=False,
        is_removed=False,
    )
    decision = request.POST.get('decision')
    if decision == 'approve':
        applicant.is_approved = True
        applicant.is_active = True
        applicant.save(update_fields=['is_approved', 'is_active'])
        delivery = send_approval_welcome_sms(applicant)
        if delivery and delivery.status == 'failed':
            messages.warning(request, approval_sms_failure_message(delivery))
        elif delivery and delivery.status == 'dry_run':
            messages.info(
                request,
                'Welcome SMS recorded in dry-run mode; no SMS was sent.',
            )
        messages.success(
            request,
            f'{applicant.get_full_name() or applicant.username} was approved as a police officer.',
        )
    elif decision == 'reject':
        username = applicant.username
        applicant.delete()
        messages.success(request, f'Police application for {username} was rejected.')
    else:
        messages.error(request, 'Invalid application decision.')

    return redirect('pending_police_applications')


@login_required
@require_POST
def toggle_user_status_view(request, user_id):
    """Toggle user active status"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard')
    
    user = get_object_or_404(User, id=user_id)
    
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('user_management')
    if user.is_removed:
        messages.error(request, 'This account has already been removed and cannot be reactivated.')
        return redirect('user_management')
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.username} has been {status}.')
    
    return redirect('user_management')


@login_required
@require_http_methods(['GET', 'POST'])
def remove_user_view(request, user_id):
    """Disable and anonymize an account while preserving its activity history."""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to remove user accounts.')
        return redirect('dashboard')

    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        messages.error(request, 'You cannot remove your own account.')
        return redirect('user_management')

    if request.method == 'POST':
        if request.POST.get('confirm') != 'yes':
            messages.error(request, 'Confirm account removal to continue.')
            return redirect('user_management')

        with transaction.atomic():
            target.username = f'removed-account-{uuid4().hex}'
            target.first_name = ''
            target.last_name = ''
            target.email = ''
            target.phone_number = ''
            target.address = ''
            target.police_employee_number = None
            target.police_station = ''
            target.police_unit = ''
            target.profile_picture = ''
            target.is_active = False
            target.is_approved = False
            target.is_removed = True
            target.is_staff = False
            target.is_superuser = False
            target.set_unusable_password()
            target.save(update_fields=[
                'username',
                'first_name',
                'last_name',
                'email',
                'phone_number',
                'address',
                'police_employee_number',
                'police_station',
                'police_unit',
                'profile_picture',
                'is_active',
                'is_approved',
                'is_removed',
                'is_staff',
                'is_superuser',
                'password',
            ])
            target.groups.clear()
            target.user_permissions.clear()

            try:
                profile = target.profile
            except UserProfile.DoesNotExist:
                profile = None
            if profile:
                profile.emergency_contact_name = ''
                profile.emergency_contact_phone = ''
                profile.id_number = ''
                profile.save(update_fields=[
                    'emergency_contact_name',
                    'emergency_contact_phone',
                    'id_number',
                ])

        messages.success(
            request,
            'Account access was removed and personal account details were cleared. '
            'Incident and activity history has been preserved.',
        )
        return redirect('user_management')

    return render(
        request,
        'accounts/confirm_user_removal.html',
        {'target_user': target},
    )
