import json
import os
import socket
import sys
from pathlib import Path
from urllib.parse import unquote

from flask import Flask, jsonify, render_template_string, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# =========================================================
# CONFIGURATION & FOLDERS
# =========================================================
DEFAULT_FOLDERS = {
    "Downloads": Path.home() / "Downloads",
    "Desktop": Path.home() / "Desktop",
    "Documents": Path.home() / "Documents",
    "Videos": Path.home() / "Videos",
}

CONFIG_FILE = Path(__file__).resolve().parent / "shared_folders.json"


def load_allowed_folders():
    """Load default folders and persistable custom folders for Linux/Windows/macOS."""
    folders = {}
    for name, p in DEFAULT_FOLDERS.items():
        try:
            p.expanduser().mkdir(parents=True, exist_ok=True)
            folders[name] = p.expanduser().resolve()
        except OSError:
            folders[name] = p.expanduser()

    custom_folders = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for name, path_str in saved.items():
                    p = Path(path_str).expanduser()
                    if p.exists() and p.is_dir():
                        resolved = p.resolve()
                        folders[name] = resolved
                        custom_folders[name] = str(resolved)
        except Exception as e:
            print(f"Warning: Could not read {CONFIG_FILE}: {e}")

    return folders, custom_folders


ALLOWED_FOLDERS, CUSTOM_FOLDERS = load_allowed_folders()


def save_custom_folders():
    """Save user-added folders to disk so they persist across restarts."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(CUSTOM_FOLDERS, f, indent=4)
    except Exception as e:
        print(f"Warning: Could not save {CONFIG_FILE}: {e}")


# =========================================================
# HELPERS
# =========================================================
def get_root(folder_key: str) -> Path:
    """Return the configured root folder for a folder key."""
    if folder_key not in ALLOWED_FOLDERS:
        raise ValueError("Invalid folder selection.")
    return ALLOWED_FOLDERS[folder_key].expanduser().resolve()


def safe_path(root: Path, relative_path: str = "") -> Path:
    """Resolve a path and make sure it stays strictly inside root."""
    relative_path = relative_path or ""
    target = (root / relative_path).resolve()

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Invalid path.") from exc

    return target


def relative_posix(root: Path, target: Path) -> str:
    """Return a URL-friendly relative path."""
    return target.relative_to(root).as_posix()


def get_local_ip() -> str:
    """Best-effort local LAN IP detection."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def is_host_request() -> bool:
    """Return True if the request originated from the local host machine."""
    remote_ip = request.remote_addr or ""
    if remote_ip in ("127.0.0.1", "::1", "localhost"):
        return True
    try:
        if remote_ip == get_local_ip():
            return True
    except Exception:
        pass
    return False


