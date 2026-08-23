from django.urls import path
from .views import dashboard_view, file_download_view, file_preview_view, web_upload_view, toggle_favorite_view

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('download/<int:file_id>/', file_download_view, name='download_file'),
    path('preview/<int:file_id>/', file_preview_view, name='file_preview'),
    path('upload/', web_upload_view, name='web_upload'),
    path('toggle_favorite/<int:file_id>/', toggle_favorite_view, name='toggle_favorite'),
]
