from django.urls import path

from . import views

app_name = "imports"
urlpatterns = [
    path("", views.paste, name="paste"),
    path("review/", views.review, name="review"),
    path("discard/", views.discard, name="discard"),
]
