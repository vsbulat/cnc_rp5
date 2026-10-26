#!/bin/bash

echo "=== Встановлення залежностей (включно з socat) ==="
sudo apt update
sudo apt install -y python3-serial python3-lgpio socat

echo "=== Копіювання файлів мосту ==="
INSTALL_DIR="$HOME/cnc_bridge"
mkdir -p "$INSTALL_DIR"
cp pi_local_bridge.py "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/pi_local_bridge.py"

echo "=== Створення головного скрипта запуску (~/start_cnc.sh) ==="
cat << 'EOF' > "$HOME/start_cnc.sh"
#!/bin/bash

# Зупиняємо попередні процеси та очищаємо старі посилання
pkill socat
pkill -f pi_local_bridge.py
rm -f /tmp/vport_*

# Запускаємо socat для створення пари пов'язаних терміналів
socat pty,link=/tmp/vport_bridge,raw,echo=0 pty,link=/tmp/vport_candle,raw,echo=0 &
SOCAT_PID=$!

# Чекаємо появи обох портів (до 5 секунд)
echo "Очікування ініціалізації віртуальних портів..."
for i in {1..10}; do
    if [ -e /tmp/vport_bridge ] && [ -e /tmp/vport_candle ]; then
        echo "Віртуальні порти створено успішно!"
        break
    fi
    sleep 0.5
done

if [ ! -e /tmp/vport_bridge ] || [ ! -e /tmp/vport_candle ]; then
    echo "Помилка: socat не зміг створити порти!"
    kill $SOCAT_PID
    exit 1
fi

# Запускаємо Python-міст у фоні
python3 ~/cnc_bridge/pi_local_bridge.py /tmp/vport_bridge /dev/ttyUSB0 &
BRIDGE_PID=$!

sleep 1

# Запускаємо Candle
/home/cnc/Candle/build/src/candle/candle &
CANDLE_PID=$!

# Чекаємо закриття Candle
wait $CANDLE_PID

# Завершуємо роботу мосту та socat
kill $BRIDGE_PID
kill $SOCAT_PID
rm -f /tmp/vport_*
echo "Систему безпечно зупинено."
EOF

chmod +x "$HOME/start_cnc.sh"
echo "=== Встановлення успішно завершено! ==="
