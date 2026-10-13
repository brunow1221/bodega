import tkinter as tk
import unicodedata
from tkinter import TclError, ttk


class SearchableCombobox(ttk.Frame):
    """Entrada buscable con lista flotante que conserva el foco al escribir."""

    def __init__(
        self,
        master,
        label_getter,
        search_getter=None,
        on_selected=None,
        **kwargs
    ):
        width = kwargs.pop("width", 45)
        font = kwargs.pop("font", None)
        super().__init__(master, **kwargs)

        self.label_getter = label_getter
        self.search_getter = search_getter or label_getter
        self.on_selected = on_selected
        self._items = []
        self._label_to_item = {}
        self._filtered_labels = []
        self._popup = None
        self._listbox = None
        self._scrollbar = None
        self._highlight_index = -1

        self.grid_columnconfigure(0, weight=1)
        entry_options = {"width": width}
        if font is not None:
            entry_options["font"] = font

        self.entry = ttk.Entry(self, **entry_options)
        self.entry.grid(row=0, column=0, sticky="ew")

        self.button = ttk.Button(
            self,
            text="▼",
            width=3,
            takefocus=False,
            command=self.toggle_lista
        )
        self.button.grid(row=0, column=1, sticky="ns")

        self.entry.bind("<KeyRelease>", self._on_key_release, add="+")
        self.entry.bind("<Down>", self._on_down, add="+")
        self.entry.bind("<Up>", self._on_up, add="+")
        self.entry.bind("<Return>", self._on_return, add="+")
        self.entry.bind("<Escape>", self._on_escape, add="+")
        self.entry.bind("<FocusOut>", self._on_focus_out, add="+")
        self.bind("<Configure>", self._reposicionar_popup, add="+")

    @staticmethod
    def normalizar(texto):
        base = unicodedata.normalize("NFKD", str(texto or ""))
        return "".join(c for c in base if not unicodedata.combining(c)).casefold()

    @classmethod
    def filtrar(cls, items, consulta, search_getter):
        termino = cls.normalizar(consulta).strip()
        if not termino:
            return list(items)
        palabras = termino.split()
        return [
            item
            for item in items
            if all(
                palabra in cls.normalizar(search_getter(item))
                for palabra in palabras
            )
        ]

    def set_items(self, items):
        texto_actual = self.get().strip()
        self._items = list(items or [])
        self._label_to_item = {}

        for item in self._items:
            etiqueta_base = str(self.label_getter(item)).strip()
            etiqueta = etiqueta_base
            repeticion = 2
            while etiqueta in self._label_to_item:
                etiqueta = f"{etiqueta_base} ({repeticion})"
                repeticion += 1
            self._label_to_item[etiqueta] = item

        self._mostrar_items(self._items)
        if texto_actual not in self._label_to_item:
            self.set("")

    def _mostrar_items(self, items):
        permitidos = {id(item) for item in items}
        self._filtered_labels = [
            etiqueta
            for etiqueta, item in self._label_to_item.items()
            if id(item) in permitidos
        ]
        self._highlight_index = 0 if self._filtered_labels else -1

        if self._listbox and self._listbox.winfo_exists():
            self._rellenar_listbox()

    def _rellenar_listbox(self):
        self._listbox.delete(0, "end")
        for etiqueta in self._filtered_labels:
            self._listbox.insert("end", etiqueta)
        self._marcar_indice(self._highlight_index)

    def _on_key_release(self, event=None):
        if event and event.keysym in {
            "Up", "Down", "Return", "Escape", "Tab",
            "Left", "Right", "Home", "End", "Prior", "Next"
        }:
            return

        filtrados = self.filtrar(
            self._items,
            self.get(),
            self.search_getter
        )
        self._mostrar_items(filtrados)

        if self.get().strip() and self._filtered_labels:
            self.mostrar_lista()
        else:
            self.ocultar_lista()

        # La lista flotante nunca debe interrumpir la escritura continua.
        self.entry.focus_set()

    def _crear_popup(self):
        if self._popup and self._popup.winfo_exists():
            return

        self._popup = tk.Toplevel(self)
        self._popup.withdraw()
        self._popup.overrideredirect(True)
        self._popup.transient(self.winfo_toplevel())

        frame = ttk.Frame(self._popup, relief="solid", borderwidth=1)
        frame.pack(fill="both", expand=True)

        self._scrollbar = ttk.Scrollbar(frame, orient="vertical")
        self._scrollbar.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            frame,
            activestyle="dotbox",
            exportselection=False,
            yscrollcommand=self._scrollbar.set,
            font=self.entry.cget("font"),
            borderwidth=0,
            highlightthickness=0
        )
        self._listbox.pack(side="left", fill="both", expand=True)
        self._scrollbar.configure(command=self._listbox.yview)

        self._listbox.bind("<ButtonRelease-1>", self._seleccionar_click)
        self._listbox.bind("<Motion>", self._resaltar_mouse)

    def mostrar_lista(self):
        if not self._filtered_labels:
            return
        self._crear_popup()
        self._rellenar_listbox()
        self._reposicionar_popup()
        self._popup.deiconify()
        self._popup.lift()
        self.entry.focus_set()

    def ocultar_lista(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.withdraw()

    def toggle_lista(self):
        self.entry.focus_set()
        if self._popup and self._popup.winfo_viewable():
            self.ocultar_lista()
            return

        filtrados = self.filtrar(
            self._items,
            self.get(),
            self.search_getter
        )
        self._mostrar_items(filtrados)
        self.mostrar_lista()

    def _reposicionar_popup(self, event=None):
        if not self._popup or not self._popup.winfo_exists():
            return
        try:
            self.update_idletasks()
            ancho = max(self.winfo_width(), 360)
            filas = min(max(len(self._filtered_labels), 1), 8)
            alto = filas * 28 + 4
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            self._popup.geometry(f"{ancho}x{alto}+{x}+{y}")
        except TclError:
            pass

    def _marcar_indice(self, indice):
        if not self._listbox or not self._filtered_labels:
            return
        indice = max(0, min(indice, len(self._filtered_labels) - 1))
        self._highlight_index = indice
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(indice)
        self._listbox.activate(indice)
        self._listbox.see(indice)

    def _on_down(self, event=None):
        if not self._filtered_labels:
            return "break"
        self.mostrar_lista()
        self._marcar_indice(self._highlight_index + 1)
        self.entry.focus_set()
        return "break"

    def _on_up(self, event=None):
        if not self._filtered_labels:
            return "break"
        self.mostrar_lista()
        self._marcar_indice(self._highlight_index - 1)
        self.entry.focus_set()
        return "break"

    def _on_return(self, event=None):
        if self.get() in self._label_to_item:
            self._notificar_seleccion()
        elif self._filtered_labels:
            indice = max(self._highlight_index, 0)
            self.set(self._filtered_labels[indice])
            self._notificar_seleccion()
        self.ocultar_lista()
        return "break"

    def _on_escape(self, event=None):
        self.ocultar_lista()
        return "break"

    def _seleccionar_click(self, event=None):
        seleccion = self._listbox.curselection()
        if seleccion:
            self.set(self._listbox.get(seleccion[0]))
            self._notificar_seleccion()
        self.ocultar_lista()
        self.entry.focus_set()
        return "break"

    def _resaltar_mouse(self, event):
        if self._listbox.size() > 0:
            self._marcar_indice(self._listbox.nearest(event.y))

    def _notificar_seleccion(self):
        item = self.get_selected()
        if item is not None and self.on_selected:
            self.on_selected(item)

    def _on_focus_out(self, event=None):
        self.after(120, self._ocultar_si_perdio_foco)

    def _ocultar_si_perdio_foco(self):
        try:
            foco = self.focus_get()
            if foco not in (self.entry, self._listbox):
                self.ocultar_lista()
        except TclError:
            pass

    def get(self):
        return self.entry.get()

    def set(self, valor):
        self.entry.delete(0, "end")
        self.entry.insert(0, str(valor or ""))

    def delete(self, first, last=None):
        self.entry.delete(first, last)

    def insert(self, index, texto):
        self.entry.insert(index, texto)

    def focus_set(self):
        self.entry.focus_set()

    def get_selected(self):
        return self._label_to_item.get(self.get().strip())

    def clear(self):
        self.set("")
        self._mostrar_items(self._items)
        self.ocultar_lista()

    def destroy(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        super().destroy()

