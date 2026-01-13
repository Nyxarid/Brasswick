# Brasswick

An A1111-like web UI for image generation that uses **ComfyUI** as a backend.
Think: a lightweight frontend for ComfyUI with a queue, quick presets, LoRA stacking, and history — useful for experimenting locally.

---

## Table of contents

1. [Quick highlights](#quick-highlights)
2. [Requirements](#requirements)
3. [Download & install](#download--install)

   * [Linux (recommended)](#linux-recommended)
   * [Windows](#windows)
4. [Configuration](#configuration)
5. [Running Brasswick](#running-brasswick)
6. [Using Brasswick — UI & API examples](#using-brasswick---ui--api-examples)

   * [Web UI](#web-ui)
   * [Managing ComfyUI from Brasswick (Linux caveat)](#managing-comfyui-from-brasswick-linux-caveat)
7. [Security & deployment notes](#security--deployment-notes)
8. [Troubleshooting](#troubleshooting)
9. [Developer notes & roadmap](#developer-notes--roadmap)
10. [Credits & license](#credits--license)

---

# Quick highlights

* Browser-based UI for ComfyUI with:

  * Image generation (positive/negative prompts)
  * Seed, CFG, steps, sampler, scheduler, model, LoRAs (up to 3)
  * ETA & progress updates
  * Generation history (since startup)
  * Image tagger (via WD14)
  * Start/stop/restart ComfyUI support on Linux
  * Basic multi-user support (WIP)

---

# Requirements

* Python 3.8+ (system or virtualenv)
* `pip`
* Git
* ComfyUI running locally or reachable over network (HTTP + WebSocket)
* ComfyUI Custom Nodes:
  * `comfyui-wd14-tagger` (Search for "WD14 Tagger" in ComfyUI Manager or install [pythongosssss/ComfyUI-WD14-Tagger](https://github.com/pythongosssss/ComfyUI-WD14-Tagger))
* On your machine:

  * `Flask` and other Python packages listed in `requirements.txt`

`requirements.txt` (already provided):

```
Flask==2.3.2
requests==2.31.0
websocket-client==1.6.3
```

---

# Download & install

Clone the repository and install dependencies.

```bash
# clone
git clone https://github.com/Nyxarid/Brasswick.git
cd Brasswick

# create and activate virtualenv (recommended)
python3 -m venv brasswick-venv             # (Python for Windows)
source brasswick-venv/bin/activate        # Linux / macOS
.\brasswick-venv\Scripts\Activate.ps1     # Windows PowerShell

# install
pip install -r requirements.txt
```

> If you don't want a venv, you can install dependencies globally, but a venv is recommended.

## Linux (recommended)

1. Install Python, pip, venv and git.
```bash
# Ubuntu/Debian systems
sudo apt install python3 python3-pip python3-venv git

# CentOS/RHEL
sudo yum install python3 python3-pip git

# Fedora
sudo dnf install python3 python3-pip git

# Arch Linux
sudo pacman -S python python-pip git
```

2. Clone and `pip install -r requirements.txt` as above.

```bash
# Clone
git clone https://github.com/Nyxarid/Brasswick.git
cd Brasswick

# create and activate virtualenv (recommended)
python3 -m venv brasswick-venv
source brasswick-venv/bin/activate

# install
pip install -r requirements.txt
```
3. Ensure ComfyUI is installed somewhere and is reachable (see **Configuration**).
4. Start brasswick using `python3 app.py` (see [Running Brasswick](#running-brasswick)).

You can optionally create a `systemd` service (example below) to run Brasswick as a background service.

**Example `systemd` service**

```
[Unit]
Description=Brasswick Flask App
After=network.target

[Service]
User=youruser
Group=yourgroup
WorkingDirectory=/path/to/Brasswick
Environment=PATH=/path/to/Brasswick/venv/bin
ExecStart=/path/to/Brasswick/venv/bin/python /path/to/Brasswick/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Windows

1. Install Python 3.8+ and Git.
2. Clone repository.
3. Create and activate virtualenv:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Configure `brasswick_config.json` (see below) to point `comfy_server` at your running ComfyUI service (e.g. `127.0.0.1:8188`).
5. Start using:

```powershell
python .\app.py
```

**Windows caveat:** Brasswick includes functions to start/stop ComfyUI but those assume Unix-like `venv/bin/python` paths. On Windows either:

* Run ComfyUI manually in a separate terminal (recommended), or
* Modify `start_comfy_server()` in `app.py` to use `comfy_venv\Scripts\python.exe` (Windows path) if you want Brasswick to try to manage ComfyUI.

---

# Configuration

When you first run Brasswick it creates a `data/brasswick_config.json` file (in the same folder). Defaults shipped in settings:

`ComfyUI Server Address`: `127.0.0.1:8188`
`ComfyUI Installation Path`: `/path/to/ComfyUI`
`ComfyUI Virtual Environment (Optional)`: `/path/to/ComfyUI/venv`
`Brasswick Port`: `5000`
`Max History Items`: `50`

You can modify the settings through the 

You can edit this file manually or use the 

**Important fields**

* `ComfyUI Server Address (comfy_server)`: host:port for ComfyUI (HTTP + WS). Example: `"127.0.0.1:8188"`.
* `ComfyUI Installation Path (comfy_path)`: directory where ComfyUI `main.py` is located when using the built-in start/stop functions.
* `ComfyUI Virtual Environment (Optional) (comfy_venv)`: path to ComfyUI virtualenv. On Linux this script expects `comfy_venv/bin/python`; on Windows adjust as noted above.
* `Brasswick Port (port)`: port Brasswick binds to (default `5000`).
* `Max History Items (max_history)te`: max number of history entries stored per user session.
* `multi_user`: enable/disable per-session client IDs (WIP).

---

# Running Brasswick

```bash
# from repo root
python app.py
```

Default binds to `0.0.0.0` on the port set in config (default 5000), with Flask's `debug=True` in the provided script.

Open your browser to: `http://localhost:5000/`

---

# Using Brasswick — UI & API examples

## Web UI

* Open `http://<host>:<port>/` in your browser.
* UI features:

* Generate Tab:
  * Fill positive and negative prompts.
  * Choose model, sampler, scheduler, steps, CFG, seed (or set `-1` for random), width / height, batch size.
  * Up to 3 LoRAs with weights.
  * Queue/pause/cancel generation.
  * Download generated image or access history items.
* Tagger Tab:
  * Upload any image to analyze it.
  * Select a WD14 model (e.g., `wd-eva02-large-tagger-v3`) and threshold.
  * Extract tags and copy them directly to your positive prompt or clipboard.

## Managing ComfyUI from Brasswick (Linux caveat)

Brasswick can optionally start/stop/restart ComfyUI using `ComfyUI Installation Path` and `ComfyUI Virtual Environment`. This is Linux-oriented in the shipped code (it looks for `comfy_venv/bin/python`).

* If you want Brasswick to manage ComfyUI on **Linux**, set:

  * `comfy_path` to the directory containing `main.py` for ComfyUI.
  * `comfy_venv` to the virtualenv used by ComfyUI (so the start code can call `venv/bin/python main.py`).
* On **Windows**, either:

  * Run ComfyUI separately and point `comfy_server` at it, or
  * Edit `start_comfy_server()`/`stop_comfy_server()` to use Windows paths (`Scripts\python.exe`), or add detection logic. If you do this and it is succesful, you can do a pull request so others can enjoy this feature.

---

# Security & deployment notes

* **Do not** expose Brasswick directly to the public internet unless you know what you are doing. It sends prompts and can trigger generation on your local machine.
* Always run behind a firewall/VPN or on a private network.
* If exposing externally, use an authenticated reverse proxy (with TLS) and restrict access.
* Consider adding HTTP authentication or integrating a proper auth layer before public deployment.
* The README's disclaimer: **Do not expose this UI in public networks or port forward this** — there may be security vulnerabilities and external users could generate content on your machine.

---

# Troubleshooting

### Brasswick can't reach ComfyUI (connection refused / timeout)

* Verify ComfyUI is running and reachable at `http://{comfy_server}` (default `127.0.0.1:8188`).
* If ComfyUI runs on another machine, ensure firewall & network allow access.
* Use `curl` to test ComfyUI base endpoints:

  ```bash
  curl http://127.0.0.1:8188/
  curl http://127.0.0.1:8188/object_info
  ```
* Confirm `comfy_server` in `data/brasswick_config.json` is correct.

### `get_models()` / `get_loras()` return empties or errors

* ComfyUI’s `object_info` endpoint must return expected data. If ComfyUI custom nodes differ, the keys used by Brasswick (`CheckpointLoaderSimple`, `LoraLoader`, `CR LoRA Stack`) may be different — adjust `get_models()` / `get_loras()` accordingly.

### WebSocket errors

* WebSocket connection uses `ws://{comfy_server}/ws?clientId=...`. If ComfyUI runs behind TLS (`https`), change to `wss://` and make sure ComfyUI supports secure WS or use a reverse proxy.

### `start_comfy_server()` on Windows

* The included function expects `comfy_venv/bin/python`. Edit it to use `Scripts/python.exe` on Windows.

### Images are 404 or blank

* The app stores image bytes in-memory per-session. If `current_image_data` is empty, check generation logs (ComfyUI side) and the websocket/progress messages. Also check that ComfyUI `history/<prompt_id>` returns outputs referencing images.

### Long-term production usage

* Brasswick stores history in memory per session only. For longer persistence, implement saving images to disk or attach a database.

---

# Developer notes & roadmap

**WIP / possible future features**

* Full multi-user (roles/passwords)
* Persistent storage for history & galleries
* Custom workflows & UI templates
* Built-in inpainting/outpainting and upscaler integrations
* Docker image / easier installs
* Per-user quotas & limits
* API/CLI improvements
* Similarity search (Tagging added)
* GGUF / new model formats support

**Notes for contributors**

* ComfyUI API shapes (nodes & keys) may vary by ComfyUI version and installed nodes. Where the code expects specific node names (`CheckpointLoaderSimple`, `CR LoRA Stack`, `KSampler`, etc.), make sure the node names match or add compatibility logic.
* The code assumes `comfy_server` exposes REST and WS endpoints described in the project. If you run a non-standard ComfyUI fork, the endpoints may differ.

---

# Credits & license

**Developers**

* Nyxarid
* Claude (contributor)

**License**
Brasswick is released under the **Apache License 2.0**. See the `LICENSE` file for details.

---