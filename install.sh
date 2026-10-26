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

# Зупиняємо попередні мости та очищаємо старі файли
pkill -f pi_local_bridge.py
rm -f /tmp/vport_candle

# Запускаємо Python-міст у фоні
python3 ~/cnc_bridge/pi_local_bridge.py /dev/ttyUSB0 &
BRIDGE_PID=$!

# Чекаємо появи файлу віртуального порту (до 5 секунд)
echo "Очікування ініціалізації віртуального порту..."
for i in {1..10}; do
    if [ -e /tmp/vport_candle ]; then
        echo "Віртуальний порт успішно створено!"
        break
    fi
    sleep 0.5
done

# Якщо порт так і не з'явився — виходимо з помилкою
if [ ! -e /tmp/vport_candle ]; then
    echo "Помилка: Python-міст не зміг створити /tmp/vport_candle!"
    kill $BRIDGE_PID
    exit 1
fi

# Запускаємо Candle
/home/cnc/Candle/build/src/candle/candle &
CANDLE_PID=$!

# Чекаємо закриття Candle
wait $CANDLE_PID

# Завершуємо роботу мосту
kill $BRIDGE_PID
rm -f /tmp/vport_candle
echo "Систему безпечно зупинено."
EOF

chmod +x "$HOME/start_cnc.sh"
echo "=== Встановлення успішно завершено! ==="
