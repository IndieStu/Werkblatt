from django.urls import path

from .views import workshop_list

urlpatterns = [path("", workshop_list, name="workshop-list")]
