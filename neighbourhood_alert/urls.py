"""
URL configuration for neighbourhood_alert project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('incidents/', include('incidents.urls')),
    path('volunteers/', include('volunteers.urls')),
    path('donations/', include('donations.urls')),
    path('alerts/', include('alerts.urls')),
    path('analytics/', include('analytics.urls')),
    path('problem-reports/', include('problem_reports.urls')),
]

handler500 = 'problem_reports.error_views.server_error'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
