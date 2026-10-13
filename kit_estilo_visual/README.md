# Kit de estilo visual y zoom

Este directorio es una plantilla portable para aplicaciones de escritorio hechas con Python y CustomTkinter. Reproduce el lenguaje visual del Sistema de Gestión de Bodega sin depender del resto del proyecto.

## Vista general

- Fondo general azul muy claro: `#edf5fb`.
- Paneles blancos con borde azul: `#ffffff` / `#1659af`.
- Acción principal azul: `#1d4ed8`; al pasar el mouse: `#1e40af`.
- Texto principal casi negro: `#0f172a`; texto secundario: `#64748b`.
- Estados: verde `#0f766e`, rojo `#b91c1c` y ámbar `#b7791f`.
- Tipografía: Segoe UI, títulos en negrita, bordes redondeados de 8 a 10 px.
- Las tablas usan encabezado celeste, selección azul y colores suaves para stock bajo o crítico.

## Ejecutar la muestra

Desde este directorio:

```powershell
python -m pip install -r requirements.txt
python ejemplo.py
```

Para reutilizarlo, copie este directorio dentro de la otra aplicación e importe lo necesario:

```python
import customtkinter as ctk
from tkinter import ttk

from kit_estilo_visual.tema import (
    PALETA,
    aplicar_tema_base,
    configurar_treeview_global,
    estilos_boton,
    estilos_panel,
)
from kit_estilo_visual.zoom import GestorZoom


class MiAplicacion(ctk.CTk):
    def __init__(self):
        aplicar_tema_base()
        super().__init__()
        self.configure(fg_color=PALETA["fondo"])

        self.estilo_tablas = ttk.Style(self)
        self.zoom = GestorZoom(
            self,
            nombre_aplicacion="MiAplicacion",
            al_cambiar=self.actualizar_tablas,
        )

        barra = ctk.CTkFrame(self, **estilos_panel())
        barra.pack(fill="x", padx=20, pady=12)
        self.zoom.crear_controles(barra).pack(side="right", padx=10, pady=6)

        ctk.CTkButton(
            self,
            text="Guardar",
            **estilos_boton("primario"),
        ).pack(pady=20)

    def actualizar_tablas(self, escala):
        configurar_treeview_global(self.estilo_tablas, escala)
```

## Configuración del zoom

La configuración predeterminada es:

```python
GestorZoom(
    ventana=self,
    nombre_aplicacion="MiAplicacion",
    zoom_predeterminado=100,
    zoom_minimo=80,
    zoom_maximo=160,
    paso=10,
    al_cambiar=self.actualizar_tablas,
)
```

- `zoom_predeterminado`: tamaño utilizado la primera vez y al restablecer.
- `zoom_minimo` y `zoom_maximo`: límites permitidos.
- `paso`: aumento o disminución de cada clic.
- `nombre_aplicacion`: nombre de la carpeta donde se guarda la preferencia.
- `al_cambiar`: función opcional que recibe la escala decimal; se usa para actualizar componentes `ttk`, como `Treeview`, que no siguen automáticamente todo el escalado de CustomTkinter.

El gestor aplica simultáneamente:

```python
ctk.set_widget_scaling(escala)
ctk.set_window_scaling(escala)
```

Los controles `−`, porcentaje y `+` se crean con `crear_controles()`. Al pulsar el porcentaje se restablece a 100 %. También quedan disponibles:

- `Ctrl` + `+`: aumentar.
- `Ctrl` + `-`: disminuir.
- `Ctrl` + `0`: restablecer.

La selección queda guardada en Windows en `%LOCALAPPDATA%\MiAplicacion\preferencias.json`, por lo que se mantiene al cerrar y volver a abrir el programa.

El zoom de CustomTkinter es global para el proceso. Debe crearse un solo `GestorZoom` en la ventana principal y compartir su escala con tablas u otros componentes `ttk` mediante `al_cambiar`.
