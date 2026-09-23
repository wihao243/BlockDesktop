# -*- coding: utf-8 -*-
"""Modelo de datos.

Define la estructura de una regla de bloqueo y utilidades para manejar
fechas y horas de forma legible.
"""
from dataclasses import dataclass, field
from datetime import datetime

# 0 = Lunes ... 6 = Domingo (mismo orden que datetime.weekday())
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
DIAS_CORTOS = ["L", "M", "X", "J", "V", "S", "D"]


def fmt_min(minutos: int) -> str:
    """Convierte minutos desde medianoche en texto 'HH:MM'."""
    minutos = max(0, int(minutos))
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


@dataclass
class BlockRule:
    """Regla que prohíbe abrir un ejecutable en determinados días y horas.

    Atributos:
        name:      etiqueta legible elegida por el usuario (ej. "Chrome").
        exe:       nombre del proceso/ejecutable (ej. "chrome.exe").
        days:      lista de días de la semana (0=Lunes ... 6=Domingo).
        start_min: hora de inicio del bloqueo en minutos desde las 00:00.
        end_min:   hora de fin del bloqueo.
    """

    name: str = ""
    exe: str = ""
    days: list = field(default_factory=list)
    start_min: int = 0
    end_min: int = 0

    # ---------- serialización ----------
    @classmethod
    def from_dict(cls, d: dict) -> "BlockRule":
        """Reconstruye una regla desde un diccionario (JSON)."""
        return cls(
            name=str(d.get("name", "")),
            exe=str(d.get("exe", "")),
            days=list(d.get("days", []) or []),
            start_min=int(d.get("start_min", 0)),
            end_min=int(d.get("end_min", 0)),
        )

    def to_dict(self) -> dict:
        """Convierte la regla a diccionario para guardarla en JSON."""
        return {
            "name": self.name,
            "exe": self.exe,
            "days": sorted(self.days),
            "start_min": self.start_min,
            "end_min": self.end_min,
        }

    # ---------- texto legible ----------
    def hours_str(self) -> str:
        return f"{fmt_min(self.start_min)} - {fmt_min(self.end_min)}"

    def days_str(self) -> str:
        if len(self.days) == 7:
            return "Todos los días"
        if len(self.days) == 5 and set(self.days) == {0, 1, 2, 3, 4}:
            return "Solo laborables"
        if len(self.days) == 2 and set(self.days) == {5, 6}:
            return "Solo fin de semana"
        return ", ".join(DIAS[d] for d in sorted(self.days))

    def describe(self) -> str:
        """Descripción corta usada en los avisos de bloqueo."""
        return f"{self.name} ({self.exe}) — {self.days_str()} {self.hours_str()}"

    # ---------- lógica temporal ----------
    def matches(self, dt: datetime) -> bool:
        """¿La regla está activa en el instante `dt`?

        Soporta rangos que cruzan medianoche (p. ej. 22:00 → 02:00) y el
        caso especial en que inicio == fin, interpretado como "todo el día".
        """
        ahora = dt.hour * 60 + dt.minute
        wd = dt.weekday()
        prev_wd = (wd - 1) % 7  # día anterior (para rangos nocturnos)

        if self.start_min < self.end_min:
            # rango normal dentro del mismo día
            return wd in self.days and self.start_min <= ahora < self.end_min

        if self.start_min == self.end_min:
            # inicio == fin  =>  bloqueo durante todo ese día
            return wd in self.days

        # Cruza medianoche: activa desde `start` en los días indicados y,
        # además, hasta `end` en el día siguiente si ese día también está marcado.
        en_dia_inicio = wd in self.days and ahora >= self.start_min
        en_dia_anterior = prev_wd in self.days and ahora < self.end_min
        return en_dia_inicio or en_dia_anterior

    def valid(self) -> bool:
        """Comprueba que la regla tenga datos mínimos coherentes."""
        return bool(self.name.strip()) and bool(self.exe.strip()) and bool(self.days)