# =========================================================
# FRONTEND
# =========================================================
HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Local Transfer</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #f4f6f8;
            color: #222;
        }

        .container {
            width: 100%;
            max-width: 760px;
            margin: 0 auto;
        }

        h1 {
            text-align: center;
            font-size: 26px;
            margin-bottom: 20px;
        }

        .box {
            background: white;
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 18px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
        }

        .host-box {
            border: 2px solid #2563eb;
            background: #f8faff;
        }

        .host-badge {
            background: #dbeafe;
            color: #1e40af;
            font-size: 12px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 999px;
            display: inline-block;
        }

        select,
        input[type="file"],
        input[type="text"],
        button {
            width: 100%;
            padding: 12px;
            margin-top: 10px;
            border-radius: 9px;
            font-size: 15px;
        }

        select,
        input[type="file"],
        input[type="text"] {
            border: 1px solid #ccc;
            background: white;
        }

        button {
            border: none;
            background: #007bff;
            color: white;
            cursor: pointer;
            font-weight: 500;
            transition: opacity 0.2s;
        }

        button:hover {
            opacity: 0.92;
        }

        button:disabled {
            opacity: 0.55;
            cursor: not-allowed;
        }

        .green {
            background: #28a745;
        }

        .blue {
            background: #007bff;
        }

        .danger {
            background: #dc3545;
        }

        .gray {
            background: #6c757d;
        }

        .small-button {
            width: auto;
            padding: 8px 12px;
            margin: 0;
            font-size: 14px;
        }

        .toolbar {
            display: flex;
            gap: 8px;
            align-items: center;
            margin-top: 12px;
            flex-wrap: wrap;
        }

        .toolbar button {
            width: auto;
            margin-top: 0;
        }

        #currentPath {
            margin-top: 12px;
            padding: 10px;
            border-radius: 8px;
            background: #f0f2f5;
            word-break: break-all;
            font-family: monospace;
        }

        #fileList {
            max-height: 350px;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 6px;
            scroll-behavior: smooth;
        }

        #fileList::-webkit-scrollbar {
            width: 8px;
        }

        #fileList::-webkit-scrollbar-thumb {
            background: #b5b5b5;
            border-radius: 10px;
        }

        #fileList::-webkit-scrollbar-track {
            background: #f1f1f1;
        }

        @media (max-width: 600px) {
            #fileList {
                max-height: 300px;
            }
        }

        .entry {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 12px 4px;
            border-bottom: 1px solid #eee;
        }

        .entry:last-child {
            border-bottom: none;
        }

        .entry-main {
            min-width: 0;
            flex: 1;
        }

        .entry-name {
            font-weight: 600;
            word-break: break-word;
        }

        .entry-meta {
            color: #666;
            font-size: 13px;
            margin-top: 4px;
        }

        .entry-actions {
            flex: 0 0 auto;
        }

        .entry-actions button {
            margin: 0;
            width: auto;
            padding: 8px 12px;
        }

        progress {
            width: 100%;
            height: 24px;
            margin-top: 12px;
        }

        .percentage {
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            margin-top: 8px;
        }

        .stats {
            margin-top: 12px;
            background: #f7f7f7;
            padding: 12px;
            border-radius: 9px;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 6px 0;
            border-bottom: 1px solid #e6e6e6;
        }

        .stat-row:last-child {
            border-bottom: none;
        }

        .stat-row span:last-child {
            text-align: right;
            word-break: break-word;
        }

        .status {
            margin-top: 12px;
            text-align: center;
            font-weight: bold;
        }

        .muted {
            color: #666;
            font-size: 13px;
        }

        .error {
            color: #b00020;
        }

        .success {
            color: #16803a;
        }

        /* Modal styling */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.55);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 14px;
        }

        .modal-card {
            background: white;
            border-radius: 14px;
            width: 100%;
            max-width: 600px;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 10px 25px rgba(0,0,0,0.25);
            overflow: hidden;
        }

        .modal-header {
            padding: 16px;
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .modal-close {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #666;
            width: auto;
            margin: 0;
            padding: 0 6px;
        }

        .modal-body {
            padding: 16px;
            overflow-y: auto;
        }

        .fs-path-bar {
            padding: 8px 12px;
            background: #f1f5f9;
            border-radius: 8px;
            font-family: monospace;
            font-size: 13px;
            word-break: break-all;
        }

        .fs-dir-list {
            max-height: 300px;
            overflow-y: auto;
            margin-top: 10px;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
        }

        .fs-dir-item {
            padding: 10px 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            border-bottom: 1px solid #f1f5f9;
        }

        .fs-dir-item:hover {
            background: #f8fafc;
        }

        .fs-dir-item:last-child {
            border-bottom: none;
        }
    </style>
</head>
<body>
<div class="container">
    <h1>Python Local Transfer</h1>

    <div class="box">
        <h3>Send Text Message</h3>
        <input type="text" id="msgInput" placeholder="Type a message...">
        <button onclick="sendMessage()">Send Message</button>
    </div>

    {% if is_host %}
    <div class="box host-box">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <h3 style="margin:0; color:#1e40af;">💻 Manage Allowed Folders (Host Only)</h3>
            <span class="host-badge">Host Laptop/Server</span>
        </div>
        <div class="muted" style="margin-top:6px;">
            Add any folder from this machine (Linux / Windows / macOS) to share with connected devices on your network.
        </div>

        <div style="margin-top:12px;">
            <div style="display:flex; gap:8px; flex-wrap:wrap;">
                <input type="text" id="newFolderName" placeholder="Folder Nickname (e.g. Movies)" style="flex:1; min-width:160px; margin-top:0;">
                <input type="text" id="newFolderPath" placeholder="Full Directory Path (e.g. /media/movies or D:\Movies)" style="flex:2; min-width:240px; margin-top:0;">
            </div>
            <div class="toolbar" style="margin-top:8px;">
                <button type="button" class="blue" onclick="addAllowedFolder()">➕ Add Shared Folder</button>
                <button type="button" class="gray" onclick="openFsModal()">📂 Browse Filesystem</button>
                <button type="button" class="gray" id="btnNativePicker" onclick="tryNativePicker()" title="Try OS GUI file picker">🖥️ System Dialog</button>
            </div>
        </div>

        <div id="customFoldersList" style="margin-top:14px;"></div>
    </div>
    {% endif %}

    <div class="box">
        <h3>1. Choose Laptop Folder</h3>

        <select id="folderSelect"></select>

        <div class="toolbar">
            <button class="gray" onclick="goParent()">⬅ Parent Folder</button>
            <button class="gray" onclick="refreshFiles()">⟳ Refresh</button>
        </div>

        <div id="currentPath">/</div>
    </div>

    <div class="box">
        <h3>2. Upload to Laptop</h3>
        <div class="muted">Items will be saved into the folder currently open above.</div>

        <div class="toolbar" style="margin-top:10px;">
            <input type="file" id="uploadFilesInput" multiple style="display:none;" onchange="onFilesSelected(this)">
            <input type="file" id="uploadFolderInput" webkitdirectory directory multiple style="display:none;" onchange="onFolderSelected(this)">

            <button type="button" class="green" onclick="document.getElementById('uploadFilesInput').click()" style="flex:1; min-width:140px; margin-top:0;">
                📄 Upload File(s)
            </button>
            <button type="button" class="blue" onclick="document.getElementById('uploadFolderInput').click()" style="flex:1; min-width:140px; margin-top:0;">
                📁 Upload Folder
            </button>
        </div>

        <div id="selectedUploadInfo" style="display:none; margin-top:12px; padding:12px; background:#eef4fb; border-radius:8px;">
            <div id="selectedCountText" style="font-weight:600; color:#1e3a8a;"></div>
            <div class="toolbar" style="margin-top:10px;">
                <button id="uploadStartButton" class="green small-button" onclick="startBatchUpload()">Start Upload</button>
                <button id="uploadCancelButton" class="danger small-button" onclick="cancelBatchUpload()">Cancel</button>
            </div>
        </div>
    </div>

    <div class="box">
        <h3>3. Laptop Files</h3>
        <div id="fileList">Loading...</div>
    </div>

    <div class="box" id="progressBox" style="display:none;">
        <h3 id="operationTitle">Transfer Status</h3>

        <progress id="progressBar" value="0" max="100"></progress>
        <div id="percentageText" class="percentage">0%</div>

        <div class="stats">
            <div class="stat-row">
                <span>Transferred</span>
                <span id="transferredText">0 B / 0 B</span>
            </div>

            <div class="stat-row">
                <span>Speed</span>
                <span id="speedText">-</span>
            </div>

            <div class="stat-row">
                <span>Elapsed</span>
                <span id="elapsedText">0 sec</span>
            </div>

            <div class="stat-row">
                <span>Remaining</span>
                <span id="etaText">-</span>
            </div>
        </div>

        <div id="statusText" class="status">Preparing...</div>
    </div>
</div>

<!-- Host Web Filesystem Browser Modal -->
<div id="fsModal" class="modal-overlay" style="display:none;">
    <div class="modal-card">
        <div class="modal-header">
            <h3 style="margin:0;">📂 Select Server Directory</h3>
            <button class="modal-close" onclick="closeFsModal()">&times;</button>
        </div>
        <div class="modal-body">
            <div id="fsCurrentPath" class="fs-path-bar">/</div>
            <div class="toolbar" style="margin: 10px 0;">
                <button class="gray small-button" onclick="fsGoParent()">⬆️ Parent Directory</button>
                <button class="green small-button" onclick="fsSelectCurrent()">✅ Select This Folder</button>
            </div>
            <div id="fsDirList" class="fs-dir-list">Loading directories...</div>
        </div>
    </div>
</div>

<script>
    let currentFolderKey = "";
    let currentPath = "";

    // Upload queue state
    let uploadQueue = [];
    let currentXHR = null;
    let isUploading = false;

    function formatBytes(bytes) {
        if (!Number.isFinite(bytes) || bytes < 0) return "-";
        if (bytes === 0) return "0 B";

        const units = ["B", "KB", "MB", "GB", "TB"];
        const base = 1024;
        const index = Math.min(
            Math.floor(Math.log(bytes) / Math.log(base)),
            units.length - 1
        );

        const value = bytes / Math.pow(base, index);
        return value.toFixed(index === 0 ? 0 : 2) + " " + units[index];
    }

    function formatTime(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) return "Calculating...";
        if (seconds < 1) return "< 1 sec";

        seconds = Math.ceil(seconds);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        if (hours > 0) return `${hours}h ${minutes}m ${secs}s`;
        if (minutes > 0) return `${minutes}m ${secs}s`;
        return `${secs} sec`;
    }

    function resetProgress(title) {
        document.getElementById("progressBox").style.display = "block";
        document.getElementById("operationTitle").textContent = title;
        document.getElementById("progressBar").value = 0;
        document.getElementById("percentageText").textContent = "0%";
        document.getElementById("transferredText").textContent = "0 B / 0 B";
        document.getElementById("speedText").textContent = "Calculating...";
        document.getElementById("elapsedText").textContent = "0 sec";
        document.getElementById("etaText").textContent = "Calculating...";
        document.getElementById("statusText").textContent = "Preparing...";
        document.getElementById("statusText").className = "status";
    }

    function setProgress(loaded, total, speed, elapsedSeconds) {
        const progressBar = document.getElementById("progressBar");
        const percentageText = document.getElementById("percentageText");
        const transferredText = document.getElementById("transferredText");
        const speedText = document.getElementById("speedText");
        const elapsedText = document.getElementById("elapsedText");
        const etaText = document.getElementById("etaText");

        if (total > 0) {
            const percent = Math.min(100, (loaded / total) * 100);
            progressBar.value = percent;
            percentageText.textContent = percent.toFixed(1) + "%";
            transferredText.textContent = `${formatBytes(loaded)} / ${formatBytes(total)}`;

            if (speed > 0) {
                const remainingBytes = Math.max(0, total - loaded);
                etaText.textContent = formatTime(remainingBytes / speed) + " (estimate)";
            }
        } else {
            progressBar.removeAttribute("value");
            percentageText.textContent = "...";
            transferredText.textContent = formatBytes(loaded);
            etaText.textContent = "Unknown";
        }

        speedText.textContent = speed > 0 ? `${formatBytes(speed)}/s` : "Calculating...";
        elapsedText.textContent = formatTime(elapsedSeconds);
    }

    async function sendMessage() {
        const input = document.getElementById("msgInput");
        const message = input.value.trim();

        if (!message) {
            alert("Please type a message first.");
            return;
        }

        try {
            const response = await fetch("/api/message", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({message})
            });

            const data = await response.json();
            alert(data.text || "Message sent.");

            if (response.ok && data.success) {
                input.value = "";
            }
        } catch (error) {
            alert(`Message failed: ${error.message}`);
        }
    }

    async function loadFolderChoices() {
        const select = document.getElementById("folderSelect");

        try {
            const response = await fetch("/api/folders");
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.text || "Unable to load folders.");
            }

            select.innerHTML = "";

            data.folders.forEach((folderName) => {
                const option = document.createElement("option");
                option.value = folderName;
                option.textContent = folderName;
                select.appendChild(option);
            });

            // If host, render custom folders list
            if (data.is_host && data.details) {
                const customList = document.getElementById("customFoldersList");
                if (customList) {
                    customList.innerHTML = '<div style="font-size:13px; font-weight:600; margin-bottom:8px; color:#334155;">Active Shared Folders:</div>';
                    data.details.forEach(f => {
                        const row = document.createElement("div");
                        row.style.cssText = "display:flex; justify-content:space-between; align-items:center; padding:7px 0; border-bottom:1px solid #e2e8f0; font-size:13px;";
                        row.innerHTML = `
                            <div style="min-width:0; flex:1; padding-right:8px;">
                                <strong>📁 ${f.name}</strong> <span class="muted" style="margin-left:6px; font-family:monospace; word-break:break-all;">${f.path}</span>
                            </div>
                            <div>
                                ${f.is_custom ? `<button type="button" class="small-button danger" onclick="removeAllowedFolder('${f.name}')">Remove</button>` : `<span class="muted" style="font-size:12px;">Default</span>`}
                            </div>
                        `;
                        customList.appendChild(row);
                    });
                }
            }

            if (data.folders.length === 0) {
                document.getElementById("fileList").textContent = "No folders configured.";
                return;
            }

            if (!currentFolderKey || !data.folders.includes(currentFolderKey)) {
                currentFolderKey = data.folders[0];
                currentPath = "";
            }

            select.value = currentFolderKey;

            select.onchange = () => {
                currentFolderKey = select.value;
                currentPath = "";
                refreshFiles();
            };

            await refreshFiles();

        } catch (error) {
            document.getElementById("fileList").innerHTML = "";
            const div = document.createElement("div");
            div.className = "error";
            div.textContent = error.message;
            document.getElementById("fileList").appendChild(div);
        }
    }

    async function refreshFiles() {
        if (!currentFolderKey) return;

        const fileList = document.getElementById("fileList");
        fileList.textContent = "Loading...";

        const params = new URLSearchParams({
            folder: currentFolderKey,
            path: currentPath
        });

        try {
            const response = await fetch(`/api/list?${params.toString()}`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.text || "Unable to read folder.");
            }

            currentPath = data.path;
            document.getElementById("currentPath").textContent =
                `${currentFolderKey}: /${currentPath}`;

            renderEntries(data.entries);

        } catch (error) {
            fileList.innerHTML = "";
            const div = document.createElement("div");
            div.className = "error";
            div.textContent = error.message;
            fileList.appendChild(div);
        }
    }

    function renderEntries(entries) {
        const fileList = document.getElementById("fileList");
        fileList.innerHTML = "";

        if (!entries.length) {
            const empty = document.createElement("div");
            empty.className = "muted";
            empty.textContent = "This folder is empty.";
            fileList.appendChild(empty);
            return;
        }

        for (const item of entries) {
            const row = document.createElement("div");
            row.className = "entry";

            const main = document.createElement("div");
            main.className = "entry-main";

            const name = document.createElement("div");
            name.className = "entry-name";
            name.textContent = item.type === "folder" ? `📁 ${item.name}` : `📄 ${item.name}`;
            main.appendChild(name);

            const meta = document.createElement("div");
            meta.className = "entry-meta";
            meta.textContent = item.type === "folder" ? "Folder" : formatBytes(item.size);
            main.appendChild(meta);

            const actions = document.createElement("div");
            actions.className = "entry-actions";

            const actionButton = document.createElement("button");
            actionButton.className = "small-button";

            if (item.type === "folder") {
                actionButton.textContent = "Open";
                actionButton.onclick = () => {
                    currentPath = item.path;
                    refreshFiles();
                };
            } else {
                actionButton.textContent = "Download";
                actionButton.onclick = () => downloadFile(item.path, item.name);
            }

            actions.appendChild(actionButton);
            row.appendChild(main);
            row.appendChild(actions);
            fileList.appendChild(row);
        }
    }

    function goParent() {
        if (!currentPath) return;

        const parts = currentPath.split("/").filter(Boolean);
        parts.pop();
        currentPath = parts.join("/");
        refreshFiles();
    }

    // =========================================================
    // MULTI-FILE & FOLDER UPLOADS
    // =========================================================
    function onFilesSelected(input) {
        if (!input.files || input.files.length === 0) return;
        uploadQueue = Array.from(input.files);
        showUploadSummary(false);
    }

    function onFolderSelected(input) {
        if (!input.files || input.files.length === 0) return;
        uploadQueue = Array.from(input.files);
        showUploadSummary(true);
    }

    function showUploadSummary(isFolder) {
        const summaryBox = document.getElementById("selectedUploadInfo");
        const countText = document.getElementById("selectedCountText");
        const totalBytes = uploadQueue.reduce((acc, f) => acc + f.size, 0);

        if (uploadQueue.length === 0) {
            summaryBox.style.display = "none";
            return;
        }

        if (isFolder) {
            const firstRel = uploadQueue[0].webkitRelativePath || "";
            const topFolder = firstRel.split("/")[0] || "Folder";
            countText.textContent = `📁 Folder "${topFolder}": ${uploadQueue.length} files (${formatBytes(totalBytes)}) ready to upload.`;
        } else {
            countText.textContent = `📄 ${uploadQueue.length} file(s) selected (${formatBytes(totalBytes)}) ready to upload.`;
        }

        summaryBox.style.display = "block";
    }

    function cancelBatchUpload() {
        if (isUploading) {
            if (currentXHR) {
                currentXHR.abort();
            }
            isUploading = false;
            document.getElementById("statusText").textContent = "Upload cancelled.";
            document.getElementById("statusText").className = "status error";
        }
        uploadQueue = [];
        document.getElementById("uploadFilesInput").value = "";
        document.getElementById("uploadFolderInput").value = "";
        document.getElementById("selectedUploadInfo").style.display = "none";
    }

    async function startBatchUpload() {
        if (!uploadQueue.length) {
            alert("Please select files or a folder first.");
            return;
        }

        if (!currentFolderKey) {
            alert("Please select a target folder first.");
            return;
        }

        isUploading = true;
        document.getElementById("uploadStartButton").disabled = true;
        document.getElementById("selectedUploadInfo").style.display = "none";

        const totalBatchBytes = uploadQueue.reduce((acc, f) => acc + f.size, 0);
        let completedBytes = 0;
        const batchStartTime = performance.now();
        let smoothedSpeed = 0;
        let lastTime = batchStartTime;
        let lastLoadedTotal = 0;

        resetProgress(`Uploading ${uploadQueue.length} item(s)...`);

        for (let i = 0; i < uploadQueue.length; i++) {
            if (!isUploading) break;

            const file = uploadQueue[i];
            const relativeFilePath = file.webkitRelativePath || "";

            document.getElementById("operationTitle").textContent =
                `Uploading (${i + 1}/${uploadQueue.length}): ${file.name}`;
            document.getElementById("statusText").textContent =
                `Transferring ${file.name}...`;

            const params = new URLSearchParams({
                folder: currentFolderKey,
                path: currentPath
            });

            const uploadSuccess = await new Promise((resolve) => {
                const xhr = new XMLHttpRequest();
                currentXHR = xhr;

                xhr.open("POST", `/api/upload?${params.toString()}`, true);
                xhr.setRequestHeader("Content-Type", "application/octet-stream");
                xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));
                if (relativeFilePath) {
                    xhr.setRequestHeader("X-Relative-Path", encodeURIComponent(relativeFilePath));
                }

                xhr.upload.onprogress = (event) => {
                    const now = performance.now();
                    const currentFileLoaded = event.loaded;
                    const overallLoaded = completedBytes + currentFileLoaded;
                    const elapsedSeconds = (now - batchStartTime) / 1000;
                    const deltaSeconds = (now - lastTime) / 1000;

                    if (deltaSeconds >= 0.2) {
                        const deltaBytes = overallLoaded - lastLoadedTotal;
                        const instantSpeed = deltaBytes / deltaSeconds;
                        if (instantSpeed > 0) {
                            smoothedSpeed = smoothedSpeed === 0 ? instantSpeed : (smoothedSpeed * 0.75) + (instantSpeed * 0.25);
                        }
                        lastTime = now;
                        lastLoadedTotal = overallLoaded;
                    }

                    const avgSpeed = elapsedSeconds > 0 ? overallLoaded / elapsedSeconds : 0;
                    const displaySpeed = smoothedSpeed > 0 ? smoothedSpeed : avgSpeed;

                    setProgress(overallLoaded, totalBatchBytes, displaySpeed, elapsedSeconds);
                };

                xhr.onload = () => {
                    try {
                        const resp = JSON.parse(xhr.responseText);
                        if (xhr.status >= 200 && xhr.status < 300 && resp.success) {
                            completedBytes += file.size;
                            resolve(true);
                        } else {
                            document.getElementById("statusText").textContent =
                                `Error uploading ${file.name}: ${resp.text || "Failed"}`;
                            document.getElementById("statusText").className = "status error";
                            resolve(false);
                        }
                    } catch (_) {
                        resolve(false);
                    }
                };

                xhr.onerror = () => resolve(false);
                xhr.onabort = () => resolve(false);

                xhr.send(file);
            });

            if (!uploadSuccess && isUploading) {
                const shouldContinue = confirm(`Failed to upload "${file.name}". Continue with remaining items?`);
                if (!shouldContinue) {
                    isUploading = false;
                    break;
                }
            }
        }

        currentXHR = null;
        isUploading = false;
        document.getElementById("uploadStartButton").disabled = false;
        document.getElementById("uploadFilesInput").value = "";
        document.getElementById("uploadFolderInput").value = "";
        uploadQueue = [];

        document.getElementById("progressBar").value = 100;
        document.getElementById("percentageText").textContent = "100%";
        document.getElementById("etaText").textContent = "Finished";
        document.getElementById("statusText").textContent = "✓ Upload completed successfully";
        document.getElementById("statusText").className = "status success";

        await refreshFiles();
    }

    // =========================================================
    // DOWNLOAD
    // =========================================================
    async function downloadFile(relativePath, filename) {
        resetProgress(`Downloading: ${filename}`);
        document.getElementById("statusText").textContent = "Downloading...";

        const params = new URLSearchParams({
            folder: currentFolderKey,
            path: relativePath
        });

        const startTime = performance.now();
        let lastTime = startTime;
        let lastLoaded = 0;
        let smoothedSpeed = 0;

        try {
            const response = await fetch(`/api/download?${params.toString()}`);

            if (!response.ok) {
                let message = `Download failed (${response.status}).`;
                try {
                    const data = await response.json();
                    message = data.text || message;
                } catch (_) {
                    // Keep default
                }
                throw new Error(message);
            }

            const total = Number(response.headers.get("Content-Length")) || 0;

            if (!response.body) {
                throw new Error("This browser does not support streamed downloads.");
            }

            const reader = response.body.getReader();
            const chunks = [];
            let loaded = 0;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                chunks.push(value);
                loaded += value.byteLength;

                const now = performance.now();
                const elapsedSeconds = (now - startTime) / 1000;
                const deltaSeconds = (now - lastTime) / 1000;

                if (deltaSeconds >= 0.2) {
                    const deltaBytes = loaded - lastLoaded;
                    const instantSpeed = deltaBytes / deltaSeconds;

                    if (instantSpeed > 0) {
                        smoothedSpeed = smoothedSpeed === 0
                            ? instantSpeed
                            : (smoothedSpeed * 0.75) + (instantSpeed * 0.25);
                    }

                    lastTime = now;
                    lastLoaded = loaded;
                }

                const averageSpeed = elapsedSeconds > 0 ? loaded / elapsedSeconds : 0;
                const displaySpeed = smoothedSpeed > 0 ? smoothedSpeed : averageSpeed;

                setProgress(loaded, total, displaySpeed, elapsedSeconds);
            }

            const blob = new Blob(chunks);
            const objectUrl = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = objectUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();

            setTimeout(() => URL.revokeObjectURL(objectUrl), 30000);

            document.getElementById("progressBar").value = 100;
            document.getElementById("percentageText").textContent = "100%";
            document.getElementById("etaText").textContent = "Finished";
            document.getElementById("statusText").textContent = "✓ Download completed";
            document.getElementById("statusText").className = "status success";

            if (total > 0) {
                document.getElementById("transferredText").textContent =
                    `${formatBytes(total)} / ${formatBytes(total)}`;
            }

        } catch (error) {
            document.getElementById("statusText").textContent = `Download failed: ${error.message}`;
            document.getElementById("statusText").className = "status error";
        }
    }

    // =========================================================
    // HOST FOLDER MANAGEMENT
    // =========================================================
    async function addAllowedFolder() {
        const nameInput = document.getElementById("newFolderName");
        const pathInput = document.getElementById("newFolderPath");
        const name = nameInput.value.trim();
        const path = pathInput.value.trim();

        if (!name || !path) {
            alert("Please enter both a Folder Nickname and the Full Path.");
            return;
        }

        try {
            const response = await fetch("/api/host/add_folder", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({name, path})
            });
            const data = await response.json();
            if (response.ok && data.success) {
                alert(data.text || "Folder added successfully.");
                nameInput.value = "";
                pathInput.value = "";
                await loadFolderChoices();
            } else {
                alert(`Error: ${data.text || "Failed to add folder."}`);
            }
        } catch (e) {
            alert(`Request failed: ${e.message}`);
        }
    }

    async function removeAllowedFolder(name) {
        if (!confirm(`Are you sure you want to stop sharing "${name}"?`)) return;

        try {
            const response = await fetch("/api/host/remove_folder", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({name})
            });
            const data = await response.json();
            if (response.ok && data.success) {
                alert(data.text);
                await loadFolderChoices();
            } else {
                alert(`Error: ${data.text || "Failed to remove folder."}`);
            }
        } catch (e) {
            alert(`Request failed: ${e.message}`);
        }
    }

    async function tryNativePicker() {
        const btn = document.getElementById("btnNativePicker");
        try {
            if (btn) btn.disabled = true;
            const response = await fetch("/api/host/browse_native", { method: "POST" });
            const data = await response.json();
            if (btn) btn.disabled = false;

            if (response.ok && data.success) {
                document.getElementById("newFolderPath").value = data.path;
                if (!document.getElementById("newFolderName").value) {
                    document.getElementById("newFolderName").value = data.name;
                }
            } else {
                if (data.gui_unavailable) {
                    alert(data.text);
                    openFsModal();
                } else if (data.text) {
                    alert(data.text);
                }
            }
        } catch (e) {
            if (btn) btn.disabled = false;
            alert(`System dialog unavailable: ${e.message}`);
            openFsModal();
        }
    }

    let fsCurrentDirectory = "";

    async function openFsModal() {
        const modal = document.getElementById("fsModal");
        if (!modal) return;
        modal.style.display = "flex";
        await loadFsDirectory("");
    }

    function closeFsModal() {
        const modal = document.getElementById("fsModal");
        if (modal) modal.style.display = "none";
    }

    async function loadFsDirectory(dirPath) {
        const listEl = document.getElementById("fsDirList");
        const pathEl = document.getElementById("fsCurrentPath");
        listEl.innerHTML = '<div style="padding:12px;" class="muted">Loading directories...</div>';

        try {
            const params = new URLSearchParams({ path: dirPath });
            const res = await fetch(`/api/host/fs_browse?${params.toString()}`);
            const data = await res.json();

            if (!res.ok || !data.success) {
                throw new Error(data.text || "Could not read directory.");
            }

            fsCurrentDirectory = data.current_path;
            pathEl.textContent = data.current_path || "(Computer Root / Drives)";

            listEl.innerHTML = "";
            if (!data.directories || data.directories.length === 0) {
                listEl.innerHTML = '<div style="padding:12px;" class="muted">No accessible subfolders found in this directory.</div>';
                return;
            }

            data.directories.forEach((dir) => {
                const item = document.createElement("div");
                item.className = "fs-dir-item";
                item.innerHTML = `<span>📁</span> <strong style="word-break:break-all;">${dir.name}</strong>`;
                item.onclick = () => loadFsDirectory(dir.path);
                listEl.appendChild(item);
            });

        } catch (err) {
            listEl.innerHTML = `<div style="padding:12px;" class="error">${err.message}</div>`;
        }
    }

    async function fsGoParent() {
        if (!fsCurrentDirectory) return;
        try {
            const params = new URLSearchParams({ path: fsCurrentDirectory });
            const res = await fetch(`/api/host/fs_browse?${params.toString()}`);
            const data = await res.json();
            if (data.parent_path !== null && data.parent_path !== undefined) {
                loadFsDirectory(data.parent_path);
            } else {
                loadFsDirectory("");
            }
        } catch (_) {
            loadFsDirectory("");
        }
    }

    function fsSelectCurrent() {
        if (!fsCurrentDirectory) {
            alert("Please navigate into a specific folder first.");
            return;
        }
        document.getElementById("newFolderPath").value = fsCurrentDirectory;
        const leaf = fsCurrentDirectory.split(/[\\/]/).filter(Boolean).pop() || "SharedFolder";
        if (!document.getElementById("newFolderName").value) {
            document.getElementById("newFolderName").value = leaf;
        }
        closeFsModal();
    }

    window.addEventListener("DOMContentLoaded", loadFolderChoices);
