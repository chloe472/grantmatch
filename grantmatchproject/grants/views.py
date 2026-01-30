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
from .matching import compute_match_score


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
    try:
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
            'new_matching_grants': new_matching_grants[:2],
        }
        
        return render(request, 'grants/dashboard.html', context)
    except Exception as e:
        import traceback
        error_msg = f"Dashboard error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        # Return a simple error page
        from django.http import HttpResponse
        return HttpResponse(f"<h1>Error</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>", status=500)


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
        # Calculate matches and redirect to results page
        return redirect('grants:project_matches', project_id=project.id)
    
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


@login_required
def project_edit(request, project_id):
    """Edit an existing project and recalculate matches"""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    
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
        
        # Update project
        project.title = request.POST.get('title')
        project.description = request.POST.get('description')
        project.focus_area = request.POST.get('focus_area', '')
        project.budget_required_min = float(budget_min) if budget_min else None
        project.budget_required_max = float(budget_max) if budget_max else None
        project.duration_years = request.POST.get('duration_years', '')
        project.kpis = request.POST.get('kpis', '')
        project.service_outcomes = request.POST.get('service_outcomes', '')
        project.beneficiary_types = beneficiary_types
        project.target_beneficiaries_count = int(target_count) if target_count else None
        project.project_start_date = start_date if start_date else None
        project.project_end_date = end_date if end_date else None
        project.interested_in = interested_in
        project.need_support_for = need_support_for
        project.want_support_from = want_support_from
        project.save()
        
        # Recalculate matches with updated project details
        calculate_matches_for_project(project)
        
        return redirect('grants:project_matches', project_id=project.id)
    
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
        'project': project,
        'agencies': agencies,
        'beneficiary_types_options': beneficiary_types_options,
        'interested_in_options': interested_in_options,
        'need_support_for_options': need_support_for_options,
        'is_edit': True,
    }
    
    return render(request, 'grants/project_form.html', context)


def calculate_matches_for_project(project):
    """Calculate grant matches for a project using deterministic scoring logic"""
    grants = Grant.objects.filter(status='open')

    for grant in grants:
        score, reasons, negative_reasons = compute_match_score(project, grant)

        if score >= 70:
            GrantMatch.objects.update_or_create(
                project=project,
                grant=grant,
                defaults={
                    'match_score': score,
                    'match_reasons': reasons[:3],
                }
            )


@login_required
def project_matches(request, project_id):
    """Display matching grants for a project with scores calculated using rule-based matching"""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    
    # Get all open grants
    grants = Grant.objects.filter(status='open').select_related('agency')
    
    # Calculate matches for all grants using rule-based matching
    matching_grants = []
    
    for grant in grants:
        try:
            score, reasons, negative_reasons = compute_match_score(project, grant)
            
            # Include all grants with calculated scores (display all matches)
            matching_grants.append({
                'grant': grant,
                'match_score': score,
                'match_reasons': reasons[:3] if reasons else ["Grant opportunity"]
            })
                
        except Exception as e:
            print(f"Error matching grant {grant.id} ({grant.title}): {e}")
            continue
    
    # Sort by match score (highest first)
    matching_grants.sort(key=lambda x: x['match_score'], reverse=True)
    
    print(f"✓ Processed {len(matching_grants)} grants using rule-based matching")
    
    # Get user's saved grants for the star icon
    saved_grant_ids = set(
        GrantMatch.objects.filter(
            project__user=request.user,
            is_saved=True
        ).values_list('grant_id', flat=True)
    )
    
    context = {
        'project': project,
        'matching_grants': matching_grants,
        'saved_grant_ids': saved_grant_ids,
    }
    
    return render(request, 'grants/project_matches.html', context)



