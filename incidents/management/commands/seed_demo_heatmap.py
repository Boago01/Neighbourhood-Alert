from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from incidents.models import Incident


DEMO_DESCRIPTION_PREFIX = (
    'FICTIONAL DEMONSTRATION DATA – NOT A REAL INCIDENT.'
)

DEMO_INCIDENTS = (
    {
        'title': 'DEMO – Mobile phone theft',
        'category': 'theft',
        'severity': 'high',
        'latitude': '-28.72820000',
        'longitude': '24.74990000',
        'location_description': 'Kimberley Central demonstration cluster',
    },
    {
        'title': 'DEMO – Suspicious activity',
        'category': 'suspicious',
        'severity': 'medium',
        'latitude': '-28.72780000',
        'longitude': '24.75120000',
        'location_description': 'Kimberley Central demonstration cluster',
    },
    {
        'title': 'DEMO – Vehicle break-in',
        'category': 'theft',
        'severity': 'medium',
        'latitude': '-28.73110000',
        'longitude': '24.74880000',
        'location_description': 'Kimberley Central demonstration cluster',
    },
    {
        'title': 'DEMO – Attempted house break-in',
        'category': 'theft',
        'severity': 'high',
        'latitude': '-28.73850000',
        'longitude': '24.75800000',
        'location_description': 'Southern Kimberley demonstration cluster',
    },
    {
        'title': 'DEMO – Property vandalism',
        'category': 'vandalism',
        'severity': 'low',
        'latitude': '-28.74110000',
        'longitude': '24.76150000',
        'location_description': 'Southern Kimberley demonstration cluster',
    },
    {
        'title': 'DEMO – Suspicious vehicle',
        'category': 'suspicious',
        'severity': 'medium',
        'latitude': '-28.73920000',
        'longitude': '24.76400000',
        'location_description': 'Southern Kimberley demonstration cluster',
    },
    {
        'title': 'DEMO – Bicycle theft',
        'category': 'theft',
        'severity': 'medium',
        'latitude': '-28.71100000',
        'longitude': '24.75900000',
        'location_description': 'Northern Kimberley demonstration cluster',
    },
    {
        'title': 'DEMO – Streetlight vandalism',
        'category': 'vandalism',
        'severity': 'low',
        'latitude': '-28.71350000',
        'longitude': '24.76140000',
        'location_description': 'Northern Kimberley demonstration cluster',
    },
    {
        'title': 'DEMO – Suspicious activity near shops',
        'category': 'suspicious',
        'severity': 'medium',
        'latitude': '-28.70920000',
        'longitude': '24.76420000',
        'location_description': 'Northern Kimberley demonstration cluster',
    },
)


class Command(BaseCommand):
    help = 'Create or update the nine fictional incidents for heatmap demos.'

    @transaction.atomic
    def handle(self, *args, **options):
        residents = list(
            User.objects.filter(
                role='resident',
                is_active=True,
                is_removed=False,
            ).order_by('pk')
        )
        if not residents:
            raise CommandError(
                'No active, non-removed resident accounts exist. '
                'No demonstration incidents were created.'
            )

        titles = [incident['title'] for incident in DEMO_INCIDENTS]
        conflicting_titles = list(
            Incident.objects.filter(title__in=titles)
            .exclude(description__startswith=DEMO_DESCRIPTION_PREFIX)
            .values_list('title', flat=True)
        )
        if conflicting_titles:
            raise CommandError(
                'Refusing to overwrite incident(s) without the fictional '
                'demonstration marker: '
                + ', '.join(sorted(conflicting_titles))
            )

        created_count = 0
        updated_count = 0
        for index, incident_data in enumerate(DEMO_INCIDENTS):
            defaults = {
                **incident_data,
                'description': (
                    f'{DEMO_DESCRIPTION_PREFIX} '
                    'Synthetic record for a project presentation only.'
                ),
                'status': 'active',
                'reported_by': residents[index % len(residents)],
                'is_anonymous': True,
                'assigned_officer': None,
                'resolved_by': None,
                'case_number': None,
            }
            _, created = Incident.objects.update_or_create(
                title=incident_data['title'],
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {len(DEMO_INCIDENTS)} fictional incidents '
                f'({created_count} created, {updated_count} updated) '
                f'using {len(residents)} existing resident account(s).'
            )
        )
