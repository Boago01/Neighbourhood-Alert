from django.urls import path

from . import views

urlpatterns = [
    path('', views.problem_report_create_view, name='problem_report_create'),
    path('mine/', views.problem_report_mine_view, name='problem_report_mine'),
    path(
        'manage/',
        views.problem_report_admin_list_view,
        name='problem_report_admin_list',
    ),
    path(
        'manage/<str:reference>/',
        views.problem_report_admin_detail_view,
        name='problem_report_admin_detail',
    ),
    path(
        'manage/<str:reference>/update/',
        views.problem_report_admin_update_view,
        name='problem_report_admin_update',
    ),
    path(
        '<str:reference>/screenshot/',
        views.problem_report_screenshot_view,
        name='problem_report_screenshot',
    ),
    path(
        '<str:reference>/',
        views.problem_report_detail_view,
        name='problem_report_detail',
    ),
]
