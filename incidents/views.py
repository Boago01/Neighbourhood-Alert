from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.db import IntegrityError
from django.utils import timezone
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST

from .models import Incident, Comment, IncidentUpdate, IncidentAssignment
from .forms import (
    IncidentForm,
    CommentForm,
    IncidentStatusForm,
    IncidentFilterForm,
    VolunteerProgressForm,
)
from volunteers.models import Volunteer, VolunteerResponse
from accounts.models import User


def _is_approved_active_volunteer(user):
    return (
        user.is_authenticated
        and user.is_volunteer()
        and user.is_active
        and user.is_approved
        and Volunteer.objects.filter(
            user=user,
            is_approved=True,
            is_active=True,
        ).exists()
    )


@login_required
def incident_feed_view(request):
    """View all incidents in a feed"""
    incidents = Incident.objects.all()

    if request.user.is_police() or request.user.is_admin_user():
        pass
    elif request.user.is_resident():
        incidents = incidents.filter(reported_by=request.user)
    elif _is_approved_active_volunteer(request.user):
        incidents = incidents.filter(
            volunteer_assignments__volunteer=request.user,
        ).distinct()
    else:
        incidents = incidents.none()
    
    # Filter form
    filter_form = IncidentFilterForm(request.GET)
    
    if filter_form.is_valid():
        data = filter_form.cleaned_data
        
        if data.get('status'):
            incidents = incidents.filter(status=data['status'])
        
        if data.get('severity'):
            incidents = incidents.filter(severity=data['severity'])
        
        if data.get('category'):
            incidents = incidents.filter(category=data['category'])
        
        if data.get('date_from'):
            incidents = incidents.filter(created_at__date__gte=data['date_from'])
        
        if data.get('date_to'):
            incidents = incidents.filter(created_at__date__lte=data['date_to'])
        
        if data.get('search'):
            search = data['search']
            incidents = incidents.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(location_description__icontains=search)
            )
    
    incidents = incidents.order_by('-created_at')
    
    context = {
        'incidents': incidents,
        'filter_form': filter_form,
    }
    
    return render(request, 'incidents/incident_feed.html', context)


@login_required
def report_incident_view(request):
    """Report a new incident"""
    if request.method == 'POST':
        form = IncidentForm(request.POST, request.FILES)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.reported_by = request.user
            incident.save()
            
            messages.success(request, 'Incident reported successfully!')
            return redirect('incident_detail', incident_id=incident.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = IncidentForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'incidents/report_incident.html', context)


@login_required
def incident_detail_view(request, incident_id):
    """Show incident details only to the reporter and authorized responders."""
    incident = get_object_or_404(Incident, id=incident_id)

    is_reporter = incident.reported_by_id == request.user.pk
    is_authorized_police = request.user.is_police()
    is_admin = request.user.is_admin_user()
    is_assigned_volunteer = (
        _is_approved_active_volunteer(request.user)
        and IncidentAssignment.objects.filter(
            incident=incident,
            volunteer=request.user,
        ).exists()
    )
    if not (
        is_reporter
        or is_authorized_police
        or is_admin
        or is_assigned_volunteer
    ):
        raise Http404

    # Comments
    comments = incident.comments.all()
    comment_form = CommentForm()
    
    # Check if user has responded (for volunteers)
    user_response = None
    if request.user.is_volunteer():
        volunteer = Volunteer.objects.filter(
            user=request.user,
            is_approved=True,
            is_active=True,
        ).first()
        if volunteer:
            user_response = VolunteerResponse.objects.filter(
                incident=incident,
                volunteer=volunteer,
            ).first()
    
    context = {
        'incident': incident,
        'comments': comments,
        'comment_form': comment_form,
        'user_response': user_response,
    }
    
    return render(request, 'incidents/incident_detail.html', context)


def _can_view_incident_data(user, incident):
    if not user.is_authenticated:
        return False
    if (
        incident.reported_by_id == user.pk
        or user.is_police()
        or user.is_admin_user()
    ):
        return True
    return (
        _is_approved_active_volunteer(user)
        and IncidentAssignment.objects.filter(
            incident=incident,
            volunteer=user,
        ).exists()
    )


@login_required
def add_comment_view(request, incident_id):
    """Add a comment to an incident"""
    incident = get_object_or_404(Incident, id=incident_id)
    
    if request.method == 'POST':
        if not _can_view_incident_data(request.user, incident):
            raise Http404
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.incident = incident
            comment.author = request.user
            
            # Official comments only from police/admin
            if request.user.is_police() or request.user.is_admin_user():
                comment.is_official = request.POST.get('is_official') == 'on'
            
            comment.save()
            messages.success(request, 'Comment added successfully!')
        else:
            messages.error(request, 'Please enter a valid comment.')
    
    return redirect('incident_detail', incident_id=incident.id)


