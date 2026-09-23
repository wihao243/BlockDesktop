# -*- coding: utf-8 -*-
"""Monitor de ventana activa.

Hilo en segundo plano que preguntar a Windows cuál es la ventana en primer
plano, atribuye el tiempo transcurrido a esa aplicación (registro diario) y
avisa al motor de bloqueo para que aplique las reglas en tiempo real.
"""
import ctypes
import threading
import time
from datetime import datetime

import psutil

import config


class UsageMonitor(threading.Thread):
    """Muestrea la ventana activa cada POLL_INTERVAL segundos."""

    def __init__(self, storage, blocker):
        super().__init__(daemon=True, name="MonitorDeUso")
        self.storage = storage
        self.blocker = blocker
        self._stop = threading.Event()
        self._prev_active = None   # (ejecutable, título) en la muestra anterior
        self._last_sample = None   # instante de la muestra anterior
        self._ticks = 0
        self._user32 = None

    def stop(self):
        """Pide al hilo que termine y vuelca los datos pendientes."""
        self._stop.set()

    # ==================== bucle principal ====================
    def run(self):
        if config.IS_WINDOWS:
            self._user32 = self._setup_user32()

        while not self._stop.is_set():
            ahora = datetime.now()
            activa = self._active_window() if self._user32 is not None else None

            # El tiempo transcurrido desde la muestra anterior se atribuye a
            # la aplicación que estaba en primer plano, para no perder el
            # intervalo en el que se cambió de ventana.
            if self._last_sample is not None and self._prev_active is not None:
                transcurrido = max(0.0, (ahora - self._last_sample).total_seconds())
                self.storage.add_usage(self._prev_active[0], transcurrido, ahora.date())

            # Aplicar reglas de bloqueo sobre la ventana que acaba de llegar
            # a primer plano (de esta forma se detecta el intento de abrirla).
            if activa is not None:
                self.blocker.enforce(activa[0], activa[1], ahora)

            self._last_sample = ahora
            self._prev_active = activa

            # Guardado periódico a disco
            self._ticks += 1
            if self._ticks >= config.SAVE_EVERY_TICKS:
                self.storage.save()
                self._ticks = 0

            # Espera con cortes finos para poder detener el hilo con rapidez
            inicio = time.time()
            while time.time() - inicio < config.POLL_INTERVAL:
                if self._stop.wait(0.1):
                    break

        # Vaciado final al cerrar la aplicación
        self.storage.save()

    # ==================== helpers de Windows ====================
    @staticmethod
    def _setup_user32():
        """Configura los prototipos (argtypes/restype) de las funciones
        Win32 que vamos a usar. Es importante ajustar restype a c_void_p
        para no truncar manejadores (HWND) en sistemas de 64 bits."""
        user32 = ctypes.windll.user32
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.GetForegroundWindow.argtypes = []
        user32.GetWindowThreadProcessId.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)
        ]
        user32.GetWindowTextW.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int
        ]
        user32.GetWindowTextW.restype = ctypes.c_int
        return user32

    def _active_window(self):
        """Devuelve (nombre_del_ejecutable, título) de la ventana enfocada,
        o None si no hay ninguna ventana de usuario (escritorio, E/S, ...)."""
        try:
            hwnd = self._user32.GetForegroundWindow()
            if not hwnd:
                return None

            pid = ctypes.c_ulong()
            self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            buf = ctypes.create_unicode_buffer(512)
            self._user32.GetWindowTextW(hwnd, buf, 512)
            titulo = buf.value or ""

            if pid.value == 0:
                return None  # ventana del sistema sin proceso de usuario

            proc = psutil.Process(pid.value)
            return proc.name(), titulo
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
        except Exception:
            return None