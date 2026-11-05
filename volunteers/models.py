from django.db import models
from django.conf import settings


class Volunteer(models.Model):
    AVAILABILITY_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('weekends', 'Weekends Only'),
        ('evenings', 'Evenings Only'),
        ('on_call', 'On Call'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='volunteer')
    
    # Application details
    motivation = models.TextField(help_text='Why do you want to be a volunteer?')
    experience = models.TextField(blank=True, null=True, help_text='Any relevant experience?')
    skills = models.CharField(max_length=255, blank=True, null=True, help_text='e.g., First Aid, Security, Medical')
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='part_time')
    
    # Approval status
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='approved_volunteers')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Stats
    total_responses = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - Volunteer"
    
    def get_status_display_text(self):
        if self.is_approved and self.is_active:
            return 'Active'
        elif self.is_approved and not self.is_active:
            return 'Inactive'
        else:
            return 'Pending Approval'


class VolunteerResponse(models.Model):
    STATUS_CHOICES = [
        ('responding', 'Responding'),
        ('on_scene', 'On Scene'),
        ('assisting', 'Assisting'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name='responses')
    incident = models.ForeignKey('incidents.Incident', on_delete=models.CASCADE, related_name='volunteer_responses')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='responding')
    notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    responded_at = models.DateTimeField(auto_now_add=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-responded_at']
        unique_together = ['volunteer', 'incident']
    
    def __str__(self):
        return f"{self.volunteer.user.username} responded to {self.incident.title}"


class VolunteerReview(models.Model):
    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review for {self.volunteer.user.username} by {self.reviewer.username}"
