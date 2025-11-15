import sys
import time
import subprocess
from datetime import datetime

def main():
    while True:  # ⬅️ BUCLE INFINITO - clave aquí
        try:
            print(f"🔄 Iniciando bot - {datetime.now()}")
            # Ejecuta el bot ORIGINAL como subproceso
            process = subprocess.Popen([sys.executable, "bot.py"])
            process.wait()  # ⬅️ Espera a que el bot termine (si se cierra)
            
        except Exception as e:
            print(f"❌ Error en el supervisor: {e}")
        
        print("🔄 Reiniciando en 10 segundos...")
        time.sleep(10)  # ⬅️ Pausa antes de reiniciar

if __name__ == "__main__":
    main()