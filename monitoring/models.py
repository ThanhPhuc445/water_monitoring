from django.db import models
from django.utils import timezone

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
