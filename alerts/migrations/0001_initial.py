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
            name='Alert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('priority', models.CharField(max_length=10, choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium')),
                ('latitude', models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)),
                ('longitude', models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)),
                ('radius', models.PositiveIntegerField(null=True, blank=True, help_text='Radius in meters')),
                ('is_active', models.BooleanField(default=True)),
                ('expires_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_alerts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SafetyResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('resource_type', models.CharField(max_length=20, choices=[('emergency_contact', 'Emergency Contact'), ('safety_tip', 'Safety Tip'), ('guideline', 'Guideline'), ('helpline', 'Helpline')])),
                ('description', models.TextField()),
                ('contact_number', models.CharField(max_length=20, blank=True, null=True)),
                ('contact_email', models.EmailField(blank=True, null=True)),
                ('address', models.TextField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['resource_type', 'title'],
            },
        ),
        migrations.CreateModel(
            name='AlertAcknowledgment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acknowledged_at', models.DateTimeField(auto_now_add=True)),
                ('alert', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acknowledgments', to='alerts.alert')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': [('alert', 'user')],
            },
        ),
    ]
