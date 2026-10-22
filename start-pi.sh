#!/usr/bin/env bash
# Start BMO on Raspberry Pi OS after the documented venv and camera setup.
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
camera=0
auto_camera=0
observe=0
lan_ip=''
port=8765
pc_port=''
camera_index=0
model="${OPENAI_MODEL:-gpt-4.1-mini}"
dialogue_mode='realtime'

usage() {
  cat <<'EOF'
Usage: bash start-pi.sh [--camera|--auto-camera] [--observe] [--camera-index N] [--lan PI_IP] [--port PORT] [--pc-port PORT] [--model MODEL] [--dialogue-mode realtime|live]
  No options: voice conversation on the Pi itself or through an SSH tunnel.
  --camera: add a Pi camera photo only when selected for a question.
  --auto-camera: use a detected Pi camera; otherwise start with voice only.
  --observe: sample while idle, summarize changes and speak briefly when useful.
  --lan PI_IP: enable HTTPS for an iPhone on the same Wi-Fi; requires certs/bmo.pem and certs/bmo-key.pem.
  --pc-port PORT: allow the PC browser address when an SSH tunnel uses another local port.
EOF
}

while (($#)); do
  case "$1" in
    --camera) camera=1; shift ;;
    --auto-camera) auto_camera=1; shift ;;
    --observe) observe=1; auto_camera=1; shift ;;
    --camera-index|--lan|--port|--pc-port|--model|--dialogue-mode)
      option="$1"
      if (($# < 2)); then echo "Missing value for $option" >&2; exit 2; fi
      case "$option" in
        --camera-index) camera_index="$2" ;;
        --lan) lan_ip="$2" ;;
        --port) port="$2" ;;
        --pc-port) pc_port="$2" ;;
        --model) model="$2" ;;
        --dialogue-mode) dialogue_mode="$2" ;;
      esac
      shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if ((auto_camera && !camera)); then
  if command -v rpicam-hello >/dev/null 2>&1 && rpicam-hello --list-cameras 2>&1 | grep -Eq '^[[:space:]]*[0-9]+[[:space:]]*:'; then
    camera=1
    echo 'Pi camera detected.'
  else
    echo 'No Pi camera detected; starting voice conversation without camera.'
  fi
fi

if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
  echo 'Port must be between 1 and 65535.' >&2; exit 2
fi
if [[ -n "$pc_port" ]] && { [[ ! "$pc_port" =~ ^[0-9]+$ ]] || ((pc_port < 1 || pc_port > 65535)); }; then
  echo 'PC port must be between 1 and 65535.' >&2; exit 2
fi
if [[ ! "$camera_index" =~ ^[0-9]+$ ]]; then
  echo 'Camera index must be a nonnegative integer.' >&2; exit 2
fi
if [[ -z "$model" ]]; then
  echo 'Model ID is required.' >&2; exit 2
fi
if [[ "$dialogue_mode" != 'realtime' && "$dialogue_mode" != 'live' ]]; then
  echo 'Dialogue mode must be realtime or live.' >&2; exit 2
fi

python_bin='.venv/bin/python'
if ((camera)); then python_bin='.venv-camera/bin/python'; fi
if [[ ! -x "$python_bin" ]]; then
  echo "Missing $python_bin. Create the virtual environment as shown in README.md." >&2; exit 1
fi
if ((camera)) && ! "$python_bin" -c 'from picamera2 import Picamera2; from PIL import Image' >/dev/null 2>&1; then
  echo 'Pi camera packages are missing. Install python3-picamera2 and python3-pil, then create .venv-camera with --system-site-packages.' >&2
  exit 1
fi

if [[ "$dialogue_mode" == 'live' ]] && ! "$python_bin" -c 'import websocket' >/dev/null 2>&1; then
  echo "Live dependency missing: $python_bin -m pip install -r requirements-live.txt" >&2; exit 1
fi
args=(--provider openai --model "$model" --dialogue-mode "$dialogue_mode" --port "$port")
if [[ -n "$pc_port" ]]; then args+=(--allowed-host "127.0.0.1:$pc_port" --allowed-host "localhost:$pc_port"); fi
if ((camera)); then args+=(--source pi --camera-index "$camera_index"); fi
if ((observe && camera)); then args+=(--auto-observe); fi
if [[ -n "$lan_ip" ]]; then
  if [[ ! -f certs/bmo.pem || ! -f certs/bmo-key.pem ]]; then
    echo 'HTTPS certificate files are missing in certs/. Follow the iPhone HTTPS setup in README.md.' >&2
    exit 1
  fi
  args+=(--host 0.0.0.0 --tls-cert certs/bmo.pem --tls-key certs/bmo-key.pem --allowed-host "$lan_ip:$port")
  echo "Open https://$lan_ip:$port on the iPhone, then enter the pairing code printed below."
else
  echo "Open http://127.0.0.1:$port on the Pi or through an SSH tunnel."
fi

exec "$python_bin" -m bmo.app "${args[@]}"
