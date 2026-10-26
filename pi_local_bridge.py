#!/usr/bin/env python3
"""Telnet/TCP міст для Raspberry Pi 5: Candle (Telnet) → GRBL + GPIO реле."""

import re
import sys
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

        self.sent_count = 0
        self.completed_count = 0
        self.pending = []
        self.client_sock = None

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
                print(f"Candle підключився з {addr}")
                self.client_sock = client
                self._handle_client(client)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Помилка сервера: {e}")

    def _handle_client(self, client: socket.socket) -> None:
        client.settimeout(None)
        while not self.stop.is_set():
            try:
                data = client.recv(256)
                if not data:
                    break
                self.cnc.write(data)
                self.cnc.flush()

                for byte in data:
                    if byte in GRBL_REALTIME:
                        continue
                    if byte in (10, 13):
                        line = self._candle_line.decode("utf-8", errors="ignore").strip()
                        self._candle_line.clear()
                        clean = COMMENT_RE.sub("", line).strip()
                        if clean:
                            with self._lock:
                                self.sent_count += 1
                                upper = clean.upper()
                                if any(t in RELAY_TOKENS for t in upper.replace("\t", " ").split()):
                                    self.pending.append((self.sent_count, upper))
                        continue
                    self._candle_line.append(byte)
            except Exception:
                break
        print("Candle відключився.")
        self.client_sock = None
        try:
            client.close()
        except:
            pass

    def _read_cnc(self) -> None:
        while not self.stop.is_set():
            data = self.cnc.read(256)
            if not data:
                continue
            
            sock = self.client_sock
            if sock:
                try:
                    sock.sendall(data)
                except:
                    pass

            for byte in data:
                if byte in (10, 13):
                    resp = self._cnc_line.decode("utf-8", errors="ignore").strip()
                    self._cnc_line.clear()
                    if resp.startswith("ok") or resp.startswith("error"):
                        with self._lock:
                            self.completed_count += 1
                            self._execute_gpio()
                    continue
                self._cnc_line.append(byte)

    def _execute_gpio(self) -> None:
        while self.pending and self.pending[0][0] <= self.completed_count:
            _, cmd = self.pending.pop(0)
            print(f"GPIO дія: {cmd}")

            if "M3" in cmd or "M03" in cmd:
                lgpio.gpio_write(self.h, RELAY_SPINDLE_DIR, 1)
                lgpio.gpio_write(self.h, RELAY_SPINDLE_PWR, 0)
            elif "M4" in cmd or "M04" in cmd:
                lgpio.gpio_write(self.h, RELAY_SPINDLE_DIR, 0)
                lgpio.gpio_write(self.h, RELAY_SPINDLE_PWR, 0)
            elif "M5" in cmd or "M05" in cmd:
                lgpio.gpio_write(self.h, RELAY_SPINDLE_DIR, 1)
                lgpio.gpio_write(self.h, RELAY_SPINDLE_PWR, 1)
            elif "M7" in cmd or "M07" in cmd:
                lgpio.gpio_write(self.h, PIN_M7, 0)
            elif "M8" in cmd or "M08" in cmd:
                lgpio.gpio_write(self.h, PIN_M8, 0)
            elif "M9" in cmd or "M09" in cmd:
                lgpio.gpio_write(self.h, PIN_M7, 1)
                lgpio.gpio_write(self.h, PIN_M8, 1)

    def shutdown(self) -> None:
        self.stop.set()
        for pin in (RELAY_SPINDLE_DIR, RELAY_SPINDLE_PWR, PIN_M7, PIN_M8):
            try:
                lgpio.gpio_write(self.h, pin, 1)
            except:
                pass
        lgpio.gpiochip_close(self.h)
        try:
            self.cnc.close()
        except:
            pass


if __name__ == "__main__":
    cnc_port_name = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    bridge = TelnetBridge(cnc_port_name)
    try:
        bridge.run()
    except KeyboardInterrupt:
        bridge.shutdown()
