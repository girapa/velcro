from django.db import models


class Collection(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Bookmark(models.Model):
    """The canonical Neapolitan example model — fitting for our tests."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    url = models.URLField(unique=True)
    title = models.CharField(max_length=255)
    note = models.TextField(blank=True)
    favourite = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    collection = models.ForeignKey(Collection, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.title
