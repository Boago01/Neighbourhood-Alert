from django.db import models
from django.conf import settings


class Incident(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    CATEGORY_CHOICES = [
        ('theft', 'Theft'),
        ('assault', 'Assault'),
        ('vandalism', 'Vandalism'),
        ('burglary', 'Burglary'),
        ('fraud', 'Fraud'),
        ('drugs', 'Drug-related'),
        ('domestic', 'Domestic Violence'),
        ('noise', 'Noise Complaint'),
        ('traffic', 'Traffic Incident'),
        ('suspicious', 'Suspicious Activity'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    
    # Location
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    location_description = models.CharField(max_length=255, blank=True, null=True)
    
    # Media
    image = models.ImageField(upload_to='incident_images/', blank=True, null=True)
    
    # Reporting
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                    null=True, blank=True, related_name='reported_incidents')
    is_anonymous = models.BooleanField(default=False)
    
    # Assignment
    assigned_officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='assigned_incidents')
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='resolved_incidents')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Investigation
    investigation_notes = models.TextField(blank=True, null=True)
    case_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
    
    def get_display_reporter(self):
        if self.is_anonymous or not self.reported_by:
            return "Anonymous"
        return self.reported_by.get_full_name() or self.reported_by.username
    
    def get_severity_color(self):
        colors = {
            'low': 'success',
            'medium': 'info',
            'high': 'warning',
            'critical': 'danger',
        }
        return colors.get(self.severity, 'secondary')
    
    def get_status_color(self):
        colors = {
            'active': 'danger',
            'investigating': 'warning',
            'resolved': 'success',
            'closed': 'secondary',
        }
        return colors.get(self.status, 'secondary')


class Comment(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    is_official = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.incident.title}"


class IncidentUpdate(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='updates')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    old_status = models.CharField(max_length=15, choices=Incident.STATUS_CHOICES)
    new_status = models.CharField(max_length=15, choices=Incident.STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Update on {self.incident.title}: {self.old_status} -> {self.new_status}"


class IncidentAssignment(models.Model):
    """Model to track police assignment of volunteers to incidents"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    ASSIGNMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('on_way', 'On My Way'),
        ('arrived', 'Arrived'),
        ('assisting', 'Assisting'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='volunteer_assignments')
    volunteer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='incident_assignments')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignments_made')
    
    # Assignment details
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=ASSIGNMENT_STATUS_CHOICES, default='pending')
    assignment_notes = models.TextField(blank=True, null=True, help_text='Police officer notes for the volunteer')
    
    # Volunteer updates
    progress_notes = models.TextField(blank=True, null=True, help_text='Progress notes from volunteer')
    volunteer_images = models.ImageField(upload_to='incident_evidence/', blank=True, null=True)
    completion_report = models.TextField(blank=True, null=True, help_text='Completion report from volunteer')
    
    # Timestamps
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    on_way_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-assigned_at']
        unique_together = ['incident', 'volunteer']
    
    def __str__(self):
        return f"{self.volunteer.get_full_name()} assigned to {self.incident.title} (Priority: {self.get_priority_display()})"
    
    def get_status_color(self):
        colors = {
            'pending': 'warning',
            'accepted': 'info',
            'declined': 'danger',
            'on_way': 'primary',
            'arrived': 'info',
            'assisting': 'primary',
            'completed': 'success',
            'cancelled': 'secondary',
        }
        return colors.get(self.status, 'secondary')
