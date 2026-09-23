# BlockDesktop

Aplicación de escritorio (Windows) para el control del tiempo de uso del
ordenador y el bloqueo de aplicaciones por horarios.

**PIN obligatorio: `18032008`** — toda la interfaz (ver estadísticas,
gestionar bloqueos y cerrar la aplicación) queda bloqueada hasta introducirlo.

---

## 1. Características

- **Monitorización en segundo plano.** Detecta la ventana en primer plano y
  acumula el tiempo (h/m) que pasas en cada aplicación, día a día.
- **Bloqueo por horarios.** Eliges el ejecutable (p. ej. `chrome.exe`), los
  días de la semana y una franja horaria. Si un proceso bloqueado se abre
  dentro de su horario restringido, se cierra forzosamente y aparece una
  alerta en pantalla.
- **Protección por PIN.** La ventana arranca bloqueada. Sin el PIN no se
  pueden ver datos, añadir/quitar reglas ni cerrar el programa. El botón X
  de la ventana también pide el PIN.
- **Persistencia local.** Las reglas y los tiempos de uso se guardan en JSON
  en `%USERPROFILE%\.blockdesktop\` y sobreviven al apagado del equipo.

---

## 2. Tecnología elegida

| Componente | Tecnología | Motivo |
|---|---|---|
| Lenguaje | Python 3.9+ | Rápido de desarrollar, multiplataforma, amplia biblioteca |
| Ventana activa | `ctypes` + Win32 API | Sin dependencias extra, detecta el ejecutable y título |
| Procesos | `psutil` | Listar, buscar y terminar procesos de forma fiable |
| Interfaz | `Tkinter` / `ttk` | Incluida con Python: sin instalación adicional |
| Persistencia | JSON local | Simple, legible y suficiente para estos datos |

Alternativas consideradas: **C#/WPF** (mejor rendimiento y tray nativo pero
requiere Visual Studio y .NET) y **PyQt6** (más bonito pero más pesado).
Para este caso, Python + Tkinter es la opción más ligera y fácil de
mantener.

---

## 3. Estructura del proyecto

```
BlockDesktop/
├── main.py          # Punto de entrada: instancia única, hilos y ciclo GUI
├── config.py        # Constantes: PIN, directorio de datos, parámetros
├── models.py        # Modelo de regla de bloqueo y utilidades de horas
├── storage.py       # Persistencia JSON segura para múltiples hilos
├── monitor.py       # Hilo que muestrea la ventana activa (tiempos)
├── blocker.py       # Motor de bloqueo: cierra procesos y emite alertas
├── auth.py          # Diálogo modal de código PIN
├── ui.py            # Interfaz: pestañas Estadísticas y Reglas de Bloqueo
├── requirements.txt # Dependencias
└── README.md        # Este documento
```

### Flujo interno

```
main.py
 ├─ storage.Storage            (reglas + tiempos, JSON en disco)
 ├─ blocker.Blocker            (comprueba reglas, mata procesos, alertas)
 ├─ monitor.UsageMonitor       (hilo en segundo plano cada 2 s)
 └─ GUI
     ├─ Pantalla bloqueada     (pide PIN 18032008)
     └─ Panel de control       (2 pestañas: Estadísticas y Reglas)
```

`monitor` alimenta `storage` (tiempos) y `blocker` (bloqueos) a través de
una cola de eventos que la GUI consume para mostrar las alertas.

---

## 4. Instalación

1. **Python.** Descarga e instala Python 3.9+ desde
   <https://www.python.org/downloads/> marcando *"Add Python to PATH"*.
   Tkinter viene incluido por defecto en el instalador de Windows.

2. **Dependencias.** Dentro de la carpeta del proyecto:

   ```powershell
   cd BlockDesktop
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   (Solo instala `psutil`; el resto es biblioteca estándar.)

   > **Varios Python instalados:** si `python --version` no corresponde al
   > Python de python.org (p. ej. apunta a MSYS2/conda sin `pip` ni Tkinter),
   > usa el intérprete correcto, por ejemplo:
   > `& "C:\Users\TuUsuario\AppData\Local\Programs\Python\Python313\python.exe" -m pip install -r requirements.txt`
   > para instalar, y el mismo ejecutable para lanzar `main.py`.

