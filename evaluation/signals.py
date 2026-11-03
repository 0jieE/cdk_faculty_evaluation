from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from .models import ISScore, RASScore


def update_submission_totals(submission):
    is_scores = ISScore.objects.filter(submission=submission).select_related("statement")

    is_total = 0
    for item in is_scores:
        if item.statement.is_positive:
            is_total += item.score
        else:
            is_total += (6 - item.score)

    ras_total = RASScore.objects.filter(submission=submission).aggregate(
        total=Sum("score")
    )["total"] or 0

    is_percent = is_total / 100
    ras_percent = ras_total / 10

    rating = ((is_percent * 0.9) + (ras_percent * 0.1)) * 100

    submission.isscore_total = is_total
    submission.rasscore_total = ras_total
    submission.rating = rating

    submission.save(update_fields=["isscore_total", "rasscore_total", "rating"])


# ✅ ISScore
@receiver(post_save, sender=ISScore)
def update_is_score(sender, instance, created, **kwargs):
    if not created:  # 🔥 ONLY on update
        update_submission_totals(instance.submission)


@receiver(post_delete, sender=ISScore)
def delete_is_score(sender, instance, **kwargs):
    update_submission_totals(instance.submission)


# ✅ RASScore
@receiver(post_save, sender=RASScore)
def update_ras_score(sender, instance, created, **kwargs):
    if not created:  # 🔥 ONLY on update
        update_submission_totals(instance.submission)


@receiver(post_delete, sender=RASScore)
def delete_ras_score(sender, instance, **kwargs):
    update_submission_totals(instance.submission)