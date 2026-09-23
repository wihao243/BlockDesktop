# -*- coding: utf-8 -*-
"""Autenticación por código PIN.

Toda la interfaz permanece bloqueada hasta introducir el PIN correcto
(18032008). El mismo diálogo se usa para autorizar el cierre de la aplicación.
"""
import tkinter as tk
from tkinter import ttk

import config


class PinDialog(tk.Toplevel):
    """Ventana modal que pide el PIN. Al cerrarse, `result` indica si el
    código introducido era correcto."""

    def __init__(self, master, title="Introduce el PIN"):
        super().__init__(master)
        self.result = False
        self.title(title)
        self.resizable(False, False)
        self.configure(padx=28, pady=24)
        self.transient(master)
        self.grab_set()   # bloquea el resto de la interfaz
        self._build()
        self.bind("<Return>", lambda e: self._try())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build(self):
        ttk.Label(
            self,
            text=f"{config.NOMBRE_APP} está protegido.\nIntroduce el código PIN:",
            justify="center",
        ).pack()
        self.entry = ttk.Entry(self, show="*", width=18, justify="center",
                               font=("Segoe UI", 14))
        self.entry.pack(pady=12)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self._try())

        fila = ttk.Frame(self)
        fila.pack()
        ttk.Button(fila, text="Aceptar", command=self._try).pack(side="left", padx=5)
        ttk.Button(fila, text="Cancelar", command=self._cancel).pack(side="left", padx=5)

        self.lbl_error = ttk.Label(self, foreground="#c62828")
        self.lbl_error.pack(pady=(10, 0))

    def _try(self):
        """Valida el PIN; si es correcto cierra el diálogo con éxito."""
        if self.entry.get() == config.SECURITY_PIN:
            self.result = True
            self.destroy()
        else:
            self.lbl_error.config(text="Código incorrecto")
            self.entry.delete(0, "end")
            self.entry.focus_set()

    def _cancel(self):
        self.result = False
        self.destroy()


def prompt_pin(master, title="Introduce el PIN") -> bool:
    """Muestra el diálogo de forma modal (bloqueante) y devuelve True si el
    usuario introdujo el PIN correcto."""
    dialogo = PinDialog(master, title)
    master.wait_window(dialogo)  # espera hasta que el diálogo se cierre
    return dialogo.result