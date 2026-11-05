from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DonationCampaign, Donation, Payout, DonationCampaignItem
from .forms import DonationCampaignForm, DonationForm, PayoutRequestForm, PayoutProcessForm


def donation_list_view(request):
    """List all active donation campaigns"""
    campaigns = DonationCampaign.objects.filter(status='active').order_by('-created_at')
    
    context = {
        'campaigns': campaigns,
    }
    
    return render(request, 'donations/donation_list.html', context)


def campaign_detail_view(request, campaign_id):
    """View campaign details"""
    campaign = get_object_or_404(DonationCampaign, id=campaign_id)
    can_manage_donations = (
        request.user.is_authenticated
        and (
            campaign.created_by_id == request.user.pk
            or request.user.is_admin_user()
        )
    )
    donations = campaign.donations.none()
    if can_manage_donations:
        donations = campaign.donations.select_related('donor').order_by('-created_at')[:10]
    elif request.user.is_authenticated:
        donations = campaign.donations.filter(
            donor=request.user,
        ).select_related('donor').order_by('-created_at')[:10]

    context = {
        'campaign': campaign,
        'donations': donations,
        'can_manage_donations': can_manage_donations,
        'donation_status_actions': [
            ('accepted', 'Accept', 'btn-success'),
            ('rejected', 'Reject', 'btn-danger'),
            ('collected', 'Mark Collected', 'btn-warning'),
            ('completed', 'Mark Completed', 'btn-primary'),
        ],
    }
    
    return render(request, 'donations/campaign_detail.html', context)


