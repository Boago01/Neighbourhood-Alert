from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Alert, AlertAcknowledgment, SafetyResource
from .forms import AlertForm, SafetyResourceForm
from .services import send_alert_sms


def alert_list_view(request):
    """View all active alerts"""
    alerts = Alert.objects.filter(is_active=True).order_by('-created_at')
    
    # Filter out expired alerts
    alerts = [alert for alert in alerts if not alert.is_expired()]
    
    context = {
        'alerts': alerts,
    }
    
    return render(request, 'alerts/alert_list.html', context)


def alert_detail_view(request, alert_id):
    """View alert details"""
    alert = get_object_or_404(Alert, id=alert_id)
    
    # Check if user has acknowledged
    has_acknowledged = False
    if request.user.is_authenticated:
        has_acknowledged = AlertAcknowledgment.objects.filter(alert=alert, user=request.user).exists()
    
    context = {
        'alert': alert,
        'has_acknowledged': has_acknowledged,
    }
    
    return render(request, 'alerts/alert_detail.html', context)


@login_required
def create_alert_view(request):
    """Create a new alert (Police/Admin only)"""
    if not (request.user.is_police() or request.user.is_admin_user()):
        messages.error(request, 'You do not have permission to create alerts.')
        return redirect('alert_list')
    
    if request.method == 'POST':
        form = AlertForm(request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.created_by = request.user
            alert.save()

            delivery = send_alert_sms(alert)
            if delivery.status == 'submitted':
                messages.info(
                    request,
                    f'SMS notification submitted for {delivery.recipient_count} recipient(s).',
                )
            elif delivery.status == 'dry_run':
                messages.info(
                    request,
                    'SMS notification recorded in dry-run mode; no SMS was sent.',
                )
            elif delivery.status == 'failed':
                messages.warning(
                    request,
                    'The alert was created, but its SMS notification could not be submitted. '
                    'An administrator can review the delivery record.',
                )
            messages.success(request, 'Alert created successfully!')
            return redirect('alert_detail', alert_id=alert.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AlertForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'alerts/create_alert.html', context)


@login_required
@require_POST
def acknowledge_alert_view(request, alert_id):
    """Acknowledge an alert"""
    alert = get_object_or_404(Alert, id=alert_id)
    
    # Check if already acknowledged
    existing = AlertAcknowledgment.objects.filter(alert=alert, user=request.user).first()
    if existing:
        messages.info(request, 'You have already acknowledged this alert.')
        return redirect('alert_detail', alert_id=alert_id)
    
    AlertAcknowledgment.objects.create(alert=alert, user=request.user)
    messages.success(request, 'Alert acknowledged!')
    
    return redirect('alert_detail', alert_id=alert_id)


@login_required
@require_POST
def deactivate_alert_view(request, alert_id):
    """Deactivate an alert (Creator or Admin only)"""
    alert = get_object_or_404(Alert, id=alert_id)
    
    if not (request.user == alert.created_by or request.user.is_admin_user()):
        messages.error(request, 'You do not have permission to deactivate this alert.')
        return redirect('alert_detail', alert_id=alert_id)
    
    alert.is_active = False
    alert.save()
    
    messages.success(request, 'Alert has been deactivated.')
    return redirect('alert_list')


def safety_resources_view(request):
    """View safety resources"""
    resources = SafetyResource.objects.filter(is_active=True)
    
    # Group by type
    emergency_contacts = resources.filter(resource_type='emergency_contact')
    safety_tips = resources.filter(resource_type='safety_tip')
    guidelines = resources.filter(resource_type='guideline')
    helplines = resources.filter(resource_type='helpline')
    
    context = {
        'emergency_contacts': emergency_contacts,
        'safety_tips': safety_tips,
        'guidelines': guidelines,
        'helplines': helplines,
    }
    
    return render(request, 'alerts/safety_resources.html', context)


@login_required
def create_safety_resource_view(request):
    """Create a safety resource (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to create safety resources.')
        return redirect('safety_resources')
    
    if request.method == 'POST':
        form = SafetyResourceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Safety resource created successfully!')
            return redirect('safety_resources')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SafetyResourceForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'alerts/create_safety_resource.html', context)


@login_required
def edit_safety_resource_view(request, resource_id):
    """Edit a safety resource (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to edit safety resources.')
        return redirect('safety_resources')
    
    resource = get_object_or_404(SafetyResource, id=resource_id)
    
    if request.method == 'POST':
        form = SafetyResourceForm(request.POST, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, 'Safety resource updated successfully!')
            return redirect('safety_resources')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SafetyResourceForm(instance=resource)
    
    context = {
        'form': form,
        'resource': resource,
    }
    
    return render(request, 'alerts/edit_safety_resource.html', context)


@login_required
def delete_safety_resource_view(request, resource_id):
    """Delete a safety resource (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to delete safety resources.')
        return redirect('safety_resources')
    
    resource = get_object_or_404(SafetyResource, id=resource_id)
    
    if request.method == 'POST':
        resource.delete()
        messages.success(request, 'Safety resource deleted successfully!')
        return redirect('safety_resources')
    
    context = {
        'resource': resource,
    }
    
    return render(request, 'alerts/delete_safety_resource.html', context)


def get_active_alerts_json(request):
    """Get active alerts as JSON"""
    alerts = Alert.objects.filter(is_active=True)
    
    data = []
    for alert in alerts:
        if not alert.is_expired():
            data.append({
                'id': alert.id,
                'title': alert.title,
                'message': alert.message,
                'priority': alert.priority,
                'latitude': float(alert.latitude) if alert.latitude else None,
                'longitude': float(alert.longitude) if alert.longitude else None,
                'radius': alert.radius,
                'created_at': alert.created_at.isoformat(),
            })
    
    return JsonResponse({'alerts': data})
