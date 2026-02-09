from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('edit_row/', views.edit_row, name='edit_row'),
    path('add_row/', views.add_row, name='add_row'),
    path('delete_row/', views.delete_row, name='delete_row'),
]
