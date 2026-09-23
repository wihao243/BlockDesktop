# -*- coding: utf-8 -*-
"""Interfaz gráfica principal.

Dos pestañas:
  - Estadísticas: tiempos de uso por aplicación y día.
  - Reglas de Bloqueo: creación, edición y borrado de restricciones
    (ejecutable + días de la semana + franja horaria).
Toda la ventana se muestra únicamente tras desbloquear con el PIN.
"""
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import psutil

import auth
import config
import models


class ProcesoPicker(tk.Toplevel):
    """Diálogo auxiliar para elegir un proceso entre los que están en
    ejecución, con buscador por nombre."""

    def __init__(self, master, on_choose):
        super().__init__(master)
        self.on_choose = on_choose
        self.title("Buscar proceso")
        self.resizable(False, False)
        self.configure(padx=12, pady=12)
        self.transient(master)
        self.grab_set()

        fila = ttk.Frame(self)
        fila.pack(fill="x")
        ttk.Label(fila, text="Filtro:").pack(side="left")
        self.filtro = ttk.Entry(fila, width=26)
        self.filtro.pack(side="left", padx=6)
        self.filtro.focus_set()

        self.listbox = tk.Listbox(self, width=48, height=18)
        self.listbox.pack(pady=8)
        barra = ttk.Scrollbar(self.listbox, orient="vertical",
                              command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=barra.set)

        ttk.Button(self, text="Usar el seleccionado",
                   command=self._choose).pack()

        self._nombres = []
        self._cargar()
        self.filtro.bind("<KeyRelease>", lambda e: self._aplicar_filtro())
        self.listbox.bind("<Double-Button-1>", lambda e: self._choose())
        self.listbox.bind("<Return>", lambda e: self._choose())

    def _cargar(self):
        """Enumera los nombres de procesos en ejecución (sin duplicados)."""
        try:
            nombres = set()
            for proc in psutil.process_iter(["name"]):
                nom = proc.info.get("name")
                if nom:
                    nombres.add(nom)
            self._nombres = sorted(nombres)
        except Exception:
            self._nombres = []
        self._aplicar_filtro()

    def _aplicar_filtro(self):
        texto = self.filtro.get().strip().lower()
        candidatos = [n for n in self._nombres if texto in n.lower()] if texto else self._nombres
        self.listbox.delete(0, "end")
        for nombre in candidatos:
            self.listbox.insert("end", nombre)

    def _choose(self):
        if not self.listbox.curselection():
            return
        nombre = self.listbox.get(self.listbox.curselection()[0])
        self.on_choose(nombre)
        self.destroy()


