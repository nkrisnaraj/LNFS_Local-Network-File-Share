import os
import socket
from pathlib import Path
from urllib.parse import unquote

from flask import Flask, jsonify, render_template_string, request, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

# =========================================================
# CONFIGURATION
# =========================================================
# Change these paths to the folders you want to share.
# Only these folders will be visible from the mobile browser.
#
# Windows examples:
#     "Downloads": Path(r"C:\\Users\\YourName\\Downloads"),
#     "Movies": Path(r"D:\\Movies"),
#     "Transfer": Path(r"D:\\MobileTransfer"),
#
# Linux/macOS examples:
#     "Downloads": Path.home() / "Downloads",
#     "Transfer": Path("/home/yourname/MobileTransfer"),

ALLOWED_FOLDERS = {
    "Downloads": Path.home() / "Downloads",
    "Desktop": Path.home() / "Desktop",
    "Documents": Path.home() / "Documents",
    "Videos": Path.home() / "Videos",
}

# Create missing configured folders automatically.
for folder_path in ALLOWED_FOLDERS.values():
    folder_path.expanduser().mkdir(parents=True, exist_ok=True)


# =========================================================
# HELPERS
# =========================================================
def get_root(folder_key: str) -> Path:
    """Return the configured root folder for a folder key."""
    if folder_key not in ALLOWED_FOLDERS:
        raise ValueError("Invalid folder selection.")

    return ALLOWED_FOLDERS[folder_key].expanduser().resolve()


def safe_path(root: Path, relative_path: str = "") -> Path:
    """Resolve a path and make sure it stays inside root."""
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
        return "<LAPTOP_IP>"
    finally:
        sock.close()


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
        }

        button:disabled {
            opacity: 0.55;
            cursor: not-allowed;
        }

        .green {
            background: #28a745;
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
        <h3>2. Mobile → Laptop Upload</h3>
        <div class="muted">The file will be saved into the folder currently open below.</div>

        <input type="file" id="uploadInput">
        <button id="uploadButton" class="green" onclick="uploadSelectedFile()">Upload File</button>
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

<script>
    let currentFolderKey = "";
    let currentPath = "";

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

    function joinPath(base, name) {
        if (!base) return name;
        return `${base}/${name}`;
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

            if (data.folders.length === 0) {
                document.getElementById("fileList").textContent = "No folders configured.";
                return;
            }

            currentFolderKey = data.folders[0];
            currentPath = "";
            select.value = currentFolderKey;

            select.addEventListener("change", () => {
                currentFolderKey = select.value;
                currentPath = "";
                refreshFiles();
            });

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

    function uploadSelectedFile() {
        const input = document.getElementById("uploadInput");
        const file = input.files[0];
        const button = document.getElementById("uploadButton");

        if (!file) {
            alert("Please select a file first.");
            return;
        }

        resetProgress(`Uploading: ${file.name}`);
        document.getElementById("transferredText").textContent = `0 B / ${formatBytes(file.size)}`;
        document.getElementById("statusText").textContent = "Uploading...";
        button.disabled = true;

        const params = new URLSearchParams({
            folder: currentFolderKey,
            path: currentPath
        });

        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/upload?${params.toString()}`, true);
        xhr.setRequestHeader("Content-Type", "application/octet-stream");
        xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name));

        const startTime = performance.now();
        let lastTime = startTime;
        let lastLoaded = 0;
        let smoothedSpeed = 0;

        xhr.upload.onprogress = (event) => {
            const now = performance.now();
            const loaded = event.loaded;
            const total = event.lengthComputable ? event.total : file.size;
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

            if (total > 0 && loaded >= total) {
                document.getElementById("statusText").textContent =
                    "File sent. Waiting for server confirmation...";
            }
        };

        xhr.onload = async () => {
            button.disabled = false;

            let data = {};
            try {
                data = JSON.parse(xhr.responseText);
            } catch (_) {
                data = { success: false, text: "Invalid response from server." };
            }

            if (xhr.status >= 200 && xhr.status < 300 && data.success) {
                document.getElementById("progressBar").value = 100;
                document.getElementById("percentageText").textContent = "100%";
                document.getElementById("etaText").textContent = "Finished";
                document.getElementById("statusText").textContent = "✓ Upload completed and confirmed by server";
                document.getElementById("statusText").className = "status success";

                if (Number.isFinite(data.received_bytes)) {
                    document.getElementById("transferredText").textContent =
                        `${formatBytes(data.received_bytes)} / ${formatBytes(file.size)}`;
                }

                input.value = "";
                await refreshFiles();
            } else {
                document.getElementById("statusText").textContent =
                    `Upload failed: ${data.text || "Unknown error"}`;
                document.getElementById("statusText").className = "status error";
            }
        };

        xhr.onerror = () => {
            button.disabled = false;
            document.getElementById("statusText").textContent = "Upload failed because of a network error.";
            document.getElementById("statusText").className = "status error";
        };

        xhr.onabort = () => {
            button.disabled = false;
            document.getElementById("statusText").textContent = "Upload cancelled.";
            document.getElementById("statusText").className = "status error";
        };

        xhr.send(file);
    }

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
                    // Keep default message.
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
    return render_template_string(HTML_PAGE)


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
    return jsonify({
        "success": True,
        "folders": list(ALLOWED_FOLDERS.keys()),
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

    if not encoded_filename:
        return jsonify({"success": False, "text": "Filename was not received."}), 400

    try:
        root = get_root(folder_key)
        destination_folder = safe_path(root, relative_path)

        if not destination_folder.exists():
            return jsonify({"success": False, "text": "Destination folder does not exist."}), 404

        if not destination_folder.is_dir():
            return jsonify({"success": False, "text": "Destination is not a folder."}), 400

        original_filename = unquote(encoded_filename)
        filename = secure_filename(original_filename)

        if not filename:
            return jsonify({"success": False, "text": "Invalid filename."}), 400

        destination = safe_path(destination_folder, filename)
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
            "filename": filename,
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
# START SERVER
# =========================================================
if __name__ == "__main__":
    local_ip = get_local_ip()

    print("\nPython Local Transfer server is running.")
    print("Make sure the laptop and mobile are on the same Wi-Fi/network.")
    print(f"Open this address on your mobile: http://{local_ip}:5000\n")

    app.run(host="0.0.0.0", port=5000, threaded=True)
