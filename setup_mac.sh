#!/bin/bash
# File Buddy setup (macOS). Run:  bash setup_mac.sh
cd "$(dirname "$0")"
PY=$(command -v python3.11 || command -v python3.12 || command -v python3)
[ -z "$PY" ] && { echo "Install Python 3.11 from python.org first."; exit 1; }
echo "Using $PY"
"$PY" -m venv .venv && .venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -r requirements.txt || exit 1
cat > "Start File Buddy.command" <<'EOS'
#!/bin/bash
cd "$(dirname "$0")" && .venv/bin/python FileBuddy.pyw
EOS
chmod +x "Start File Buddy.command"
echo "Done! Double-click 'Start File Buddy.command'. For local AI 3D: bash install_ai_engine.sh"
