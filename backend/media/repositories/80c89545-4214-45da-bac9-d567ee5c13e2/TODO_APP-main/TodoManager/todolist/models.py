from django.db import models

class Task(models.Model):
    task = models.CharField(max_length = 100)
    isCompleted = models.BooleanField(default = False)
    
    def __str__(self):
        return f"{self.task}"
