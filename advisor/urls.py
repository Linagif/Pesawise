from django.urls import path

from . import views

app_name = "advisor"
urlpatterns = [path("", views.tips, name="tips")]
