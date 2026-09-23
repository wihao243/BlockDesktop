# -*- coding: utf-8 -*-
"""Motor de bloqueo.

Comprueba si el proceso en primer plano coincide con alguna regla activa
en ese momento; si es así, termina todos sus procesos y encola una alerta
visual que la interfaz mostrará en pantalla.
"""
import os
import time

import psutil

import config

ALERT = "alert"  # tipo de evento emitido hacia la interfaz


def _kill(ejecutable, pid_propio):
    """Fuerza el cierre de todos los procesos cuyo nombre coincide."""
    nombre = ejecutable.strip().lower()

    objetivos = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            nombre_proc = (proc.info.get("name") or "").strip().lower()
            if nombre_proc == nombre and proc.info.get("pid") != pid_propio:
                objetivos.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # primer intento: cierre cooperativo
    for proc in objetivos:
        try:
            proc.terminate()
        except Exception:
            pass

    # segundo intento: cierre forzado si sigue vivo
    time.sleep(1.0)
    for proc in objetivos:
        try:
            if proc.is_running():
                proc.kill()
        except Exception:
            pass


class Blocker:
    """Encargado de aplicar las reglas y notificar los bloqueos."""

    def __init__(self, storage, event_queue):
        self.storage = storage
        self.event_queue = event_queue       # cola thread-safe hacia la GUI
        self._pid_propio = os.getpid()       # nunca se bloquea a sí misma
        self._ultimo_aviso = {}              # ejecutable -> última alerta

    def enforce(self, ejecutable, titulo_ventana, ahora):
        """Si `ejecutable` está bloqueado en este instante, lo cierra y
        emite una alerta (con un cooldown para no saturar la pantalla)."""
        if not ejecutable:
            return
        ejecutable = ejecutable.strip()
        exe = ejecutable.lower()

        for regla in self.storage.rules:
            if regla.exe.strip().lower() == exe and regla.matches(ahora):
                _kill(ejecutable, self._pid_propio)

                ultimo = self._ultimo_aviso.get(exe, 0)
                if ahora.timestamp() - ultimo >= config.ALERT_COOLDOWN:
                    self._ultimo_aviso[exe] = ahora.timestamp()
                    self.event_queue.put((ALERT, ejecutable, regla.describe(), titulo_ventana))
                return