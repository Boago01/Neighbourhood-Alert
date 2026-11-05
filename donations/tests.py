from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from volunteers.models import Volunteer
from .forms import DonationCampaignForm, DonationForm, PayoutRequestForm
from .models import Donation, DonationCampaign, DonationCampaignItem


class DeleteCampaignTests(TestCase):
    def setUp(self):
        self.volunteer = User.objects.create_user(
            username='volunteer',
            password='test-password',
            role='volunteer',
        )
        self.other_volunteer = User.objects.create_user(
            username='other-volunteer',
            password='test-password',
            role='volunteer',
        )
        self.campaign = DonationCampaign.objects.create(
            title='Community safety equipment',
            description='Equipment for local volunteers.',
            created_by=self.volunteer,
        )
        self.item = DonationCampaignItem.objects.create(
            campaign=self.campaign,
            name='Torch',
            quantity_needed=4,
        )
        self.url = reverse('delete_campaign', args=[self.campaign.id])

    def test_owner_can_view_campaign_deletion_confirmation(self):
        self.client.force_login(self.volunteer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'donations/delete_campaign.html')
        self.assertTrue(DonationCampaign.objects.filter(id=self.campaign.id).exists())

    def test_owner_can_delete_campaign(self):
        self.client.force_login(self.volunteer)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('my_campaigns'))
        self.assertFalse(DonationCampaign.objects.filter(id=self.campaign.id).exists())
        self.assertFalse(DonationCampaignItem.objects.filter(id=self.item.id).exists())

    def test_volunteer_cannot_delete_another_volunteers_campaign(self):
        self.client.force_login(self.other_volunteer)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(DonationCampaign.objects.filter(id=self.campaign.id).exists())

    def test_resident_cannot_delete_campaign(self):
        resident = User.objects.create_user(
            username='resident',
            password='test-password',
            role='resident',
        )
        self.client.force_login(resident)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(DonationCampaign.objects.filter(id=self.campaign.id).exists())


