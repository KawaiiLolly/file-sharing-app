from django.shortcuts import render, get_object_or_404
from django.http import FileResponse, HttpResponseForbidden, Http404
from django.contrib.auth.decorators import login_required
from files.models import ServerNode, FileTransfer, File
from policies.engine import PolicyEngine
import os
from django.conf import settings

def categorize_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']: return 'Photo'
    if ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']: return 'Video'
    if ext in ['.pdf', '.doc', '.docx', '.txt', '.xls', '.xlsx', '.ppt', '.pptx', '.csv']: return 'Document'
    if ext in ['.mp3', '.wav', '.aac', '.ogg', '.flac']: return 'Audio'
    if ext in ['.exe', '.dmg', '.apk', '.sh', '.bat', '.msi', '.app']: return 'Application'
    return 'Other'

@login_required
def dashboard_view(request):
    nodes = ServerNode.objects.all()
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    show_all = request.GET.get('all', '') == 'true'
    show_favorites = request.GET.get('favorites', '') == 'true'
    
    # Base query for files
    all_files = File.objects.all().order_by('-created_at')
    
    # Filter by search
    if search_query:
        all_files = all_files.filter(original_name__icontains=search_query)
        
    # Filter favorites
    if show_favorites:
        all_files = all_files.filter(is_favorite=True)
        
    visible_files = [f for f in all_files if PolicyEngine.can_read(request.user, f)]
    
    # Filter by category
    if category_filter:
        visible_files = [f for f in visible_files if categorize_file(f.original_name) == category_filter]
    
    # Top 10 recent files unless 'all' is true
    if show_all:
        recent_shares = visible_files
    else:
        recent_shares = visible_files[:10]
    
    # All transfers for the queue panel (up to 20)
    transfers = FileTransfer.objects.filter(file__in=visible_files).order_by('-updated_at')[:20]
    
    # Compute Categories for UI (based on all readable files, ignoring category filter)
    # This prevents the category cards from disappearing when a category is selected.
    ui_files = [f for f in File.objects.all().order_by('-created_at') if PolicyEngine.can_read(request.user, f)]
    if search_query:
        ui_files = [f for f in ui_files if search_query.lower() in f.original_name.lower()]
    if show_favorites:
        ui_files = [f for f in ui_files if f.is_favorite]
    
    # Compute Categories for UI
    categories = {
        'Photo': {'count': 0, 'size': 0, 'color': '#f06292', 'icon': '🖼️'},
        'Video': {'count': 0, 'size': 0, 'color': '#42a5f5', 'icon': '🎥'},
        'Application': {'count': 0, 'size': 0, 'color': '#29b6f6', 'icon': '💻'},
        'Document': {'count': 0, 'size': 0, 'color': '#ffca28', 'icon': '📄'},
        'Audio': {'count': 0, 'size': 0, 'color': '#ef5350', 'icon': '🎵'},
        'Other': {'count': 0, 'size': 0, 'color': '#9e9e9e', 'icon': '📁'}
    }
    
    total_size = 0
    for f in ui_files:
        cat = categorize_file(f.original_name)
        categories[cat]['count'] += 1
        categories[cat]['size'] += f.size
        total_size += f.size
        
    # Calculate percentages for the progress bar
    for cat, data in categories.items():
        data['percentage'] = (data['size'] / total_size * 100) if total_size > 0 else 0
        
    # Sort categories by size descending for the cards
    sorted_categories = sorted(categories.items(), key=lambda x: x[1]['size'], reverse=True)
    
    context = {
        'nodes': nodes,
        'recent_shares': recent_shares,
        'transfers': transfers,
        'search_query': search_query,
        'categories': categories,
        'sorted_categories': sorted_categories,
        'total_size': total_size,
        'category_filter': category_filter,
        'show_all': show_all,
        'show_favorites': show_favorites
    }
    return render(request, 'dashboard/index.html', context)

@login_required
def toggle_favorite_view(request, file_id):
    from django.http import JsonResponse
    file_obj = get_object_or_404(File, id=file_id)
    if not PolicyEngine.can_read(request.user, file_obj):
        return JsonResponse({"status": "error", "message": "Permission denied."}, status=403)
        
    file_obj.is_favorite = not file_obj.is_favorite
    file_obj.save()
    
    return JsonResponse({"status": "success", "is_favorite": file_obj.is_favorite})

