from django.urls import path
from . import views

urlpatterns = [
    path('', views.alert_list_view, name='alert_list'),
    path('create/', views.create_alert_view, name='create_alert'),
    path('api/active-alerts/', views.get_active_alerts_json, name='active_alerts_json'),
    path('<int:alert_id>/', views.alert_detail_view, name='alert_detail'),
    path('<int:alert_id>/acknowledge/', views.acknowledge_alert_view, name='acknowledge_alert'),
    path('<int:alert_id>/deactivate/', views.deactivate_alert_view, name='deactivate_alert'),
    path('safety-resources/', views.safety_resources_view, name='safety_resources'),
    path('safety-resources/create/', views.create_safety_resource_view, name='create_safety_resource'),
    path('safety-resources/<int:resource_id>/edit/', views.edit_safety_resource_view, name='edit_safety_resource'),
    path('safety-resources/<int:resource_id>/delete/', views.delete_safety_resource_view, name='delete_safety_resource'),
]
