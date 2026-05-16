# Day 1 Preparation — Install Docker Desktop

## What This Is

Before Day 1 can be implemented, Docker Desktop must be installed and running on the
host machine. Day 1 creates the `Dockerfile` and `.dockerignore`, but the acceptance
criteria require actually building and running the image — that requires Docker.

This is a one-time host setup step, not a code change. Nothing is committed to the repo.

---

## Steps

### 1. Install Docker Desktop for Windows

Download from the official source:
```
https://www.docker.com/products/docker-desktop/
```

Run the installer. When prompted:
- Enable **WSL 2 backend** (recommended over Hyper-V for Windows 11)
- Enable **"Use WSL 2 instead of Hyper-V"** if given the choice

Restart the machine after installation if prompted.

### 2. Start Docker Desktop

Open Docker Desktop from the Start menu. Wait until the bottom-left status indicator
shows **"Engine running"** (green dot). This takes 30–60 seconds on first launch.

### 3. Verify Docker is working

Open PowerShell and run:

```powershell
docker --version
docker run --rm hello-world
```

Expected output from `hello-world`:
```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

If `hello-world` runs successfully, Docker is ready.

### 4. Configure WSL 2 resource limits (optional but recommended)

By default Docker Desktop may claim significant RAM. To cap it, create or edit
`C:\Users\<YourUser>\.wslconfig`:

```ini
[wsl2]
memory=4GB
processors=2
```

Restart Docker Desktop after saving.

---

## Done — Checklist Before Starting Day 1

- [ ] `docker --version` returns a version string (no error)
- [ ] `docker run --rm hello-world` exits 0 and prints the "Hello from Docker!" message
- [ ] Docker Desktop shows "Engine running" in the system tray
- [ ] You are on branch `main` (Day 1 will create `sandbox/day1` from `main`)

Once all four are checked, proceed to `dev_setup_update/specs/day1.md`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `docker: command not found` after install | PowerShell session predates install | Close and reopen PowerShell |
| Docker Desktop won't start | WSL 2 not enabled | Run `wsl --install` in an admin PowerShell, then restart |
| `hello-world` hangs | Docker engine not fully started | Wait 60 seconds; check the system tray icon |
| Virtualisation error on start | Virtualisation disabled in BIOS | Enable VT-x / AMD-V in BIOS settings |
