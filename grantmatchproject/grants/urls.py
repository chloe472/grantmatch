from django.urls import path
from . import views

app_name = 'grants'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('projects/', views.projects_list, name='projects'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('projects/<int:project_id>/matches/', views.project_matches, name='project_matches'),
    path('grants/', views.grants_list, name='grants_list'),
    path('grants/<int:grant_id>/', views.grant_detail, name='grant_detail'),
    path('grants/<int:grant_id>/save/', views.toggle_save_grant, name='toggle_save_grant'),
    path('grants/<int:grant_id>/start-application/', views.start_application, name='start_application'),
    path('grants/<int:grant_id>/start-application/recommended/', views.start_application_recommended, name='start_application_recommended'),
    path('saved/', views.saved_grants, name='saved_grants'),
    path('applications/', views.applications_list, name='applications'),
    path('applications/<int:application_id>/update-status/', views.update_application_status, name='update_application_status'),
    path('applications/<int:application_id>/proposal/', views.proposal_template, name='proposal_template'),
    path('applications/create/<int:grant_id>/', views.application_create, name='application_create'),
    path('settings/', views.settings_view, name='settings'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
]
