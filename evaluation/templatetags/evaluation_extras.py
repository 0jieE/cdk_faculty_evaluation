from django import template

from ..services import full_name as _full_name, grade_for

register = template.Library()


@register.filter
def grade(rating):
    """Descriptive equivalent of a rating, e.g. 'Very Satisfactory'."""
    return grade_for(rating)[1] or ""


@register.filter
def grade_code(rating):
    return grade_for(rating)[0] or ""


@register.filter
def score(value, places=2):
    """Format an average; a dash when there is nothing yet."""
    if value is None:
        return "–"
    return f"{value:.{int(places)}f}"


@register.filter
def percent_of(value, maximum):
    """Width (0-100) of `value` on a 0..maximum scale, for bars."""
    try:
        return max(0, min(100, round(100 * float(value) / float(maximum), 1)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def full_name(user):
    return _full_name(user, middle=False)


@register.filter
def field_type(bound_field):
    return bound_field.field.widget.__class__.__name__
