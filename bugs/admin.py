from django.contrib import admin
from .models import Bug, Notification, Comment, BugEvent, Attachment, Tag
for m in (Bug, Notification, Comment, BugEvent, Attachment, Tag):
    admin.site.register(m)
