# Generated initial migration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Incident',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('category', models.CharField(max_length=20, choices=[('theft', 'Theft'), ('assault', 'Assault'), ('vandalism', 'Vandalism'), ('burglary', 'Burglary'), ('fraud', 'Fraud'), ('drugs', 'Drug-related'), ('domestic', 'Domestic Violence'), ('noise', 'Noise Complaint'), ('traffic', 'Traffic Incident'), ('suspicious', 'Suspicious Activity'), ('other', 'Other')])),
                ('severity', models.CharField(max_length=10, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')])),
                ('status', models.CharField(max_length=15, choices=[('active', 'Active'), ('investigating', 'Under Investigation'), ('resolved', 'Resolved'), ('closed', 'Closed')], default='active')),
                ('latitude', models.DecimalField(max_digits=10, decimal_places=8)),
                ('longitude', models.DecimalField(max_digits=11, decimal_places=8)),
                ('location_description', models.CharField(max_length=255, blank=True, null=True)),
                ('image', models.ImageField(upload_to='incident_images/', blank=True, null=True)),
                ('is_anonymous', models.BooleanField(default=False)),
                ('investigation_notes', models.TextField(blank=True, null=True)),
                ('case_number', models.CharField(max_length=50, blank=True, null=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolved_at', models.DateTimeField(null=True, blank=True)),
                ('assigned_officer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_incidents', to=settings.AUTH_USER_MODEL)),
                ('reported_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reported_incidents', to=settings.AUTH_USER_MODEL)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_incidents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('is_official', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='incidents.incident')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='IncidentUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_status', models.CharField(max_length=15, choices=[('active', 'Active'), ('investigating', 'Under Investigation'), ('resolved', 'Resolved'), ('closed', 'Closed')])),
                ('new_status', models.CharField(max_length=15, choices=[('active', 'Active'), ('investigating', 'Under Investigation'), ('resolved', 'Resolved'), ('closed', 'Closed')])),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('incident', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='updates', to='incidents.incident')),
                ('updated_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
