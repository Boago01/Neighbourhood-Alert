from django.urls import path
from . import views

urlpatterns = [
    path('', views.volunteer_list_view, name='volunteer_list'),
    path('apply/', views.volunteer_application_view, name='volunteer_application'),
    path('dashboard/', views.volunteer_dashboard_view, name='volunteer_dashboard'),
    path('pending-approvals/', views.pending_approvals_view, name='pending_approvals'),
    path('<int:volunteer_id>/', views.volunteer_detail_view, name='volunteer_detail'),
    path('<int:volunteer_id>/approve/', views.approve_volunteer_view, name='approve_volunteer'),
    path('<int:volunteer_id>/reject/', views.reject_volunteer_view, name='reject_volunteer'),
    path('<int:volunteer_id>/review/', views.add_volunteer_review_view, name='add_volunteer_review'),
    path('respond/<int:incident_id>/', views.respond_to_incident_view, name='respond_to_incident'),
    path('response/<int:response_id>/update/', views.update_response_status_view, name='update_response_status'),
]
