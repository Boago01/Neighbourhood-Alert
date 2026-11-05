from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Avg
from django.db import transaction
from django.views.decorators.http import require_POST

from .models import Volunteer, VolunteerResponse, VolunteerReview
from .forms import VolunteerApplicationForm, VolunteerResponseForm, VolunteerResponseStatusForm, VolunteerReviewForm
from alerts.services import (
    approval_sms_failure_message,
    send_approval_welcome_sms,
)
from incidents.models import Incident


@login_required
def volunteer_list_view(request):
    """List all approved volunteers"""
    volunteers = Volunteer.objects.filter(is_approved=True, is_active=True)
    
    # Filter by availability
    availability = request.GET.get('availability')
    if availability:
        volunteers = volunteers.filter(availability=availability)
    
    # Search
    search = request.GET.get('search')
    if search:
        volunteers = volunteers.filter(
            models.Q(user__first_name__icontains=search) |
            models.Q(user__last_name__icontains=search) |
            models.Q(skills__icontains=search)
        )
    
    volunteers = volunteers.order_by('-rating', '-total_responses')
    
    context = {
        'volunteers': volunteers,
    }
    
    return render(request, 'volunteers/volunteer_list.html', context)


@login_required
def volunteer_application_view(request):
    """Apply to become a volunteer"""
    # Check if already a volunteer
    if hasattr(request.user, 'volunteer'):
        messages.info(request, 'You have already applied as a volunteer.')
        return redirect('volunteer_dashboard')
    
    if request.method == 'POST':
        form = VolunteerApplicationForm(request.POST)
        if form.is_valid():
            volunteer = form.save(commit=False)
            volunteer.user = request.user
            volunteer.save()
            
            # Update user role
            request.user.role = 'volunteer'
            request.user.is_approved = False
            request.user.save()
            
            messages.success(request, 'Your volunteer application has been submitted! You will be notified once approved.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VolunteerApplicationForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'volunteers/volunteer_application.html', context)


@login_required
def volunteer_dashboard_view(request):
    """Volunteer dashboard"""
    if not hasattr(request.user, 'volunteer'):
        messages.error(request, 'You are not registered as a volunteer.')
        return redirect('volunteer_application')
    
    volunteer = request.user.volunteer
    
    context = {
        'volunteer': volunteer,
        'recent_responses': volunteer.responses.order_by('-responded_at')[:5],
        'available_incidents': Incident.objects.filter(status='active').order_by('-created_at')[:5],
        'total_responses': volunteer.responses.count(),
        'completed_responses': volunteer.responses.filter(status='completed').count(),
    }
    
    return render(request, 'volunteers/volunteer_dashboard.html', context)


@login_required
def respond_to_incident_view(request, incident_id):
    """Redirect volunteers to cases assigned by police."""
    if not hasattr(request.user, 'volunteer'):
        messages.error(request, 'Only volunteers can respond to incidents.')
        return redirect('incident_detail', incident_id=incident_id)
    
    volunteer = request.user.volunteer
    
    if not volunteer.is_approved:
        messages.error(request, 'Your volunteer application is pending approval.')
        return redirect('incident_detail', incident_id=incident_id)
    
    incident = get_object_or_404(Incident, id=incident_id)
    messages.info(
        request,
        'Incidents are assigned by police. Check your assigned cases for updates.',
    )
    return redirect('volunteer_assigned_cases')


@login_required
def update_response_status_view(request, response_id):
    """Update volunteer response status"""
    response = get_object_or_404(VolunteerResponse, id=response_id)
    
    # Only the volunteer who created the response can update it
    if response.volunteer.user != request.user:
        messages.error(request, 'You can only update your own responses.')
        return redirect('incident_detail', incident_id=response.incident.id)
    
    if request.method == 'POST':
        form = VolunteerResponseStatusForm(request.POST, instance=response)
        if form.is_valid():
            response = form.save(commit=False)
            
            # Update timestamps based on status
            if response.status == 'on_scene' and not response.arrived_at:
                response.arrived_at = timezone.now()
            elif response.status == 'completed' and not response.completed_at:
                response.completed_at = timezone.now()
            
            response.save()
            messages.success(request, 'Response status updated successfully!')
            return redirect('incident_detail', incident_id=response.incident.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VolunteerResponseStatusForm(instance=response)
    
    context = {
        'form': form,
        'response': response,
    }
    
    return render(request, 'volunteers/update_response_status.html', context)


@login_required
def pending_approvals_view(request):
    """View pending volunteer approvals (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    pending_volunteers = Volunteer.objects.filter(
        is_approved=False,
        user__is_removed=False,
    )
    
    context = {
        'pending_volunteers': pending_volunteers,
    }
    
    return render(request, 'volunteers/pending_approvals.html', context)


@login_required
@require_POST
def approve_volunteer_view(request, volunteer_id):
    """Approve a volunteer application (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard')
    
    volunteer = get_object_or_404(
        Volunteer,
        id=volunteer_id,
        user__is_removed=False,
    )
    
    with transaction.atomic():
        volunteer.is_approved = True
        volunteer.approved_by = request.user
        volunteer.approved_at = timezone.now()
        volunteer.save()

        volunteer.user.is_approved = True
        volunteer.user.save(update_fields=['is_approved'])

    delivery = send_approval_welcome_sms(volunteer.user)
    if delivery and delivery.status == 'failed':
        messages.warning(request, approval_sms_failure_message(delivery))
    elif delivery and delivery.status == 'dry_run':
        messages.info(
            request,
            'Welcome SMS recorded in dry-run mode; no SMS was sent.',
        )
    
    messages.success(request, f'{volunteer.user.get_full_name() or volunteer.user.username} has been approved as a volunteer.')
    return redirect('pending_approvals')


@login_required
def reject_volunteer_view(request, volunteer_id):
    """Reject a volunteer application (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard')
    
    volunteer = get_object_or_404(
        Volunteer,
        id=volunteer_id,
        user__is_removed=False,
    )
    
    if request.method == 'POST':
        # Revert user to resident role
        volunteer.user.role = 'resident'
        volunteer.user.is_approved = True
        volunteer.user.save()
        
        # Delete volunteer application
        volunteer.delete()
        
        messages.success(request, 'Volunteer application has been rejected.')
        return redirect('pending_approvals')
    
    context = {
        'volunteer': volunteer,
    }
    
    return render(request, 'volunteers/reject_volunteer.html', context)


@login_required
def volunteer_detail_view(request, volunteer_id):
    """View volunteer details"""
    volunteer = get_object_or_404(Volunteer, id=volunteer_id)
    can_review = request.user.is_authenticated and request.user.is_resident()
    has_reviewed = (
        can_review
        and volunteer.reviews.filter(reviewer=request.user).exists()
    )
    
    context = {
        'volunteer': volunteer,
        'responses': volunteer.responses.order_by('-responded_at')[:10],
        'reviews': volunteer.reviews.order_by('-created_at')[:5],
        'can_review': can_review,
        'has_reviewed': has_reviewed,
    }
    
    return render(request, 'volunteers/volunteer_detail.html', context)


@login_required
def add_volunteer_review_view(request, volunteer_id):
    """Add a review for a volunteer"""
    volunteer = get_object_or_404(Volunteer, id=volunteer_id)

    if not request.user.is_resident():
        messages.error(request, 'Only residents can review volunteers.')
        return redirect('volunteer_detail', volunteer_id=volunteer_id)
    
    # Check if user has already reviewed
    existing_review = VolunteerReview.objects.filter(volunteer=volunteer, reviewer=request.user).first()
    if existing_review:
        messages.info(request, 'You have already reviewed this volunteer.')
        return redirect('volunteer_detail', volunteer_id=volunteer_id)
    
    if request.method == 'POST':
        form = VolunteerReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.volunteer = volunteer
            review.reviewer = request.user
            review.save()
            
            # Update volunteer rating
            avg_rating = VolunteerReview.objects.filter(volunteer=volunteer).aggregate(Avg('rating'))['rating__avg']
            volunteer.rating = avg_rating or 5.00
            volunteer.save()
            
            messages.success(request, 'Review added successfully!')
            return redirect('volunteer_detail', volunteer_id=volunteer_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = VolunteerReviewForm()
    
    context = {
        'form': form,
        'volunteer': volunteer,
    }
    
    return render(request, 'volunteers/add_review.html', context)
