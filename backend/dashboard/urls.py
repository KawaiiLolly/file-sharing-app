from django.urls import path
from .views import dashboard_view, file_download_view, file_preview_view, api_upload_init, api_upload_chunk, api_upload_finalize, toggle_favorite_view

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('download/<int:file_id>/', file_download_view, name='download_file'),
    path('preview/<int:file_id>/', file_preview_view, name='file_preview'),
    path('api/upload/init/', api_upload_init, name='api_upload_init'),
    path('api/upload/chunk/', api_upload_chunk, name='api_upload_chunk'),
    path('api/upload/finalize/', api_upload_finalize, name='api_upload_finalize'),
    path('toggle_favorite/<int:file_id>/', toggle_favorite_view, name='toggle_favorite'),
]
