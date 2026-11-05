from collections import defaultdict

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from incidents.models import Incident
from accounts.models import User
from volunteers.models import Volunteer
from donations.models import Donation
from alerts.models import Alert

PUBLIC_HEATMAP_MIN_INCIDENTS = 2


@login_required
def heatmap_view(request):
    """Show exact incident locations to authenticated users."""
    can_view_exact_locations = request.user.is_authenticated
    can_filter_incidents = (
        request.user.is_police() or request.user.is_admin_user()
    )
    incidents = Incident.objects.all()

    severity_filter = category = date_from = date_to = ''
    if can_filter_incidents:
        severity_filter = request.GET.get('severity', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        category = request.GET.get('category', '')
        if severity_filter:
            incidents = incidents.filter(severity=severity_filter)
        if date_from:
            incidents = incidents.filter(created_at__date__gte=date_from)
        if date_to:
            incidents = incidents.filter(created_at__date__lte=date_to)
        if category:
            incidents = incidents.filter(category=category)

    if can_view_exact_locations:
        map_points = [
            {
                'lat': float(incident.latitude),
                'lng': float(incident.longitude),
                'severity': incident.severity,
                'title': incident.title,
                'category': incident.get_category_display(),
                'id': incident.pk,
                'count': 1,
                'exact': True,
            }
            for incident in incidents
        ]
    else:
        area_counts = defaultdict(int)
        for latitude, longitude in incidents.values_list('latitude', 'longitude'):
            area_counts[(round(float(latitude), 2), round(float(longitude), 2))] += 1
        map_points = [
            {
                'lat': latitude,
                'lng': longitude,
                'count': count,
                'exact': False,
            }
            for (latitude, longitude), count in sorted(area_counts.items())
            if count >= PUBLIC_HEATMAP_MIN_INCIDENTS
        ]

    context = {
        'map_points': map_points,
        'incident_count': len(map_points),
        'can_view_exact_locations': can_view_exact_locations,
        'can_filter_incidents': can_filter_incidents,
        'severity_filter': severity_filter,
        'date_from': date_from,
        'date_to': date_to,
        'category': category,
        'categories': Incident.CATEGORY_CHOICES,
        'severities': Incident.SEVERITY_CHOICES,
    }
    
    return render(request, 'analytics/heatmap.html', context)


@login_required
def statistics_view(request):
    """Statistics dashboard view"""
    if not (request.user.is_police() or request.user.is_admin_user()):
        messages.error(request, 'You do not have permission to view statistics.')
        return redirect('dashboard')
    
    # Date ranges
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    
    # Incident statistics
    total_incidents = Incident.objects.count()
    incidents_last_7_days = Incident.objects.filter(created_at__date__gte=last_7_days).count()
    incidents_last_30_days = Incident.objects.filter(created_at__date__gte=last_30_days).count()
    
    # Incidents by status
    incidents_by_status = {
        'active': Incident.objects.filter(status='active').count(),
        'investigating': Incident.objects.filter(status='investigating').count(),
        'resolved': Incident.objects.filter(status='resolved').count(),
        'closed': Incident.objects.filter(status='closed').count(),
    }
    
    # Incidents by severity
    incidents_by_severity = {
        'low': Incident.objects.filter(severity='low').count(),
        'medium': Incident.objects.filter(severity='medium').count(),
        'high': Incident.objects.filter(severity='high').count(),
        'critical': Incident.objects.filter(severity='critical').count(),
    }
    
    # Incidents by category
    incidents_by_category = Incident.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # User statistics
    total_users = User.objects.count()
    users_by_role = {
        'resident': User.objects.filter(role='resident').count(),
        'volunteer': User.objects.filter(role='volunteer').count(),
        'police': User.objects.filter(role='police').count(),
        'admin': User.objects.filter(role='admin').count(),
    }
    
    # Volunteer statistics
    total_volunteers = Volunteer.objects.filter(is_approved=True).count()
    pending_volunteers = Volunteer.objects.filter(is_approved=False).count()
    
    # Donation statistics
    total_donations = Donation.objects.filter(is_paid=True).count()
    total_donation_amount = Donation.objects.filter(is_paid=True).values_list('amount', flat=True)
    total_donation_amount = sum(total_donation_amount) if total_donation_amount else 0
    
    # Recent trends (last 7 days)
    daily_incidents = []
    for i in range(7):
        date = today - timedelta(days=i)
        count = Incident.objects.filter(created_at__date=date).count()
        daily_incidents.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': count
        })
    daily_incidents.reverse()
    
    context = {
        'total_incidents': total_incidents,
        'incidents_last_7_days': incidents_last_7_days,
        'incidents_last_30_days': incidents_last_30_days,
        'incidents_by_status': incidents_by_status,
        'incidents_by_severity': incidents_by_severity,
        'incidents_by_category': incidents_by_category,
        'total_users': total_users,
        'users_by_role': users_by_role,
        'total_volunteers': total_volunteers,
        'pending_volunteers': pending_volunteers,
        'total_donations': total_donations,
        'total_donation_amount': total_donation_amount,
        'daily_incidents': daily_incidents,
    }
    
    return render(request, 'analytics/statistics.html', context)


@login_required
def incident_trends_view(request):
    """View incident trends over time"""
    if not (request.user.is_police() or request.user.is_admin_user()):
        messages.error(request, 'You do not have permission to view trends.')
        return redirect('dashboard')
    
    # Get date range
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Daily incident counts
    daily_data = []
    current_date = start_date
    while current_date <= end_date:
        count = Incident.objects.filter(created_at__date=current_date).count()
        daily_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'count': count
        })
        current_date += timedelta(days=1)
    
    # Category trends
    category_trends = []
    for category_code, category_name in Incident.CATEGORY_CHOICES:
        counts = []
        current_date = start_date
        while current_date <= end_date:
            count = Incident.objects.filter(
                category=category_code,
                created_at__date=current_date
            ).count()
            counts.append(count)
            current_date += timedelta(days=1)
        
        category_trends.append({
            'name': category_name,
            'data': counts
        })
    
    context = {
        'days': days,
        'daily_data': daily_data,
        'category_trends': category_trends,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'analytics/incident_trends.html', context)


@login_required
def hotspot_analysis_view(request):
    """Analyze crime hotspots"""
    if not (request.user.is_police() or request.user.is_admin_user()):
        messages.error(request, 'You do not have permission to view hotspot analysis.')
        return redirect('dashboard')
    
    # Get incidents grouped by location description
    hotspots = Incident.objects.values('location_description').annotate(
        count=Count('id'),
        high_severity=Count('id', filter=Q(severity__in=['high', 'critical']))
    ).filter(count__gte=2).order_by('-count')[:20]
    
    # Get recent high-severity incidents
    recent_high_severity = Incident.objects.filter(
        severity__in=['high', 'critical']
    ).order_by('-created_at')[:10]
    
    context = {
        'hotspots': hotspots,
        'recent_high_severity': recent_high_severity,
    }
    
    return render(request, 'analytics/hotspot_analysis.html', context)


def get_statistics_json(request):
    """Get statistics as JSON for API"""
    data = {
        'total_incidents': Incident.objects.count(),
        'active_incidents': Incident.objects.filter(status='active').count(),
        'resolved_incidents': Incident.objects.filter(status='resolved').count(),
        'total_users': User.objects.count(),
        'active_volunteers': Volunteer.objects.filter(is_approved=True, is_active=True).count(),
        'active_alerts': Alert.objects.filter(is_active=True).count(),
    }
    
    return JsonResponse(data)