</script>
</body>
</html>
"""


# =========================================================
# ROUTES
# =========================================================
@app.route("/")
def index():
    return render_template_string(HTML_PAGE, is_host=is_host_request())


@app.post("/api/message")
def api_message():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify({"success": False, "text": "Message is empty."}), 400

    print(f"New message: {message}")
    return jsonify({"success": True, "text": "Message received successfully on laptop."})


@app.get("/api/folders")
def api_folders():
    is_host = is_host_request()
    details = []
    if is_host:
        for name, path in ALLOWED_FOLDERS.items():
            details.append({
                "name": name,
                "path": str(path),
                "is_custom": name in CUSTOM_FOLDERS,
            })

    return jsonify({
        "success": True,
        "folders": list(ALLOWED_FOLDERS.keys()),
        "is_host": is_host,
        "details": details,
    })


@app.get("/api/list")
def api_list():
    folder_key = request.args.get("folder", "")
    relative_path = request.args.get("path", "")

    try:
        root = get_root(folder_key)
        current = safe_path(root, relative_path)

        if not current.exists():
            return jsonify({"success": False, "text": "Folder does not exist."}), 404

        if not current.is_dir():
            return jsonify({"success": False, "text": "Selected path is not a folder."}), 400

        entries = []

        for item in current.iterdir():
            try:
                if item.is_dir():
                    entries.append({
                        "type": "folder",
                        "name": item.name,
                        "path": relative_posix(root, item),
                        "size": None,
                    })
                elif item.is_file():
                    entries.append({
                        "type": "file",
                        "name": item.name,
                        "path": relative_posix(root, item),
                        "size": item.stat().st_size,
                    })
            except (PermissionError, OSError):
                # Skip entries that cannot be inspected.
                continue

        entries.sort(key=lambda x: (x["type"] != "folder", x["name"].casefold()))

        return jsonify({
            "success": True,
            "folder": folder_key,
            "path": relative_posix(root, current) if current != root else "",
            "entries": entries,
        })

    except PermissionError:
        return jsonify({"success": False, "text": "Permission denied for this folder."}), 403
    except ValueError as error:
        return jsonify({"success": False, "text": str(error)}), 400
    except OSError as error:
        return jsonify({"success": False, "text": f"Unable to read folder: {error}"}), 500


@app.post("/api/upload")
def api_upload():
    folder_key = request.args.get("folder", "")
    relative_path = request.args.get("path", "")
    encoded_filename = request.headers.get("X-Filename", "")
    encoded_rel_path = request.headers.get("X-Relative-Path", "")

    if not encoded_filename and not encoded_rel_path:
        return jsonify({"success": False, "text": "Filename was not received."}), 400

    try:
        root = get_root(folder_key)
        destination_folder = safe_path(root, relative_path)

        if not destination_folder.exists():
            return jsonify({"success": False, "text": "Destination folder does not exist."}), 404

        if not destination_folder.is_dir():
            return jsonify({"success": False, "text": "Destination is not a folder."}), 400

        # Handle folder uploads with nested subdirectories (webkitRelativePath)
        if encoded_rel_path:
            raw_rel = unquote(encoded_rel_path).replace("\\", "/")
            clean_parts = []
            for part in raw_rel.split("/"):
                cleaned = secure_filename(part)
                if cleaned and cleaned not in (".", ".."):
                    clean_parts.append(cleaned)

            if not clean_parts:
                return jsonify({"success": False, "text": "Invalid relative path."}), 400

            destination = destination_folder.joinpath(*clean_parts)
            # Security: ensure resolved path cannot escape root
            try:
                destination.resolve().relative_to(root)
            except ValueError:
                return jsonify({"success": False, "text": "Invalid destination path."}), 400
        else:
            original_filename = unquote(encoded_filename)
            filename = secure_filename(original_filename)
            if not filename:
                return jsonify({"success": False, "text": "Invalid filename."}), 400
            destination = safe_path(destination_folder, filename)

        # Automatically create intermediate directories on Windows and Linux
        destination.parent.mkdir(parents=True, exist_ok=True)

        expected_size = request.content_length
        received_bytes = 0

        with open(destination, "wb") as output_file:
            while True:
                chunk = request.stream.read(1024 * 1024)
                if not chunk:
                    break
                output_file.write(chunk)
                received_bytes += len(chunk)

        if expected_size is not None and received_bytes != expected_size:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass

            return jsonify({
                "success": False,
                "text": (
                    f"Upload incomplete. Expected {expected_size} bytes "
                    f"but received {received_bytes} bytes."
                ),
            }), 400

        print(f"Uploaded: {destination} ({received_bytes:,} bytes)")

        return jsonify({
            "success": True,
            "text": "File uploaded successfully.",
            "filename": destination.name,
            "received_bytes": received_bytes,
            "expected_bytes": expected_size,
        })

    except PermissionError:
        return jsonify({"success": False, "text": "Permission denied while saving the file."}), 403
    except ValueError as error:
        return jsonify({"success": False, "text": str(error)}), 400
    except OSError as error:
        return jsonify({"success": False, "text": f"Upload failed: {error}"}), 500


@app.get("/api/download")
def api_download():
    folder_key = request.args.get("folder", "")
    relative_path = request.args.get("path", "")

    try:
        root = get_root(folder_key)
        file_path = safe_path(root, relative_path)

        if not file_path.exists():
            return jsonify({"success": False, "text": "File does not exist."}), 404

        if not file_path.is_file():
            return jsonify({"success": False, "text": "Selected path is not a file."}), 400

        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_path.name,
            conditional=True,
        )

    except PermissionError:
        return jsonify({"success": False, "text": "Permission denied for this file."}), 403
    except ValueError as error:
        return jsonify({"success": False, "text": str(error)}), 400
    except OSError as error:
        return jsonify({"success": False, "text": f"Download failed: {error}"}), 500


# =========================================================
# HOST-ONLY MANAGEMENT APIS
# =========================================================
@app.post("/api/host/add_folder")
def api_host_add_folder():
    if not is_host_request():
        return jsonify({"success": False, "text": "Access denied. Host only."}), 403

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    path_str = str(data.get("path", "")).strip()

    if not name:
        return jsonify({"success": False, "text": "Folder nickname is required."}), 400
    if not path_str:
        return jsonify({"success": False, "text": "Folder path is required."}), 400

    try:
        target = Path(path_str).expanduser().resolve()
        if not target.exists():
            return jsonify({"success": False, "text": f"Path '{path_str}' does not exist."}), 400
        if not target.is_dir():
            return jsonify({"success": False, "text": f"Path '{path_str}' is not a directory."}), 400

        # Verify read permission
        try:
            next(target.iterdir(), None)
        except PermissionError:
            return jsonify({"success": False, "text": "Permission denied reading this directory."}), 403

        ALLOWED_FOLDERS[name] = target
        CUSTOM_FOLDERS[name] = str(target)
        save_custom_folders()

        return jsonify({
            "success": True,
            "text": f"Folder '{name}' added successfully.",
            "folders": list(ALLOWED_FOLDERS.keys()),
        })

    except Exception as e:
        return jsonify({"success": False, "text": str(e)}), 500


@app.post("/api/host/remove_folder")
def api_host_remove_folder():
    if not is_host_request():
        return jsonify({"success": False, "text": "Access denied. Host only."}), 403

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()

    if not name:
        return jsonify({"success": False, "text": "Folder name is required."}), 400

    if name in ALLOWED_FOLDERS:
        del ALLOWED_FOLDERS[name]
        if name in CUSTOM_FOLDERS:
            del CUSTOM_FOLDERS[name]
            save_custom_folders()
        return jsonify({
            "success": True,
            "text": f"Folder '{name}' removed successfully.",
            "folders": list(ALLOWED_FOLDERS.keys()),
        })
    else:
        return jsonify({"success": False, "text": f"Folder '{name}' not found."}), 404


@app.get("/api/host/fs_browse")
def api_host_fs_browse():
    """Web directory browser modal for Linux/Windows/macOS."""
    if not is_host_request():
        return jsonify({"success": False, "text": "Access denied. Host only."}), 403

    req_path = request.args.get("path", "").strip()

    # Root view when path is empty
    if not req_path:
        roots = []
        if os.name == "nt":
            import string
            for letter in string.ascii_uppercase:
                drive_path = Path(f"{letter}:/")
                if drive_path.exists():
                    roots.append({"name": f"{letter}: Drive", "path": str(drive_path)})
            home = Path.home()
            if home.exists():
                roots.insert(0, {"name": f"Home ({home.name})", "path": str(home)})
        else:
            # Linux & macOS
            roots.append({"name": "Root (/)", "path": "/"})
            home = Path.home()
            if home.exists():
                roots.append({"name": f"Home ({home.name})", "path": str(home)})
            for common_dir in ("/media", "/mnt", "/var", "/tmp"):
                cd = Path(common_dir)
                if cd.exists():
                    roots.append({"name": common_dir, "path": str(cd)})

        return jsonify({
            "success": True,
            "current_path": "",
            "parent_path": None,
            "is_root": True,
            "directories": roots,
        })

    try:
        target = Path(req_path).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            return jsonify({"success": False, "text": "Directory not found."}), 404

        directories = []
        for item in target.iterdir():
            try:
                # Show directories only, skip hidden dirs
                if item.is_dir() and not item.name.startswith("."):
                    directories.append({
                        "name": item.name,
                        "path": str(item),
                    })
            except (PermissionError, OSError):
                continue

        directories.sort(key=lambda d: d["name"].casefold())
        parent_path = str(target.parent) if target.parent != target else ""

        return jsonify({
            "success": True,
            "current_path": str(target),
            "parent_path": parent_path,
            "is_root": False,
            "directories": directories,
        })

    except PermissionError:
        return jsonify({"success": False, "text": "Permission denied reading this directory."}), 403
    except Exception as e:
        return jsonify({"success": False, "text": str(e)}), 500


@app.post("/api/host/browse_native")
def api_host_browse_native():
    """Trigger OS-native directory picker if graphical display is available."""
    if not is_host_request():
        return jsonify({"success": False, "text": "Access denied. Host only."}), 403

    # On Linux, ensure display server is present
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return jsonify({
            "success": False,
            "gui_unavailable": True,
            "text": "No graphical desktop detected on this Linux session. Please use 'Browse Filesystem' instead.",
        })

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="Select Folder to Share")
        root.destroy()

        if selected:
            p = Path(selected).resolve()
            return jsonify({
                "success": True,
                "path": str(p),
                "name": p.name or "Shared_Folder",
            })
        return jsonify({"success": False, "text": "Folder selection cancelled."})

    except Exception as e:
        return jsonify({
            "success": False,
            "gui_unavailable": True,
            "text": f"System dialog unavailable ({e}). Please use 'Browse Filesystem' instead.",
        })


# =========================================================
# START SERVER
# =========================================================
if __name__ == "__main__":
    local_ip = get_local_ip()

    print("\n=======================================================")
    print("  Python Local Transfer Server is running.")
    print("=======================================================")
    print("• Make sure laptop/server and mobile are on the same Wi-Fi.")
    print(f"• Laptop / Host URL:  http://localhost:5000")
    print(f"• Mobile / LAN URL:   http://{local_ip}:5000\n")

    app.run(host="0.0.0.0", port=5000, threaded=True)
