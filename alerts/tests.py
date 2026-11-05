from datetime import timedelta
import json
from unittest.mock import patch

from django.contrib import admin as django_admin
from django.test import Client, TestCase, override_settings
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from volunteers.models import Volunteer

from .admin import AlertAdmin
from .models import (
    Alert,
    AlertAcknowledgment,
    AlertSMSDelivery,
    ApprovalSMSDelivery,
)
from .forms import AlertForm
from .services import (
    approval_sms_failure_message,
    normalize_south_african_mobile,
    send_alert_sms,
    send_approval_welcome_sms,
)

class FakeBulkSMSResponse:
    status = 201

    def read(self):
        return json.dumps([
            {'submission': {'id': 'submission-123'}}
        ]).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ApprovalSMSFailureMessageTests(TestCase):
    def test_missing_public_url_message_explains_configuration_fix(self):
        class FailedDelivery:
            error_code = 'missing_public_url'

        message = approval_sms_failure_message(FailedDelivery())

        self.assertIn('BULKSMS_PUBLIC_URL', message)
        self.assertIn('public HTTPS website URL', message)
        self.assertIn('restart Django', message)


@override_settings(
    BULKSMS_ENABLED=True,
    BULKSMS_DRY_RUN=False,
    BULKSMS_TEST_MODE=False,
    BULKSMS_TOKEN_ID='test-token-id',
    BULKSMS_TOKEN_SECRET='test-token-secret',
    BULKSMS_PUBLIC_URL='https://example.test',
)
class AlertSMSTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username='police',
            password='test-password',
            role='police',
            is_approved=True,
            phone_number='079 640 8096',
        )
        self.recipient = User.objects.create_user(
            username='resident-recipient',
            password='test-password',
            role='resident',
            is_active=True,
            phone_number='0821234567',
        )
        self.alert = Alert.objects.create(
            title='Road closed',
            message='Avoid the bridge due to flooding.',
            priority='critical',
            latitude=-28.7282,
            longitude=24.7499,
            radius=500,
            expires_at=timezone.now() + timedelta(hours=2),
            created_by=self.creator,
        )

    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_broadcast_targets_active_users_with_south_african_mobile_numbers(self, send):
        User.objects.create_user(
            username='admin',
            password='test-password',
            role='admin',
            is_active=True,
            phone_number='+27 61 234 5678',
        )
        approved_police = User.objects.create_user(
            username='approved-police',
            password='test-password',
            role='police',
            is_active=True,
            is_approved=True,
            phone_number='0831234567',
        )
        approved_volunteer_user = User.objects.create_user(
            username='approved-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
            phone_number='0841234567',
        )
        Volunteer.objects.create(
            user=approved_volunteer_user,
            motivation='Help neighbors.',
            is_approved=True,
            is_active=True,
        )
        User.objects.create_user(
            username='inactive-approved-police',
            password='test-password',
            role='police',
            is_active=False,
            is_approved=True,
            phone_number='0871234567',
        )
        User.objects.create_user(
            username='unapproved-police',
            password='test-password',
            role='police',
            is_active=True,
            is_approved=False,
            phone_number='0851234567',
        )
        unapproved_volunteer_user = User.objects.create_user(
            username='unapproved-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
            phone_number='0861234567',
        )
        Volunteer.objects.create(
            user=unapproved_volunteer_user,
            motivation='Still awaiting approval.',
            is_approved=False,
            is_active=True,
        )
        User.objects.create_user(
            username='inactive',
            password='test-password',
            role='resident',
            is_active=False,
            phone_number='0831234567',
        )
        User.objects.create_user(
            username='invalid-number',
            password='test-password',
            role='resident',
            is_active=True,
            phone_number='0123456789',
        )
        User.objects.create_user(
            username='removed-account',
            password='test-password',
            role='resident',
            is_active=True,
            is_removed=True,
            phone_number='0881234567',
        )

        delivery = send_alert_sms(self.alert)

        self.assertEqual(delivery.status, 'submitted')
        self.assertEqual(delivery.recipient_count, 3)
        request = send.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(
            {entry['to'] for entry in payload},
            {'+27821234567', '+27831234567', '+27841234567'},
        )
        body = payload[0]['body']
        self.assertEqual(body.splitlines(), [
            'NEIGHBOURHOOD ALERT: Road closed',
            'Priority: Critical',
            'Details: Avoid the bridge due to flooding.',
            'Location: -28.72820, 24.74990 (within 500 m)',
            f'Expires: {timezone.localtime(self.alert.expires_at):%d %b %Y %H:%M %Z}',
            'View: https://example.test/alerts/1/',
        ])
        self.assertTrue(all(entry['body'] == body for entry in payload))
        self.assertNotIn('..', body)
        self.assertIn(
            f'deduplication-id={1_000_000_000 + self.alert.pk}',
            request.full_url,
        )
        self.assertEqual(delivery.provider_submission_id, 'submission-123')

    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_sms_normalizes_repeated_final_periods_in_alert_details(self, send):
        self.alert.message = 'Avoid the bridge..'
        self.alert.save(update_fields=['message'])

        send_alert_sms(self.alert)

        payload = json.loads(send.call_args.args[0].data)
        self.assertIn('Details: Avoid the bridge.', payload[0]['body'])
        self.assertNotIn('..', payload[0]['body'])

    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_sms_explains_location_when_alert_has_no_map_coordinates(self, send):
        self.alert.latitude = None
        self.alert.longitude = None
        self.alert.save(update_fields=['latitude', 'longitude'])

        send_alert_sms(self.alert)

        payload = json.loads(send.call_args.args[0].data)
        self.assertIn(
            'Location: Not specified (select a point on the alert map)',
            payload[0]['body'],
        )

    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_existing_delivery_is_not_submitted_again(self, send):
        first = send_alert_sms(self.alert)
        second = send_alert_sms(self.alert)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(AlertSMSDelivery.objects.filter(alert=self.alert).count(), 1)

    @override_settings(BULKSMS_TEST_MODE=True, BULKSMS_TEST_PHONE_NUMBER='0766408096')
    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_test_mode_uses_only_the_configured_test_number(self, send):
        User.objects.create_user(
            username='other-resident',
            password='test-password',
            role='resident',
            phone_number='0821234567',
        )

        delivery = send_alert_sms(self.alert)

        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(delivery.recipient_count, 1)
        self.assertEqual([entry['to'] for entry in payload], ['+27766408096'])

    @override_settings(BULKSMS_TEST_MODE=True, BULKSMS_TEST_PHONE_NUMBER='0796408096')
    @patch('alerts.services.urlopen')
    def test_test_mode_does_not_send_to_alert_creator(self, send):
        delivery = send_alert_sms(self.alert)

        self.assertEqual(delivery.status, 'failed')
        self.assertEqual(delivery.error_code, 'no_valid_recipients')
        self.assertEqual(delivery.recipient_count, 0)
        send.assert_not_called()

    @override_settings(BULKSMS_DRY_RUN=True)
    @patch('alerts.services.urlopen')
    def test_dry_run_records_intent_without_calling_provider(self, send):
        delivery = send_alert_sms(self.alert)

        self.assertEqual(delivery.status, 'dry_run')
        self.assertEqual(delivery.recipient_count, 1)
        send.assert_not_called()

    @override_settings(BULKSMS_ENABLED=False)
    @patch('alerts.services.urlopen')
    def test_disabled_service_does_not_send_and_records_skipped_delivery(self, send):
        delivery = send_alert_sms(self.alert)

        self.assertEqual(delivery.status, 'skipped')
        self.assertEqual(delivery.error_code, 'sms_disabled')
        send.assert_not_called()

    @patch('alerts.services.urlopen', side_effect=OSError('connection failed'))
    def test_provider_failure_is_recorded_without_raising(self, send):
        delivery = send_alert_sms(self.alert)

        self.assertEqual(delivery.status, 'failed')
        self.assertEqual(delivery.error_code, 'provider_unavailable')
        self.assertEqual(delivery.recipient_count, 1)
        send.assert_called_once()


