from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('resident', 'Resident'),
        ('volunteer', 'Community Volunteer'),
        ('police', 'Police Officer'),
        ('admin', 'Administrator'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='resident')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    police_employee_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )
    police_station = models.CharField(max_length=150, blank=True)
    police_unit = models.CharField(max_length=150, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    is_removed = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def is_resident(self):
        return self.role == 'resident'
    
    def is_volunteer(self):
        return self.role == 'volunteer'
    
    def is_police(self):
        return self.role == 'police' and self.is_approved and self.is_active
    
    def is_admin_user(self):
        return self.role == 'admin' or self.is_superuser
    
    def can_respond_to_incidents(self):
        return self.role in ['volunteer', 'police', 'admin'] and self.is_approved
    
    def can_manage_incidents(self):
        return self.is_police() and not self.is_admin_user()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    id_number = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"
