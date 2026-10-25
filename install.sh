#!/bin/bash

echo "=== Встановлення залежностей для CNC мосту ==="
sudo apt update
sudo apt install -y python3-serial python3-lgpio socat

echo "=== Копіювання файлів проєкту ==="
INSTALL_DIR="$HOME/cnc_bridge"
mkdir -p "$INSTALL_DIR"
cp pi_local_bridge.py "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/pi_local_bridge.py"

echo "=== Створення головного скрипта запуску (~/start_cnc.sh) ==="
cat << 'EOF' > "$HOME/start_cnc.sh"
#!/bin/bash

# Запускаємо socat та отримуємо порти
SOCAT_OUT=$(socat pty,raw,echo=0 pty,raw,echo=0 2>&1 &)
sleep 1

PORTS=($(ls /dev/pts/ | grep -E '^[0-9]+$' | tail -n 2))
P1="/dev/pts/${PORTS[0]}"
P2="/dev/pts/${PORTS[1]}"

echo "Віртуальні порти створено: $P1 (для мосту) та $P2 (для Candle)"

# Запускаємо Python-міст у фоні
python3 ~/cnc_bridge/pi_local_bridge.py "$P1" /dev/ttyUSB0 &
BRIDGE_PID=$!

# Запускаємо Candle (шлях до вашого скомпільованого бінарника)
/home/cnc/Candle/build/src/candle/candle &
CANDLE_PID=$!

# Чекаємо закриття Candle
wait $CANDLE_PID

# Завершуємо роботу мосту та socat
kill $BRIDGE_PID
pkill socat
echo "Систему зупинено."
EOF

chmod +x "$HOME/start_cnc.sh"

echo "=== Готово! Тепер ви можете запускати систему командою: ~/start_cnc.sh ==="