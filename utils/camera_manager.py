import cv2
from pyzbar.pyzbar import decode
from PIL import Image
import threading
import time

class CameraScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self._lock = threading.Lock()
        
        # 1. OPTIMIZACIÓN DE HARDWARE: Forzamos a la cámara a no grabar en HD 
        # (No necesitamos 1080p para leer un código, esto quita muchísimo lag)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.ultimo_codigo_escaneado = ""
        self.frame_actual_pil = None
        self.codigos_actuales = []
        self.corriendo = True
        
        self.hilo_camara = threading.Thread(target=self._procesar_camara_fondo, daemon=True)
        self.hilo_camara.start()

    def _procesar_camara_fondo(self):
        contador_escaneo = 0
        
        while self.corriendo:
            if not self.cap.isOpened():
                time.sleep(0.1)
                continue

            ret, frame = self.cap.read()
            if ret:
                # 2. EL VIDEO SIEMPRE VA FLUIDO (A color para la pantalla)
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame_pil = Image.fromarray(frame_rgb)

                # 3. EL ESCÁNER SOLO TRABAJA 1 DE CADA 6 VECES
                # Esto es el "Frame Skipping" que eliminará el lag de la tabla
                contador_escaneo += 1
                if contador_escaneo >= 6:
                    contador_escaneo = 0 # Reiniciamos el contador
                    
                    # Convertimos a gris y achicamos SOLO para que pyzbar lea rápido
                    frame_gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    frame_pequeno = cv2.resize(frame_gris, (320, 240))
                    
                    codigos_leidos = []
                    for codigo in decode(frame_pequeno):
                        codigos_leidos.append(codigo.data.decode('utf-8'))
                        
                    with self._lock:
                        self.codigos_actuales = codigos_leidos

                with self._lock:
                    self.frame_actual_pil = frame_pil
                    
            time.sleep(0.03)

    def obtener_frame_listo(self):
        with self._lock:
            return self.frame_actual_pil, list(self.codigos_actuales)

    def liberar(self):
        self.corriendo = False
        if self.cap.isOpened():
            self.cap.release()
        if self.hilo_camara.is_alive():
            self.hilo_camara.join(timeout=1)
