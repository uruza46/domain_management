import hashlib

from django.conf import settings
from django.db import models


class APIServiceToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_service_token")
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash_key(raw_key):
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def __str__(self):
        return self.prefix
