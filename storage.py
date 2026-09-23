# -*- coding: utf-8 -*-
"""Persistencia local en JSON.

Guarda en disco las reglas de bloqueo y los tiempos de uso acumulados por
día y aplicación. El acceso está protegido con un candado para poder usarse
desde varios hilos (el monitor escribe mientras la interfaz consulta).
"""
import json
import os
import threading
from datetime import date

import config
from models import BlockRule


class Storage:
    """Repositorio en memoria + disco de reglas y tiempos de uso."""

    RETENCION_DIAS = 90  # se descartan registros de uso más antiguos

    def __init__(self):
        self._lock = threading.RLock()
        self.rules = []   # lista de BlockRule
        self.usage = {}   # {fecha "YYYY-MM-DD": {ejecutable: segundos(float)}}
        self._load()

    # ==================== carga / guardado ====================
    def _load(self):
        try:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        try:
            datos = self._read_json(config.RULES_FILE, [])
            self.rules = [BlockRule.from_dict(d) for d in datos if isinstance(d, dict)]
        except Exception:
            self.rules = []

        try:
            datos = self._read_json(config.USAGE_FILE, {})
            self.usage = datos if isinstance(datos, dict) else {}
        except Exception:
            self.usage = {}

        self._prune()

    @staticmethod
    def _read_json(path, default):
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def save(self):
        """Vuelca reglas y tiempos a disco de forma atómica."""
        with self._lock:
            self._write_json(config.RULES_FILE, [r.to_dict() for r in self.rules])
            self._write_json(config.USAGE_FILE, self.usage)

    @staticmethod
    def _write_json(path, data):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)  # escritura atómica: no corrompe el fichero

    def _prune(self):
        """Elimina registros de uso más antiguos que RETENCION_DIAS."""
        limite = {d for d in list(self.usage)}
        # se borra lo que no esté dentro del horizonte de retención
        for clave in list(self.usage):
            try:
                dia = date.fromisoformat(clave)
                if (date.today() - dia).days > self.RETENCION_DIAS:
                    del self.usage[clave]
            except ValueError:
                del self.usage[clave]
        _ = limite

    # ==================== tiempos de uso ====================
    def add_usage(self, exe, seconds, day: date):
        """Suma `seconds` a la aplicación `exe` en la fecha `day`."""
        if seconds <= 0 or not exe:
            return
        with self._lock:
            clave = day.strftime(config.DATE_FMT)
            bucket = self.usage.setdefault(clave, {})
            bucket[exe] = bucket.get(exe, 0) + seconds

    def usage_for(self, day: date) -> dict:
        """Devuelve {ejecutable: segundos} ordenado de mayor a menor."""
        with self._lock:
            bucket = self.usage.get(day.strftime(config.DATE_FMT), {})
            return dict(sorted(bucket.items(), key=lambda kv: kv[1], reverse=True))

    def available_dates(self) -> list:
        """Fechas con datos almacenados, de la más reciente a la más antigua."""
        with self._lock:
            return sorted(self.usage.keys(), reverse=True)

    # ==================== reglas ====================
    def add_rule(self, rule: BlockRule) -> int:
        """Añade una regla y la guarda. Devuelve el índice asignado."""
        with self._lock:
            self.rules.append(rule)
            self.save()
            return len(self.rules) - 1

    def update_rule(self, index: int, rule: BlockRule):
        """Sustituye la regla del índice dado."""
        with self._lock:
            if 0 <= index < len(self.rules):
                self.rules[index] = rule
                self.save()

    def remove_rule(self, index: int) -> bool:
        """Elimina la regla del índice dado."""
        with self._lock:
            if 0 <= index < len(self.rules):
                del self.rules[index]
                self.save()
                return True
            return False