# -*- coding: utf-8 -*-
"""Punto de entrada de BlockDesktop.

Secuencia de arranque:
  1. Comprobación de instancia única.
  2. Carga de los datos persistentes (reglas y tiempos de uso).
  3. Motor de bloqueo + monitor de uso (hilo en segundo plano).
  4. Pantalla de pantalla de bloqueo con PIN; al desbloquear se muestra
     la interfaz principal con las pestañas Estadísticas y Reglas.

El monitor y el motor de bloqueo funcionan en segundo plano aunque la
ventana esté bloqueada o minimizada.
"""
import queue
import socket
import sys
import tkinter as tk
from tkinter import messagebox, ttk

import auth
import blocker
import config
import monitor
import storage
import ui

PUERTO_INSTANCIA_UNICA = 48123
event_queue = queue.Queue()  # cola thread-safe monitor/GUI


def main():
    if not _aquire_single_instance_lock():
        messagebox.showerror(config.NOMBRE_APP,
                             "BlockDesktop ya está en ejecución.")
        return

    # Estado compartido
    store = storage.Storage()
    blk = blocker.Blocker(store, event_queue)
    mon = monitor.UsageMonitor(store, blk)
    mon.start()

    # Ventana raíz
    root = tk.Tk()
    root.title("Bloqueado")
    root.geometry("380x220")
    root.minsize(380, 220)
    root.protocol("WM_DELETE_WINDOW", lambda: _on_window_close(root, mon, store))

    def show_lock():
        """Pantalla de bloqueo: pide el PIN antes de permitir cualquier uso."""
        for w in root.winfo_children():
            w.destroy()
        root.geometry("380x220")
        _build_lock(root, build_main)

    def build_main():
        """Interfaz principal (solo tras desbloquear con el PIN)."""
        for w in root.winfo_children():
            w.destroy()
        app = ui.BlockDesktopApp(
            root,
            store,
            on_lock=show_lock,
            on_quit=lambda: _on_window_close(root, mon, store),
        )
        root.geometry("880x540")
        root.minsize(760, 460)
        _ = app

    # Consumidor de eventos del monitor (alertas de bloqueo)
    root.after(250, lambda: _poll_events(root))
    show_lock()
    root.mainloop()


# ==================== cierre ====================
def _on_window_close(root, mon, store):
    """No se permite cerrar la aplicación sin autorización PIN."""
    if auth.prompt_pin(root, "Cerrar BlockDesktop"):
        mon.stop()
        store.save()
        root.destroy()
        sys.exit(0)


# ==================== pantalla de bloqueo ====================
def _build_lock(root, on_unlock):
    marco = ttk.Frame(root, padding=30)
    marco.pack(fill="both", expand=True)
    ttk.Label(marco, text=f"{config.NOMBRE_APP} está protegido",
              font=("Segoe UI", 14, "bold")).pack()
    ttk.Label(marco,
              text="Introduce el PIN para desbloquear.\n"
                   "La monitorización y el bloqueo siguen activos.",
              justify="center").pack(pady=(6, 14))

    entrada = ttk.Entry(marco, show="*", width=20, justify="center",
                        font=("Segoe UI", 14))
    entrada.pack()
    entrada.focus_set()

    error = ttk.Label(marco, foreground="#c62828")
    error.pack(pady=(8, 0))

    def _try():
        if entrada.get() == config.SECURITY_PIN:
            error.config(text="")
            on_unlock()
        else:
            error.config(text="Código incorrecto")
            entrada.delete(0, "end")
            entrada.focus_set()

    ttk.Button(marco, text="Desbloquear", command=_try).pack(pady=(14, 0))
    entrada.bind("<Return>", lambda e: _try())
    marco.bind("<Return>", lambda e: _try())


# ==================== cola de eventos ====================
def _poll_events(root):
    """Muestra en pantalla las alertas emitidas por el motor de bloqueo."""
    try:
        while True:
            evento = event_queue.get_nowait()
            if evento and evento[0] == blocker.ALERT:
                _, ejecutable, descripcion, titulo = evento
                _show_alert(root, ejecutable, descripcion, titulo)
    except queue.Empty:
        pass
    root.after(250, lambda: _poll_events(root))


def _show_alert(root, ejecutable, descripcion, titulo):
    """Ventana pequeña, siempre al frente, que avisa del cierre forzado."""
    if not root.winfo_exists():
        return
    top = tk.Toplevel(root)
    top.title("Aplicación bloqueada")
    top.attributes("-topmost", True)
    top.resizable(False, False)

    marco = ttk.Frame(top, padding=18)
    marco.pack(fill="both", expand=True)
    ttk.Label(marco, text="Aplicación bloqueada",
              font=("Segoe UI", 12, "bold"), foreground="#c62828").pack()
    ttk.Label(marco, text=f"Se ha cerrado: {ejecutable}").pack(pady=(6, 0))
    ttk.Label(marco, text=f"Motivo: {descripcion}").pack()
    ttk.Button(marco, text="OK", command=top.destroy).pack(pady=(12, 0))

    top.update_idletasks()
    ancho = top.winfo_width()
    alto = top.winfo_height()
    x = (top.winfo_screenwidth() - ancho) // 2
    y = (top.winfo_screenheight() - alto) // 2
    top.geometry(f"+{x}+{y}")
    top.after(config.ALERT_DURATION, top.destroy)


# ==================== instancia única ====================
def _aquire_single_instance_lock() -> bool:
    """Asegura que solo haya una copia del programa (usa un puerto local)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", PUERTO_INSTANCIA_UNICA))
        sock.listen(1)
        globals()["_lock_socket"] = sock  # mantener abierto durante la sesión
        return True
    except OSError:
        return False


if __name__ == "__main__":
    main()