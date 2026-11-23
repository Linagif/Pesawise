from django.urls import path

from . import views

app_name = "budgets"
urlpatterns = [
    path("", views.budget_list, name="list"),
    path("new/", views.budget_create, name="create"),
    path("<int:pk>/", views.budget_detail, name="detail"),
    path("<int:pk>/delete/", views.budget_delete, name="delete"),
    path("allocation/<int:pk>/edit/", views.allocation_edit, name="allocation_edit"),
    path("allocation/<int:pk>/delete/", views.allocation_delete, name="allocation_delete"),
]
