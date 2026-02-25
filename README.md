# Edukacije — Education Event Sign-In App

A web application for collecting attendee sign-ins and digital signatures at EU-funded educational events (STEP RI). Supports INNO2MARE, EDIH, EEN, and GREENPACT project templates.

---

## Prerequisites

- Linux server with systemd
- Python 3.10+
- `git`
- `sudo` access (for systemd service management)

---

## First-Time Server Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_ORG/edukacije.git /opt/edukacije
cd /opt/edukacije
```

### 2. Create the virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set credentials

```bash
cp .env.example .env
nano .env
```

Edit `.env` and set a real username and password. **Do not use the defaults in production.**

### 4. Set up the systemd service

```bash
cp edukacije.service.example /etc/systemd/system/edukacije.service
nano /etc/systemd/system/edukacije.service
```

Replace all `YOUR_USER` and `/path/to/edukacije` placeholders with actual values (e.g. `User=pi`, `WorkingDirectory=/opt/edukacije`).

```bash
sudo systemctl daemon-reload
sudo systemctl enable edukacije.service
sudo systemctl start edukacije.service
```

### 5. Set up the auto-restart git hook

This hook automatically reinstalls dependencies and restarts the service after every `git pull`.

```bash
cp hooks/post-merge.sh .git/hooks/post-merge
chmod +x .git/hooks/post-merge
```

---

## Accessing the App

Open a browser on any device connected to the same network:

```
http://<SERVER_IP>:8505
```

- LAN cable (office desktop): `http://10.16.18.109:8505`
- Wi-Fi (tablets): `http://192.168.102.246:8505`

---

## Deploying Updates

Push changes from your development machine:

```bash
git push origin master
```

On the server, pull the latest code — the post-merge hook handles the rest automatically:

```bash
git pull origin master
```

The hook runs `run_server.sh` (with git pull skipped), which reinstalls requirements and restarts the service.

---

## Project Structure

```
app.py                      # Main Streamlit application
requirements.txt            # Python dependencies
run_server.sh               # Deployment helper script
hooks/post-merge.sh         # Git hook: auto-restart after pull
assets/                     # Document templates and logos per project
data/                       # Runtime data (CSVs, signatures) — not in git
docs/admin-guide.md         # Admin user guide
tests/test_app.py           # Unit tests
.env.example                # Environment variable template
edukacije.service.example   # Systemd service template
```

---

## Running Tests

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/
```
