from django.db import models
from django.contrib.auth.models import User

class Video(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/')
    result_file = models.FileField(upload_to='processed/', null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class SpeedViolation(models.Model):
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='violations')
    frame_id = models.IntegerField(default=0)
    timestamp = models.DateTimeField()
    vehicle = models.CharField(max_length=200)
    speed = models.FloatField()
    plate = models.CharField(max_length=50)
    location = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.vehicle} - {self.speed} km/h"
