from django.urls import path
from . import views

urlpatterns = [
    path('heatmap/', views.heatmap_view, name='heatmap'),
    path('statistics/', views.statistics_view, name='statistics'),
    path('trends/', views.incident_trends_view, name='incident_trends'),
    path('hotspots/', views.hotspot_analysis_view, name='hotspot_analysis'),
    path('api/statistics/', views.get_statistics_json, name='statistics_json'),
]
