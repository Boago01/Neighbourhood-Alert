import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import User
from .error_utils import sanitize_problem_page_path
from .error_views import server_error
from .models import ProblemReport


def image_upload(image_format='PNG', filename=None, extra=b''):
    output = io.BytesIO()
    Image.new('RGB', (4, 4), color='blue').save(output, format=image_format)
    extension = {
        'JPEG': 'jpg',
        'PNG': 'png',
        'WEBP': 'webp',
        'GIF': 'gif',
    }[image_format]
    return SimpleUploadedFile(
        filename or f'screenshot.{extension}',
        output.getvalue() + extra,
        content_type=f'image/{image_format.lower()}',
    )


class ProblemReportFeatureTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='report-owner',
            password='test-password',
            role='resident',
            is_active=True,
        )
        self.other_user = User.objects.create_user(
            username='other-user',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        self.administrator = User.objects.create_user(
            username='report-admin',
            password='test-password',
            role='admin',
            is_active=True,
        )
        self.storage_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage_temp.cleanup)
        self.storage = ProblemReport._meta.get_field('screenshot').storage
        self.storage._location = self.storage_temp.name
        self.storage.__dict__.pop('location', None)

    def report_data(self, **overrides):
        data = {
            'category': 'bug_error',
            'title': 'Button does not work',
            'description': 'The save button stays disabled.',
            'page_path': '/alerts/',
            'expected_behavior': 'The alert should save.',
        }
        data.update(overrides)
        return data

    def create_report(self, reporter=None, **overrides):
        return ProblemReport.objects.create(
            reporter=reporter or self.owner,
            **self.report_data(**overrides),
        )

    def test_authenticated_user_can_submit_and_report_gets_unique_reference(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('problem_report_create'),
            self.report_data(),
        )

        report = ProblemReport.objects.get()
        self.assertRedirects(
            response,
            reverse('problem_report_detail', args=[report.reference]),
        )
        self.assertEqual(report.reporter, self.owner)
        self.assertEqual(report.status, ProblemReport.STATUS_SUBMITTED)
        self.assertTrue(report.reference.startswith('PR-'))

        second_report = self.create_report(title='Another report')
        self.assertNotEqual(report.reference, second_report.reference)

    def test_opening_submission_form_does_not_create_a_report(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('problem_report_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-problem-report-form')
        self.assertFalse(ProblemReport.objects.exists())

    def test_base_navigation_and_footer_have_no_permanent_report_links(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/problem-reports/"')
        self.assertNotContains(response, 'href="/problem-reports/mine/"')
        self.assertNotContains(response, 'Problem Reports</a>')

    def test_login_preserves_safe_report_return_path(self):
        login_page = self.client.get(
            f'{reverse("login")}?next={reverse("problem_report_create")}',
        )
        self.assertContains(
            login_page,
            f'value="{reverse("problem_report_create")}"',
        )

        response = self.client.post(
            reverse('login'),
            {
                'username': self.owner.username,
                'password': 'test-password',
                'next': reverse('problem_report_create'),
            },
        )
        self.assertRedirects(response, reverse('problem_report_create'))

    def test_unauthenticated_users_cannot_access_protected_pages(self):
        report = self.create_report()
        for url in (
            reverse('problem_report_create'),
            reverse('problem_report_mine'),
            reverse('problem_report_detail', args=[report.reference]),
            reverse('problem_report_admin_list'),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('login')))

    def test_submission_and_review_changes_require_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        response = csrf_client.post(
            reverse('problem_report_create'),
            self.report_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ProblemReport.objects.exists())

        report = self.create_report()
        csrf_client.force_login(self.administrator)
        response = csrf_client.post(
            reverse('problem_report_admin_update', args=[report.reference]),
            {
                'status': ProblemReport.STATUS_RESOLVED,
                'administrator_notes': 'Resolved.',
            },
        )
        self.assertEqual(response.status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.status, ProblemReport.STATUS_SUBMITTED)

    def test_users_can_only_see_their_own_reports(self):
        own_report = self.create_report()
        other_report = self.create_report(
            reporter=self.other_user,
            title='Private issue',
        )
        self.client.force_login(self.owner)

        list_response = self.client.get(reverse('problem_report_mine'))
        own_response = self.client.get(
            reverse('problem_report_detail', args=[own_report.reference]),
        )
        other_response = self.client.get(
            reverse('problem_report_detail', args=[other_report.reference]),
        )

        self.assertContains(list_response, own_report.reference)
        self.assertNotContains(list_response, other_report.reference)
        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(other_response.status_code, 404)

    def test_admin_can_filter_reports_and_update_status_and_notes(self):
        report = self.create_report()
        self.client.force_login(self.administrator)

        response = self.client.get(
            reverse('problem_report_admin_list'),
            {'status': ProblemReport.STATUS_SUBMITTED},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, report.reference)

        response = self.client.post(
            reverse('problem_report_admin_update', args=[report.reference]),
            {
                'status': ProblemReport.STATUS_UNDER_REVIEW,
                'administrator_notes': 'Investigating the reported issue.',
            },
        )

        report.refresh_from_db()
        self.assertRedirects(
            response,
            reverse('problem_report_admin_detail', args=[report.reference]),
        )
        self.assertEqual(report.status, ProblemReport.STATUS_UNDER_REVIEW)
        self.assertEqual(report.administrator_notes, 'Investigating the reported issue.')
        self.assertEqual(report.reviewed_by, self.administrator)

    def test_non_administrators_cannot_list_or_update_reports(self):
        report = self.create_report()
        self.client.force_login(self.owner)

        list_response = self.client.get(reverse('problem_report_admin_list'))
        update_response = self.client.post(
            reverse('problem_report_admin_update', args=[report.reference]),
            {
                'status': ProblemReport.STATUS_RESOLVED,
                'administrator_notes': 'Not allowed',
            },
        )

        report.refresh_from_db()
        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(report.status, ProblemReport.STATUS_SUBMITTED)
        self.assertEqual(report.administrator_notes, '')

    def test_invalid_form_and_local_page_path_with_query_are_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('problem_report_create'),
            self.report_data(title='', page_path='/alerts/?token=private'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProblemReport.objects.exists())
        self.assertIn('title', response.context['form'].errors)
        self.assertIn('page_path', response.context['form'].errors)
        self.assertContains(
            response,
            'class="modal fade" id="unexpectedErrorModal"',
        )

    def test_page_paths_redact_sensitive_segments_and_reject_query_strings(self):
        self.client.force_login(self.owner)
        safe_response = self.client.post(
            reverse('problem_report_create'),
            self.report_data(
                page_path='/accounts/password-reset/private-token-value/',
            ),
        )
        self.assertEqual(safe_response.status_code, 302)
        report = ProblemReport.objects.get()
        self.assertEqual(report.page_path, '/accounts/[redacted]/[redacted]/')

        rejected_response = self.client.post(
            reverse('problem_report_create'),
            self.report_data(title='Query string case', page_path='/alerts/?token=do-not-store'),
        )
        self.assertEqual(rejected_response.status_code, 200)
        self.assertEqual(ProblemReport.objects.count(), 1)

    def test_server_error_fallback_shows_generic_report_prompt_only(self):
        request = self.client.get('/incidents/private-token-value/?session=secret').wsgi_request
        response = server_error(request)

        self.assertEqual(response.status_code, 500)
        body = response.content.decode()
        self.assertIn('Something went wrong', body)
        self.assertIn('Report Problem', body)
        self.assertIn('data-page-path="/incidents/[redacted]/"', body)
        self.assertNotIn('private-token-value', body)
        self.assertNotIn('session=secret', body)
        self.assertNotIn('Traceback', body)

    def test_error_fallback_does_not_offer_reporting_on_problem_report_routes(self):
        request = self.client.get('/problem-reports/private-token-value/').wsgi_request
        response = server_error(request)

        self.assertEqual(response.status_code, 500)
        self.assertNotIn(
            'data-server-error-report',
            response.content.decode(),
        )

    def test_admin_rejects_invalid_status(self):
        report = self.create_report()
        self.client.force_login(self.administrator)

        response = self.client.post(
            reverse('problem_report_admin_update', args=[report.reference]),
            {'status': 'unknown', 'administrator_notes': 'Test'},
        )

        report.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(report.status, ProblemReport.STATUS_SUBMITTED)
        self.assertIsNone(report.reviewed_by)

    def test_unsupported_invalid_and_oversized_screenshots_are_rejected(self):
        self.client.force_login(self.owner)
        cases = [
            ('unsupported extension', image_upload('GIF')),
            ('invalid image bytes', SimpleUploadedFile(
                'broken.jpg',
                b'not an image',
                content_type='image/jpeg',
            )),
            ('oversized image', image_upload('PNG', extra=b'x' * (5 * 1024 * 1024))),
        ]
        for label, upload in cases:
            with self.subTest(label=label):
                response = self.client.post(
                    reverse('problem_report_create'),
                    {
                        **self.report_data(title=f'Report {label}'),
                        'screenshot': upload,
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn('screenshot', response.context['form'].errors)
        self.assertFalse(ProblemReport.objects.exists())

    def test_screenshot_is_private_and_download_requires_owner_or_admin(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('problem_report_create'),
            {
                **self.report_data(),
                'screenshot': image_upload(),
            },
        )
        report = ProblemReport.objects.get()
        screenshot_path = report.screenshot.path
        self.assertTrue(screenshot_path.startswith(self.storage_temp.name))
        self.assertNotIn('media', screenshot_path.lower())
        self.assertRedirects(
            response,
            reverse('problem_report_detail', args=[report.reference]),
        )

        download_url = reverse(
            'problem_report_screenshot',
            args=[report.reference],
        )
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(download_url).status_code, 404)

        self.client.force_login(self.owner)
        owner_response = self.client.get(download_url)
        self.assertEqual(owner_response.status_code, 200)
        self.assertTrue(owner_response['Content-Disposition'].startswith('attachment;'))
        owner_response.close()

        self.client.force_login(self.administrator)
        admin_response = self.client.get(download_url)
        self.assertEqual(admin_response.status_code, 200)
        admin_response.close()

    def test_successful_submission_message_contains_reference(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('problem_report_create'),
            self.report_data(),
            follow=True,
        )
        report = ProblemReport.objects.get()
        self.assertContains(response, report.reference)
        self.assertContains(response, 'submitted successfully')