class AlertCreationPermissionTests(TestCase):
    def test_alert_form_loads_google_maps_with_configured_api_key(self):
        police = User.objects.create_user(
            username='approved-police',
            password='test-password',
            role='police',
            is_approved=True,
        )
        self.client.force_login(police)

        with override_settings(GOOGLE_MAPS_API_KEY='test-google-maps-key'):
            response = self.client.get(reverse('create_alert'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://maps.googleapis.com/maps/api/js')
        self.assertContains(response, 'callback=initAlertMap')
        self.assertContains(response, 'test-google-maps-key')

    def test_alert_form_rejects_out_of_range_or_partial_coordinates(self):
        out_of_range = AlertForm(data={
            'title': 'Invalid map point',
            'message': 'Coordinates outside valid ranges.',
            'priority': 'high',
            'latitude': '91',
            'longitude': '24',
            'radius': '500',
            'expires_at': '',
        })
        partial = AlertForm(data={
            'title': 'Partial map point',
            'message': 'Only one coordinate was submitted.',
            'priority': 'high',
            'latitude': '-28',
            'longitude': '',
            'radius': '',
            'expires_at': '',
        })

        self.assertFalse(out_of_range.is_valid())
        self.assertIn('latitude', out_of_range.errors)
        self.assertFalse(partial.is_valid())
        self.assertIn('longitude', partial.errors)

    def test_alert_map_coordinates_are_rendered_as_hidden_fields(self):
        police = User.objects.create_user(
            username='approved-police',
            password='test-password',
            role='police',
            is_approved=True,
        )
        self.client.force_login(police)

        response = self.client.get(reverse('create_alert'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="id_latitude"')
        self.assertContains(response, 'id="id_longitude"')
        self.assertContains(response, 'id="id_radius"')
        self.assertContains(response, 'type="hidden"')

    @override_settings(BULKSMS_ENABLED=False)
    def test_alert_can_be_created_with_datetime_local_expiry(self):
        police = User.objects.create_user(
            username='police-with-expiry',
            password='test-password',
            role='police',
            is_approved=True,
        )
        self.client.force_login(police)

        response = self.client.post(
            reverse('create_alert'),
            {
                'title': 'Road closure',
                'message': 'Avoid the affected road.',
                'priority': 'high',
                'expires_at': '2026-10-20T12:30',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Alert.objects.filter(title='Road closure').exists())

    @override_settings(BULKSMS_ENABLED=False)
    def test_alert_accepts_map_coordinates_at_supported_precision(self):
        police = User.objects.create_user(
            username='police-map-location',
            password='test-password',
            role='police',
            is_approved=True,
        )
        self.client.force_login(police)

        response = self.client.post(
            reverse('create_alert'),
            {
                'title': 'Road closure',
                'message': 'Avoid the affected road.',
                'priority': 'high',
                'latitude': '-28.72820000',
                'longitude': '24.74990000',
                'radius': '500',
                'expires_at': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        alert = Alert.objects.get(title='Road closure')
        self.assertEqual(str(alert.latitude), '-28.72820000')
        self.assertEqual(str(alert.longitude), '24.74990000')

    @override_settings(BULKSMS_ENABLED=False)
    def test_invalid_expiry_error_is_displayed(self):
        police = User.objects.create_user(
            username='police-invalid-expiry',
            password='test-password',
            role='police',
            is_approved=True,
        )
        self.client.force_login(police)

        response = self.client.post(
            reverse('create_alert'),
            {
                'title': 'Road closure',
                'message': 'Avoid the affected road.',
                'priority': 'high',
                'expires_at': 'not-a-date',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid date/time.')
        self.assertFalse(Alert.objects.filter(title='Road closure').exists())

    @override_settings(BULKSMS_ENABLED=False)
    def test_authorized_police_can_create_alert_with_sms_disabled(self):
        police = User.objects.create_user(
            username='approved-police',
            password='test-password',
            role='police',
            is_approved=True,
        )
        self.client.force_login(police)

        response = self.client.post(
            reverse('create_alert'),
            {
                'title': 'Safety notice',
                'message': 'A generic safety notice.',
                'priority': 'high',
            },
        )

        alert = Alert.objects.get(title='Safety notice')
        self.assertRedirects(
            response,
            reverse('alert_detail', kwargs={'alert_id': alert.pk}),
        )
        self.assertEqual(alert.sms_delivery.status, 'skipped')

    @override_settings(BULKSMS_ENABLED=False)
    def test_resident_cannot_create_alert(self):
        resident = User.objects.create_user(
            username='resident',
            password='test-password',
            role='resident',
            is_approved=True,
        )
        self.client.force_login(resident)

        response = self.client.post(
            reverse('create_alert'),
            {
                'title': 'Unauthorized notice',
                'message': 'Should not be saved.',
                'priority': 'high',
            },
        )

        self.assertRedirects(response, reverse('alert_list'))
        self.assertFalse(Alert.objects.filter(title='Unauthorized notice').exists())

    def test_acknowledgment_and_deactivation_require_post(self):
        police = User.objects.create_user(
            username='alert-owner',
            password='test-password',
            role='police',
            is_approved=True,
        )
        alert = Alert.objects.create(
            title='Method guard alert',
            message='No GET mutations.',
            created_by=police,
        )
        self.client.force_login(police)

        acknowledge_response = self.client.get(
            reverse('acknowledge_alert', args=[alert.pk]),
        )
        deactivate_response = self.client.get(
            reverse('deactivate_alert', args=[alert.pk]),
        )

        self.assertEqual(acknowledge_response.status_code, 405)
        self.assertEqual(deactivate_response.status_code, 405)
        self.assertFalse(
            AlertAcknowledgment.objects.filter(
                alert=alert,
                user=police,
            ).exists()
        )
        alert.refresh_from_db()
        self.assertTrue(alert.is_active)

    def test_acknowledgment_post_requires_csrf_token(self):
        police = User.objects.create_user(
            username='csrf-alert-user',
            password='test-password',
            role='police',
            is_approved=True,
        )
        alert = Alert.objects.create(
            title='CSRF test alert',
            message='Check POST CSRF enforcement.',
            created_by=police,
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(police)

        response = csrf_client.post(
            reverse('acknowledge_alert', args=[alert.pk]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AlertAcknowledgment.objects.filter(
                alert=alert,
                user=police,
            ).exists()
        )

    @override_settings(BULKSMS_ENABLED=False)
    @patch('alerts.admin.send_alert_sms')
    def test_admin_site_alert_creation_uses_sms_service_once(self, send_sms):
        admin_user = User.objects.create_user(
            username='site-admin',
            password='test-password',
            role='admin',
            is_approved=True,
        )
        request = RequestFactory().post('/admin/alerts/alert/add/')
        request.user = admin_user
        alert = Alert(
            title='Admin alert',
            message='Public safety details.',
            priority='high',
            created_by=admin_user,
        )

        AlertAdmin(Alert, django_admin.site).save_model(
            request,
            alert,
            form=None,
            change=False,
        )

        self.assertTrue(Alert.objects.filter(pk=alert.pk).exists())
        send_sms.assert_called_once_with(alert)

    @override_settings(BULKSMS_ENABLED=False)
    @patch('alerts.admin.send_alert_sms')
    def test_admin_site_edit_does_not_resend_sms(self, send_sms):
        admin_user = User.objects.create_user(
            username='site-admin',
            password='test-password',
            role='admin',
            is_approved=True,
        )
        alert = Alert.objects.create(
            title='Existing alert',
            message='Public safety details.',
            priority='high',
            created_by=admin_user,
        )
        request = RequestFactory().post(f'/admin/alerts/alert/{alert.pk}/change/')
        request.user = admin_user

        AlertAdmin(Alert, django_admin.site).save_model(
            request,
            alert,
            form=None,
            change=True,
        )

        send_sms.assert_not_called()


class SouthAfricanMobileNumberTests(TestCase):
    def test_normalizes_supported_south_african_mobile_formats(self):
        self.assertEqual(normalize_south_african_mobile('079 640 8096'), '+27796408096')
        self.assertEqual(normalize_south_african_mobile('+27 79 640 8096'), '+27796408096')
        self.assertEqual(normalize_south_african_mobile('0027796408096'), '+27796408096')

    def test_rejects_invalid_or_nonmobile_numbers(self):
        self.assertIsNone(normalize_south_african_mobile('0123456789'))
        self.assertIsNone(normalize_south_african_mobile('123'))
        self.assertIsNone(normalize_south_african_mobile(''))


@override_settings(
    BULKSMS_ENABLED=True,
    BULKSMS_DRY_RUN=False,
    BULKSMS_TEST_MODE=False,
    BULKSMS_TOKEN_ID='test-token-id',
    BULKSMS_TOKEN_SECRET='test-token-secret',
    BULKSMS_PUBLIC_URL='https://example.test',
)
class ApprovalWelcomeSMSTests(TestCase):
    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_approved_police_receives_one_welcome_message(self, send):
        police = User.objects.create_user(
            username='approved-police',
            password='test-password',
            role='police',
            is_approved=True,
            is_active=True,
            phone_number='0796408096',
        )

        delivery = send_approval_welcome_sms(police)
        duplicate = send_approval_welcome_sms(police)

        self.assertEqual(delivery.status, 'submitted')
        self.assertEqual(duplicate.pk, delivery.pk)
        self.assertEqual(send.call_count, 1)
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload[0]['to'], '+27796408096')
        self.assertIn('police account has been approved', payload[0]['body'])
        self.assertIn('https://example.test/login/', payload[0]['body'])
        self.assertEqual(ApprovalSMSDelivery.objects.count(), 1)

    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_approved_volunteer_receives_dashboard_welcome(self, send):
        volunteer_user = User.objects.create_user(
            username='approved-volunteer',
            password='test-password',
            role='volunteer',
            is_approved=True,
            is_active=True,
            phone_number='0821234567',
        )
        Volunteer.objects.create(
            user=volunteer_user,
            motivation='Help neighbors.',
            is_approved=True,
            is_active=True,
        )

        delivery = send_approval_welcome_sms(volunteer_user)

        self.assertEqual(delivery.status, 'submitted')
        payload = json.loads(send.call_args.args[0].data)
        self.assertIn('volunteer account has been approved', payload[0]['body'])
        self.assertIn(
            'https://example.test/volunteers/dashboard/',
            payload[0]['body'],
        )

    @patch('alerts.services.urlopen')
    def test_unapproved_user_does_not_receive_welcome(self, send):
        police = User.objects.create_user(
            username='pending-police',
            password='test-password',
            role='police',
            is_approved=False,
            is_active=False,
            phone_number='0796408096',
        )

        delivery = send_approval_welcome_sms(police)

        self.assertIsNone(delivery)
        self.assertEqual(ApprovalSMSDelivery.objects.count(), 0)
        send.assert_not_called()

    @patch('alerts.services.urlopen')
    def test_invalid_welcome_number_is_recorded_without_sending(self, send):
        police = User.objects.create_user(
            username='invalid-number-police',
            password='test-password',
            role='police',
            is_approved=True,
            is_active=True,
            phone_number='0123456789',
        )

        delivery = send_approval_welcome_sms(police)

        self.assertEqual(delivery.status, 'failed')
        self.assertEqual(delivery.error_code, 'invalid_phone_number')
        self.assertEqual(ApprovalSMSDelivery.objects.count(), 1)
        send.assert_not_called()

    @override_settings(BULKSMS_PUBLIC_URL='')
    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_welcome_sms_sends_without_site_url_when_not_configured(self, send):
        police = User.objects.create_user(
            username='police-no-site-url',
            password='test-password',
            role='police',
            is_approved=True,
            is_active=True,
            phone_number='0796408096',
        )

        delivery = send_approval_welcome_sms(police)

        self.assertEqual(delivery.status, 'submitted')
        self.assertEqual(delivery.error_code, '')
        payload = json.loads(send.call_args.args[0].data)
        body = payload[0]['body']
        self.assertIn('approved. You can now log in and use the website.', body)
        self.assertNotIn('https://', body)

    @override_settings(BULKSMS_PUBLIC_URL='')
    @patch('alerts.services.urlopen', return_value=FakeBulkSMSResponse())
    def test_prior_missing_url_failure_can_be_retried(self, send):
        police = User.objects.create_user(
            username='police-retry-site-url',
            password='test-password',
            role='police',
            is_approved=True,
            is_active=True,
            phone_number='0796408096',
        )
        previous_delivery = ApprovalSMSDelivery.objects.create(
            user=police,
            status='failed',
            error_code='missing_public_url',
        )

        delivery = send_approval_welcome_sms(police)

        self.assertEqual(delivery.pk, previous_delivery.pk)
        self.assertEqual(delivery.status, 'submitted')
        self.assertEqual(delivery.error_code, '')
        send.assert_called_once()