@login_required
def update_incident_status_view(request, incident_id):
    """Update incident status (Police/Admin only)"""
    if not request.user.can_manage_incidents():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('incident_detail', incident_id=incident_id)
    
    incident = get_object_or_404(Incident, id=incident_id)
    
    if request.method == 'POST':
        old_status = incident.status
        form = IncidentStatusForm(request.POST, instance=incident)
        
        if form.is_valid():
            incident = form.save(commit=False)
            
            # Assign officer if investigating
            if incident.status == 'investigating' and not incident.assigned_officer:
                incident.assigned_officer = request.user
            
            # Set resolved info
            if incident.status == 'resolved' and old_status != 'resolved':
                incident.resolved_by = request.user
                incident.resolved_at = timezone.now()
            
            incident.save()
            
            # Create update record
            if old_status != incident.status:
                IncidentUpdate.objects.create(
                    incident=incident,
                    updated_by=request.user,
                    old_status=old_status,
                    new_status=incident.status,
                    notes=incident.investigation_notes
                )
            
            messages.success(request, 'Incident status updated successfully!')
            return redirect('incident_detail', incident_id=incident.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return redirect('incident_detail', incident_id=incident.id)


@login_required
def my_incidents_view(request):
    """View incidents reported by the current user"""
    incidents = Incident.objects.filter(reported_by=request.user).order_by('-created_at')
    
    context = {
        'incidents': incidents,
    }
    
    return render(request, 'incidents/my_incidents.html', context)


@login_required
def delete_incident_view(request, incident_id):
    """Delete an incident (Admin only or owner if active)"""
    incident = get_object_or_404(Incident, id=incident_id)
    
    can_delete = (
        request.user.is_admin_user() or 
        (incident.reported_by == request.user and incident.status == 'active')
    )
    
    if not can_delete:
        messages.error(request, 'You do not have permission to delete this incident.')
        return redirect('incident_detail', incident_id=incident_id)
    
    if request.method == 'POST':
        incident.delete()
        messages.success(request, 'Incident deleted successfully.')
        return redirect('incident_feed')
    
    context = {
        'incident': incident,
    }
    
    return render(request, 'incidents/delete_incident.html', context)


@login_required
@require_POST
def assign_incident_view(request, incident_id):
    """Assign incident to police officer"""
    if not request.user.is_police() or request.user.is_admin_user():
        messages.error(request, 'Only police officers can assign incidents.')
        return redirect('incident_detail', incident_id=incident_id)
    
    incident = get_object_or_404(Incident, id=incident_id)
    incident.assigned_officer = request.user
    incident.status = 'investigating'
    incident.save()
    
    # Create update record
    IncidentUpdate.objects.create(
        incident=incident,
        updated_by=request.user,
        old_status='active',
        new_status='investigating',
        notes=f'Assigned to {request.user.get_full_name()}'
    )
    
    messages.success(request, 'Incident assigned to you successfully!')
    return redirect('incident_detail', incident_id=incident.id)


@login_required
def get_incidents_json(request):
    """Return sensitive incident locations only to police and administrators."""
    if not (request.user.is_police() or request.user.is_admin_user()):
        return JsonResponse(
            {'detail': 'You do not have permission to view incident locations.'},
            status=403,
        )

    incidents = Incident.objects.all()
    
    data = []
    for incident in incidents:
        data.append({
            'id': incident.id,
            'title': incident.title,
            'latitude': float(incident.latitude),
            'longitude': float(incident.longitude),
            'severity': incident.severity,
            'category': incident.category,
            'status': incident.status,
            'created_at': incident.created_at.isoformat(),
        })
    
    return JsonResponse({'incidents': data})


# ==================== POLICE CASE MANAGEMENT ====================

@login_required
def police_my_cases_view(request):
    """Show this officer's cases and open cases not yet assigned to an officer."""
    if not request.user.is_police():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    # Open cases already owned by another officer belong only on that officer's
    # list; volunteer assignments do not change police case ownership.
    cases = Incident.objects.filter(
        Q(assigned_officer=request.user) |
        Q(assigned_officer__isnull=True, status__in=['active', 'investigating'])
    ).distinct().order_by('-created_at')
    
    context = {
        'cases': cases,
        'total_cases': cases.count(),
        'active_cases': cases.filter(status__in=['active', 'investigating']).count(),
        'resolved_cases': cases.filter(status='resolved').count(),
    }
    
    return render(request, 'incidents/police_my_cases.html', context)


@login_required
def police_assign_volunteers_view(request, incident_id):
    """Police officer assign volunteers to an incident"""
    if not request.user.is_police():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('incident_detail', incident_id=incident_id)
    
    incident = get_object_or_404(Incident, id=incident_id)
    
    # Get approved volunteers
    approved_volunteers = User.objects.filter(
        role='volunteer',
        is_approved=True,
        volunteer__is_active=True,
        volunteer__is_approved=True,
    ).exclude(
        incident_assignments__incident=incident
    )
    
    if request.method == 'POST':
        volunteer_ids = request.POST.getlist('volunteers')
        priority = request.POST.get('priority', 'medium')
        notes = request.POST.get('assignment_notes', '')

        allowed_priorities = {
            value for value, _label in IncidentAssignment.PRIORITY_CHOICES
        }
        if priority not in allowed_priorities or len(notes) > 5000:
            messages.error(request, 'The assignment priority or notes are invalid.')
            return redirect('police_monitor_case', incident_id=incident_id)
        
        for volunteer_id in volunteer_ids:
            volunteer = User.objects.filter(
                id=volunteer_id,
                role='volunteer',
                is_active=True,
                is_approved=True,
                volunteer__is_active=True,
                volunteer__is_approved=True,
            ).first()
            if volunteer is None:
                messages.error(
                    request,
                    f'Volunteer with ID {volunteer_id} is not eligible for assignment.',
                )
                continue
                
            try:
                assignment = IncidentAssignment.objects.create(
                    incident=incident,
                    volunteer=volunteer,
                    assigned_by=request.user,
                    priority=priority,
                    assignment_notes=notes
                )
                messages.success(
                    request, 
                    f'Assigned {volunteer.get_full_name()} to case {incident.title}'
                )
            except IntegrityError:
                messages.info(
                    request,
                    f'{volunteer.get_full_name()} is already assigned to this case.',
                )
        
        return redirect('police_monitor_case', incident_id=incident_id)
    
    # Get already assigned volunteers
    assigned_volunteers = incident.volunteer_assignments.all()
    
    context = {
        'incident': incident,
        'approved_volunteers': approved_volunteers,
        'assigned_volunteers': assigned_volunteers,
    }
    
    return render(request, 'incidents/police_assign_volunteers.html', context)


@login_required
def police_monitor_case_view(request, incident_id):
    """Police officer monitor volunteer activity on a case"""
    if not request.user.is_police():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('incident_detail', incident_id=incident_id)
    
    incident = get_object_or_404(Incident, id=incident_id)
    assignments = incident.volunteer_assignments.all().order_by('-assigned_at')
    
    context = {
        'incident': incident,
        'assignments': assignments,
    }
    
    return render(request, 'incidents/police_monitor_case.html', context)


@login_required
def police_remove_volunteer_view(request, assignment_id):
    """Police officer remove a volunteer from a case"""
    assignment = get_object_or_404(IncidentAssignment, id=assignment_id)
    incident_id = assignment.incident.id
    
    if not request.user.is_police():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('incident_detail', incident_id=incident_id)
    
    if request.method == 'POST':
        volunteer_name = assignment.volunteer.get_full_name()
        assignment.delete()
        messages.success(request, f'Removed {volunteer_name} from this case.')
        return redirect('police_monitor_case', incident_id=incident_id)
    
    context = {
        'assignment': assignment,
    }
    
    return render(request, 'incidents/police_remove_volunteer.html', context)


@login_required
def police_close_case_view(request, incident_id):
    """Police officer close a case"""
    if not request.user.is_police():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('incident_detail', incident_id=incident_id)
    
    incident = get_object_or_404(Incident, id=incident_id)
    
    if request.method == 'POST':
        old_status = incident.status
        incident.status = 'closed'
        incident.resolved_by = request.user
        incident.resolved_at = timezone.now()
        incident.save()
        
        # Create update record
        IncidentUpdate.objects.create(
            incident=incident,
            updated_by=request.user,
            old_status=old_status,
            new_status='closed',
            notes='Case closed by police officer'
        )
        
        messages.success(request, 'Case closed successfully!')
        return redirect('police_my_cases')
    
    context = {
        'incident': incident,
    }
    
    return render(request, 'incidents/police_close_case.html', context)


# ==================== VOLUNTEER CASE MANAGEMENT ====================

@login_required
def volunteer_assigned_cases_view(request):
    """Volunteer view their assigned cases"""
    if not _is_approved_active_volunteer(request.user):
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    assignments = IncidentAssignment.objects.filter(
        volunteer=request.user
    ).select_related('incident').order_by('-assigned_at')
    
    context = {
        'assignments': assignments,
        'total_assignments': assignments.count(),
        'pending_assignments': assignments.filter(status='pending').count(),
        'active_assignments': assignments.filter(
            status__in=['on_way', 'arrived', 'assisting']
        ).count(),
        'completed_assignments': assignments.filter(status='completed').count(),
    }
    
    return render(request, 'incidents/volunteer_assigned_cases.html', context)


@login_required
def volunteer_assignment_detail_view(request, assignment_id):
    """Volunteer view details of an assigned case"""
    assignment = get_object_or_404(IncidentAssignment, id=assignment_id)
    
    if (
        assignment.volunteer != request.user
        or not _is_approved_active_volunteer(request.user)
    ):
        messages.error(request, 'You do not have permission to view this assignment.')
        return redirect('volunteer_assigned_cases')
    
    incident = assignment.incident
    
    context = {
        'assignment': assignment,
        'incident': incident,
    }
    
    return render(request, 'incidents/volunteer_assignment_detail.html', context)


@login_required
def volunteer_update_assignment_status_view(request, assignment_id):
    """Volunteer update assignment status"""
    assignment = get_object_or_404(IncidentAssignment, id=assignment_id)
    
    if (
        assignment.volunteer != request.user
        or not _is_approved_active_volunteer(request.user)
    ):
        messages.error(request, 'You do not have permission to update this assignment.')
        return redirect('volunteer_assigned_cases')
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [choice[0] for choice in IncidentAssignment.ASSIGNMENT_STATUS_CHOICES]
        
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status.')
            return redirect('volunteer_assignment_detail', assignment_id=assignment_id)
        
        old_status = assignment.status
        assignment.status = new_status
        
        # Update timestamps
        now = timezone.now()
        if new_status == 'accepted' and not assignment.accepted_at:
            assignment.accepted_at = now
        elif new_status == 'on_way' and not assignment.on_way_at:
            assignment.on_way_at = now
        elif new_status == 'arrived' and not assignment.arrived_at:
            assignment.arrived_at = now
        elif new_status == 'completed' and not assignment.completed_at:
            assignment.completed_at = now
        
        assignment.save()
        
        messages.success(request, f'Status updated to {assignment.get_status_display()}')
        return redirect('volunteer_assignment_detail', assignment_id=assignment_id)
    
    context = {
        'assignment': assignment,
    }
    
    return render(request, 'incidents/volunteer_update_status.html', context)


@login_required
def volunteer_update_progress_view(request, assignment_id):
    """Volunteer submit progress notes"""
    assignment = get_object_or_404(IncidentAssignment, id=assignment_id)
    
    if (
        assignment.volunteer != request.user
        or not _is_approved_active_volunteer(request.user)
    ):
        messages.error(request, 'You do not have permission to update this assignment.')
        return redirect('volunteer_assigned_cases')
    
    form = VolunteerProgressForm(
        request.POST or None,
        request.FILES or None,
        initial={'progress_notes': assignment.progress_notes},
    )
    if request.method == 'POST':
        if form.is_valid():
            progress_notes = form.cleaned_data['progress_notes']
            image = form.cleaned_data['image']

            if progress_notes:
                assignment.progress_notes = progress_notes

            if image:
                assignment.volunteer_images = image

            assignment.last_updated = timezone.now()
            assignment.save()

            messages.success(request, 'Progress update submitted successfully!')
            return redirect('volunteer_assignment_detail', assignment_id=assignment_id)
        messages.error(request, 'Please correct the errors below.')
    
    context = {
        'assignment': assignment,
        'form': form,
    }
    
    return render(request, 'incidents/volunteer_update_progress.html', context)


@login_required
def volunteer_submit_completion_report_view(request, assignment_id):
    """Volunteer submit completion report"""
    assignment = get_object_or_404(IncidentAssignment, id=assignment_id)
    
    if (
        assignment.volunteer != request.user
        or not _is_approved_active_volunteer(request.user)
    ):
        messages.error(request, 'You do not have permission to update this assignment.')
        return redirect('volunteer_assigned_cases')
    
    if request.method == 'POST':
        completion_report = request.POST.get('completion_report', '').strip()
        
        if completion_report:
            assignment.completion_report = completion_report
            assignment.status = 'completed'
            assignment.completed_at = timezone.now()
            assignment.save()
            
            messages.success(request, 'Completion report submitted successfully!')
            return redirect('volunteer_assigned_cases')
        else:
            messages.error(request, 'Please provide a completion report.')
    
    context = {
        'assignment': assignment,
    }
    
    return render(request, 'incidents/volunteer_submit_report.html', context)
