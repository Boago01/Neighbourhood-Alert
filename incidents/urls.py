from django.urls import path
from . import views

urlpatterns = [
    path('', views.incident_feed_view, name='incident_feed'),
    path('report/', views.report_incident_view, name='report_incident'),
    path('my-incidents/', views.my_incidents_view, name='my_incidents'),
    path('api/incidents/', views.get_incidents_json, name='incidents_json'),
    path('<int:incident_id>/', views.incident_detail_view, name='incident_detail'),
    path('<int:incident_id>/comment/', views.add_comment_view, name='add_comment'),
    path('<int:incident_id>/update-status/', views.update_incident_status_view, name='update_incident_status'),
    path('<int:incident_id>/assign/', views.assign_incident_view, name='assign_incident'),
    path('<int:incident_id>/delete/', views.delete_incident_view, name='delete_incident'),
    
    # Police officer routes
    path('police/my-cases/', views.police_my_cases_view, name='police_my_cases'),
    path('police/<int:incident_id>/assign-volunteers/', views.police_assign_volunteers_view, name='police_assign_volunteers'),
    path('police/<int:incident_id>/monitor/', views.police_monitor_case_view, name='police_monitor_case'),
    path('police/<int:incident_id>/close/', views.police_close_case_view, name='police_close_case'),
    path('police/assignment/<int:assignment_id>/remove-volunteer/', views.police_remove_volunteer_view, name='police_remove_volunteer'),
    
    # Volunteer routes
    path('volunteer/assigned-cases/', views.volunteer_assigned_cases_view, name='volunteer_assigned_cases'),
    path('volunteer/assignment/<int:assignment_id>/', views.volunteer_assignment_detail_view, name='volunteer_assignment_detail'),
    path('volunteer/assignment/<int:assignment_id>/update-status/', views.volunteer_update_assignment_status_view, name='volunteer_update_status'),
    path('volunteer/assignment/<int:assignment_id>/update-progress/', views.volunteer_update_progress_view, name='volunteer_update_progress'),
    path('volunteer/assignment/<int:assignment_id>/submit-report/', views.volunteer_submit_completion_report_view, name='volunteer_submit_report'),
]
