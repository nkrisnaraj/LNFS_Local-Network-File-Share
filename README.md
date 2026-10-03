# Python Local Transfer

A simple local-network file transfer application built with **Python Flask**.

It allows you to transfer files between a laptop/desktop and a mobile device using only a web browser. Both devices should normally be connected to the same local network.

## Features

- Mobile → Laptop file upload
- Laptop → Mobile file download
- Browse allowed laptop folders and subfolders
- Upload files into the currently opened laptop folder
- Download files from the laptop to the mobile device
- Upload progress percentage
- Download progress percentage
- Transfer speed display
- Elapsed time display
- Estimated remaining time (ETA)
- File size display
- Text-message sending from the browser to the server terminal
- Mobile-friendly web interface
- Configurable shared folders
- Path-traversal protection
- Cross-platform support for Windows, Linux, and macOS

## Supported Devices

### Server

The Flask server can run on:

- Windows
- Linux
- macOS

### Client

The web interface can be opened from:

- Android phones and tablets
- iPhone and iPad
- Windows computers
- Linux computers
- macOS computers

The client device does not need Python installed. A modern web browser is enough.

## Requirements

- Python 3.9 or newer recommended
- Flask
- A modern web browser
- Both devices connected to the same local network

## Installation

### 1. Clone or download the project

Place the Python file in a project folder.

Example:

```text
python-local-transfer/
├── app.py
├── README.md
├── requirements.txt
├── LICENSE
├── SECURITY.md
└── .gitignore
```

### 2. Install dependencies

Open Command Prompt, PowerShell, Terminal, or your preferred shell inside the project folder.

```bash
python -m pip install -r requirements.txt
```

On systems where Python is invoked as `python3`, use:

```bash
python3 -m pip install -r requirements.txt
```

## Folder Configuration

The folders visible from the mobile browser are controlled by `ALLOWED_FOLDERS`.

Example:

```python
from pathlib import Path

ALLOWED_FOLDERS = {
    "Downloads": Path.home() / "Downloads",
    "Desktop": Path.home() / "Desktop",
    "Documents": Path.home() / "Documents",
    "Videos": Path.home() / "Videos",
}
```

Every configured path should be a `Path` object.

Correct:

```python
"Transfer": Path("B:/MobileTransfer")
```

Incorrect:

```python
"Transfer": "B:/MobileTransfer"
```

The application uses `Path` methods such as `expanduser()` and `resolve()`, so plain strings should not be used for configured folder paths.

## Windows Folder Examples

```python
ALLOWED_FOLDERS = {
    "Downloads": Path(r"C:\Users\YourName\Downloads"),
    "Movies": Path(r"D:\Movies"),
    "Photos": Path(r"D:\Photos"),
    "Transfer": Path(r"B:\MobileTransfer"),
}
```

You can also expose an entire drive:

```python
ALLOWED_FOLDERS = {
    "B Drive": Path("B:/"),
}
```

Use this only for drives or folders that you intentionally want devices on your local network to access.

## Linux Folder Examples

```python
ALLOWED_FOLDERS = {
    "Downloads": Path("/home/username/Downloads"),
    "Videos": Path("/home/username/Videos"),
    "Transfer": Path("/home/username/MobileTransfer"),
}
```

## macOS Folder Examples

```python
ALLOWED_FOLDERS = {
    "Downloads": Path("/Users/username/Downloads"),
    "Movies": Path("/Users/username/Movies"),
    "Transfer": Path("/Users/username/MobileTransfer"),
}
```

Using `Path.home()` makes common folders easier to configure across operating systems:

```python
ALLOWED_FOLDERS = {
    "Downloads": Path.home() / "Downloads",
    "Desktop": Path.home() / "Desktop",
    "Documents": Path.home() / "Documents",
}
```

## Running the Server

Run:

```bash
python app.py
```

or, depending on your system:

```bash
python3 app.py
```

The application binds to:

```python
host="0.0.0.0"
```

This allows other devices on the local network to connect to the Flask server.

A typical server configuration is:

```python
PORT = 5000

app.run(
    host="0.0.0.0",
    port=PORT,
    threaded=True
)
```

Keep the port shown in the terminal message and the port passed to `app.run()` the same.

For example:

```text
http://192.168.1.20:5000
```

## Connecting From a Mobile Device

1. Connect the laptop and mobile device to the same Wi-Fi or local network.
2. Start the Python server.
3. Find the laptop's local IP address.
4. Open the displayed address in the mobile browser.

Example:

```text
http://192.168.1.20:5000
```

Do not use this on the mobile device:

```text
http://127.0.0.1:5000
```

`127.0.0.1` on the phone refers to the phone itself, not the laptop.

## Mobile → Laptop Upload

1. Open the application on the mobile browser.
2. Select one of the configured laptop folders.
3. Browse into the required subfolder.
4. Select a file from the mobile device.
5. Press **Upload File**.

The selected file is uploaded into the folder currently open in the browser.

Example:

```text
Mobile
  │
  │ Upload
  ▼
Laptop
D:\Movies\Tamil\video.mp4
```

During an upload, the interface can show:

```text
Uploading: video.mp4

67.4%

Transferred   674.20 MB / 1.00 GB
Speed         28.52 MB/s
Elapsed       24 sec
Remaining     12 sec (estimate)
```

After all browser-side bytes have been sent, the page may briefly display:

```text
File sent. Waiting for server confirmation...
```

The upload is treated as complete only after the Flask server confirms receipt.

## Laptop → Mobile Download

1. Open the application from the mobile browser.
2. Select a configured laptop folder.
3. Browse into a subfolder if needed.
4. Find the required file.
5. Press **Download**.