@login_required
def file_download_view(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    
    if not PolicyEngine.can_read(request.user, file_obj):
        return HttpResponseForbidden("You do not have permission to download this file.")
        
    file_path = os.path.join(settings.UPLOADS_DIR, file_obj.stored_name)
    
    if not os.path.exists(file_path):
        raise Http404("File not found on server storage.")
        
    response = FileResponse(open(file_path, 'rb'), as_attachment=True, filename=file_obj.original_name)
    return response

@login_required
def file_preview_view(request, file_id):
    file_obj = get_object_or_404(File, id=file_id)
    
    if not PolicyEngine.can_read(request.user, file_obj):
        return HttpResponseForbidden("You do not have permission to view this file.")
        
    file_path = os.path.join(settings.UPLOADS_DIR, file_obj.stored_name)
    
    if not os.path.exists(file_path):
        raise Http404("File not found on server storage.")
        
    return FileResponse(open(file_path, 'rb'))

@login_required
def api_upload_init(request):
    from django.http import JsonResponse
    from bridge.ipc import DjangoBridge
    from asgiref.sync import async_to_sync
    import json
    import os

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filename = data.get('filename')
            file_size = data.get('file_size')
            visibility = data.get('visibility', File.Visibility.PRIVATE)

            resp = async_to_sync(DjangoBridge.initialize_upload)(
                request.user.username, filename, file_size, visibility
            )
            
            if "error" in resp:
                return JsonResponse(resp, status=400)
                
            file_id = resp["file_id"]
            stored_name = resp["stored_name"]
            
            # Immediately create or update the transfer state so that it is persisted
            # and can be found by initialize_upload if the server crashes.
            async_to_sync(DjangoBridge.update_transfer_state)(
                file_id, request.user.username, 'TRANSFERRING', 0
            )
            
            file_path = os.path.join(settings.UPLOADS_DIR, stored_name)
            uploaded_bytes = 0
            if os.path.exists(file_path):
                uploaded_bytes = os.path.getsize(file_path)
                
            return JsonResponse({
                "status": "success",
                "file_id": file_id,
                "uploaded_bytes": uploaded_bytes
            })
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
    return JsonResponse({"status": "error", "message": "Invalid method."}, status=405)

@login_required
def api_upload_chunk(request):
    from django.http import JsonResponse
    import os
    
    if request.method == 'POST':
        file_id = request.POST.get('file_id')
        offset = int(request.POST.get('offset', 0))
        chunk = request.FILES.get('chunk')
        
        if not file_id or chunk is None:
            return JsonResponse({"status": "error", "message": "Missing file_id or chunk data"}, status=400)
            
        file_obj = get_object_or_404(File, id=file_id, owner=request.user)
        file_path = os.path.join(settings.UPLOADS_DIR, file_obj.stored_name)
        
        mode = 'r+b' if os.path.exists(file_path) else 'w+b'
        with open(file_path, mode) as f:
            f.seek(offset)
            f.write(chunk.read())
            
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "message": "Invalid method."}, status=405)

@login_required
def api_upload_finalize(request):
    from django.http import JsonResponse
    from bridge.ipc import DjangoBridge
    from asgiref.sync import async_to_sync
    import json
    import os
    import hashlib
    
    if request.method == 'POST':
        data = json.loads(request.body)
        file_id = data.get('file_id')
        
        if not file_id:
            return JsonResponse({"status": "error", "message": "Missing file_id"}, status=400)
            
        file_obj = get_object_or_404(File, id=file_id, owner=request.user)
        file_path = os.path.join(settings.UPLOADS_DIR, file_obj.stored_name)
        
        if not os.path.exists(file_path):
            return JsonResponse({"status": "error", "message": "File not found on server"}, status=404)
            
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096 * 1024), b""):
                hasher.update(chunk)
                
        async_to_sync(DjangoBridge.update_transfer_state)(
            file_id, request.user.username, 'COMPLETE', file_obj.size
        )
        async_to_sync(DjangoBridge.finalize_upload)(
            file_id, hasher.hexdigest()
        )
        
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "message": "Invalid method."}, status=405)
