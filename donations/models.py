from django.db import models
from django.conf import settings


class DonationCampaign(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='donation_campaigns')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    ends_at = models.DateTimeField(null=True, blank=True)
    goal_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def total_items_needed(self):
        return sum(item.quantity_needed for item in self.items.all())
    
    def total_items_received(self):
        return sum(item.quantity_received for item in self.items.all())
    
    def get_progress_percentage(self):
        needed = self.total_items_needed()
        if needed == 0:
            return 0
        return min(100, int((self.total_items_received() / needed) * 100))
    
    def is_fully_funded(self):
        return self.total_items_received() >= self.total_items_needed()


class DonationCampaignItem(models.Model):
    campaign = models.ForeignKey(DonationCampaign, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=200)
    quantity_needed = models.PositiveIntegerField(default=1)
    quantity_received = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.name} ({self.quantity_received}/{self.quantity_needed})"


class Donation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('collected', 'Collected'),
        ('completed', 'Completed'),
    ]
    
    campaign = models.ForeignKey(DonationCampaign, on_delete=models.CASCADE, related_name='donations', null=True, blank=True)
    campaign_item = models.ForeignKey(DonationCampaignItem, on_delete=models.CASCADE, related_name='donations', null=True, blank=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_donations')
    donor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='made_donations')
    
    equipment_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=50, blank=True, null=True)
    pickup_address = models.TextField()
    phone_number = models.CharField(max_length=20)
    message = models.TextField(blank=True, null=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    donor_name = models.CharField(max_length=100, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    is_anonymous = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        donor = self.donor.get_full_name() if self.donor else self.equipment_name
        return f"{donor} donated {self.quantity} x {self.equipment_name}"


class Payout(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    volunteer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Bank details
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    account_holder = models.CharField(max_length=100)
    
    # Timestamps
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='processed_payouts')
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"Payout of R{self.amount} to {self.volunteer.username}"
