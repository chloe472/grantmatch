from django.contrib import admin
from .models import Agency, Grant, UserProfile, Project, GrantMatch, Application, Notification


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ['acronym', 'name', 'website']
    search_fields = ['name', 'acronym']


@admin.register(Grant)
class GrantAdmin(admin.ModelAdmin):
    list_display = ['title', 'agency', 'status', 'closing_date', 'match_score', 'funding_range']
    list_filter = ['status', 'agency', 'closing_date']
    search_fields = ['title', 'description', 'agency__name']
    date_hierarchy = 'closing_date'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization_name', 'organization_type']
    search_fields = ['user__username', 'organization_name']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'focus_area', 'created_at']
    list_filter = ['focus_area', 'created_at']
    search_fields = ['title', 'description']


@admin.register(GrantMatch)
class GrantMatchAdmin(admin.ModelAdmin):
    list_display = ['project', 'grant', 'match_score', 'is_saved', 'created_at']
    list_filter = ['is_saved', 'match_score']
    search_fields = ['project__title', 'grant__title']


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['user', 'grant', 'project', 'status', 'submitted_at']
    list_filter = ['status', 'submitted_at']
    search_fields = ['user__username', 'grant__title']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['title', 'message']
