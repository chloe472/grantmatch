from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
import json
from .models import Grant, Project, GrantMatch, Application, Notification, Agency, UserProfile
from django.contrib.auth.models import User
from .services import SGGrantsService


def register(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(
                user=user,
                avatar_initials=user.username[:2].upper() if len(user.username) >= 2 else user.username[0].upper()
            )
            login(request, user)
            return redirect('grants:dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    """Main dashboard view"""
    user = request.user
    
    # Get or create user profile
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'avatar_initials': user.username[:2].upper() if len(user.username) >= 2 else user.username[0].upper()}
    )
    
    # Get user's projects
    projects = Project.objects.filter(user=user)
    
    # Get recent matches (top 3)
    recent_matches = GrantMatch.objects.filter(project__user=user).select_related('grant', 'grant__agency')[:3]
    
    # Get upcoming deadlines (grants closing in next 120 days)
    upcoming_deadlines = Grant.objects.filter(
        status='open',
        closing_date__gte=timezone.now().date(),
        closing_date__lte=timezone.now().date() + timedelta(days=120)
    ).order_by('closing_date')[:3]
    
    # Get unread notifications count
    unread_notifications = Notification.objects.filter(user=user, is_read=False).count()
    
    # Get new grants matching user's projects (if any)
    new_matching_grants = []
    if projects.exists():
        # Find grants that match user's project focus areas
        for project in projects[:1]:  # Check first project
            matching_grants = Grant.objects.filter(
                status='open',
                match_score__gte=80
            ).exclude(
                matches__project=project
            )[:2]
            new_matching_grants.extend(matching_grants)
    
    context = {
        'user': user,
        'profile': profile,
        'projects': projects,
        'recent_matches': recent_matches,
        'upcoming_deadlines': upcoming_deadlines,
        'unread_notifications': unread_notifications,
        'new_matching_grants': new_matching_grants[:2],
    }
    
    return render(request, 'grants/dashboard.html', context)


@login_required
def projects_list(request):
    """List user's projects"""
    projects = Project.objects.filter(user=request.user).annotate(
        match_count=Count('matches')
    )
    return render(request, 'grants/projects.html', {'projects': projects})


@login_required
def project_create(request):
    """Create a new project"""
    if request.method == 'POST':
        # Parse JSON fields from form
        beneficiary_types = request.POST.getlist('beneficiary_types')
        interested_in = request.POST.getlist('interested_in')
        need_support_for = request.POST.getlist('need_support_for')
        want_support_from = request.POST.getlist('want_support_from')
        
        # Parse dates
        start_date = request.POST.get('project_start_date') or None
        end_date = request.POST.get('project_end_date') or None
        
        # Parse budget amounts
        budget_min = request.POST.get('budget_required_min')
        budget_max = request.POST.get('budget_required_max')
        
        # Parse target beneficiaries count
        target_count = request.POST.get('target_beneficiaries_count')
        
        project = Project.objects.create(
            user=request.user,
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            focus_area=request.POST.get('focus_area', ''),
            budget_required_min=float(budget_min) if budget_min else None,
            budget_required_max=float(budget_max) if budget_max else None,
            duration_years=request.POST.get('duration_years', ''),
            kpis=request.POST.get('kpis', ''),
            service_outcomes=request.POST.get('service_outcomes', ''),
            beneficiary_types=beneficiary_types,
            target_beneficiaries_count=int(target_count) if target_count else None,
            project_start_date=start_date if start_date else None,
            project_end_date=end_date if end_date else None,
            interested_in=interested_in,
            need_support_for=need_support_for,
            want_support_from=want_support_from,
        )
        # Trigger AI matching (simplified - in production, use actual AI service)
        calculate_matches_for_project(project)
        return redirect('grants:projects')
    
    # Get agencies for the "I want support from" dropdown with grant counts
    agencies = Agency.objects.annotate(grant_count=Count('grants')).order_by('acronym')
    
    # Define the options for multi-select fields
    beneficiary_types_options = [
        'Seniors', 'Youth', 'Children', 'Intellectually disabled', 
        'Physically disabled', 'Low-income families', 'Caregivers'
    ]
    
    interested_in_options = [
        ('Arts', 26), ('Care', 17), ('Community', 33), ('Digital Skills/Tools', 9),
        ('Education/Learning', 24), ('Engagement Marketing', 11), ('Environment', 7),
        ('Health', 15), ('Heritage', 14), ('Social Cohesion', 15),
        ('Social Service', 21), ('Sport', 14), ('Youth', 19)
    ]
    
    need_support_for_options = [
        ('Apps/Social Media/Website', 16), ('Classes/Seminar/Workshop', 28),
        ('Construction', 3), ('Dialogue/Conversation', 14),
        ('Event/Exhibition/Performance', 27), ('Fund-Raising', 6),
        ('Music/Video', 18), ('Publication', 17),
        ('Research/Documentation/Prototype', 15), ('Visual Arts', 11)
    ]
    
    context = {
        'agencies': agencies,
        'beneficiary_types_options': beneficiary_types_options,
        'interested_in_options': interested_in_options,
        'need_support_for_options': need_support_for_options,
    }
    
    return render(request, 'grants/project_form.html', context)


