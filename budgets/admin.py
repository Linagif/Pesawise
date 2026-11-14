from django.contrib import admin

from .models import Budget, BudgetAllocation

admin.site.register(Budget)
admin.site.register(BudgetAllocation)
