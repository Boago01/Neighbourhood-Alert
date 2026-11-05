from uuid import uuid4

from django.conf import settings
from django.db import models

from .storage import PrivateProblemReportStorage


def generate_report_reference():
    return f'PR-{uuid4().hex.upper()}'


def private_screenshot_storage():
    return PrivateProblemReportStorage()


class ProblemReport(models.Model):
    CATEGORY_CHOICES = [
        ('bug_error', 'Bug or error'),
        ('page_not_loading', 'Page not loading'),
        ('feature_not_working', 'Feature not working'),
        ('incorrect_information', 'Incorrect information'),
        ('other', 'Other'),
    ]

    STATUS_SUBMITTED = 'submitted'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_RESOLVED = 'resolved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_RESOLVED, 'Resolved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    reference = models.CharField(
        max_length=35,
        unique=True,
        default=generate_report_reference,
        editable=False,
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='problem_reports',
    )
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=5000)
    page_path = models.CharField(max_length=500)
    expected_behavior = models.TextField(max_length=3000)
    screenshot = models.ImageField(
        upload_to='screenshots/',
        storage=private_screenshot_storage,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED,
    )
    administrator_notes = models.TextField(max_length=5000, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_problem_reports',
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.reference}: {self.title}'

    @property
    def status_badge_class(self):
        return {
            self.STATUS_SUBMITTED: 'primary',
            self.STATUS_UNDER_REVIEW: 'warning',
            self.STATUS_RESOLVED: 'success',
            self.STATUS_REJECTED: 'secondary',
        }[self.status]
