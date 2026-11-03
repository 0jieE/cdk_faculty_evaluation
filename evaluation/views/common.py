from functools import reduce
from operator import or_

from django.contrib.admin.utils import NestedObjects
from django.core.paginator import Paginator
from django.db import router
from django.db.models import Q

PAGE_SIZE = 25


def search(queryset, query, fields):
    """Case-insensitive match of every word in `query` against any of `fields`."""
    for word in (query or "").split():
        queryset = queryset.filter(reduce(or_, (Q(**{f"{f}__icontains": word}) for f in fields)))
    return queryset


def paginate(request, queryset, per_page=PAGE_SIZE):
    page = Paginator(queryset, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return page, params.urlencode()


def blocking_usage(obj):
    """What would be deleted along with `obj` (every FK here cascades).

    Returns [(label, count)] of other records; empty means it is safe to delete.
    """
    collector = NestedObjects(using=router.db_for_write(obj.__class__))
    collector.collect([obj])
    usage = []
    for model, instances in collector.model_objs.items():
        count = len([i for i in instances if not (model is obj.__class__ and i.pk == obj.pk)])
        if count:
            singular, plural = FRIENDLY_NAMES.get(
                model._meta.model_name, (model._meta.verbose_name, model._meta.verbose_name_plural))
            usage.append((singular if count == 1 else plural, count))
    return sorted(usage, key=lambda item: -item[1])


FRIENDLY_NAMES = {
    "user": ("account", "accounts"),
    "facultyclass": ("class", "classes"),
    "studentclass": ("enrollment", "enrollments"),
    "evaluationsubmission": ("evaluation", "evaluations"),
    "isscore": ("inventory answer", "inventory answers"),
    "rasscore": ("rapid appraisal answer", "rapid appraisal answers"),
    "inventorystatement": ("inventory statement", "inventory statements"),
    "rapidappraisalstatement": ("rapid appraisal statement", "rapid appraisal statements"),
    "yearlevel": ("year level", "year levels"),
    "schoolyear": ("school year", "school years"),
    "faculty": ("faculty member", "faculty members"),
}


def int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
