from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.category_list, name="list"),
    path("add/", views.category_add, name="add"),
    path("<int:pk>/delete/", views.category_delete, name="delete"),
]
