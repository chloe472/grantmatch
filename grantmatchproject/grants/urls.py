from django.urls import path
from . import views

app_name = 'grants'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('projects/', views.projects_list, name='projects'),
    path('projects/create/', views.project_create, name='project_create'),
    path('grants/', views.grants_list, name='grants_list'),
    path('grants/<int:grant_id>/', views.grant_detail, name='grant_detail'),
    path('grants/<int:grant_id>/save/', views.toggle_save_grant, name='toggle_save_grant'),
    path('saved/', views.saved_grants, name='saved_grants'),
    path('applications/', views.applications_list, name='applications'),
    path('applications/create/<int:grant_id>/', views.application_create, name='application_create'),
    path('settings/', views.settings_view, name='settings'),
]