@login_required
def grants_list(request):
    """Browse all grants with enhanced filtering"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Use select_related but don't exclude grants without agencies
        grants = Grant.objects.select_related('agency').all()
        total_grants_count = grants.count()
        logger.info(f"Total grants in database: {total_grants_count}")
        
        if total_grants_count == 0:
            logger.warning("No grants found in database. Grants may need to be synced using: python manage.py sync_grants")
        else:
            # Log some sample grant titles for debugging
            sample_grants = grants[:3]
            for grant in sample_grants:
                logger.info(f"Sample grant: {grant.title} (Agency: {grant.agency.acronym if grant.agency else 'None'})")
    except Exception as e:
        logger.error(f"Error querying grants: {e}", exc_info=True)
        grants = Grant.objects.none()  # Return empty queryset on error
    
    # Filtering
    search_query = request.GET.get('search', '')
    agency_filter = request.GET.getlist('agency', [])  # Multiple agencies
    status_filter = request.GET.get('status', '')
    match_score_filter = request.GET.get('match_score', '')
    deadline_filter = request.GET.get('deadline', '')
    
    if search_query:
        grants = grants.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(agency__name__icontains=search_query)
        )
    
    if agency_filter:
        grants = grants.filter(agency__acronym__in=agency_filter)
    
    if status_filter:
        grants = grants.filter(status=status_filter)
    
    # Match score filtering - REMOVED: Match scores should only come from GrantMatch records
    # Users should not filter by match score in browse all grants
    # Match scores are only available after creating a project and searching
    
    # Deadline filtering
    if deadline_filter:
        today = timezone.now().date()
        if deadline_filter == 'next-30':
            grants = grants.filter(
                closing_date__gte=today,
                closing_date__lte=today + timedelta(days=30)
            )
        elif deadline_filter == '30-60':
            grants = grants.filter(
                closing_date__gte=today + timedelta(days=30),
                closing_date__lte=today + timedelta(days=60)
            )
        elif deadline_filter == '60-90':
            grants = grants.filter(
                closing_date__gte=today + timedelta(days=60),
                closing_date__lte=today + timedelta(days=90)
            )
        elif deadline_filter == '90+':
            grants = grants.filter(closing_date__gte=today + timedelta(days=90))
    
    # Get user's saved grants and match data
    user_saved_grant_ids = set()
    user_grant_matches = {}
    if request.user.is_authenticated:
        user_project = Project.objects.filter(user=request.user).first()
        if user_project:
            matches = GrantMatch.objects.filter(
                project=user_project
            ).select_related('grant')
            
            user_saved_grant_ids = set(
                matches.filter(is_saved=True).values_list('grant_id', flat=True)
            )
            
            # Create a dict mapping grant_id to match object
            for match in matches:
                user_grant_matches[match.grant_id] = match
    
    # Annotate grants with saved status and match data (only from GrantMatch records)
    # Order by closing_date (nulls last) to show grants with dates first
    try:
        grants_list = list(grants.order_by('-closing_date', '-id'))
        logger.info(f"Grants after filtering: {len(grants_list)}")
    except Exception as e:
        logger.error(f"Error converting grants to list: {e}", exc_info=True)
        # Fallback: try without ordering
        try:
            grants_list = list(grants)
            logger.info(f"Grants after filtering (no ordering): {len(grants_list)}")
        except Exception as e2:
            logger.error(f"Error even without ordering: {e2}", exc_info=True)
            grants_list = []
    
    # Add match data to each grant (only if there's an actual GrantMatch record)
    for grant in grants_list:
        try:
            if grant.id in user_grant_matches:
                match = user_grant_matches[grant.id]
                grant.user_match_score = match.match_score
                grant.user_match_reasons = match.match_reasons[:3] if match.match_reasons else []
            else:
                grant.user_match_score = None  # No match - don't show score
                grant.user_match_reasons = []
        except Exception as e:
            logger.error(f"Error processing grant {grant.id}: {e}", exc_info=True)
            # Continue processing other grants
            grant.user_match_score = None
            grant.user_match_reasons = []
    
    agencies = Agency.objects.all().order_by('acronym')
    
    # Get saved grant IDs for the current user
    saved_grant_ids = set()
    if request.user.is_authenticated:
        saved_matches = GrantMatch.objects.filter(
            project__user=request.user,
            is_saved=True
        ).values_list('grant_id', flat=True)
        saved_grant_ids = set(saved_matches)
    
    context = {
        'grants': grants_list,
        'agencies': agencies,
        'search_query': search_query,
        'agency_filter': agency_filter,
        'status_filter': status_filter,
        'match_score_filter': match_score_filter,
        'deadline_filter': deadline_filter,
        'user_saved_grant_ids': user_saved_grant_ids,
    }
    
    return render(request, 'grants/grants_list.html', context)


@login_required
def grant_detail(request, grant_id):
    """View grant details - fetches live data from OurSG Grants Portal and generates AI analysis"""
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
    
    # Get user's project for AI analysis
    user_project = Project.objects.filter(user=request.user).first()
    
    # Get user matches for this grant
    user_matches = GrantMatch.objects.filter(
        grant=grant,
        project__user=request.user
    ).select_related('project')
    
    is_saved = False
    match_score = 0
    positive_reasons = []
    negative_reasons = []
    
    if user_matches.exists():
        match = user_matches.first()
        is_saved = match.is_saved
        match_score = match.match_score
    
    # When user has a project, always compute match to get both positive and negative reasons for display
    if user_project:
        score, pos_reasons, neg_reasons = compute_match_score(user_project, grant)
        positive_reasons = (pos_reasons[:5] if pos_reasons else [])  # Up to 5 most relevant
        negative_reasons = (neg_reasons[:5] if neg_reasons else [])   # Up to 5 most relevant
        # Use computed score for display if we have no stored match (e.g. viewing from browse)
        if not user_matches.exists():
            match_score = score
    else:
        # No project: use stored match reasons if any
        if user_matches.exists():
            match = user_matches.first()
            positive_reasons = (match.match_reasons or [])[:5]
    
    # Check if user has an existing application for this grant
    existing_application = Application.objects.filter(
        user=request.user,
        grant=grant
    ).first()
    
    # Get similar grants (same focus area or same agency, with match scores)
    similar_grants = []
    if user_project:
        # Get grants with similar focus areas
        similar_grants = Grant.objects.filter(
            status='open'
        ).exclude(id=grant.id)
        
        # Try to match by focus area first
        if user_project.focus_area:
            similar_grants = similar_grants.filter(
                description__icontains=user_project.focus_area
            )[:3]
        
        # If not enough, get from same agency
        if len(similar_grants) < 3:
            agency_grants = Grant.objects.filter(
                agency=grant.agency,
                status='open'
            ).exclude(id=grant.id)[:3]
            similar_grants = list(similar_grants) + list(agency_grants)
            similar_grants = similar_grants[:3]
    else:
        # Fallback: same agency
        similar_grants = Grant.objects.filter(
            agency=grant.agency,
            status='open'
        ).exclude(id=grant.id)[:3]
    
    # Add match scores to similar grants if user has projects
    if user_project:
        for similar_grant in similar_grants:
            similar_match = GrantMatch.objects.filter(
                project=user_project,
                grant=similar_grant
            ).first()
            if similar_match:
                similar_grant.user_match_score = similar_match.match_score
            else:
                similar_grant.user_match_score = 0
    
    context = {
        'grant': grant,
        'live_data': live_grant_data,  # Live data from portal
        'user_matches': user_matches,
        'is_saved': is_saved,
        'match_score': match_score,
        'match_reasons': positive_reasons,   # Why This Grant Matches (max 5)
        'negative_reasons': negative_reasons, # Why It May Not Match (max 5)
        'similar_grants': similar_grants,
        'existing_application': existing_application,
        'user_project': user_project,
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
    
    # Find or create a match (create default project if user has none)
    project = Project.objects.filter(user=request.user).first()
    if not project:
        # Create a default project for the user
        project = Project.objects.create(
            user=request.user,
            title="My Grants",
            description="Default project for saved grants"
        )
    
    match, created = GrantMatch.objects.get_or_create(
        project=project,
        grant=grant,
        defaults={'match_score': grant.match_score or 0}
    )
    match.is_saved = not match.is_saved
    match.save()
    is_saved = match.is_saved
    
    # Return JSON response for fetch/AJAX requests
    return JsonResponse({'success': True, 'is_saved': is_saved})


def bulk_unsave_grants(request):
    """Bulk unsave grants marked for removal"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            grant_ids = data.get('grant_ids', [])
            
            # Get user's project (create default if needed)
            project = Project.objects.filter(user=request.user).first()
            if not project:
                project = Project.objects.create(
                    user=request.user,
                    title="My Grants",
                    description="Default project for saved grants"
                )
            
            # Unsave the specified grants
            GrantMatch.objects.filter(
                project=project,
                grant_id__in=grant_ids,
                is_saved=True
            ).update(is_saved=False)
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False}, status=405)


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
def start_application_recommended(request, grant_id):
    """Start application with recommended proposal template"""
    grant = get_object_or_404(Grant, id=grant_id)
    
    # Get user's first project (optional - for pre-filling data)
    project = Project.objects.filter(user=request.user).first()
    
    # Get or create application - project can be None
    application, created = Application.objects.get_or_create(
        user=request.user,
        grant=grant,
        project=project,
        defaults={'status': 'in_progress'}
    )
    
    if not created and application.status != 'in_progress':
        application.status = 'in_progress'
        application.save()
    
    # Pre-fill proposal from project data if not already filled
    if not application.proposal_title:
        application.proposal_title = f"Project Proposal Template - {grant.title}"
    
    # Pre-fill sections from project data only if project exists
    if project:
        if not application.community_needs_analysis:
            # Use project description for community needs analysis
            if project.description:
                application.community_needs_analysis = project.description
            # Also use beneficiary types if available
            if project.beneficiary_types:
                beneficiary_text = f"This project targets: {', '.join(project.beneficiary_types)}."
                if application.community_needs_analysis:
                    application.community_needs_analysis += "\n\n" + beneficiary_text
                else:
                    application.community_needs_analysis = beneficiary_text
        
        if not application.project_objective:
            if project.service_outcomes:
                application.project_objective = project.service_outcomes
            elif project.description:
                # Extract objectives from description
                application.project_objective = project.description
        
        if not application.description_of_project:
            if project.description:
                application.description_of_project = project.description
            # Add timeline if available
            if project.project_start_date and project.project_end_date:
                timeline_text = f"\n\nProject Timeline: {project.project_start_date.strftime('%d %b %Y')} to {project.project_end_date.strftime('%d %b %Y')}"
                application.description_of_project += timeline_text
            if project.target_beneficiaries_count:
                application.description_of_project += f"\n\nTarget Number of Beneficiaries: {project.target_beneficiaries_count}"
    
    if not application.last_saved:
        application.last_saved = timezone.now()
    
    application.save()
    
    return redirect('grants:proposal_template', application_id=application.id)


