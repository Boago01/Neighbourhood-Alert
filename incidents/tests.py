from collections import Counter
from io import StringIO

from django.contrib.admin.sites import site
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from volunteers.models import Volunteer
from .admin import IncidentAdmin
from .forms import IncidentForm, VolunteerProgressForm, validate_image_upload
from .models import Incident, IncidentAssignment


class DemoHeatmapSeedCommandTests(TestCase):
    def setUp(self):
        self.resident = User.objects.create_user(
            username='demo-resident',
            password='Resident-password-123!',
            role='resident',
            is_active=True,
        )

    def test_command_creates_nine_valid_incidents_for_existing_residents(self):
        call_command('seed_demo_heatmap', stdout=StringIO())

        incidents = Incident.objects.filter(title__startswith='DEMO –')
        self.assertEqual(incidents.count(), 9)
        self.assertTrue(
            all(
                incident.description.startswith(
                    'FICTIONAL DEMONSTRATION DATA – NOT A REAL INCIDENT.'
                )
                and incident.status == 'active'
                and incident.reported_by_id == self.resident.pk
                and incident.is_anonymous
                and incident.case_number is None
                for incident in incidents
            )
        )
        self.assertTrue(
            all(
                incident.category in dict(Incident.CATEGORY_CHOICES)
                and incident.severity in dict(Incident.SEVERITY_CHOICES)
                and incident.status in dict(Incident.STATUS_CHOICES)
                for incident in incidents
            )
        )
        rounded_clusters = Counter(
            (
                round(float(incident.latitude), 2),
                round(float(incident.longitude), 2),
            )
            for incident in incidents
        )
        self.assertEqual(sorted(rounded_clusters.values()), [3, 3, 3])

    def test_command_distributes_incidents_across_available_residents(self):
        second_resident = User.objects.create_user(
            username='second-demo-resident',
            password='Resident-password-456!',
            role='resident',
            is_active=True,
        )

        call_command('seed_demo_heatmap', stdout=StringIO())

        assigned_resident_ids = set(
            Incident.objects.filter(title__startswith='DEMO –')
            .values_list('reported_by_id', flat=True)
        )
        self.assertEqual(
            assigned_resident_ids,
            {self.resident.pk, second_resident.pk},
        )

    def test_command_is_idempotent_and_preserves_unrelated_incidents(self):
        genuine = Incident.objects.create(
            title='Existing genuine incident',
            description='Existing record must not be changed.',
            category='theft',
            severity='low',
            latitude='-28.70000000',
            longitude='24.70000000',
        )

        call_command('seed_demo_heatmap', stdout=StringIO())
        call_command('seed_demo_heatmap', stdout=StringIO())

        self.assertEqual(
            Incident.objects.filter(title__startswith='DEMO –').count(),
            9,
        )
        genuine.refresh_from_db()
        self.assertEqual(
            genuine.description,
            'Existing record must not be changed.',
        )

    def test_command_aborts_without_residents(self):
        self.resident.delete()

        with self.assertRaises(CommandError):
            call_command('seed_demo_heatmap', stdout=StringIO())

        self.assertEqual(Incident.objects.count(), 0)

    def test_command_refuses_to_overwrite_an_unmarked_matching_incident(self):
        Incident.objects.create(
            title='DEMO – Mobile phone theft',
            description='An existing record without the demo marker.',
            category='theft',
            severity='high',
            latitude='-28.72820000',
            longitude='24.74990000',
        )

        with self.assertRaises(CommandError):
            call_command('seed_demo_heatmap', stdout=StringIO())

        self.assertEqual(Incident.objects.count(), 1)


class IncidentAdminPermissionsTests(TestCase):
    def test_admin_cannot_edit_incident_status_or_assignment_in_django_admin(self):
        administrator = User.objects.create_user(
            username='incident-admin',
            password='test-password',
            role='admin',
            is_staff=True,
            is_active=True,
            is_approved=True,
        )
        request = RequestFactory().get('/admin/incidents/incident/')
        request.user = administrator
        incident_admin = IncidentAdmin(Incident, site)

        readonly_fields = incident_admin.get_readonly_fields(request)
        actions = incident_admin.get_actions(request)

        self.assertIn('status', readonly_fields)
        self.assertIn('assigned_officer', readonly_fields)
        self.assertNotIn('mark_as_resolved', actions)
        self.assertNotIn('mark_as_investigating', actions)
        self.assertNotIn('mark_as_active', actions)


