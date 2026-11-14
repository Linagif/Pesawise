from django.urls import path

from . import views

app_name = "savings"
urlpatterns = [
    path("", views.goal_list, name="list"),
    path("new/", views.goal_add, name="add"),
    path("<int:pk>/", views.goal_detail, name="detail"),
    path("<int:pk>/edit/", views.goal_edit, name="edit"),
    path("<int:pk>/delete/", views.goal_delete, name="delete"),
    path("contribution/<int:pk>/edit/", views.contribution_edit, name="contribution_edit"),
    path("contribution/<int:pk>/delete/", views.contribution_delete, name="contribution_delete"),
]
