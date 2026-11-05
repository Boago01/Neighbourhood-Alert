import mimetypes
from pathlib import PurePosixPath

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    ProblemReportFilterForm,
    ProblemReportForm,
    ProblemReportReviewForm,
)
from .models import ProblemReport


def _require_problem_report_admin(user):
    if not user.is_admin_user():
        raise PermissionDenied


@login_required
def problem_report_create_view(request):
    if request.method == 'POST':
        form = ProblemReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.save()
            messages.success(
                request,
                f'Problem report {report.reference} was submitted successfully.',
            )
            return redirect('problem_report_detail', reference=report.reference)
    else:
        form = ProblemReportForm()

    return render(request, 'problem_reports/report_form.html', {'form': form})


@login_required
def problem_report_mine_view(request):
    reports = ProblemReport.objects.filter(reporter=request.user)
    return render(
        request,
        'problem_reports/my_reports.html',
        {'reports': reports},
    )


@login_required
def problem_report_detail_view(request, reference):
    report = get_object_or_404(
        ProblemReport.objects.filter(reporter=request.user),
        reference=reference,
    )
    return render(
        request,
        'problem_reports/report_detail.html',
        {'report': report, 'is_administrator': False},
    )


@login_required
def problem_report_admin_list_view(request):
    _require_problem_report_admin(request.user)
    filter_form = ProblemReportFilterForm(request.GET)
    reports = ProblemReport.objects.select_related('reporter', 'reviewed_by')
    if filter_form.is_valid() and filter_form.cleaned_data['status']:
        reports = reports.filter(status=filter_form.cleaned_data['status'])
    return render(
        request,
        'problem_reports/admin_list.html',
        {'reports': reports, 'filter_form': filter_form},
    )


@login_required
def problem_report_admin_detail_view(request, reference):
    _require_problem_report_admin(request.user)
    report = get_object_or_404(
        ProblemReport.objects.select_related('reporter', 'reviewed_by'),
        reference=reference,
    )
    review_form = ProblemReportReviewForm(instance=report)
    return render(
        request,
        'problem_reports/admin_detail.html',
        {'report': report, 'review_form': review_form},
    )


@login_required
@require_POST
def problem_report_admin_update_view(request, reference):
    _require_problem_report_admin(request.user)
    report = get_object_or_404(ProblemReport, reference=reference)
    review_form = ProblemReportReviewForm(request.POST, instance=report)
    if review_form.is_valid():
        report = review_form.save(commit=False)
        report.reviewed_by = request.user
        report.save(update_fields=[
            'status',
            'administrator_notes',
            'reviewed_by',
            'updated_at',
        ])
        messages.success(request, f'{report.reference} was updated.')
        return redirect('problem_report_admin_detail', reference=report.reference)

    return render(
        request,
        'problem_reports/admin_detail.html',
        {'report': report, 'review_form': review_form},
    )


@login_required
def problem_report_screenshot_view(request, reference):
    report = get_object_or_404(ProblemReport, reference=reference)
    if (
        report.reporter_id != request.user.pk
        and not request.user.is_admin_user()
    ):
        raise Http404
    if not report.screenshot:
        raise Http404

    try:
        screenshot = report.screenshot.open('rb')
    except OSError as error:
        raise Http404 from error

    suffix = PurePosixPath(report.screenshot.name).suffix.lower()
    content_type = mimetypes.guess_type(f'screenshot{suffix}')[0]
    response = FileResponse(
        screenshot,
        as_attachment=True,
        filename=f'{report.reference}-screenshot{suffix}',
        content_type=content_type or 'application/octet-stream',
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response