def calculate_matches_for_project(project):
    """Calculate grant matches for a project using AI matching logic"""
    grants = Grant.objects.filter(status='open')
    
    for grant in grants:
        score = 0
        reasons = []
        
        # Simple matching logic (replace with actual AI in production)
        if project.focus_area.lower() in grant.description.lower():
            score += 30
            reasons.append(f"Perfect alignment with {project.focus_area} programs")
        
        if project.budget_required_min and grant.funding_min:
            if grant.funding_min <= project.budget_required_max and grant.funding_max >= project.budget_required_min:
                score += 25
                reasons.append("Budget range matches your requirements")
        
        if project.kpis and grant.description:
            score += 20
            reasons.append("KPIs align with your service outcomes")
        
        if project.duration_years and grant.duration_years:
            score += 15
            reasons.append("Timeline aligns with project scope")
        
        # Add some base score for open grants
        score += 10
        
        if score >= 70:  # Only create matches with 70%+ score
            GrantMatch.objects.update_or_create(
                project=project,
                grant=grant,
                defaults={
                    'match_score': min(score, 100),
                    'match_reasons': reasons[:3]  # Top 3 reasons
                }
            )


@login_required
def grants_list(request):
    """Browse all grants"""
    grants = Grant.objects.select_related('agency').all()
    
    # Filtering
    search_query = request.GET.get('search', '')
    agency_filter = request.GET.get('agency', '')
    status_filter = request.GET.get('status', '')
    
    if search_query:
        grants = grants.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(agency__name__icontains=search_query)
        )
    
    if agency_filter:
        grants = grants.filter(agency__acronym=agency_filter)
    
    if status_filter:
        grants = grants.filter(status=status_filter)
    
    agencies = Agency.objects.all()
    
    context = {
        'grants': grants,
        'agencies': agencies,
        'search_query': search_query,
        'agency_filter': agency_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'grants/grants_list.html', context)


@login_required
def grant_detail(request, grant_id):
    """View grant details - fetches live data from OurSG Grants Portal"""
    # Get grant from database first (for basic info and relationships)
    grant = get_object_or_404(Grant, id=grant_id)
    
    # Fetch LIVE detailed data from OurSG Grants Portal
    service = SGGrantsService()
    grant_value = None
    if grant.source_url:
        # Extract grant value from URL (e.g., /grants/ssgacg/instruction -> ssgacg)
        import re
        match = re.search(r'/grants/([^/]+)/', grant.source_url)
        if match:
            grant_value = match.group(1)
    
    live_grant_data = None
    if grant_value or grant.external_id:
        try:
            live_grant_data = service.fetch_grant_detail(
                grant_value=grant_value,
                external_id=grant.external_id
            )
        except Exception as e:
            print(f"Error fetching live grant data: {e}")
            # Fallback to database data
    
    # Get user matches for this grant
    user_matches = GrantMatch.objects.filter(
        grant=grant,
        project__user=request.user
    ).select_related('project')
    
    is_saved = False
    match_score = 0
    match_reasons = []
    if user_matches.exists():
        match = user_matches.first()
        is_saved = match.is_saved
        match_score = match.match_score
        match_reasons = match.match_reasons or []
    
    # Check if user has an existing application for this grant
    existing_application = Application.objects.filter(
        user=request.user,
        grant=grant
    ).first()
    
    # Get similar grants (from same agency or similar focus)
    similar_grants = Grant.objects.filter(
        agency=grant.agency
    ).exclude(id=grant.id)[:3]
    
    # Calculate match reasons for display
    positive_reasons = match_reasons[:4] if match_reasons else []
    # Generate some negative reasons if needed (this would come from AI matching logic)
    negative_reasons = []
    
    context = {
        'grant': grant,
        'live_data': live_grant_data,  # Live data from portal
        'user_matches': user_matches,
        'is_saved': is_saved,
        'match_score': match_score,
        'match_reasons': positive_reasons,
        'negative_reasons': negative_reasons,
        'similar_grants': similar_grants,
        'existing_application': existing_application,
    }
    
    return render(request, 'grants/grant_detail.html', context)


