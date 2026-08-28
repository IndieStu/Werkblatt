from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .models import Workshop


@login_required
def workshop_list(request):
    lower_bound = timezone.now() - timedelta(days=30)
    workshops = Workshop.objects.for_organization(
        request.organization_context.organization_id
    ).filter(
        starts_at__gte=lower_bound,
    )
    return render(request, "workshops/list.html", {"workshops": workshops})