Example:

```text
Laptop
  │
  │ Download
  ▼
Mobile
```

The interface displays download progress, speed, elapsed time, and estimated remaining time.

## Folder Browser

Only roots listed in `ALLOWED_FOLDERS` are exposed through the web interface.

For example:

```python
ALLOWED_FOLDERS = {
    "Movies": Path("D:/Movies"),
    "Photos": Path("D:/Photos"),
}
```

The mobile browser can navigate inside those roots, including subfolders.

It should not be able to navigate outside an allowed root using paths such as:

```text
../
../../
```

The server resolves and checks paths before allowing file operations.

## File List Scroll Area

If a folder contains many files, the visible list can be limited with CSS:

```css
#fileList {
    max-height: 350px;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 6px;
}
```

For a smaller mobile display:

```css
@media (max-width: 600px) {
    #fileList {
        max-height: 300px;
    }
}
```

## Transfer Progress

### Percentage

When the total size is known:

```text
percentage = transferred_bytes / total_bytes × 100
```

The percentage and transferred byte count are measurements of the transfer progress reported by the browser.

### Speed

Transfer speed is calculated from the number of bytes transferred over a measured time interval.

A smoothed value is used to reduce rapid changes in the displayed speed.

### ETA

Estimated remaining time is calculated approximately as:

```text
remaining_bytes / current_transfer_speed
```

ETA is always an estimate because Wi-Fi and network speeds can change during a transfer.

## Text Messages

The application also includes a simple text-message feature.

A message entered from the browser is sent to the Flask server and printed in the server terminal.

This feature is intended for simple local communication/testing and is not a chat-storage system.

## Large File Note

The current custom download-progress implementation reads the response stream in the browser and builds a `Blob` before triggering the final device download.

This provides detailed progress information, but very large files may consume significant browser memory.

For very large files, direct browser downloads or a streaming-to-file approach may be more suitable.

Upload handling is performed as a streamed request on the Flask server rather than loading the whole uploaded file into server memory.

## Security

This project is intended primarily for trusted local networks.

Important recommendations:

- Use it only on networks you trust.
- Do not expose the development Flask server directly to the public internet.
- Only add folders to `ALLOWED_FOLDERS` that you are comfortable sharing.
- Avoid exposing an entire system drive unless necessary.
- Do not expose sensitive folders.
- Keep operating-system firewall protection enabled.
- Stop the server when file sharing is no longer required.

The project currently does not include user authentication or HTTPS.

Anyone who can reach the server on the local network may be able to access the folders you configured.

## Windows Firewall

The first time Python accepts incoming connections, Windows may display a firewall prompt.

Allow Python on **Private networks** if you want devices on your trusted local network to connect.

Avoid enabling access on public networks unless you understand the security implications.

## Linux Firewall

If UFW is enabled and the server is using port `5000`, you may need:

```bash
sudo ufw allow 5000/tcp
```

Only open the port when required.

## macOS Firewall

macOS may ask whether Python is allowed to accept incoming connections.

Allow it if you want other trusted local-network devices to connect.

## Troubleshooting

### Mobile cannot open the page

Check:

- Laptop and phone are connected to the same network.
- Flask is running.
- The correct laptop LAN IP is being used.
- The URL contains the correct port.
- The operating-system firewall allows the connection.
- Client isolation / AP isolation is not enabled on the Wi-Fi network.

Example:

```text
http://192.168.1.20:5000
```

### New folder path does not work

Make sure the configured value uses `Path(...)`.

Correct:

```python
ALLOWED_FOLDERS = {
    "New Folder": Path(r"D:\New Folder"),
}
```

Incorrect:

```python
ALLOWED_FOLDERS = {
    "New Folder": r"D:\New Folder",
}
```

### Folder shows "Permission denied"

The operating-system account running Python must have permission to read the folder.

For uploads, it must also have write permission.

### Drive does not exist

This will not work if the drive is not mounted or available:

```python
Path("Z:/")
```

Verify that the drive exists on the computer running the Flask server.

### Wrong port is displayed

Make sure the same port variable is used when printing the URL and starting Flask.

Recommended:

```python
PORT = 5000

print(f"http://{local_ip}:{PORT}")

app.run(
    host="0.0.0.0",
    port=PORT,
    threaded=True
)
```

### Server works on laptop but not phone

Try opening the server address on another device connected to the same network.

If it works on the laptop using:

```text
http://127.0.0.1:5000
```

but not from the phone, check the laptop's LAN IP and firewall settings.

## Example Project Structure

```text
python-local-transfer/
│
├── app.py
├── README.md
│
└── optional-transfer-folders/
```

The shared folders do not need to be inside the project directory. They can be anywhere on the computer as long as they are configured in `ALLOWED_FOLDERS` and Python has permission to access them.

## Development Notes

The project uses:

- Flask for the HTTP server
- `pathlib.Path` for filesystem paths
- `secure_filename()` for safer uploaded filenames
- `XMLHttpRequest` upload progress events
- Fetch streaming for custom download progress
- JavaScript for the browser user interface

## Possible Future Improvements

Possible additions include:

- Password or PIN authentication
- QR code for the server URL
- Drag-and-drop uploads
- Multiple-file uploads
- Upload cancel button
- Download cancel button
- File search
- Folder creation from mobile
- Rename files and folders
- Delete files with confirmation
- Image/video previews
- Dark mode
- HTTPS support
- Direct streaming downloads for very large files
- Automatic network-interface selection

## License

This repository includes the MIT License. See `LICENSE` for details.

---

**Python Local Transfer** is designed as a simple local-network file transfer tool for your own devices and trusted networks.