class CreateCampaignItemsTests(TestCase):
    def setUp(self):
        self.volunteer = User.objects.create_user(
            username='campaign-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        self.url = reverse('create_campaign')

    def test_created_campaign_saves_each_needed_item(self):
        self.client.force_login(self.volunteer)

        response = self.client.post(
            self.url,
            {
                'title': 'Emergency Response Equipment',
                'description': 'Essential emergency response equipment.',
                'needed_items': 'Torch | 5\nFirst aid kit | 3',
                'ends_at': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        campaign = DonationCampaign.objects.get(
            title='Emergency Response Equipment',
            created_by=self.volunteer,
        )
        self.assertCountEqual(
            list(campaign.items.values_list('name', 'quantity_needed')),
            [('Torch', 5), ('First aid kit', 3)],
        )

        self.client.force_login(self.volunteer)
        response = self.client.get(reverse('my_campaigns'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Torch')
        self.assertContains(response, 'First aid kit')

    def test_needed_items_reject_empty_names_and_zero_quantities(self):
        for invalid_items in (' | 1', 'Torch | 0'):
            with self.subTest(invalid_items=invalid_items):
                form = DonationCampaignForm(data={
                    'title': 'Invalid campaign items',
                    'description': 'Invalid item test.',
                    'needed_items': invalid_items,
                    'ends_at': '',
                })
                self.assertFalse(form.is_valid())
                self.assertIn('needed_items', form.errors)

    def test_payout_and_donation_quantities_reject_nonpositive_values(self):
        donation_form = DonationForm(data={
            'equipment_name': 'Torch',
            'quantity': '0',
            'condition': 'Used',
            'pickup_address': 'Private Road',
            'phone_number': '0821234567',
        })
        payout_form = PayoutRequestForm(data={
            'amount': '-100',
            'bank_name': 'Example Bank',
            'account_number': '1234567890',
            'account_holder': 'Test User',
        })

        self.assertFalse(donation_form.is_valid())
        self.assertIn('quantity', donation_form.errors)
        self.assertFalse(payout_form.is_valid())
        self.assertIn('amount', payout_form.errors)


class DonateEquipmentTests(TestCase):
    def setUp(self):
        self.volunteer_user = User.objects.create_user(
            username='donation-volunteer',
            password='test-password',
            role='volunteer',
            is_active=True,
            is_approved=True,
        )
        self.campaign = DonationCampaign.objects.create(
            title='Emergency Response Equipment',
            description='Essential emergency response equipment.',
            created_by=self.volunteer_user,
        )
        self.item = DonationCampaignItem.objects.create(
            campaign=self.campaign,
            name='Reflective Safety Vest',
            quantity_needed=5,
        )
        self.donor = User.objects.create_user(
            username='equipment-donor',
            password='test-password',
            role='resident',
        )

    def test_campaign_item_name_is_saved_without_an_equipment_name_input(self):
        self.client.force_login(self.donor)
        url = reverse('donate_to_campaign', args=[self.campaign.id])

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        self.assertContains(get_response, 'Item to Donate')
        self.assertNotContains(get_response, 'Equipment name:')

        response = self.client.post(
            url,
            {
                'campaign_item': self.item.id,
                'quantity': 2,
                'condition': 'New',
                'pickup_address': '10 Main Street',
                'phone_number': '0123456789',
                'message': '',
            },
        )

        self.assertRedirects(
            response,
            reverse('campaign_detail', args=[self.campaign.id]),
        )
        donation = Donation.objects.get(donor=self.donor)
        self.assertEqual(donation.equipment_name, self.item.name)
        self.assertEqual(donation.campaign_item, self.item)

    def test_direct_volunteer_donation_uses_shared_template(self):
        volunteer = Volunteer.objects.create(
            user=self.volunteer_user,
            motivation='Help the community.',
            is_approved=True,
        )
        self.client.force_login(self.donor)

        response = self.client.get(
            reverse('donate_to_volunteer', args=[volunteer.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'donations/donate.html')
        self.assertContains(response, 'Equipment name:')

    def test_non_resident_cannot_access_direct_volunteer_donation(self):
        volunteer = Volunteer.objects.create(
            user=self.volunteer_user,
            motivation='Help the community.',
            is_approved=True,
        )
        self.client.force_login(self.volunteer_user)

        response = self.client.get(
            reverse('donate_to_volunteer', args=[volunteer.id])
        )

        self.assertRedirects(
            response,
            reverse('volunteer_detail', args=[volunteer.id]),
        )
        self.assertFalse(Donation.objects.filter(donor=self.volunteer_user).exists())

    def test_public_campaign_page_does_not_disclose_donor_or_pickup_details(self):
        Donation.objects.create(
            campaign=self.campaign,
            campaign_item=self.item,
            recipient=self.volunteer_user,
            donor=self.donor,
            equipment_name=self.item.name,
            quantity=1,
            pickup_address='42 Private Road',
            phone_number='0821234567',
            status='pending',
        )

        response = self.client.get(
            reverse('campaign_detail', args=[self.campaign.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Donation and donor details are only visible')
        self.assertNotContains(response, '42 Private Road')
        self.assertNotContains(response, 'equipment-donor')
        self.assertNotContains(response, '0821234567')

    def test_campaign_owner_can_manage_donations_and_anonymous_identity_is_hidden(self):
        donation = Donation.objects.create(
            campaign=self.campaign,
            campaign_item=self.item,
            recipient=self.volunteer_user,
            donor=self.donor,
            equipment_name=self.item.name,
            quantity=1,
            pickup_address='42 Private Road',
            phone_number='0821234567',
            is_anonymous=True,
            status='pending',
        )
        self.client.force_login(self.volunteer_user)

        response = self.client.get(
            reverse('campaign_detail', args=[self.campaign.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pickup: 42 Private Road')
        self.assertContains(response, 'Donor: Anonymous')
        self.assertNotContains(response, 'equipment-donor')
        self.assertContains(
            response,
            reverse(
                'update_donation_status',
                args=[self.campaign.pk, donation.pk, 'accepted'],
            ),
        )

    def test_donor_can_see_only_their_own_donation_details(self):
        another_donor = User.objects.create_user(
            username='another-donor',
            password='test-password',
            role='resident',
        )
        own_donation = Donation.objects.create(
            campaign=self.campaign,
            campaign_item=self.item,
            recipient=self.volunteer_user,
            donor=self.donor,
            equipment_name=self.item.name,
            quantity=1,
            pickup_address='My Private Road',
            phone_number='0821234567',
            is_anonymous=True,
        )
        Donation.objects.create(
            campaign=self.campaign,
            campaign_item=self.item,
            recipient=self.volunteer_user,
            donor=another_donor,
            equipment_name=self.item.name,
            quantity=1,
            pickup_address='Other Donor Road',
            phone_number='0831234567',
        )
        self.client.force_login(self.donor)

        response = self.client.get(
            reverse('campaign_detail', args=[self.campaign.pk]),
        )

        self.assertContains(response, 'My Private Road')
        self.assertNotContains(response, 'Other Donor Road')
        self.assertNotContains(response, '0831234567')
        self.assertContains(response, 'Donor: You')
        self.assertNotContains(response, 'Accept')

    def test_donation_status_cannot_be_changed_with_get(self):
        donation = Donation.objects.create(
            campaign=self.campaign,
            campaign_item=self.item,
            recipient=self.volunteer_user,
            donor=self.donor,
            equipment_name=self.item.name,
            quantity=1,
            pickup_address='42 Private Road',
            phone_number='0821234567',
            status='pending',
        )
        self.client.force_login(self.volunteer_user)

        response = self.client.get(
            reverse(
                'update_donation_status',
                args=[self.campaign.pk, donation.pk, 'completed'],
            ),
        )

        self.assertEqual(response.status_code, 405)
        donation.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(donation.status, 'pending')
        self.assertEqual(self.item.quantity_received, 0)
