#!/usr/bin/env python3
"""Telnet/TCP міст для Raspberry Pi 5: UGS (Telnet) → GRBL + GPIO реле."""

import re
import sys
import os
import socket
import threading
import time
import serial
import lgpio

# ================= НАЛАШТУВАННЯ ПІНІВ (BCM) =================
RELAY_SPINDLE_DIR = 17  # Реверс / полярність (M3 / M4)
RELAY_SPINDLE_PWR = 27  # Увімкнення шпинделя
PIN_M7 = 22             # Додатковий пін M7
PIN_M8 = 23             # Додатковий пін M8
# ==========================================================

BAUD_RATE = 115200
TCP_PORT = 2323

COMMENT_RE = re.compile(r"\(.*?\)|;.*")
RELAY_TOKENS = {"M3", "M03", "M4", "M04", "M5", "M05", "M7", "M07", "M8", "M08", "M9", "M09"}
GRBL_REALTIME = {0x18, ord("?"), ord("!"), ord("~")}


class TelnetBridge:
    def __init__(self, cnc_port: str) -> None:
        print(f"Підключення до станка на порту {cnc_port}...")
        self.cnc = serial.Serial(cnc_port, BAUD_RATE, timeout=0.05)
        self.stop = threading.Event()

        self._candle_line = bytearray()
        self._cnc_line = bytearray()
        self._lock = threading.Lock()

        # Ініціалізація GPIO на Raspberry Pi 5
        self.h = lgpio.gpiochip_open(0)
        for pin in (RELAY_SPINDLE_DIR, RELAY_SPINDLE_PWR, PIN_M7, PIN_M8):
            lgpio.gpio_claim_output(self.h, pin)
            lgpio.gpio_write(self.h, pin, 1)  # HIGH (вимкнено для активного LOW)

        self.client_sock = None
        print("GPIO успішно ініціалізовано.")

    def run(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", TCP_PORT))
        server.listen(1)
        print(f"Telnet міст запущено і слухає на 127.0.0.1:{TCP_PORT}...")

        cnc_thread = threading.Thread(target=self._read_cnc, daemon=True)
        cnc_thread.start()

        while not self.stop.is_set():
            try:
                server.settimeout(1.0)
                client, addr = server.accept()
                print(f"Клієнт підключився з {addr}")
                self.client_sock = client
                self._handle_client(client)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Помилка сервера: {e}")

    def _read_cnc(self) -> None:
        while not self.stop.is_set():
            try:
                data = self.cnc.read(256)
                if data:
                    with self._lock:
                        if self.client_sock:
                            try:
                                self.client_sock.sendall(data)
                            except Exception:
                                pass
            except Exception as e:
                print(f"Помилка читання з CNC: {e}")
                time.sleep(0.1)

    def _handle_client(self, client: socket.socket) -> None:
        client.settimeout(None)
        while not self.stop.is_set():
            try:
                data = client.recv(256)
                if not data:
                    break
                
                for b in data:
                    if b in GRBL_REALTIME:
                        self.cnc.write(bytes([b]))
                    else:
                        self._candle_line.append(b)
                        if b == ord('\n'):
                            line = self._candle_line.decode('utf-8', errors='ignore').strip()
                            self._candle_line.clear()
                            self._process_line(line)
            except Exception as e:
                print(f"Помилка клієнта: {e}")
                break
        
        with self._lock:
            self.client_sock = None
        client.close()
        print("Клієнт відключився")

    def _process_line(self, line: str) -> None:
        clean_line = COMMENT_RE.sub("", line).upper()
        tokens = clean_line.split()
        
        for token in tokens:
            if token in RELAY_TOKENS:
                print(f"Знайдено токен реле в команді: {token} (рядок: {line})")
                self._handle_relay(token)

        self.cnc.write((line + '\n').encode('utf-8'))

    def _handle_relay(self, token: str) -> None:
        try:
            if token in ("M3", "M03"):
                lgpio.gpio_write(self.h, RELAY_SPINDLE_PWR, 0)  # LOW (увімкнено)
                lgpio.gpio_write(self.h, RELAY_SPINDLE_DIR, 1)  # Пряме
                print("-> Реле шпинделя УВІМКНЕНО (M3)")
            elif token in ("M4", "M04"):
                lgpio.gpio_write(self.h, RELAY_SPINDLE_PWR, 0)  # LOW (увімкнено)
                lgpio.gpio_write(self.h, RELAY_SPINDLE_DIR, 0)  # Реверс
                print("-> Реле шпинделя УВІМКНЕНО Реверс (M4)")
            elif token in ("M5", "M05"):
                lgpio.gpio_write(self.h, RELAY_SPINDLE_PWR, 1)  # HIGH (вимкнено)
                lgpio.gpio_write(self.h, RELAY_SPINDLE_DIR, 1)  # Пряме
                print("-> Реле шпинделя ВИМКНЕНО (M5)")
            elif token in ("M7", "M07"):
                lgpio.gpio_write(self.h, PIN_M7, 0)
                print("-> Пін M7 активовано")
            elif token in ("M8", "M08"):
                lgpio.gpio_write(self.h, PIN_M8, 0)
                print("-> Пін M8 активовано")
            elif token in ("M9", "M09"):
                lgpio.gpio_write(self.h, RELAY_SPINDLE_PWR, 1)
                lgpio.gpio_write(self.h, PIN_M7, 1)
                lgpio.gpio_write(self.h, PIN_M8, 1)
                print("-> Все охолодження/шпиндель ВИМКНЕНО (M9)")
        except Exception as e:
            print(f"Помилка керування реле ({token}): {e}")


if __name__ == "__main__":
    cnc_port_name = '/dev/ttyACM0'
    
    # Чекаємо появи порту станка при запуску системи (до 20 секунд)
    print(f"Очікування появи портів станка ({cnc_port_name})...")
    for _ in range(20):
        if os.path.exists(cnc_port_name):
            break
        time.sleep(1)
    
    try:
        bridge = TelnetBridge(cnc_port_name)
        bridge.run()
    except KeyboardInterrupt:
        print("\nЗупинка мосту...")
    except Exception as e:
        print(f"Критична помилка мосту: {e}")
