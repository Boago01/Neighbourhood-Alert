from django.db import models
from django.conf import settings


class Alert(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Location (optional - for location-specific alerts)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    radius = models.PositiveIntegerField(null=True, blank=True, help_text='Radius in meters')
    
    # Creator
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_alerts')
    
    # Status
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_priority_display()})"
    
    def get_priority_color(self):
        colors = {
            'low': 'info',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'dark',
        }
        return colors.get(self.priority, 'secondary')
    
    def is_expired(self):
        from django.utils import timezone
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class AlertSMSDelivery(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
        ('dry_run', 'Dry run'),
    ]

    alert = models.OneToOneField(
        Alert,
        on_delete=models.CASCADE,
        related_name='sms_delivery',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    provider_submission_id = models.CharField(max_length=100, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)
    attempted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self):
        return f"SMS delivery for alert {self.alert_id}: {self.get_status_display()}"


class ApprovalSMSDelivery(models.Model):
    STATUS_CHOICES = AlertSMSDelivery.STATUS_CHOICES

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='approval_sms_delivery',
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    provider_submission_id = models.CharField(max_length=100, blank=True)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self):
        return f"Approval SMS for user {self.user_id}: {self.get_status_display()}"


class AlertAcknowledgment(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='acknowledgments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['alert', 'user']
    
    def __str__(self):
        return f"{self.user.username} acknowledged {self.alert.title}"


class SafetyResource(models.Model):
    RESOURCE_TYPES = [
        ('emergency_contact', 'Emergency Contact'),
        ('safety_tip', 'Safety Tip'),
        ('guideline', 'Guideline'),
        ('helpline', 'Helpline'),
    ]
    
    title = models.CharField(max_length=200)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    description = models.TextField()
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['resource_type', 'title']
    
    def __str__(self):
        return f"{self.title} ({self.get_resource_type_display()})"
