# Generated initial migration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('incidents', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Volunteer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('motivation', models.TextField(help_text='Why do you want to be a volunteer?')),
                ('experience', models.TextField(blank=True, null=True, help_text='Any relevant experience?')),
                ('skills', models.CharField(max_length=255, blank=True, null=True, help_text='e.g., First Aid, Security, Medical')),
                ('availability', models.CharField(max_length=20, choices=[('full_time', 'Full Time'), ('part_time', 'Part Time'), ('weekends', 'Weekends Only'), ('evenings', 'Evenings Only'), ('on_call', 'On Call')], default='part_time')),
                ('is_approved', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('approved_at', models.DateTimeField(null=True, blank=True)),
                ('total_responses', models.PositiveIntegerField(default=0)),
                ('rating', models.DecimalField(max_digits=3, decimal_places=2, default=5.00)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_volunteers', to=settings.AUTH_USER_MODEL)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='volunteer', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VolunteerReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField(choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])),
                ('comment', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('volunteer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='volunteers.volunteer')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='VolunteerResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=20, choices=[('responding', 'Responding'), ('on_scene', 'On Scene'), ('assisting', 'Assisting'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='responding')),
                ('notes', models.TextField(blank=True, null=True)),
                ('responded_at', models.DateTimeField(auto_now_add=True)),
                ('arrived_at', models.DateTimeField(null=True, blank=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='volunteer_responses', to='incidents.incident')),
                ('volunteer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='volunteers.volunteer')),
            ],
            options={
                'ordering': ['-responded_at'],
                'unique_together': [('volunteer', 'incident')],
            },
        ),
    ]