3. **Comprobar** que los módulos compilan:

   ```powershell
   python -m py_compile main.py config.py models.py storage.py monitor.py blocker.py auth.py ui.py
   ```

---

## 5. Ejecución

```powershell
python main.py
```

Aparecerá la pantalla de bloqueo. Introduce el PIN `18032008` para abrir el
panel de control.

### Ejecución en segundo plano

El monitor y el bloqueo funcionan **siempre**, aunque la ventana esté
bloqueada o minimizada:

- Minimiza la ventana normal (`python main.py`). El proceso sigue activo.
- Para arrancar sin consola, usa `pythonw main.py` (no abre la terminal).
- **Arranque automático al iniciar Windows:** crea un acceso directo a
  `pythonw.exe` con el argumento `main.py` y colócalo en:
  `Win+R` → `shell:startup` → Enter. O ejecuta:

  ```powershell
  $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut(
      "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\BlockDesktop.lnk")
  $lnk.TargetPath = "$env:WINDIR\System32\pythonw.exe"
  $lnk.Arguments = '"C:\ruta\al\BlockDesktop\main.py"'
  $lnk.WorkingDirectory = 'C:\ruta\al\BlockDesktop'
  $lnk.Save()
  ```

- Para retirarlo del arranque, borra el acceso directo o termina el proceso
  desde el Administrador de tareas (requiere autorización por PIN desde la
  propia aplicación para cerrarse con normalidad).

> ¿Por qué no un icono de bandeja? Para no añadir dependencias pesadas
> (`pystray` + `Pillow`). El programa se controla íntegramente desde la
> ventana (bloqueada por PIN), que puede minimizarse al icono normal.

---

## 6. Uso

### Estadísticas
Pestaña **Estadísticas**: elige el día y verás el tiempo de uso por
aplicación (ordenado de mayor a menor) y el total. Se actualiza sola si el
día seleccionado es hoy.

### Reglas de bloqueo
1. Pulsa **Buscar…** para elegir un proceso en ejecución, o escribe el
   ejecutable a mano (p. ej. `notepad.exe`, `leagueclient.exe`).
2. Marca los **días** (L, M, X, J, V, S, D) y la **franja horaria**.
3. Pulsa **Añadir**. Para editar, selecciona la regla, cambia los datos y
   pulsa **Actualizar**; para borrarla, **Eliminar**.

Detalles de horarios:
- `Desde = Hasta` → bloqueo durante **todo el día**.
- Hora de **fin anterior a la de inicio** → rango nocturno que cruza
  medianoche (p. ej. 22:00 → 02:00). Para que la parte "hasta" cubra el día
  siguiente, ese día también debe estar marcado.

### Alertas
Cuando un proceso bloqueado intente abrirse, se cerrará en un máximo de
~2 segundos y verás un aviso en pantalla con el motivo. Los avisos del mismo
proceso llevan 15 s de silencio para no saturar.

### Seguridad
- El PIN se comprueba por **término exacto**: `18032008`.
- Para cambiarlo, edita `SECURITY_PIN` en `config.py`.
- Solo hay una instancia en ejecución (bloqueo por puerto local).
- La aplicación nunca se bloquea ni se cierra a sí misma.

---

## 7. Datos guardados

En `%USERPROFILE%\.blockdesktop\`:

| Fichero | Contenido |
|---|---|
| `rules.json` | Reglas de bloqueo (proceso, días, horario) |
| `usage.json` | `{fecha: {ejecutable: segundos}}` por día |

Los registros de uso se conservan 90 días y luego se purgan. Para empezar de
cero, detén el programa y borra esa carpeta.

---

## 8. Limitaciones y notas

- Funciona en **Windows** (usa la API Win32 de ventana activa).
- Los procesos que se ejecutan con **privilegios de administrador** pueden
  no poder cerrarse si BlockDesktop no corre también como administrador.
- Un usuario con permisos de administrador puede terminar el proceso desde
  el Administrador de tareas; es una limitación inherente a cualquier app de
  autocontrol, no una vulnerabilidad del programa.
- El tiempo se asigna por **ejecutable**; aplicaciones como Chrome
  (muchas ventanas/procesos) se contabilizan como una sola entrada.