class BlockDesktopApp(ttk.Frame):
    """Ventana principal con las dos pestañas."""

    def __init__(self, master, storage, on_lock, on_quit):
        super().__init__(master, padding=8)
        self.storage = storage
        self.on_lock = on_lock      # callback -> volver a la pantalla bloqueada
        self.on_quit = on_quit      # callback -> cerrar la aplicación

        self._build_topbar()
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self._build_stats_tab()
        self._build_rules_tab()

        self.pack(fill="both", expand=True)
        self.refresh_stats()
        self.refresh_rules()
        self.after(5000, self._auto_refresh)

    # ==================== barra superior ====================
    def _build_topbar(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text=f"{config.NOMBRE_APP} — Panel de control",
                  font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(top, text="Bloquear", command=self.on_lock).pack(side="right", padx=(6, 0))
        ttk.Button(top, text="Cerrar aplicación", command=self._ask_close).pack(side="right")

    def _ask_close(self):
        """Cerrar la aplicación exige autorización con PIN."""
        if auth.prompt_pin(self, "Cerrar BlockDesktop"):
            self.on_quit()

    # ==================== pestaña de estadísticas ====================
    def _build_stats_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Estadísticas")

        fila = ttk.Frame(tab)
        fila.pack(fill="x", pady=(0, 8))
        ttk.Label(fila, text="Día:").pack(side="left")

        hoy = datetime.now().strftime(config.DATE_FMT)
        fechas = [hoy] + [d for d in self.storage.available_dates() if d != hoy]
        self.date_var = tk.StringVar(value=hoy)
        self.date_box = ttk.Combobox(fila, textvariable=self.date_var,
                                     values=fechas, state="readonly", width=12)
        self.date_box.pack(side="left", padx=6)
        self.date_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_stats())
        ttk.Button(fila, text="Refrescar", command=self.refresh_stats).pack(side="left")

        cont = ttk.Frame(tab)
        cont.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(cont, columns=("app", "tiempo"),
                                 show="headings", height=16)
        self.tree.heading("app", text="Aplicación")
        self.tree.heading("tiempo", text="Tiempo de uso")
        self.tree.column("app", width=340, anchor="w")
        self.tree.column("tiempo", width=120, anchor="center")
        barra = ttk.Scrollbar(cont, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")

        self.total_lbl = ttk.Label(tab, text="", font=("Segoe UI", 10, "bold"))
        self.total_lbl.pack(anchor="w", pady=(8, 0))

    def refresh_stats(self):
        try:
            dia = datetime.strptime(self.date_var.get(), config.DATE_FMT).date()
        except Exception:
            dia = datetime.now().date()

        self.tree.delete(*self.tree.get_children())
        uso = self.storage.usage_for(dia)
        total = 0
        for app, seg in uso.items():
            self.tree.insert("", "end",
                             values=(app, _fmt_segundos(seg)))
            total += seg
        self.total_lbl.config(
            text=f"Total del día: {_fmt_segundos(total)}  "
                 f"({len(uso)} aplicación(es))")

    def _auto_refresh(self):
        """Actualiza la vista si el día seleccionado es hoy."""
        try:
            if self.winfo_exists():
                if self.date_var.get() == datetime.now().strftime(config.DATE_FMT):
                    self.refresh_stats()
                self.after(5000, self._auto_refresh)
        except Exception:
            pass

    # ==================== pestaña de reglas ====================
    def _build_rules_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Reglas de Bloqueo")

        # --- lista de reglas ---
        izquierda = ttk.Frame(tab)
        izquierda.pack(side="left", fill="both", expand=True)
        self.rule_tree = ttk.Treeview(izquierda,
                                      columns=("nombre", "proceso", "dias", "horario"),
                                      show="headings")
        cabeceras = {"nombre": "Nombre", "proceso": "Proceso",
                     "dias": "Días", "horario": "Horario"}
        anchos = {"nombre": 110, "proceso": 120, "dias": 170, "horario": 150}
        for c in cabeceras:
            self.rule_tree.heading(c, text=cabeceras[c])
            self.rule_tree.column(c, width=anchos[c], anchor="w")
        barra = ttk.Scrollbar(izquierda, orient="vertical",
                              command=self.rule_tree.yview)
        self.rule_tree.configure(yscrollcommand=barra.set)
        self.rule_tree.pack(side="left", fill="both", expand=True)
        barra.pack(side="left", fill="y")
        self.rule_tree.bind("<<TreeviewSelect>>", self._on_rule_selected)

        # --- formulario de edición ---
        form = ttk.LabelFrame(tab, text="Detalles de la regla", padding=12)
        form.pack(side="right", padx=(10, 0), fill="y")
        self.rule_index = -1  # -1 = regla nueva (no se está editando ninguna)

        ttk.Label(form, text="Nombre / etiqueta:").pack(anchor="w")
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=28).pack(pady=(2, 10))

        ttk.Label(form, text="Proceso (ejecutable):").pack(anchor="w")
        fila_proc = ttk.Frame(form)
        fila_proc.pack(fill="x", pady=(2, 10))
        self.exe_var = tk.StringVar()
        ttk.Entry(fila_proc, textvariable=self.exe_var, width=20).pack(side="left")
        ttk.Button(fila_proc, text="Buscar…",
                   command=self._pick_process).pack(side="left", padx=(6, 0))

        ttk.Label(form, text="Días de la semana:").pack(anchor="w")
        fila_dias = ttk.Frame(form)
        fila_dias.pack(fill="x", pady=(2, 10))
        self.day_vars = [tk.BooleanVar(value=False) for _ in range(7)]
        for i in range(7):
            ttk.Checkbutton(fila_dias, text=models.DIAS_CORTOS[i],
                            variable=self.day_vars[i]).pack(side="left", padx=2)

        ttk.Label(form, text="Franja horaria de bloqueo:").pack(anchor="w")
        fila_horas = ttk.Frame(form)
        fila_horas.pack(fill="x", pady=(2, 12))
        horas = [f"{h:02d}" for h in range(24)]
        minutos = [f"{m:02d}" for m in range(60)]

        ttk.Label(fila_horas, text="Desde").pack(side="left")
        self.start_h = ttk.Combobox(fila_horas, values=horas, width=3, state="readonly")
        self.start_m = ttk.Combobox(fila_horas, values=minutos, width=3, state="readonly")
        self.start_h.set("09"); self.start_m.set("00")
        self.start_h.pack(side="left", padx=(4, 2)); self.start_m.pack(side="left")

        ttk.Label(fila_horas, text="hasta").pack(side="left", padx=(10, 0))
        self.end_h = ttk.Combobox(fila_horas, values=horas, width=3, state="readonly")
        self.end_m = ttk.Combobox(fila_horas, values=minutos, width=3, state="readonly")
        self.end_h.set("18"); self.end_m.set("00")
        self.end_h.pack(side="left", padx=(4, 2)); self.end_m.pack(side="left")

        botones = ttk.Frame(form)
        botones.pack(fill="x", pady=(6, 0))
        ttk.Button(botones, text="Añadir", command=self._add_rule).pack(side="left", padx=2)
        ttk.Button(botones, text="Actualizar", command=self._update_rule).pack(side="left", padx=2)
        ttk.Button(botones, text="Eliminar", command=self._delete_rule).pack(side="left", padx=2)
        ttk.Button(botones, text="Limpiar", command=self._clear_form).pack(side="left", padx=2)

    # -------- gestión de la lista --------
    def refresh_rules(self):
        self.rule_tree.delete(*self.rule_tree.get_children())
        for i, regla in enumerate(self.storage.rules):
            self.rule_tree.insert("", "end", iid=str(i),
                                  values=(regla.name, regla.exe,
                                          regla.days_str(), regla.hours_str()))
        self._clear_form()

    def _on_rule_selected(self, _event=None):
        seleccion = self.rule_tree.selection()
        if not seleccion:
            return
        self._load_rule(int(seleccion[0]))

    def _load_rule(self, idx):
        regla = self.storage.rules[idx]
        self.rule_index = idx
        self.name_var.set(regla.name)
        self.exe_var.set(regla.exe)
        for i in range(7):
            self.day_vars[i].set(i in regla.days)
        self.start_h.set(f"{regla.start_min // 60:02d}")
        self.start_m.set(f"{regla.start_min % 60:02d}")
        self.end_h.set(f"{regla.end_min // 60:02d}")
        self.end_m.set(f"{regla.end_min % 60:02d}")

    def _clear_form(self):
        self.rule_index = -1
        self.rule_tree.selection_remove(*self.rule_tree.selection())
        self.name_var.set("")
        self.exe_var.set("")
        for var in self.day_vars:
            var.set(False)
        self.start_h.set("09"); self.start_m.set("00")
        self.end_h.set("18"); self.end_m.set("00")

    # -------- operaciones --------
    def _collect_rule(self):
        """Construye una BlockRule a partir del formulario (o None si no
        es válida, mostrando el motivo)."""
        try:
            inicio = int(self.start_h.get()) * 60 + int(self.start_m.get())
            fin = int(self.end_h.get()) * 60 + int(self.end_m.get())
        except (ValueError, TypeError):
            inicio = fin = 0
        regla = models.BlockRule(
            name=self.name_var.get().strip(),
            exe=self.exe_var.get().strip(),
            days=[i for i, v in enumerate(self.day_vars) if v.get()],
            start_min=inicio,
            end_min=fin,
        )
        if not regla.valid():
            messagebox.showwarning(
                "Datos incompletos",
                "Indica un nombre, el proceso (ejecutable) y al menos un día.",
                parent=self)
            return None
        return regla

    def _add_rule(self):
        regla = self._collect_rule()
        if regla is None:
            return
        self.storage.add_rule(regla)
        self.refresh_rules()

    def _update_rule(self):
        if self.rule_index < 0 or self.rule_index >= len(self.storage.rules):
            messagebox.showinfo("Aviso", "Selecciona una regla de la lista.",
                                parent=self)
            return
        regla = self._collect_rule()
        if regla is None:
            return
        self.storage.update_rule(self.rule_index, regla)
        self.refresh_rules()

    def _delete_rule(self):
        if self.rule_index < 0 or self.rule_index >= len(self.storage.rules):
            messagebox.showinfo("Aviso", "Selecciona una regla de la lista.",
                                parent=self)
            return
        regla = self.storage.rules[self.rule_index]
        if messagebox.askyesno("Eliminar regla",
                               f"¿Eliminar el bloqueo de \"{regla.name}\"?",
                               parent=self):
            self.storage.remove_rule(self.rule_index)
            self.refresh_rules()

    def _pick_process(self):
        ProcesoPicker(self, on_choose=lambda nombre: self.exe_var.set(nombre))


def _fmt_segundos(seg) -> str:
    """Formatea segundos como 'HH:MM'."""
    total = int(seg)
    horas, resto = divmod(total, 3600)
    minutos = resto // 60
    return f"{horas:02d}:{minutos:02d}"