@login_required
def proposal_template(request, application_id):
    """View and edit project proposal template"""
    application = get_object_or_404(Application, id=application_id, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save_draft':
            application.proposal_title = request.POST.get('proposal_title', '')
            application.community_needs_analysis = request.POST.get('community_needs_analysis', '')
            application.project_objective = request.POST.get('project_objective', '')
            application.project_uniqueness = request.POST.get('project_uniqueness', '')
            application.description_of_project = request.POST.get('description_of_project', '')
            application.project_publicity = request.POST.get('project_publicity', '')
            application.project_considerations = request.POST.get('project_considerations', '')
            application.project_evaluation = request.POST.get('project_evaluation', '')
            application.last_saved = timezone.now()
            application.save()
            return JsonResponse({'success': True, 'message': 'Draft saved successfully', 'last_saved': application.last_saved.strftime('%d %b %Y, %I:%M %p')})
        
        elif action == 'submit':
            application.proposal_title = request.POST.get('proposal_title', '')
            application.community_needs_analysis = request.POST.get('community_needs_analysis', '')
            application.project_objective = request.POST.get('project_objective', '')
            application.project_uniqueness = request.POST.get('project_uniqueness', '')
            application.description_of_project = request.POST.get('description_of_project', '')
            application.project_publicity = request.POST.get('project_publicity', '')
            application.project_considerations = request.POST.get('project_considerations', '')
            application.project_evaluation = request.POST.get('project_evaluation', '')
            application.status = 'submitted'
            application.submitted_at = timezone.now()
            application.last_saved = timezone.now()
            application.save()
            return redirect('grants:applications')
    
    context = {
        'application': application,
        'grant': application.grant,
        'project': application.project,
    }
    
    return render(request, 'grants/proposal_template.html', context)


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
@login_required
def settings_view(request):
    """User settings with multiple tabs"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    tab = request.GET.get('tab', 'organization')
    
    if request.method == 'POST':
        # Organization Information
        profile.organization_name = request.POST.get('organization_name', '')
        profile.organization_type = request.POST.get('organization_type', '')
        profile.organization_registration = request.POST.get('organization_registration', '')
        profile.organization_description = request.POST.get('organization_description', '')
        profile.organization_website = request.POST.get('organization_website', '')
        profile.organization_email = request.POST.get('organization_email', '')
        profile.organization_phone = request.POST.get('organization_phone', '')
        profile.organization_address = request.POST.get('organization_address', '')
        
        # Personal Information
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        profile.bio = request.POST.get('bio', '')
        
        # Notification Preferences
        profile.notify_email = request.POST.get('notify_email') == 'on'
        profile.notify_new_grants = request.POST.get('notify_new_grants') == 'on'
        profile.notify_deadline_reminders = request.POST.get('notify_deadline_reminders') == 'on'
        profile.notify_application_updates = request.POST.get('notify_application_updates') == 'on'
        profile.notify_weekly_digest = request.POST.get('notify_weekly_digest') == 'on'
        profile.notification_threshold = request.POST.get('notification_threshold', '70')
        
        # AI Preferences
        profile.ai_suggestions_enabled = request.POST.get('ai_suggestions_enabled') == 'on'
        profile.ai_auto_matching = request.POST.get('ai_auto_matching') == 'on'
        profile.ai_proposal_assistance = request.POST.get('ai_proposal_assistance') == 'on'
        profile.ai_deadline_alerts = request.POST.get('ai_deadline_alerts') == 'on'
        
        # Matching Preferences
        preferred_categories = request.POST.getlist('preferred_categories')
        profile.preferred_categories = preferred_categories
        profile.funding_min = request.POST.get('funding_min') or None
        profile.funding_max = request.POST.get('funding_max') or None
        profile.typical_duration = request.POST.get('typical_duration', '12_months')
        
        profile.save()
        user.save()
        
        return redirect('grants:settings')
    
    context = {
        'profile': profile,
        'tab': tab,
        'organization_type_choices': UserProfile.ORGANIZATION_TYPE_CHOICES,
        'threshold_choices': UserProfile.NOTIFICATION_THRESHOLD_CHOICES,
        'duration_choices': UserProfile.DURATION_CHOICES,
        'grant_categories': [
            'Community Care',
            'Innovation',
            'Technology',
            'Healthcare',
            'Mental Wellness',
            'Active Aging',
            'Caregiver Support',
            'Social Integration',
            'Digital Inclusion',
            'Research & Development'
        ]
    }
    
    return render(request, 'grants/settings.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.is_read = True
            notification.save()
            return JsonResponse({'status': 'success'})
        except Notification.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def mark_notification_unread(request, notification_id):
    """Mark a specific notification as unread"""
    if request.method == 'POST':
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.is_read = False
            notification.save()
            return JsonResponse({'status': 'success'})
        except Notification.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required
def mark_all_notifications_read(request):
    """Mark all user notifications as read"""
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
