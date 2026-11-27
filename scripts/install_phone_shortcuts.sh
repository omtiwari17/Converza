#!/data/data/com.termux/files/usr/bin/sh
# Converza Phone Server CLI Shortcuts Installer
# Installs 'converza' and 'update3' into $PREFIX/bin

PREFIX_BIN="${PREFIX:-/data/data/com.termux/files/usr}/bin"

cat << 'EOF' > "$PREFIX_BIN/converza"
#!/data/data/com.termux/files/usr/bin/sh

DIR="$HOME/converza"
[ ! -d "$DIR" ] && DIR="$HOME/Converza"
if [ ! -d "$DIR" ]; then
    echo "Converza directory not found in $HOME (checked ~/converza and ~/Converza)"
    exit 1
fi

IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
IP="${IP:-127.0.0.1}"

start_converza() {
    if pgrep -f "waitress-serve.*app:app" > /dev/null || pgrep -f "waitress.*5000" > /dev/null; then
        PID=$(pgrep -f "waitress" | head -n 1)
        echo "Converza is already running (PID: $PID) at http://$IP:5000/"
        return 0
    fi
    echo "Starting Converza in background (Port 5000)..."
    termux-wake-lock 2>/dev/null
    cd "$DIR" || exit 1
    nohup waitress-serve --host=0.0.0.0 --port=5000 --threads=4 app:app >> ~/converza.log 2>&1 < /dev/null &
    sleep 2
    if pgrep -f "waitress-serve.*app:app" > /dev/null || pgrep -f "waitress.*5000" > /dev/null; then
        PID=$(pgrep -f "waitress" | head -n 1)
        echo "Converza started (PID: $PID) -> http://$IP:5000/"
    else
        echo "Failed to start Converza. Check ~/converza.log"
    fi
}

stop_converza() {
    echo "Stopping Converza..."
    pkill -9 -f "waitress-serve.*app:app" 2>/dev/null
    pkill -9 -f "waitress.*5000" 2>/dev/null
    sleep 1
    echo "Converza stopped."
}

status_converza() {
    echo "=================================================="
    echo "             CONVERZA SERVICE STATUS              "
    echo "=================================================="
    if pgrep -f "waitress-serve.*app:app" > /dev/null || pgrep -f "waitress.*5000" > /dev/null; then
        PID=$(pgrep -f "waitress" | head -n 1)
        echo " [CONVERZA (5000)] : RUNNING (PID: $PID)"
        echo "   Local URL       : http://$IP:5000/"
        echo "   Health Check    : http://$IP:5000/healthz"
    else
        echo " [CONVERZA (5000)] : STOPPED"
    fi
    echo "=================================================="
    echo " Recent Logs (Last 3 lines):"
    tail -n 3 ~/converza.log 2>/dev/null
    echo "=================================================="
}

update_converza() {
    echo "=================================================="
    echo " UPDATING CONVERZA (Port 5000)..."
    echo "=================================================="
    cd "$DIR" || exit 1

    if [ -f .git/index.lock ] && ! pgrep -x git > /dev/null; then
        rm -f .git/index.lock
    fi

    echo "==> 1. Pulling latest code from GitHub..."
    git pull --ff-only 2>/dev/null || git pull --no-edit

    echo "==> 2. Installing requirements..."
    pip install -r requirements.txt -q

    echo "==> 3. Restarting Converza server..."
    stop_converza
    start_converza
}

case "$1" in
    start)   start_converza ;;
    stop)    stop_converza ;;
    restart) stop_converza; start_converza ;;
    status|"") status_converza ;;
    update)  update_converza ;;
    logs|log) tail -f ~/converza.log ;;
    *)
        echo "Usage: converza {start|stop|restart|status|update|logs}"
        exit 1
        ;;
esac
EOF

chmod +x "$PREFIX_BIN/converza"

cat << 'EOF' > "$PREFIX_BIN/update3"
#!/data/data/com.termux/files/usr/bin/sh
exec "$PREFIX/bin/converza" update
EOF

chmod +x "$PREFIX_BIN/update3"

echo "Installed 'converza' and 'update3' commands into $PREFIX_BIN."
