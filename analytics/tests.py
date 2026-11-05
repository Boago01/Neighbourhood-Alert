from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from incidents.models import Incident


class HeatmapAccessTests(TestCase):
    def setUp(self):
        Incident.objects.create(
            title='Private incident title',
            description='Incident details must not appear in the public heatmap.',
            category='theft',
            severity='high',
            latitude='-28.72829100',
            longitude='24.74996100',
        )
        Incident.objects.create(
            title='Another private incident',
            description='Private report.',
            category='assault',
            severity='critical',
            latitude='-28.72829900',
            longitude='24.74996900',
        )

    def test_anonymous_users_are_redirected_to_login(self):
        response = self.client.get(reverse('heatmap'))

        self.assertRedirects(
            response,
            f'{reverse("login")}?next={reverse("heatmap")}',
        )

    def test_residents_can_view_exact_incident_details(self):
        resident = User.objects.create_user(
            username='resident',
            password='Resident-password-123!',
            role='resident',
        )
        self.client.force_login(resident)

        with override_settings(GOOGLE_MAPS_API_KEY='test-google-maps-key'):
            response = self.client.get(reverse('heatmap'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['map_points']), 2)
        self.assertTrue(response.context['can_view_exact_locations'])
        self.assertTrue(all(point['exact'] for point in response.context['map_points']))
        self.assertContains(response, 'Private incident title')
        self.assertContains(response, 'Severity:</h6>')
        self.assertContains(response, "low: '#16A34A'")
        self.assertContains(response, 'https://maps.googleapis.com/maps/api/js')
        self.assertContains(response, 'callback=initHeatmap')
        self.assertContains(response, 'libraries=visualization')
        self.assertContains(response, 'test-google-maps-key')

    def test_volunteers_can_view_exact_incident_details(self):
        volunteer = User.objects.create_user(
            username='volunteer',
            password='Volunteer-password-123!',
            role='volunteer',
            is_approved=False,
        )
        self.client.force_login(volunteer)

        response = self.client.get(reverse('heatmap'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_view_exact_locations'])
        self.assertEqual(len(response.context['map_points']), 2)
        self.assertTrue(all(point['exact'] for point in response.context['map_points']))
        self.assertContains(response, 'Private incident title')

    def test_residents_can_view_incidents_in_single_incident_areas(self):
        resident = User.objects.create_user(
            username='resident',
            password='Resident-password-123!',
            role='resident',
        )
        self.client.force_login(resident)
        Incident.objects.create(
            title='Isolated incident',
            description='This location should not be shown publicly.',
            category='theft',
            severity='low',
            latitude='-28.71000000',
            longitude='24.73000000',
        )

        response = self.client.get(reverse('heatmap'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['map_points']), 3)
        self.assertEqual(response.context['incident_count'], 3)
        self.assertContains(response, 'Isolated incident')

    def test_approved_police_can_view_exact_incident_details(self):
        police = User.objects.create_user(
            username='police',
            password='Police-password-123!',
            role='police',
            is_approved=True,
            is_active=True,
        )
        self.client.force_login(police)

        response = self.client.get(reverse('heatmap'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_view_exact_locations'])
        self.assertEqual(len(response.context['map_points']), 2)
        self.assertTrue(all(point['exact'] for point in response.context['map_points']))
        self.assertContains(response, 'Private incident title')
        self.assertContains(response, 'Severity:</h6>')
        self.assertContains(response, "low: '#16A34A'")

    def test_administrators_can_view_exact_incident_details(self):
        administrator = User.objects.create_user(
            username='administrator',
            password='Admin-password-123!',
            role='admin',
        )
        self.client.force_login(administrator)

        response = self.client.get(reverse('heatmap'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_view_exact_locations'])
        self.assertEqual(len(response.context['map_points']), 2)
        self.assertContains(response, 'Private incident title')
        self.assertContains(response, 'Severity:</h6>')
        self.assertContains(response, "critical: '#DC2626'")

    def test_admin_heatmap_shows_all_incidents_including_singleton_areas(self):
        Incident.objects.create(
            title='Isolated private incident',
            description='This singleton area should be hidden on every heatmap.',
            category='theft',
            severity='low',
            latitude='-28.71000000',
            longitude='24.73000000',
        )
        administrator = User.objects.create_user(
            username='administrator',
            password='Admin-password-123!',
            role='admin',
        )
        self.client.force_login(administrator)

        response = self.client.get(reverse('heatmap'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['map_points']), 3)
        self.assertEqual(response.context['incident_count'], 3)
        self.assertContains(response, 'Isolated private incident')

    def test_demo_seed_shows_all_exact_incidents_to_residents(self):
        resident = User.objects.create_user(
            username='demo-heatmap-resident',
            password='Resident-password-123!',
            role='resident',
        )
        call_command('seed_demo_heatmap', stdout=StringIO())
        self.client.force_login(resident)

        response = self.client.get(reverse('heatmap'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_view_exact_locations'])
        demo_points = [
            point
            for point in response.context['map_points']
            if point.get('title', '').startswith('DEMO –')
        ]
        self.assertEqual(len(demo_points), 9)
        self.assertTrue(all(point['exact'] for point in demo_points))
        self.assertContains(response, 'DEMO – Mobile phone theft')
