from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


class Reading(models.Model):
    timestamp = models.DateTimeField(default=timezone.now)
    ph = models.FloatField()
    tds = models.FloatField()
    ntu = models.FloatField()
    battery = models.FloatField(null=True, blank=True)
    signal = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Alert(models.Model):
    timestamp = models.DateTimeField(default=timezone.now)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=(
        ("LOW","Low"),("MEDIUM","Medium"),("HIGH","High")))
    type = models.CharField(max_length=20, choices=(
        ("RULE","Rule"),("AI","AI"),("FORECAST","Forecast")))
    status = models.CharField(max_length=20, choices=(
        ("NEW","New"),("ACK","Acknowledged"),("RESOLVED","Resolved")))
    created_at = models.DateTimeField(auto_now_add=True)
    
class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('user', 'User'),
    )
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')

    def __str__(self):
        return self.username
