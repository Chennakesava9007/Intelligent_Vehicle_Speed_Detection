from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload_video, name='upload_video'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('results/<int:video_id>/', views.view_results, name='view_results'),
    path('delete/<int:video_id>/', views.delete_video, name='delete_video'),
    path('download_csv/', views.download_csv, name='download_csv'),
    path('download_excel/', views.download_excel, name='download_excel'),
    path('contact/', views.contact, name='contact'),
    path('signup/', views.signup, name='signup'),  # Signup view
]