@login_required
def create_campaign_view(request):
    """Create a new donation campaign (Volunteers only)"""
    if not request.user.is_volunteer():
        messages.error(request, 'Only volunteers can create donation campaigns.')
        return redirect('donation_list')
    
    if request.method == 'POST':
        form = DonationCampaignForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                campaign = form.save(commit=False)
                campaign.created_by = request.user
                campaign.save()
                form.save_items(campaign)
            messages.success(request, 'Donation campaign created successfully!')
            return redirect('campaign_detail', campaign_id=campaign.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DonationCampaignForm()
    
    context = {
        'form': form,
    }
    
    return render(request, 'donations/create_campaign.html', context)


@login_required
def donate_to_campaign_view(request, campaign_id):
    """Donate to a campaign"""
    campaign = get_object_or_404(DonationCampaign, id=campaign_id, status='active')
    
    if request.method == 'POST':
        form = DonationForm(request.POST, campaign=campaign)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.campaign = campaign
            donation.recipient = campaign.created_by
            donation.donor = request.user
            donation.status = 'pending'
            donation.save()
            
            messages.success(request, f'Thank you for your donation request! The volunteer will manage your donation.')
            return redirect('campaign_detail', campaign_id=campaign.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DonationForm(campaign=campaign)
    
    context = {
        'form': form,
        'campaign': campaign,
    }
    
    return render(request, 'donations/donate.html', context)


@login_required
def donate_to_volunteer_view(request, volunteer_id):
    """Donate directly to a volunteer"""
    from volunteers.models import Volunteer
    
    volunteer = get_object_or_404(
        Volunteer,
        id=volunteer_id,
        is_approved=True,
        is_active=True,
        user__is_active=True,
        user__is_approved=True,
    )
    if request.user.role != 'resident':
        messages.error(request, 'Only residents can donate directly to volunteers.')
        return redirect('volunteer_detail', volunteer_id=volunteer.id)
    
    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
            donation = form.save(commit=False)
            donation.recipient = volunteer.user
            donation.donor = request.user
            donation.status = 'completed'
            donation.is_paid = True
            donation.paid_at = timezone.now()
            donation.save()
            
            messages.success(request, f'Thank you for your donation to {volunteer.user.get_full_name() or volunteer.user.username}!')
            return redirect('volunteer_detail', volunteer_id=volunteer.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = DonationForm()
    
    context = {
        'form': form,
        'volunteer': volunteer,
    }
    
    return render(request, 'donations/donate.html', context)


@login_required
def my_donations_view(request):
    """View donations made by the current user"""
    donations_made = Donation.objects.filter(donor=request.user).order_by('-created_at')
    donations_received = Donation.objects.filter(recipient=request.user).order_by('-created_at')
    
    total_donated = donations_made.aggregate(Sum('quantity'))['quantity__sum'] or 0
    total_received = donations_received.aggregate(Sum('quantity'))['quantity__sum'] or 0
    
    context = {
        'donations_made': donations_made,
        'donations_received': donations_received,
        'total_donated': total_donated,
        'total_received': total_received,
    }
    
    return render(request, 'donations/my_donations.html', context)


@login_required
def my_campaigns_view(request):
    """View a volunteer's own campaigns and donation activity"""
    if not request.user.is_volunteer():
        messages.error(request, 'Only volunteers can view this page.')
        return redirect('dashboard')
    
    campaigns = DonationCampaign.objects.filter(created_by=request.user).order_by('-created_at')
    context = {
        'campaigns': campaigns,
    }
    return render(request, 'donations/my_campaigns.html', context)


@login_required
def delete_campaign_view(request, campaign_id):
    """Delete a campaign created by the current volunteer."""
    if not request.user.is_volunteer():
        messages.error(request, 'Only volunteers can delete campaigns.')
        return redirect('dashboard')

    campaign = get_object_or_404(
        DonationCampaign,
        id=campaign_id,
        created_by=request.user,
    )

    if request.method == 'POST':
        campaign_title = campaign.title
        campaign.delete()
        messages.success(request, f'Campaign "{campaign_title}" was deleted.')
        return redirect('my_campaigns')

    return render(request, 'donations/delete_campaign.html', {'campaign': campaign})


@login_required
@require_POST
def update_donation_status_view(request, campaign_id, donation_id, status):
    """Update donation workflow status for volunteer campaigns."""
    campaign = get_object_or_404(DonationCampaign, id=campaign_id, created_by=request.user)
    donation = get_object_or_404(Donation, id=donation_id, campaign=campaign)
    allowed_statuses = ['accepted', 'rejected', 'collected', 'completed']
    if status not in allowed_statuses:
        messages.error(request, 'Invalid donation status.')
        return redirect('campaign_detail', campaign_id=campaign.id)
    
    prior_status = donation.status
    donation.status = status
    donation.save()
    
    if prior_status != 'completed' and status == 'completed' and donation.campaign_item:
        item = donation.campaign_item
        item.quantity_received = min(item.quantity_needed, item.quantity_received + donation.quantity)
        item.save()

    messages.success(request, f'Donation status updated to {donation.get_status_display()}.')
    return redirect('campaign_detail', campaign_id=campaign.id)


@login_required
def request_payout_view(request):
    """Request a payout (Volunteers only)"""
    if not request.user.is_volunteer():
        messages.error(request, 'Only volunteers can request payouts.')
        return redirect('dashboard')
    
    # Calculate available balance
    total_received = Donation.objects.filter(recipient=request.user, is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0
    total_paid_out = Payout.objects.filter(volunteer=request.user, status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    available_balance = total_received - total_paid_out
    
    if request.method == 'POST':
        form = PayoutRequestForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            
            if amount > available_balance:
                messages.error(request, f'Insufficient balance. You have R{available_balance} available.')
                return redirect('request_payout')
            
            payout = form.save(commit=False)
            payout.volunteer = request.user
            payout.save()
            
            messages.success(request, 'Payout request submitted successfully!')
            return redirect('my_donations')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PayoutRequestForm()
    
    context = {
        'form': form,
        'available_balance': available_balance,
    }
    
    return render(request, 'donations/request_payout.html', context)


@login_required
def pending_payouts_view(request):
    """View pending payouts (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    payouts = Payout.objects.filter(status__in=['pending', 'processing']).order_by('-requested_at')
    
    context = {
        'payouts': payouts,
    }
    
    return render(request, 'donations/pending_payouts.html', context)


@login_required
def process_payout_view(request, payout_id):
    """Process a payout request (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('dashboard')
    
    payout = get_object_or_404(Payout, id=payout_id)
    
    if request.method == 'POST':
        form = PayoutProcessForm(request.POST, instance=payout)
        if form.is_valid():
            payout = form.save(commit=False)
            payout.processed_at = timezone.now()
            payout.processed_by = request.user
            payout.save()
            
            status_display = payout.get_status_display()
            messages.success(request, f'Payout has been {status_display.lower()}.')
            return redirect('pending_payouts')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PayoutProcessForm(instance=payout)
    
    context = {
        'form': form,
        'payout': payout,
    }
    
    return render(request, 'donations/process_payout.html', context)


@login_required
def all_donations_view(request):
    """View all donations (Admin only)"""
    if not request.user.is_admin_user():
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')
    
    donations = Donation.objects.all().order_by('-created_at')
    
    # Calculate totals
    total_donations = Donation.objects.filter(is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0
    total_campaigns = DonationCampaign.objects.count()
    total_payouts = Payout.objects.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'donations': donations,
        'total_donations': total_donations,
        'total_campaigns': total_campaigns,
        'total_payouts': total_payouts,
    }
    
    return render(request, 'donations/all_donations.html', context)
