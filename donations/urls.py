from django.urls import path
from . import views

urlpatterns = [
    path('', views.donation_list_view, name='donation_list'),
    path('campaign/create/', views.create_campaign_view, name='create_campaign'),
    path('campaign/<int:campaign_id>/', views.campaign_detail_view, name='campaign_detail'),
    path('campaign/<int:campaign_id>/delete/', views.delete_campaign_view, name='delete_campaign'),
    path('campaign/<int:campaign_id>/donate/', views.donate_to_campaign_view, name='donate_to_campaign'),
    path('campaign/<int:campaign_id>/status-update/<int:donation_id>/<str:status>/', views.update_donation_status_view, name='update_donation_status'),
    path('my-campaigns/', views.my_campaigns_view, name='my_campaigns'),
    path('volunteer/<int:volunteer_id>/donate/', views.donate_to_volunteer_view, name='donate_to_volunteer'),
    path('my-donations/', views.my_donations_view, name='my_donations'),
    path('request-payout/', views.request_payout_view, name='request_payout'),
    path('pending-payouts/', views.pending_payouts_view, name='pending_payouts'),
    path('payout/<int:payout_id>/process/', views.process_payout_view, name='process_payout'),
    path('all-donations/', views.all_donations_view, name='all_donations'),
]
