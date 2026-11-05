from django.shortcuts import render

from .error_utils import sanitize_problem_page_path


def server_error(request):
    page_path = sanitize_problem_page_path(request.path)
    return render(
        request,
        '500.html',
        {
            'safe_page_path': page_path,
            'can_report_error': not page_path.startswith('/problem-reports/'),
        },
        status=500,
    )
