
        // ==========================================
        // UI Enhancements (Drag & Drop)
        // ==========================================
        const dropzone = document.getElementById('dropzone');
        const fileInput = document.getElementById('fileInput');

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.style.borderColor = "var(--accent)", false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.style.borderColor = "#444", false);
        });

        dropzone.addEventListener('drop', function (e) {
            let dt = e.dataTransfer;
            let files = dt.files;
            fileInput.files = files; // Assign files to input
            if (files.length > 0) {
                document.querySelector('.dropzone-text').innerText = `${files.length} file(s) selected`;
            }
        });

        fileInput.addEventListener('change', function () {
            if (this.files.length > 0) {
                document.querySelector('.dropzone-text').innerText = `${this.files.length} file(s) selected`;
            }
        });

        // ==========================================
        // UPLOAD LOGIC (With Cancel/Rollback)
        // ==========================================
        let activeUploads = {};
        
        document.getElementById('uploadForm').addEventListener('submit', async function (e) {
            e.preventDefault();
            const form = this;
            const submitBtn = document.getElementById('uploadBtn');
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const visibility = form.querySelector('[name=visibility]').value;
            
            const fileInput = document.getElementById('fileInput');
            const folderInput = document.getElementById('folderInput');
            const files = fileInput.files.length > 0 ? fileInput.files : folderInput.files;
            
            if (files.length === 0) {
                alert("Please select files to upload");
                return;
            }
            
            submitBtn.disabled = true;
            submitBtn.style.opacity = '0.5';
            
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                await startChunkedUpload(file, visibility, csrfToken);
            }
            
            form.reset();
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
            document.querySelector('.dropzone-text').innerText = "Drag and drop file to upload";
        });
        
        async function startChunkedUpload(file, visibility, csrfToken) {
            document.getElementById('uploadProgressContainer').style.display = 'block';
            const progressContainer = document.getElementById('uploadProgressContainer');
            
            // UI elements
            const fileNameEl = document.getElementById('uploadingFileName');
            const percentEl = document.getElementById('uploadPercent');
            const progressBar = document.getElementById('uploadProgressBar');
            const cancelBtn = document.getElementById('cancelUploadBtn');
            
            fileNameEl.textContent = file.name;
            percentEl.textContent = "0%";
            progressBar.style.width = "0%";
            
            try {
                // Initialize
                const initRes = await fetch('/api/upload/init/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({
                        filename: file.name,
                        file_size: file.size,
                        visibility: visibility
                    })
                });
                
                const initData = await initRes.json();
                if (initData.status !== 'success') throw new Error(initData.message);
                
                const fileId = initData.file_id;
                let uploadedBytes = initData.uploaded_bytes || 0;
                
                const controller = new AbortController();
                activeUploads[fileId] = { controller: controller, paused: false };
                
                cancelBtn.onclick = () => {
                    if (activeUploads[fileId]) {
                        activeUploads[fileId].controller.abort();
                        activeUploads[fileId].paused = true;
                        fileNameEl.textContent = "Upload Paused";
                    }
                };
                
                const chunkSize = 5 * 1024 * 1024;
                
                while (uploadedBytes < file.size && !activeUploads[fileId].paused) {
                    const chunk = file.slice(uploadedBytes, uploadedBytes + chunkSize);
                    const formData = new FormData();
                    formData.append('file_id', fileId);
                    formData.append('offset', uploadedBytes);
                    formData.append('chunk', chunk);
                    
                    const chunkRes = await fetch('/api/upload/chunk/', {
                        method: 'POST',
                        headers: { 'X-CSRFToken': csrfToken },
                        body: formData,
                        signal: activeUploads[fileId].controller.signal
                    });
                    
                    if (!chunkRes.ok) throw new Error("Chunk upload failed");
                    
                    uploadedBytes += chunk.size;
                    const percent = Math.round((uploadedBytes / file.size) * 100);
                    progressBar.style.width = percent + '%';
                    percentEl.textContent = percent + '%';
                }
                
                if (uploadedBytes >= file.size && !activeUploads[fileId].paused) {
                    percentEl.textContent = "Finalizing...";
                    const finRes = await fetch('/api/upload/finalize/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({ file_id: fileId })
                    });
                    const finData = await finRes.json();
                    if (finData.status === 'success') {
                        percentEl.textContent = "Done!";
                        setTimeout(() => window.location.reload(), 1000);
                    } else {
                        throw new Error(finData.message);
                    }
                }
            } catch (e) {
                if (e.name === 'AbortError') {
                    console.log('Upload aborted/paused');
                } else {
                    alert("Upload error: " + e.message);
                    percentEl.textContent = "Error";
                }
            }
        }

        // ==========================================
        // DOWNLOAD MANAGER LOGIC (IndexedDB & Chunks)
        // ==========================================
        const DB_NAME = 'DownloadManagerDB';
        const DB_VERSION = 1;
        const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
        let db;
        const activeDownloads = {};

        const requestDB = indexedDB.open(DB_NAME, DB_VERSION);
        requestDB.onupgradeneeded = function (e) {
            db = e.target.result;
            if (!db.objectStoreNames.contains('chunks')) db.createObjectStore('chunks', { keyPath: ['fileId', 'chunkIndex'] });
            if (!db.objectStoreNames.contains('metadata')) db.createObjectStore('metadata', { keyPath: 'fileId' });
        };
        requestDB.onsuccess = function (e) {
            db = e.target.result;
            loadPendingDownloads();
        };

        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }

        function loadPendingDownloads() {
            const tx = db.transaction('metadata', 'readonly');
            const req = tx.objectStore('metadata').getAll();
            req.onsuccess = (e) => {
                const metas = e.target.result;
                if (metas.length > 0) {
                    document.getElementById('downloadsCard').style.display = 'block';
                    for (const meta of metas) {
                        meta.status = 'paused';
                        saveMetadata(meta);
                        renderDownloadUI(meta.fileId, meta.fileName, meta.fileSize, meta.downloadedBytes);
                        updateDownloadUIStatus(meta.fileId, 'paused');
                    }
                }
            };
        }

        async function startDownload(fileId, fileName, fileSize) {
            document.getElementById('downloadsCard').style.display = 'block';
            await saveMetadata({ fileId, fileName, fileSize, downloadedBytes: 0, status: 'downloading' });
            renderDownloadUI(fileId, fileName, fileSize, 0);
            resumeDownload(fileId);
        }

        async function resumeDownload(fileId) {
            const meta = await getMetadata(fileId);
            if (!meta) return;

            meta.status = 'downloading';
            await saveMetadata(meta);
            updateDownloadUIStatus(fileId, 'downloading');

            activeDownloads[fileId] = { paused: false, controller: new AbortController() };
            let downloadedBytes = meta.downloadedBytes || 0;
            let chunkIndex = Math.floor(downloadedBytes / CHUNK_SIZE);

            while (downloadedBytes < meta.fileSize && !activeDownloads[fileId].paused) {
                const start = downloadedBytes;
                const end = Math.min(start + CHUNK_SIZE - 1, meta.fileSize - 1);

                try {
                    const response = await fetch(`/download/${fileId}/`, {
                        headers: { 'Range': `bytes=${start}-${end}` },
                        signal: activeDownloads[fileId].controller.signal
                    });

                    if (!response.ok && response.status !== 206) throw new Error('Fetch failed');

                    const blob = await response.blob();
                    await saveChunk(fileId, chunkIndex, blob);

                    downloadedBytes += blob.size;
                    chunkIndex++;

                    meta.downloadedBytes = downloadedBytes;
                    await saveMetadata(meta);
                    updateDownloadProgress(fileId, downloadedBytes, meta.fileSize);
                } catch (err) {
                    if (err.name === 'AbortError') break;
                    else {
                        console.error(err);
                        meta.status = 'error';
                        await saveMetadata(meta);
                        updateDownloadUIStatus(fileId, 'error');
                        break;
                    }
                }
            }

            if (downloadedBytes >= meta.fileSize && !activeDownloads[fileId]?.paused) {
                meta.status = 'completed';
                await saveMetadata(meta);
                updateDownloadUIStatus(fileId, 'completed');
                await stitchAndSave(fileId, meta.fileName, meta.fileSize);
            }
        }

        function pauseDownload(fileId) {
            if (activeDownloads[fileId]) {
                activeDownloads[fileId].paused = true;
                activeDownloads[fileId].controller.abort();
            }
            getMetadata(fileId).then(meta => {
                if (meta && meta.status !== 'completed') {
                    meta.status = 'paused';
                    saveMetadata(meta);
                    updateDownloadUIStatus(fileId, 'paused');
                }
            });
        }

        async function cancelDownload(fileId) {
            if (activeDownloads[fileId]) {
                activeDownloads[fileId].paused = true;
                activeDownloads[fileId].controller.abort();
            }
            await deleteDownloadData(fileId);
            const el = document.getElementById(`dl-${fileId}`);
            if (el) el.remove();

            const container = document.getElementById('downloadsContainer');
            if (container.children.length === 0) document.getElementById('downloadsCard').style.display = 'none';
        }

        async function stitchAndSave(fileId, fileName, fileSize) {
            const chunks = [];
            const totalChunks = Math.ceil(fileSize / CHUNK_SIZE);
            for (let i = 0; i < totalChunks; i++) {
                const chunk = await getChunk(fileId, i);
                if (chunk) chunks.push(chunk);
            }

            const finalBlob = new Blob(chunks);
            const url = URL.createObjectURL(finalBlob);

            const a = document.createElement('a');
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            URL.revokeObjectURL(url);
            await deleteDownloadData(fileId);

            const el = document.getElementById(`dl-${fileId}`);
            if (el) {
                el.innerHTML = `<div style="padding: 10px; font-size: 13px; background-color: rgba(76, 175, 80, 0.1); color: #4caf50; border-radius: 4px; border: 1px solid #4caf50;"><strong>${fileName}</strong> Complete!</div>`;
                setTimeout(() => {
                    el.remove();
                    if (document.getElementById('downloadsContainer').children.length === 0) document.getElementById('downloadsCard').style.display = 'none';
                }, 5000);
            }
        }

        function saveMetadata(meta) { return new Promise(resolve => { const tx = db.transaction('metadata', 'readwrite'); tx.objectStore('metadata').put(meta); tx.oncomplete = resolve; }); }
        function getMetadata(fileId) { return new Promise(resolve => { const tx = db.transaction('metadata', 'readonly'); const req = tx.objectStore('metadata').get(fileId); req.onsuccess = () => resolve(req.result); req.onerror = () => resolve(null); }); }
        function saveChunk(fileId, chunkIndex, blob) { return new Promise(resolve => { const tx = db.transaction('chunks', 'readwrite'); tx.objectStore('chunks').put({ fileId, chunkIndex, blob }); tx.oncomplete = resolve; }); }
        function getChunk(fileId, chunkIndex) { return new Promise(resolve => { const tx = db.transaction('chunks', 'readonly'); const req = tx.objectStore('chunks').get([fileId, chunkIndex]); req.onsuccess = () => resolve(req.result ? req.result.blob : null); req.onerror = () => resolve(null); }); }
        function deleteDownloadData(fileId) { return new Promise(resolve => { const tx = db.transaction(['metadata', 'chunks'], 'readwrite'); tx.objectStore('metadata').delete(fileId); const cursorReq = tx.objectStore('chunks').openCursor(); cursorReq.onsuccess = e => { const cursor = e.target.result; if (cursor) { if (cursor.value.fileId === fileId) cursor.delete(); cursor.continue(); } else resolve(); }; }); }

        function renderDownloadUI(fileId, fileName, fileSize, downloadedBytes) {
            if (document.getElementById(`dl-${fileId}`)) return;
            const container = document.getElementById('downloadsContainer');
            const percent = Math.round((downloadedBytes / fileSize) * 100) || 0;

            const div = document.createElement('div');
            div.id = `dl-${fileId}`;
            div.className = 'file-item';
            div.style.flexDirection = 'column';
            div.style.alignItems = 'stretch';
            div.style.gap = '8px';
            div.style.padding = '12px';
            div.style.border = '1px solid var(--border-color)';

            div.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div class="file-name" style="max-width: 180px;">${fileName}</div>
                    <div style="display: flex; gap: 5px;">
                        <button onclick="resumeDownload('${fileId}')" id="dl-resume-${fileId}" style="display: none; background: #4caf50; color: white; border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; cursor: pointer;">Resume</button>
                        <button onclick="pauseDownload('${fileId}')" id="dl-pause-${fileId}" style="background: #ff9800; color: white; border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; cursor: pointer;">Pause</button>
                        <button onclick="cancelDownload('${fileId}')" style="background: transparent; border: 1px solid #dc3545; color: #dc3545; border-radius: 4px; padding: 4px 8px; font-size: 11px; cursor: pointer;">Cancel</button>
                    </div>
                </div>
                <div class="progress-bar-bg" style="margin-top: 0;">
                    <div id="dl-progress-${fileId}" class="progress-bar-fill" style="width: ${percent}%;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-secondary);">
                    <span id="dl-status-${fileId}">Starting...</span>
                    <span id="dl-text-${fileId}">${formatBytes(downloadedBytes)} / ${formatBytes(fileSize)} (${percent}%)</span>
                </div>
            `;
            container.appendChild(div);
        }

        function updateDownloadProgress(fileId, downloaded, total) {
            const percent = Math.round((downloaded / total) * 100);
            const bar = document.getElementById(`dl-progress-${fileId}`);
            const text = document.getElementById(`dl-text-${fileId}`);
            if (bar) bar.style.width = `${percent}%`;
            if (text) text.textContent = `${formatBytes(downloaded)} / ${formatBytes(total)} (${percent}%)`;
        }

        function updateDownloadUIStatus(fileId, status) {
            const statusText = document.getElementById(`dl-status-${fileId}`);
            const resumeBtn = document.getElementById(`dl-resume-${fileId}`);
            const pauseBtn = document.getElementById(`dl-pause-${fileId}`);
            if (!statusText) return;
            if (status === 'paused' || status === 'error') {
                statusText.textContent = status === 'error' ? 'Error' : 'Paused';
                statusText.style.color = status === 'error' ? '#dc3545' : '#ff9800';
                if (resumeBtn) resumeBtn.style.display = 'inline-block';
                if (pauseBtn) pauseBtn.style.display = 'none';
            } else if (status === 'downloading') {
                statusText.textContent = 'Downloading...';
                statusText.style.color = '#4caf50';
                if (resumeBtn) resumeBtn.style.display = 'none';
                if (pauseBtn) pauseBtn.style.display = 'inline-block';
            } else if (status === 'completed') {
                statusText.textContent = 'Stitching file...';
                statusText.style.color = '#007aff';
                if (resumeBtn) resumeBtn.style.display = 'none';
                if (pauseBtn) pauseBtn.style.display = 'none';
            }
        }

        async function toggleFavorite(fileId, starElement) {
            try {
                const response = await fetch(`/toggle_favorite/${fileId}/`, {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    if (data.status === 'success') {
                        starElement.innerText = data.is_favorite ? '⭐' : '☆';
                    } else {
                        alert(data.message);
                    }
                }
            } catch (e) {
                console.error("Failed to toggle favorite", e);
            }
        }
    