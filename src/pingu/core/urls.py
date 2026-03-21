from django.urls import path

from pingu.core import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("checks/new/", views.check_create, name="check_create"),
    path("checks/<int:pk>/", views.check_detail, name="check_detail"),
    path("checks/<int:pk>/edit/", views.check_edit, name="check_edit"),
    path("checks/<int:pk>/delete/", views.check_delete, name="check_delete"),
    path("checks/<int:pk>/history/", views.check_history, name="check_history"),
    path("checks/<int:pk>/run/", views.check_run, name="check_run"),
]
