#!/usr/bin/env python3
import serial
import serial.tools.list_ports
import time
import sys

BAUD_RATE = 115200

def find_cnc_port():
    print("Шукаємо підключений станок...")
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'ACM' in port.device or 'USB' in port.device:
            try:
                print(f"Перевіряємо порт: {port.device}...")
                s = serial.Serial(port.device, BAUD_RATE, timeout=1)
                time.sleep(2.0) # Очікування перезавантаження контролера
                s.write(b'\r\n?\r\n')
                time.sleep(0.5)
                resp = s.read_all()
                s.close()
                # Перевірка наявності стандартного статусу GRBL у відповіді
                if b'Idle' in resp or b'Run' in resp or b'Alarm' in resp:
                    print(f"Знайдено станок на порті: {port.device}")
                    return port.device
            except Exception:
                continue
    
    print("Попередження: Автоматичний порт не знайдено, використовуємо за замовчуванням /dev/ttyACM0")
    return "/dev/ttyACM0"

def main():
    port = find_cnc_port()
    print(f"Підключення до станка через {port} на швидкості {BAUD_RATE}...")
    
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        time.sleep(2.0)
        print("Міст успішно запущено. Очікування даних...")
        
        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                sys.stdout.buffer.write(data)
                sys.stdout.flush()
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\nРоботу мосту зупинено користувачем.")
    except Exception as e:
        print(f"Помилка з'єднання: {e}")

if __name__ == "__main__":
    main()
