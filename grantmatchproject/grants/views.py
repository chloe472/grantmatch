from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
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
        project = Project.objects.create(
            user=request.user,
            title=request.POST.get('title'),
            description=request.POST.get('description'),
            focus_area=request.POST.get('focus_area', ''),
            budget_required_min=request.POST.get('budget_required_min') or None,
            budget_required_max=request.POST.get('budget_required_max') or None,
            duration_years=request.POST.get('duration_years', ''),
            kpis=request.POST.get('kpis', ''),
            service_outcomes=request.POST.get('service_outcomes', ''),
        )
        # Trigger AI matching (simplified - in production, use actual AI service)
        calculate_matches_for_project(project)
        return redirect('grants:projects')
    return render(request, 'grants/project_form.html')


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
    """List user's applications"""
    applications = Application.objects.filter(
        user=request.user
    ).select_related('grant', 'grant__agency', 'project').order_by('-created_at')
    
    return render(request, 'grants/applications.html', {'applications': applications})


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
            status='draft',
            notes=request.POST.get('notes', '')
        )
        return redirect('grants:applications')
    
    context = {
        'grant': grant,
        'projects': projects,
    }
    
    return render(request, 'grants/application_form.html', context)


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
