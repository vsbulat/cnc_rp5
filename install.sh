#!/bin/bash

echo "=== Встановлення залежностей ==="
sudo apt update
sudo apt install -y python3-serial python3-lgpio

echo "=== Копіювання файлів мосту ==="
INSTALL_DIR="$HOME/cnc_bridge"
mkdir -p "$INSTALL_DIR"
cp pi_local_bridge.py "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/pi_local_bridge.py"

echo "=== Створення головного скрипта запуску (~/start_cnc.sh) ==="
cat << 'EOF' > "$HOME/start_cnc.sh"
#!/bin/bash

# Зупиняємо попередні мости
pkill -f pi_local_bridge.py

# Запускаємо Python Telnet-міст у фоні
python3 ~/cnc_bridge/pi_local_bridge.py /dev/ttyUSB0 &
BRIDGE_PID=$!

sleep 1

# Запускаємо Candle
/home/cnc/Candle/build/src/candle/candle &
CANDLE_PID=$!

# Чекаємо закриття Candle
wait $CANDLE_PID

# Завершуємо роботу мосту
kill $BRIDGE_PID
echo "Систему безпечно зупинено."
EOF

chmod +x "$HOME/start_cnc.sh"
echo "=== Встановлення успішно завершено! ==="
