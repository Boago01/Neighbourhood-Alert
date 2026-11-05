from django.test import SimpleTestCase
from django.urls import reverse
from django.test import TestCase, override_settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from unittest.mock import patch
from types import SimpleNamespace
import re

from alerts.models import ApprovalSMSDelivery
from .admin import UserAdmin
from .forms import validate_profile_picture
from .models import User, UserProfile
from incidents.models import Comment, Incident
from volunteers.models import Volunteer


class LoginPasswordResetUrlTests(SimpleTestCase):
    def test_login_page_renders_password_reset_link(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("password_reset")}"')

    def test_password_reset_page_renders(self):
        response = self.client.get(reverse('password_reset'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/password_reset_form.html')


class ProfileImageValidationTests(SimpleTestCase):
    def test_profile_picture_size_is_limited_to_five_megabytes(self):
        oversized_image = SimpleUploadedFile(
            'large.jpg',
            b'x' * (5 * 1024 * 1024 + 1),
            content_type='image/jpeg',
        )

        with self.assertRaisesMessage(
            ValidationError,
            'Profile pictures must be 5 MB or smaller.',
        ):
            validate_profile_picture(oversized_image)


class LogoutMethodTests(TestCase):
    def test_logout_requires_post(self):
        user = User.objects.create_user(
            username='logout-user',
            password='test-password',
            role='resident',
        )
        self.client.force_login(user)

        get_response = self.client.get(reverse('logout'))
        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(self.client.session.get('_auth_user_id'))

        post_response = self.client.post(reverse('logout'))
        self.assertRedirects(post_response, reverse('home'))
        self.assertNotIn('_auth_user_id', self.client.session)


class PendingVolunteerLoginTests(TestCase):
    def test_volunteer_can_log_in_only_after_approval(self):
        self.client.post(
            reverse('register'),
            {
                'username': 'pending-volunteer',
                'first_name': 'Pending',
                'last_name': 'Volunteer',
                'email': 'pending@example.com',
                'phone_number': '0821234567',
                'role': 'volunteer',
                'volunteer_skills': 'First aid, community support',
                'volunteer_availability': 'weekends',
                'address': '',
                'password1': 'StrongPassword-123!',
                'password2': 'StrongPassword-123!',
            },
        )
        user = User.objects.get(username='pending-volunteer')
        self.assertFalse(user.is_approved)
        volunteer = Volunteer.objects.get(user=user)
        self.assertFalse(volunteer.is_approved)
        self.assertEqual(volunteer.skills, 'First aid, community support')
        self.assertEqual(volunteer.availability, 'weekends')

        response = self.client.post(
            reverse('login'),
            {
                'username': 'pending-volunteer',
                'password': 'StrongPassword-123!',
            },
            follow=True,
        )

        self.assertEqual(response.redirect_chain, [(reverse('login'), 302)])
        self.assertContains(response, 'Your volunteer application is pending approval.')
        self.assertNotIn('_auth_user_id', self.client.session)

        user.is_approved = True
        user.save(update_fields=['is_approved'])
        response = self.client.post(
            reverse('login'),
            {
                'username': 'pending-volunteer',
                'password': 'StrongPassword-123!',
            },
            follow=True,
        )

        self.assertEqual(response.redirect_chain, [(reverse('dashboard'), 302)])
        self.assertIn('_auth_user_id', self.client.session)

    def test_new_volunteer_registration_appears_in_pending_approvals(self):
        self.client.post(
            reverse('register'),
            {
                'username': 'pending-volunteer',
                'first_name': 'Pending',
                'last_name': 'Volunteer',
                'email': 'pending@example.com',
                'phone_number': '0821234567',
                'role': 'volunteer',
                'volunteer_skills': 'First aid',
                'volunteer_availability': 'part_time',
                'address': '',
                'password1': 'StrongPassword-123!',
                'password2': 'StrongPassword-123!',
            },
        )
        administrator = User.objects.create_user(
            username='admin',
            password='AdminPassword-123!',
            role='admin',
            is_approved=True,
        )
        self.client.force_login(administrator)

        response = self.client.get(reverse('pending_approvals'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pending Volunteer')
        self.assertEqual(response.context['pending_volunteers'].count(), 1)

    def test_volunteer_registration_requires_skills_and_availability(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'volunteer-without-details',
                'first_name': 'Volunteer',
                'last_name': 'Applicant',
                'email': 'volunteer@example.com',
                'phone_number': '0821234567',
                'role': 'volunteer',
                'volunteer_skills': '',
                'volunteer_availability': '',
                'address': '',
                'password1': 'StrongPassword-123!',
                'password2': 'StrongPassword-123!',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='volunteer-without-details').exists())
        self.assertIn('volunteer_skills', response.context['form'].errors)
        self.assertIn('volunteer_availability', response.context['form'].errors)

    def test_user_admin_can_approve_public_volunteer_registration(self):
        administrator = User.objects.create_user(
            username='admin',
            password='AdminPassword-123!',
            role='admin',
            is_approved=True,
        )
        volunteer = User.objects.create_user(
            username='public-volunteer',
            password='StrongPassword-123!',
            role='volunteer',
            is_approved=False,
        )
        request = RequestFactory().post('/admin/accounts/user/')
        request.user = administrator
        user_admin = UserAdmin(User, AdminSite())

        with (
            patch.object(user_admin, 'message_user'),
            patch('accounts.admin.send_approval_welcome_sms') as send_welcome,
        ):
            user_admin.approve_users(request, User.objects.filter(pk=volunteer.pk))

        volunteer.refresh_from_db()
        self.assertTrue(volunteer.is_approved)
        self.assertTrue(volunteer.is_active)
        send_welcome.assert_called_once_with(volunteer)

    def test_user_admin_can_retry_welcome_sms_previously_blocked_by_missing_url(self):
        administrator = User.objects.create_user(
            username='admin',
            password='AdminPassword-123!',
            role='admin',
            is_approved=True,
        )
        police = User.objects.create_user(
            username='approved-police',
            password='PolicePassword-123!',
            role='police',
            is_approved=True,
            is_active=True,
        )
        ApprovalSMSDelivery.objects.create(
            user=police,
            status='failed',
            error_code='missing_public_url',
        )
        request = RequestFactory().post('/admin/accounts/user/')
        request.user = administrator
        user_admin = UserAdmin(User, AdminSite())

        with (
            patch.object(user_admin, 'message_user'),
            patch(
                'accounts.admin.send_approval_welcome_sms',
                return_value=SimpleNamespace(status='submitted'),
            ) as send_welcome,
        ):
            user_admin.retry_failed_welcome_sms(
                request,
                User.objects.filter(pk=police.pk),
            )

        send_welcome.assert_called_once_with(police)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='Neighbourhood Alert <noreply@example.test>',
)
class PasswordResetEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.user = User.objects.create_user(
            username='resident',
            email='resident@example.com',
            password='Old-password-123!',
        )

    def request_reset(self, email='resident@example.com'):
        return self.client.post(reverse('password_reset'), {'email': email})

    def test_reset_emails_link_to_address_submitted_for_account(self):
        response = self.request_reset()

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ['resident@example.com'])
        self.assertEqual(message.from_email, 'Neighbourhood Alert <noreply@example.test>')
        self.assertIn('http://testserver/reset/', message.body)
        self.assertContains(
            self.client.get(reverse('password_reset_done')),
            'emailed to it',
        )

    def test_unknown_email_uses_same_response_without_sending_email(self):
        response = self.request_reset('unknown@example.com')

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertContains(
            self.client.get(reverse('password_reset_done')),
            'If an active account matches',
        )
        self.assertEqual(mail.outbox, [])

    def test_duplicate_email_accounts_do_not_receive_reset_email(self):
        User.objects.create_user(
            username='another-resident',
            email='resident@example.com',
            password='Other-password-456!',
        )
        response = self.request_reset()
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(mail.outbox, [])

    def test_reset_link_sets_password_and_allows_login(self):
        self.request_reset()
        link = re.search(
            r'http://testserver/reset/([^/\s]+)/([^/\s]+)',
            mail.outbox[0].body,
        )
        self.assertIsNotNone(link)
        reset_url = reverse(
            'password_reset_confirm',
            kwargs={'uidb64': link.group(1), 'token': link.group(2)},
        )
        confirm_response = self.client.get(reset_url, follow=True)
        self.assertEqual(confirm_response.status_code, 200)
        self.assertTrue(confirm_response.context['validlink'])

        response = self.client.post(
            confirm_response.request['PATH_INFO'],
            {
                'new_password1': 'BrandNewPassword-456!',
                'new_password2': 'BrandNewPassword-456!',
            },
        )
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPassword-456!'))
        self.assertIsNone(
            authenticate(username='resident', password='Old-password-123!')
        )
        login_response = self.client.post(
            reverse('login'),
            {'username': 'resident', 'password': 'BrandNewPassword-456!'},
        )
        self.assertRedirects(login_response, reverse('dashboard'))
        self.assertIn('_auth_user_id', self.client.session)

    @patch('accounts.views.send_mail', side_effect=OSError('SMTP credential detail'))
    def test_smtp_failure_is_not_exposed_to_user_or_logs(self, send_mail_mock):
        with self.assertLogs('accounts.views', level='WARNING') as logs:
            response = self.request_reset()

        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertNotIn('SMTP credential detail', response.content.decode())
        self.assertNotIn('SMTP credential detail', '\n'.join(logs.output))
        send_mail_mock.assert_called_once()

    def test_invalid_and_expired_reset_tokens_are_rejected(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        invalid_response = self.client.get(
            reverse(
                'password_reset_confirm',
                kwargs={'uidb64': uid, 'token': 'invalid-token'},
            )
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertFalse(invalid_response.context['validlink'])

        with self.settings(PASSWORD_RESET_TIMEOUT=-1):
            expired_response = self.client.get(
                reverse(
                    'password_reset_confirm',
                    kwargs={'uidb64': uid, 'token': token},
                )
            )
        self.assertEqual(expired_response.status_code, 200)
        self.assertFalse(expired_response.context['validlink'])

class PoliceSelfRegistrationTests(TestCase):
    def setUp(self):
        self.application_data = {
            'first_name': 'Alex',
            'last_name': 'Officer',
            'email': 'alex.officer@example.com',
            'phone_number': '0123456789',
            'police_employee_number': 'SAPS-1234',
            'police_station': 'Central Police Station',
            'police_unit': 'Community Safety',
            'username': 'alexofficer',
            'password1': 'StrongPassword-123!',
            'password2': 'StrongPassword-123!',
        }
        self.url = reverse('police_register')

    def test_police_registration_page_renders(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Employee Number')
        self.assertContains(response, 'Police Station')
        self.assertContains(response, 'Unit / Department')

    def test_police_application_is_pending_and_cannot_authenticate(self):
        response = self.client.post(self.url, self.application_data)

        self.assertRedirects(response, reverse('login'))
        applicant = User.objects.get(username='alexofficer')
        self.assertEqual(applicant.role, 'police')
        self.assertFalse(applicant.is_approved)
        self.assertFalse(applicant.is_active)
        self.assertFalse(applicant.is_police())
        self.assertIsNone(
            authenticate(username='alexofficer', password='StrongPassword-123!')
        )
        self.assertTrue(UserProfile.objects.filter(user=applicant).exists())

    def test_employee_number_must_be_unique(self):
        User.objects.create_user(
            username='existing-officer',
            email='existing@example.com',
            password='StrongPassword-123!',
            police_employee_number='SAPS-1234',
        )

        response = self.client.post(self.url, self.application_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        self.assertFalse(User.objects.filter(username='alexofficer').exists())

    def test_public_registration_does_not_offer_police_role(self):
        response = self.client.get(reverse('register'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="police"')


class PoliceApplicationApprovalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password='AdminPassword-123!',
            role='admin',
            is_approved=True,
        )
        self.applicant = User.objects.create_user(
            username='applicant',
            password='PolicePassword-123!',
            role='police',
            is_approved=False,
            is_active=False,
            police_employee_number='SAPS-4321',
            police_station='North Station',
            police_unit='Patrol',
        )
        self.list_url = reverse('pending_police_applications')
        self.review_url = reverse(
            'review_police_application',
            args=[self.applicant.id],
        )

    def test_admin_can_approve_and_enable_police_account(self):
        self.client.force_login(self.admin)

        with patch('accounts.views.send_approval_welcome_sms') as send_welcome:
            response = self.client.post(self.review_url, {'decision': 'approve'})

        self.assertRedirects(response, self.list_url)
        self.applicant.refresh_from_db()
        self.assertTrue(self.applicant.is_approved)
        self.assertTrue(self.applicant.is_active)
        self.assertTrue(self.applicant.is_police())
        send_welcome.assert_called_once_with(self.applicant)
        self.assertIsNotNone(
            authenticate(
                username='applicant',
                password='PolicePassword-123!',
            )
        )

    def test_admin_can_reject_and_remove_pending_application(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.review_url, {'decision': 'reject'})

        self.assertRedirects(response, self.list_url)
        self.assertFalse(User.objects.filter(id=self.applicant.id).exists())

    def test_nonadmin_cannot_approve_police_application(self):
        resident = User.objects.create_user(
            username='resident',
            password='ResidentPassword-123!',
            role='resident',
            is_approved=True,
        )
        self.client.force_login(resident)

        response = self.client.post(self.review_url, {'decision': 'approve'})

        self.assertRedirects(response, reverse('dashboard'))
        self.applicant.refresh_from_db()
        self.assertFalse(self.applicant.is_approved)
        self.assertFalse(self.applicant.is_active)

    def test_get_request_cannot_approve_application(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.review_url)

        self.assertRedirects(response, self.list_url)
        self.applicant.refresh_from_db()
        self.assertFalse(self.applicant.is_approved)
        self.assertFalse(self.applicant.is_active)


class AdminUserRemovalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password='AdminPassword-123!',
            role='admin',
            is_approved=True,
        )
        self.target = User.objects.create_user(
            username='resident-to-remove',
            password='ResidentPassword-123!',
            role='resident',
            is_approved=True,
            first_name='Resident',
            last_name='Example',
            email='resident@example.com',
            phone_number='0796408096',
            address='12 Example Street',
        )
        self.profile = UserProfile.objects.create(
            user=self.target,
            emergency_contact_name='Emergency Contact',
            emergency_contact_phone='0821234567',
            id_number='1234567890123',
        )
        self.incident = Incident.objects.create(
            title='Test incident',
            description='Incident history must remain.',
            category='theft',
            severity='medium',
            latitude=-28.7282,
            longitude=24.7499,
            reported_by=self.target,
        )
        self.comment = Comment.objects.create(
            incident=self.incident,
            author=self.target,
            content='A historical comment.',
        )
        self.url = reverse('remove_user', args=[self.target.id])

    def test_admin_can_remove_account_while_preserving_history(self):
        self.client.force_login(self.admin)

        confirmation = self.client.get(self.url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, 'activity history is preserved')

        response = self.client.post(self.url, {'confirm': 'yes'})

        self.assertRedirects(response, reverse('user_management'))
        self.target.refresh_from_db()
        self.profile.refresh_from_db()
        self.incident.refresh_from_db()
        self.comment.refresh_from_db()

        self.assertFalse(self.target.is_active)
        self.assertFalse(self.target.is_approved)
        self.assertTrue(self.target.is_removed)
        self.assertFalse(self.target.is_staff)
        self.assertFalse(self.target.is_superuser)
        self.assertEqual(self.target.first_name, '')
        self.assertEqual(self.target.last_name, '')
        self.assertEqual(self.target.email, '')
        self.assertEqual(self.target.phone_number, '')
        self.assertEqual(self.target.address, '')
        self.assertTrue(self.target.username.startswith('removed-account-'))
        self.assertIsNone(
            authenticate(
                username=self.target.username,
                password='ResidentPassword-123!',
            )
        )
        self.assertEqual(self.profile.emergency_contact_name, '')
        self.assertEqual(self.profile.emergency_contact_phone, '')
        self.assertEqual(self.profile.id_number, '')
        self.assertEqual(Incident.objects.filter(pk=self.incident.pk).count(), 1)
        self.assertEqual(Comment.objects.filter(pk=self.comment.pk).count(), 1)
        self.assertEqual(self.incident.reported_by, self.target)
        self.assertEqual(self.comment.author, self.target)

    def test_admin_cannot_remove_own_account(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('remove_user', args=[self.admin.id]),
            {'confirm': 'yes'},
        )

        self.assertRedirects(response, reverse('user_management'))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_nonadmin_cannot_remove_an_account(self):
        resident = User.objects.create_user(
            username='another-resident',
            password='ResidentPassword-123!',
            role='resident',
        )
        self.client.force_login(resident)

        response = self.client.post(self.url, {'confirm': 'yes'})

        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())

    def test_post_without_confirmation_does_not_remove_account(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('user_management'))
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_removed_account_cannot_be_reactivated(self):
        self.client.force_login(self.admin)
        self.client.post(self.url, {'confirm': 'yes'})

        response = self.client.get(
            reverse('toggle_user_status', args=[self.target.id]),
        )

        self.assertEqual(response.status_code, 405)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_admin_must_post_to_change_account_status(self):
        self.client.force_login(self.admin)
        url = reverse('toggle_user_status', args=[self.target.id])

        get_response = self.client.get(url)
        self.target.refresh_from_db()
        self.assertEqual(get_response.status_code, 405)
        self.assertTrue(self.target.is_active)

        post_response = self.client.post(url)
        self.target.refresh_from_db()
        self.assertRedirects(post_response, reverse('user_management'))
        self.assertFalse(self.target.is_active)
