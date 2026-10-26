#!/bin/bash

# Зупинка у разі виникнення помилок
set -e

echo "=== Початок встановлення CNC Bridge для Raspberry Pi ==="

# 1. Оновлення системи та встановлення залежностей
echo "Оновлення системних пакетів..."
sudo apt update && sudo apt upgrade -y

echo "Встановлення Python3, pip, pyserial та Git..."
sudo apt install -y python3 python3-pip python3-serial git

# 2. Налаштування прав доступу до послідовних портів
echo "Додавання користувача $USER до групи dialout..."
sudo usermod -aG dialout $USER

# 3. Створення робочої директорії
INSTALL_DIR="$HOME/cnc_bridge"
mkdir -p "$INSTALL_DIR"

echo "=== Встановлення успішно завершено! ==="
echo "Скопіюйте файли проєкту в директорію: $INSTALL_DIR"
echo "Для запуску мосту виконайте: python3 pi_local_bridge.py"
echo "Примітка: для застосування прав групи dialout може знадобитися перезавантаження системи (reboot)."
