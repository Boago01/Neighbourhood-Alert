from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('police/register/', views.police_register_view, name='police_register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('users/', views.user_management_view, name='user_management'),
    path('users/police-applications/', views.pending_police_applications_view, name='pending_police_applications'),
    path('users/police-applications/<int:user_id>/review/', views.review_police_application_view, name='review_police_application'),
    path('users/toggle/<int:user_id>/', views.toggle_user_status_view, name='toggle_user_status'),
    path('users/<int:user_id>/remove/', views.remove_user_view, name='remove_user'),
    path(
        'password_reset/',
        views.password_reset_request_view,
        name='password_reset',
    ),
    path(
        'password_reset/done/',
        views.password_reset_done_view,
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),
    # Password change using Django auth views
    path('password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
]
