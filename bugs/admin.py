from django.contrib import admin
from .models import Bug, Notification
admin.site.register(Bug)
admin.site.register(Notification)
from .models import Comment, BugEvent
admin.site.register(Comment)
admin.site.register(BugEvent)
from .models import Attachment
admin.site.register(Attachment)
