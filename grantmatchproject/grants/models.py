from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

#hi nicolle
class Agency(models.Model):
    """Government agencies that provide grants"""
    name = models.CharField(max_length=200)
    acronym = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)
    
    def __str__(self):
        return f"{self.acronym} - {self.name}"


class Grant(models.Model):
    """Grant opportunities from various agencies"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('upcoming', 'Upcoming'),
    ]
    
    title = models.CharField(max_length=300)
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='grants')
    description = models.TextField()
    funding_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    funding_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    opening_date = models.DateField(null=True, blank=True)
    duration_years = models.CharField(max_length=50, blank=True)  # e.g., "2-3 years", "1-2 years"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    eligibility_criteria = models.TextField(blank=True)
    application_url = models.URLField(blank=True)
    icon_name = models.CharField(max_length=50, blank=True)  # For UI icons
    match_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI-calculated match score (0-100)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    source_url = models.URLField(blank=True, help_text="URL from OurSG Grants Portal")
    external_id = models.CharField(max_length=100, blank=True, help_text="External ID from source")
    
    class Meta:
        ordering = ['-match_score', '-closing_date']
        indexes = [
            models.Index(fields=['status', 'closing_date']),
            models.Index(fields=['match_score']),
        ]
    
    def __str__(self):
        return f"{self.agency.acronym} - {self.title}"
    
    @property
    def funding_range(self):
        if self.funding_min and self.funding_max:
            return f"${self.funding_min:,.0f}K - ${self.funding_max:,.0f}K"
        elif self.funding_min:
            return f"${self.funding_min:,.0f}K+"
        return "Amount not specified"
    
    @property
    def days_until_deadline(self):
        if self.closing_date:
            delta = self.closing_date - timezone.now().date()
            return delta.days
        return None


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization_name = models.CharField(max_length=200, blank=True)
    organization_type = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    avatar_initials = models.CharField(max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.organization_name}"


class Project(models.Model):
    """User projects for grant matching"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    title = models.CharField(max_length=300)
    description = models.TextField()
    focus_area = models.CharField(max_length=200, blank=True)  # e.g., "dementia care", "active aging"
    budget_required_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    budget_required_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    duration_years = models.CharField(max_length=50, blank=True)
    kpis = models.TextField(blank=True, help_text="Key Performance Indicators")
    service_outcomes = models.TextField(blank=True)
    # New fields for enhanced project form
    beneficiary_types = models.JSONField(default=list, help_text="List of beneficiary types (multi-select)")
    target_beneficiaries_count = models.IntegerField(null=True, blank=True, help_text="Target number of beneficiaries")
    project_start_date = models.DateField(null=True, blank=True, help_text="Project start date")
    project_end_date = models.DateField(null=True, blank=True, help_text="Project end date")
    interested_in = models.JSONField(default=list, help_text="List of interest areas (multi-select)")
    need_support_for = models.JSONField(default=list, help_text="List of support types needed (multi-select)")
    want_support_from = models.JSONField(default=list, help_text="List of agencies to get support from (multi-select)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


class GrantMatch(models.Model):
    """AI-calculated matches between projects and grants"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='matches')
    grant = models.ForeignKey(Grant, on_delete=models.CASCADE, related_name='matches')
    match_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Match percentage (0-100)"
    )
    match_reasons = models.JSONField(default=list, help_text="List of reasons why this is a good match")
    is_saved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['project', 'grant']
        ordering = ['-match_score']
    
    def __str__(self):
        return f"{self.project.title} ↔ {self.grant.title} ({self.match_score}%)"


class Application(models.Model):
    """Grant applications submitted by users"""
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted (In Review)'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='applications')
    grant = models.ForeignKey(Grant, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.grant.title}"


class Notification(models.Model):
    """User notifications"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
