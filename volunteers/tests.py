from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from incidents.models import Incident, IncidentAssignment
from .models import Volunteer, VolunteerReview


class VolunteerReviewTests(TestCase):
    def setUp(self):
        self.resident = User.objects.create_user(
            username='resident',
            password='test-password',
            role='resident',
        )
        self.police_officer = User.objects.create_user(
            username='officer',
            password='test-password',
            role='police',
        )
        volunteer_user = User.objects.create_user(
            username='volunteer',
            password='test-password',
            role='volunteer',
            phone_number='0827654321',
        )
        self.volunteer = Volunteer.objects.create(
            user=volunteer_user,
            motivation='Help the community.',
            is_approved=True,
        )
        self.detail_url = reverse(
            'volunteer_detail',
            args=[self.volunteer.id],
        )
        self.review_url = reverse(
            'add_volunteer_review',
            args=[self.volunteer.id],
        )

    def test_resident_can_open_review_form_from_volunteer_profile(self):
        self.client.force_login(self.resident)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rate this volunteer')
        self.assertContains(response, '0827654321')

    def test_resident_can_rate_volunteer(self):
        self.client.force_login(self.resident)

        response = self.client.post(
            self.review_url,
            {'rating': '4', 'comment': 'Helpful and responsive.'},
        )

        self.assertRedirects(response, self.detail_url)
        review = VolunteerReview.objects.get(
            volunteer=self.volunteer,
            reviewer=self.resident,
        )
        self.assertEqual(review.rating, 4)
        self.volunteer.refresh_from_db()
        self.assertEqual(float(self.volunteer.rating), 4.0)

    def test_nonresident_cannot_review_volunteer(self):
        self.client.force_login(self.police_officer)

        response = self.client.post(
            self.review_url,
            {'rating': '5', 'comment': 'Not a resident review.'},
        )

        self.assertRedirects(response, self.detail_url)
        self.assertFalse(
            VolunteerReview.objects.filter(volunteer=self.volunteer).exists()
        )


class VolunteerAssignmentWorkflowTests(TestCase):
    def setUp(self):
        self.volunteer_user = User.objects.create_user(
            username='assigned-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        self.volunteer = Volunteer.objects.create(
            user=self.volunteer_user,
            motivation='Help the community.',
            is_approved=True,
            is_active=True,
        )
        self.officer = User.objects.create_user(
            username='assigning-officer',
            password='test-password',
            role='police',
        )
        self.incident = Incident.objects.create(
            title='Street incident',
            description='Incident for assignment workflow test.',
            category='other',
            severity='medium',
            latitude='-28.7282',
            longitude='24.7499',
        )
        IncidentAssignment.objects.create(
            incident=self.incident,
            volunteer=self.volunteer_user,
            assigned_by=self.officer,
        )

    def test_legacy_respond_url_redirects_to_assigned_cases(self):
        self.client.force_login(self.volunteer_user)

        response = self.client.get(
            reverse('respond_to_incident', args=[self.incident.pk]),
        )

        self.assertRedirects(response, reverse('volunteer_assigned_cases'))


class VolunteerApprovalSMSWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password='test-password',
            role='admin',
            is_approved=True,
        )
        self.volunteer_user = User.objects.create_user(
            username='applicant',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=False,
            phone_number='0821234567',
        )
        self.volunteer = Volunteer.objects.create(
            user=self.volunteer_user,
            motivation='Help the community.',
            is_active=True,
            is_approved=False,
        )
        self.approve_url = reverse('approve_volunteer', args=[self.volunteer.pk])

    def test_admin_approval_saves_access_before_requesting_welcome_sms(self):
        self.client.force_login(self.admin)

        def assert_approved_when_sms_requested(user):
            self.assertTrue(user.is_active)
            self.assertTrue(user.is_approved)
            self.assertTrue(user.volunteer.is_approved)
            self.assertTrue(user.volunteer.is_active)

        with patch(
            'volunteers.views.send_approval_welcome_sms',
            side_effect=assert_approved_when_sms_requested,
        ) as send_welcome:
            response = self.client.post(self.approve_url)

        self.assertRedirects(response, reverse('pending_approvals'))
        send_welcome.assert_called_once_with(self.volunteer_user)

    def test_get_request_cannot_approve_volunteer(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.approve_url)

        self.assertEqual(response.status_code, 405)
        self.volunteer.refresh_from_db()
        self.volunteer_user.refresh_from_db()
        self.assertFalse(self.volunteer.is_approved)
        self.assertFalse(self.volunteer_user.is_approved)

    def test_sms_failure_does_not_revert_volunteer_approval(self):
        self.client.force_login(self.admin)

        class FailedDelivery:
            status = 'failed'
            error_code = 'missing_public_url'

        with patch(
            'volunteers.views.send_approval_welcome_sms',
            return_value=FailedDelivery(),
        ):
            response = self.client.post(self.approve_url)

        self.assertRedirects(response, reverse('pending_approvals'))
        self.volunteer.refresh_from_db()
        self.volunteer_user.refresh_from_db()
        self.assertTrue(self.volunteer.is_approved)
        self.assertTrue(self.volunteer_user.is_approved)