@login_required
def saved_grants(request):
    """View saved grants"""
    saved_matches = GrantMatch.objects.filter(
        project__user=request.user,
        is_saved=True
    ).select_related('grant', 'grant__agency', 'project')
    
    return render(request, 'grants/saved_grants.html', {'saved_matches': saved_matches})


@login_required
def toggle_save_grant(request, grant_id):
    """Toggle save status of a grant"""
    grant = get_object_or_404(Grant, id=grant_id)
    
    # Find or create a match (simplified - assumes user has at least one project)
    project = Project.objects.filter(user=request.user).first()
    if project:
        match, created = GrantMatch.objects.get_or_create(
            project=project,
            grant=grant,
            defaults={'match_score': grant.match_score or 0}
        )
        match.is_saved = not match.is_saved
        match.save()
    
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
def applications_list(request):
    """List user's applications in Kanban board format"""
    applications = Application.objects.filter(
        user=request.user
    ).select_related('grant', 'grant__agency', 'project').order_by('-updated_at')
    
    # Group applications by status
    status_groups = {
        'in_progress': [],
        'submitted': [],
        'approved': [],
        'rejected': [],
    }
    
    for app in applications:
        if app.status in status_groups:
            status_groups[app.status].append(app)
    
    context = {
        'applications': applications,
        'status_groups': status_groups,
    }
    
    return render(request, 'grants/applications.html', context)


@login_required
def start_application(request, grant_id):
    """Start a new application - creates application with 'in_progress' status"""
    grant = get_object_or_404(Grant, id=grant_id)
    
    # Get user's first project (or create a default one if needed)
    project = Project.objects.filter(user=request.user).first()
    
    if not project:
        # If user has no projects, redirect to create one
        return redirect('grants:project_create')
    
    # Check if application already exists
    application, created = Application.objects.get_or_create(
        user=request.user,
        grant=grant,
        project=project,
        defaults={'status': 'in_progress'}
    )
    
    if not created:
        # If application exists but is not in progress, update it
        if application.status != 'in_progress':
            application.status = 'in_progress'
            application.save()
    
    return redirect('grants:applications')


@login_required
def application_create(request, grant_id):
    """Create a new application"""
    grant = get_object_or_404(Grant, id=grant_id)
    projects = Project.objects.filter(user=request.user)
    
    if request.method == 'POST':
        project_id = request.POST.get('project_id')
        project = get_object_or_404(Project, id=project_id, user=request.user)
        
        application = Application.objects.create(
            user=request.user,
            project=project,
            grant=grant,
            status='in_progress',
            notes=request.POST.get('notes', '')
        )
        return redirect('grants:applications')
    
    context = {
        'grant': grant,
        'projects': projects,
    }
    
    return render(request, 'grants/application_form.html', context)


@login_required
def update_application_status(request, application_id):
    """Update application status via drag-and-drop"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    application = get_object_or_404(Application, id=application_id, user=request.user)
    new_status = request.POST.get('status')
    
    # Validate status
    valid_statuses = ['in_progress', 'submitted', 'approved', 'rejected']
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    application.status = new_status
    
    # Set submitted_at if status is 'submitted'
    if new_status == 'submitted' and not application.submitted_at:
        application.submitted_at = timezone.now()
    
    application.save()
    
    return JsonResponse({'success': True, 'status': new_status})


@login_required
def settings_view(request):
    """User settings"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        profile.organization_name = request.POST.get('organization_name', '')
        profile.organization_type = request.POST.get('organization_type', '')
        profile.bio = request.POST.get('bio', '')
        profile.save()
        
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        return redirect('grants:settings')
    
    return render(request, 'grants/settings.html', {'profile': profile})
