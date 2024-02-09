from django.db import models

# Create your models here.


class Post(models.Model):
    title = models.TextField(db_index=True)
    content = models.CharField(max_length=100, db_index=True)
