"""Category: shared by income sources, expense categories and the Savings budget line.
user = NULL means a system default that every student can see but not change."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class CategoryQuerySet(models.QuerySet):
    def visible_to(self, user):
        return self.filter(Q(user__isnull=True) | Q(user=user))

    def of_type(self, *types):
        return self.filter(category_type__in=types)


class Category(models.Model):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    SAVINGS = "SAVINGS"
    TYPE_CHOICES = [(INCOME, "Income source"), (EXPENSE, "Expense category"), (SAVINGS, "Savings")]

    ESSENTIAL = "ESSENTIAL"
    DISCRETIONARY = "DISCRETIONARY"
    SPENDING_CHOICES = [(ESSENTIAL, "Essential (needs)"), (DISCRETIONARY, "Discretionary (wants)")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=60)
    category_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    # Only meaningful for EXPENSE categories: used by the Financial Health analysis.
    spending_type = models.CharField(max_length=15, choices=SPENDING_CHOICES, default=DISCRETIONARY)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CategoryQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [models.UniqueConstraint(fields=["user", "name", "category_type"],
                                               name="unique_category_per_user_and_type")]

    def __str__(self):
        return self.name

    @property
    def is_default(self):
        return self.user_id is None

    def clean(self):
        if self.name:
            self.name = self.name.strip()
            clash = Category.objects.filter(name__iexact=self.name, category_type=self.category_type)
            clash = clash.filter(Q(user__isnull=True) | Q(user=self.user)).exclude(pk=self.pk)
            if clash.exists():
                raise ValidationError("A category with this name already exists.")


def get_savings_category():
    return Category.objects.filter(user__isnull=True, category_type=Category.SAVINGS).first()
