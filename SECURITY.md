# Security Notes

Python Local Transfer is intended for trusted local networks.

- Do not expose the Flask development server directly to the public internet.
- Only configure folders in `ALLOWED_FOLDERS` that you intend to share.
- Avoid sharing an entire system drive unless you understand the risk.
- The current project does not provide authentication or HTTPS.
- Anyone who can reach the server may be able to browse, upload to, or download from configured folders.
- Keep your operating-system firewall enabled and stop the server when it is not needed.

If you extend this project for use outside a trusted LAN, add authentication, authorization, HTTPS, request-size limits, and production-grade serving before deployment.
