from django.urls import path

from . import views

app_name = "advisor"
urlpatterns = [
    path("", views.tips, name="tips"),
    path("simulator/", views.simulator, name="simulator"),
    path("recommendations/", views.recommendations, name="recommendations"),
    path("recommendations/<int:pk>/status/", views.recommendation_status, name="recommendation_status"),
    path("recommendations/<int:pk>/feedback/", views.recommendation_feedback, name="recommendation_feedback"),
]