class VolunteerCompletionReportTests(TestCase):
    def setUp(self):
        self.volunteer = User.objects.create_user(
            username='volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        self.other_volunteer = User.objects.create_user(
            username='other-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        Volunteer.objects.create(
            user=self.volunteer,
            motivation='Help neighbors.',
            is_active=True,
            is_approved=True,
        )
        Volunteer.objects.create(
            user=self.other_volunteer,
            motivation='Help neighbors.',
            is_active=True,
            is_approved=True,
        )
        officer = User.objects.create_user(
            username='officer',
            password='test-password',
            role='police',
        )
        incident = Incident.objects.create(
            title='Street light damaged',
            description='A street light needs attention.',
            category='other',
            severity='medium',
            latitude='-28.7282',
            longitude='24.7499',
        )
        self.assignment = IncidentAssignment.objects.create(
            incident=incident,
            volunteer=self.volunteer,
            assigned_by=officer,
        )
        self.url = reverse(
            'volunteer_submit_report',
            args=[self.assignment.id],
        )

    def test_report_page_renders_for_assigned_volunteer(self):
        self.client.force_login(self.volunteer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            'incidents/volunteer_submit_report.html',
        )

    def test_assigned_volunteer_can_submit_completion_report(self):
        self.client.force_login(self.volunteer)

        response = self.client.post(
            self.url,
            {'completion_report': 'The damaged light was reported and secured.'},
        )

        self.assignment.refresh_from_db()
        self.assertRedirects(response, reverse('volunteer_assigned_cases'))
        self.assertEqual(self.assignment.status, 'completed')
        self.assertEqual(
            self.assignment.completion_report,
            'The damaged light was reported and secured.',
        )
        self.assertIsNotNone(self.assignment.completed_at)

    def test_other_volunteer_cannot_submit_report(self):
        self.client.force_login(self.other_volunteer)

        response = self.client.post(
            self.url,
            {'completion_report': 'Unauthorized update'},
        )

        self.assignment.refresh_from_db()
        self.assertRedirects(response, reverse('volunteer_assigned_cases'))
        self.assertEqual(self.assignment.status, 'pending')
        self.assertIsNone(self.assignment.completion_report)


class IncidentDetailPrivacyTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(
            username='reporter',
            password='test-password',
            role='resident',
            is_approved=True,
        )
        self.other_resident = User.objects.create_user(
            username='other-resident',
            password='test-password',
            role='resident',
            is_approved=True,
        )
        self.officer = User.objects.create_user(
            username='approved-officer',
            password='test-password',
            role='police',
            is_active=True,
            is_approved=True,
        )
        self.administrator = User.objects.create_user(
            username='administrator',
            password='test-password',
            role='admin',
            is_active=True,
            is_approved=True,
        )
        self.police_superuser = User.objects.create_user(
            username='police-superuser',
            password='test-password',
            role='police',
            is_active=True,
            is_approved=True,
            is_staff=True,
            is_superuser=True,
        )
        self.incident = Incident.objects.create(
            title='Private incident',
            description='Sensitive report contents.',
            category='other',
            severity='high',
            latitude='-28.7282',
            longitude='24.7499',
            reported_by=self.reporter,
            investigation_notes='Confidential investigation notes.',
            case_number='CASE-PRIVATE-001',
        )
        self.url = reverse('incident_detail', args=[self.incident.pk])

    def test_anonymous_user_must_log_in_before_viewing_details(self):
        response = self.client.get(self.url)

        self.assertRedirects(response, f'{reverse("login")}?next={self.url}')

    def test_report_form_loads_google_maps_with_configured_api_key(self):
        self.client.force_login(self.reporter)

        with override_settings(GOOGLE_MAPS_API_KEY='test-google-maps-key'):
            response = self.client.get(reverse('report_incident'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://maps.googleapis.com/maps/api/js')
        self.assertContains(response, 'callback=initReportMap')
        self.assertContains(response, 'test-google-maps-key')

    def test_empty_incident_report_displays_required_field_errors(self):
        self.client.force_login(self.reporter)

        response = self.client.post(reverse('report_incident'), {})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'novalidate')
        self.assertContains(response, 'Select a location on the map.')
        self.assertContains(response, 'This field is required.')
        self.assertContains(response, 'invalid-feedback d-block fw-semibold')
        self.assertContains(response, 'Please correct the errors below.')
        self.assertEqual(Incident.objects.count(), 1)

    def test_anonymous_user_must_log_in_before_incident_feed(self):
        response = self.client.get(reverse('incident_feed'))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("incident_feed")}',
        )

    def test_resident_feed_contains_only_their_incidents(self):
        Incident.objects.create(
            title='Another resident incident',
            description='Private report.',
            category='other',
            severity='medium',
            latitude='-28.7282',
            longitude='24.7499',
            reported_by=self.other_resident,
        )
        self.client.force_login(self.reporter)

        response = self.client.get(reverse('incident_feed'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Private incident')
        self.assertNotContains(response, 'Another resident incident')

    def test_incident_locations_api_requires_police_or_admin(self):
        api_url = reverse('incidents_json')
        anonymous_response = self.client.get(api_url)
        self.assertRedirects(
            anonymous_response,
            f'{reverse("login")}?next={api_url}',
        )

        self.client.force_login(self.other_resident)
        resident_response = self.client.get(api_url)
        self.assertEqual(resident_response.status_code, 403)
        self.assertNotContains(
            resident_response,
            'Private incident',
            status_code=403,
        )

    def test_police_can_view_incident_locations_api(self):
        self.client.force_login(self.officer)

        response = self.client.get(reverse('incidents_json'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['incidents']), 1)
        self.assertEqual(
            response.json()['incidents'][0]['title'],
            'Private incident',
        )

    def test_resident_cannot_view_another_residents_private_incident(self):
        self.client.force_login(self.other_resident)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(
            response,
            'Confidential investigation notes.',
            status_code=404,
        )

    def test_reporter_can_view_own_incident(self):
        self.client.force_login(self.reporter)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confidential investigation notes.')
        self.assertNotContains(response, 'Respond to Incident')
        self.assertNotContains(response, reverse('delete_incident', args=[self.incident.pk]))

    def test_admin_can_see_incident_delete_button(self):
        self.client.force_login(self.administrator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('delete_incident', args=[self.incident.pk]))

    def test_approved_police_can_view_incident_details(self):
        self.client.force_login(self.officer)

        with override_settings(GOOGLE_MAPS_API_KEY='test-google-maps-key'):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confidential investigation notes.')
        self.assertContains(response, 'Assign to Me')
        self.assertContains(response, 'Update Status')
        self.assertContains(response, 'https://maps.googleapis.com/maps/api/js')
        self.assertContains(response, 'callback=initIncidentDetailMap')
        self.assertContains(response, 'test-google-maps-key')

    def test_admin_can_view_incident_but_not_police_case_controls(self):
        self.client.force_login(self.administrator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Assign to Me')
        self.assertNotContains(response, 'Update Status')

    def test_admin_cannot_update_incident_status(self):
        self.client.force_login(self.administrator)

        response = self.client.post(
            reverse('update_incident_status', args=[self.incident.pk]),
            {
                'status': 'closed',
                'case_number': 'CASE-PRIVATE-001',
                'investigation_notes': 'Admin status change attempt.',
            },
        )

        self.assertRedirects(response, self.url)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'active')
        self.assertEqual(
            self.incident.investigation_notes,
            'Confidential investigation notes.',
        )

    def test_admin_cannot_assign_incident_to_themselves(self):
        self.client.force_login(self.administrator)

        response = self.client.get(
            reverse('assign_incident', args=[self.incident.pk]),
        )

        self.assertEqual(response.status_code, 405)
        self.incident.refresh_from_db()
        self.assertIsNone(self.incident.assigned_officer)
        self.assertEqual(self.incident.status, 'active')

    def test_police_assignment_requires_post_and_csrf(self):
        assign_url = reverse('assign_incident', args=[self.incident.pk])
        self.client.force_login(self.officer)

        get_response = self.client.get(assign_url)
        self.assertEqual(get_response.status_code, 405)

        response = self.client.post(assign_url)

        self.assertRedirects(response, self.url)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.assigned_officer, self.officer)
        self.assertEqual(self.incident.status, 'investigating')

    def test_police_assignment_form_contains_csrf_token(self):
        self.client.force_login(self.officer)

        response = self.client.get(self.url)

        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_police_cannot_assign_a_pending_volunteer(self):
        pending_user = User.objects.create_user(
            username='pending-volunteer-assignment',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=False,
        )
        Volunteer.objects.create(
            user=pending_user,
            motivation='Awaiting approval.',
            is_active=True,
            is_approved=False,
        )
        self.client.force_login(self.officer)

        response = self.client.post(
            reverse('police_assign_volunteers', args=[self.incident.pk]),
            {
                'volunteers': [str(pending_user.pk)],
                'priority': 'high',
                'assignment_notes': 'Attempted assignment.',
            },
        )

        self.assertRedirects(
            response,
            reverse('police_monitor_case', args=[self.incident.pk]),
        )
        self.assertFalse(
            IncidentAssignment.objects.filter(
                incident=self.incident,
                volunteer=pending_user,
            ).exists()
        )

    def test_unassigned_resident_cannot_add_comment_by_posting_directly(self):
        self.client.force_login(self.other_resident)

        response = self.client.post(
            reverse('add_comment', args=[self.incident.pk]),
            {'content': 'Unauthorized private incident comment.'},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            self.incident.comments.filter(
                content='Unauthorized private incident comment.',
            ).exists()
        )
    def test_superuser_with_police_role_cannot_manage_incidents_as_admin(self):
        self.client.force_login(self.police_superuser)

        response = self.client.post(
            reverse('update_incident_status', args=[self.incident.pk]),
            {'status': 'closed'},
        )

        self.assertRedirects(response, self.url)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, 'active')

    def test_pending_police_cannot_view_incident_details(self):
        pending_officer = User.objects.create_user(
            username='pending-officer',
            password='test-password',
            role='police',
            is_active=True,
            is_approved=False,
        )
        self.client.force_login(pending_officer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_assigned_approved_volunteer_can_view_incident_details(self):
        volunteer_user = User.objects.create_user(
            username='approved-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        Volunteer.objects.create(
            user=volunteer_user,
            motivation='Help neighbors.',
            is_active=True,
            is_approved=True,
        )
        IncidentAssignment.objects.create(
            incident=self.incident,
            volunteer=volunteer_user,
            assigned_by=self.officer,
        )
        self.client.force_login(volunteer_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confidential investigation notes.')

    def test_unassigned_volunteer_cannot_view_incident_details(self):
        volunteer_user = User.objects.create_user(
            username='unassigned-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        Volunteer.objects.create(
            user=volunteer_user,
            motivation='Help neighbors.',
            is_active=True,
            is_approved=True,
        )
        self.client.force_login(volunteer_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_pending_volunteer_cannot_access_assigned_incident_workflow(self):
        pending_user = User.objects.create_user(
            username='pending-assigned-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=False,
        )
        Volunteer.objects.create(
            user=pending_user,
            motivation='Awaiting review.',
            is_active=True,
            is_approved=False,
        )
        assignment = IncidentAssignment.objects.create(
            incident=self.incident,
            volunteer=pending_user,
            assigned_by=self.officer,
        )
        self.client.force_login(pending_user)

        cases_response = self.client.get(reverse('volunteer_assigned_cases'))
        detail_response = self.client.get(
            reverse('volunteer_assignment_detail', args=[assignment.pk]),
        )
        report_response = self.client.post(
            reverse('volunteer_submit_report', args=[assignment.pk]),
            {'completion_report': 'Unauthorized pending report.'},
        )

        self.assertRedirects(cases_response, reverse('dashboard'))
        self.assertEqual(detail_response.status_code, 302)
        self.assertEqual(
            detail_response['Location'],
            reverse('volunteer_assigned_cases'),
        )
        self.assertEqual(report_response.status_code, 302)
        self.assertEqual(
            report_response['Location'],
            reverse('volunteer_assigned_cases'),
        )
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'pending')
        self.assertIsNone(assignment.completion_report)


class ImageUploadValidationTests(TestCase):
    def setUp(self):
        self.volunteer = User.objects.create_user(
            username='upload-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        Volunteer.objects.create(
            user=self.volunteer,
            motivation='Help neighbors.',
            is_active=True,
            is_approved=True,
        )
        officer = User.objects.create_user(
            username='upload-officer',
            password='test-password',
            role='police',
        )
        incident = Incident.objects.create(
            title='Upload test incident',
            description='Upload testing.',
            category='other',
            severity='medium',
            latitude='-28.7282',
            longitude='24.7499',
        )
        self.assignment = IncidentAssignment.objects.create(
            incident=incident,
            volunteer=self.volunteer,
            assigned_by=officer,
        )

    def test_incident_form_rejects_non_image_upload(self):
        form = IncidentForm(
            data={
                'title': 'Unsafe upload attempt',
                'description': 'An upload test.',
                'category': 'other',
                'severity': 'medium',
                'latitude': '-28.7282',
                'longitude': '24.7499',
            },
            files={
                'image': SimpleUploadedFile(
                    'payload.png',
                    b'<script>alert(1)</script>',
                    content_type='image/png',
                ),
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)

    def test_incident_form_rejects_coordinates_outside_geographic_ranges(self):
        form = IncidentForm(data={
            'title': 'Invalid coordinates',
            'description': 'Coordinates are outside the globe.',
            'category': 'other',
            'severity': 'medium',
            'latitude': '91',
            'longitude': '181',
            'location_description': 'Test',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('latitude', form.errors)
        self.assertIn('longitude', form.errors)

    def test_volunteer_progress_rejects_non_image_upload(self):
        self.client.force_login(self.volunteer)
        response = self.client.post(
            reverse('volunteer_update_progress', args=[self.assignment.pk]),
            {
                'progress_notes': 'Progress update.',
                'image': SimpleUploadedFile(
                    'payload.png',
                    b'<script>alert(1)</script>',
                    content_type='image/png',
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('image', response.context['form'].errors)
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.volunteer_images)

    def test_upload_form_rejects_active_content_extension(self):
        form = VolunteerProgressForm(
            data={'progress_notes': 'Progress update.'},
            files={
                'image': SimpleUploadedFile(
                    'payload.html',
                    b'not a permitted image',
                    content_type='image/jpeg',
                ),
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)

    def test_upload_validator_rejects_oversized_file(self):
        with self.assertRaisesMessage(ValidationError, '5 MB or smaller'):
            validate_image_upload(
                SimpleUploadedFile(
                    'large.jpg',
                    b'x' * (5 * 1024 * 1024 + 1),
                    content_type='image/jpeg',
                )
            )

    def test_upload_validator_rejects_unapproved_extension(self):
        with self.assertRaisesMessage(ValidationError, 'Upload a JPG, PNG, or WEBP image.'):
            validate_image_upload(
                SimpleUploadedFile(
                    'payload.html',
                    b'file content',
                    content_type='image/jpeg',
                )
            )


class PoliceMyCasesTests(TestCase):
    def setUp(self):
        self.officer = User.objects.create_user(
            username='approved-officer',
            password='test-password',
            role='police',
            is_approved=True,
            is_active=True,
        )
        self.other_officer = User.objects.create_user(
            username='other-approved-officer',
            password='test-password',
            role='police',
            is_approved=True,
            is_active=True,
        )
        self.url = reverse('police_my_cases')

    def make_incident(self, title, status='active', assigned_officer=None):
        return Incident.objects.create(
            title=title,
            description='Test incident.',
            category='other',
            severity='medium',
            latitude='-28.7282',
            longitude='24.7499',
            status=status,
            assigned_officer=assigned_officer,
        )

    def test_lists_unassigned_open_cases_and_officers_own_cases_only(self):
        unassigned_open = self.make_incident('Unassigned active case')
        other_officer_open = self.make_incident(
            'Other officer active case with volunteer',
            assigned_officer=self.other_officer,
        )
        volunteer = User.objects.create_user(
            username='case-volunteer',
            password='test-password',
            role='volunteer',
        )
        IncidentAssignment.objects.create(
            incident=other_officer_open,
            volunteer=volunteer,
            assigned_by=self.other_officer,
        )
        self_assigned_investigation = self.make_incident(
            'My investigating case',
            status='investigating',
            assigned_officer=self.officer,
        )
        self_assigned_resolved = self.make_incident(
            'My resolved case',
            status='resolved',
            assigned_officer=self.officer,
        )
        unrelated_resolved = self.make_incident(
            'Another resolved case',
            status='resolved',
            assigned_officer=self.other_officer,
        )
        closed_case = self.make_incident(
            'Unassigned closed case',
            status='closed',
        )
        self.client.force_login(self.officer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        cases = list(response.context['cases'])
        self.assertCountEqual(
            [case.id for case in cases],
            [
                unassigned_open.id,
                self_assigned_investigation.id,
                self_assigned_resolved.id,
            ],
        )
        case_titles = [case.title for case in cases]
        self.assertNotIn('Other officer active case with volunteer', case_titles)
        self.assertNotIn('Another resolved case', case_titles)
        self.assertNotIn('Unassigned closed case', case_titles)

    def test_unapproved_police_cannot_view_all_cases(self):
        pending_officer = User.objects.create_user(
            username='pending-officer',
            password='test-password',
            role='police',
            is_approved=False,
            is_active=False,
        )
        self.client.force_login(pending_officer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))
