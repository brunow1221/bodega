from queue import Empty, Queue


def iniciar_despachador_ui(widget, intervalo_ms=40):
    """Prepara una cola para que los hilos no llamen directamente a Tkinter."""
    if hasattr(widget, "_cola_tareas_ui"):
        return

    widget._cola_tareas_ui = Queue()

    def procesar():
        try:
            for _ in range(100):
                try:
                    callback, args, kwargs = widget._cola_tareas_ui.get_nowait()
                except Empty:
                    break

                try:
                    callback(*args, **kwargs)
                except Exception as error:
                    print(f"Error actualizando interfaz: {error}")

            if widget.winfo_exists():
                widget.after(intervalo_ms, procesar)
        except Exception:
            # La ventana puede haberse destruido mientras terminaba un hilo.
            return

    widget.after(intervalo_ms, procesar)


def ejecutar_en_ui(widget, callback, *args, **kwargs):
    """Encola una función para ejecutarla desde el hilo principal de Tk."""
    widget._cola_tareas_ui.put((callback, args, kwargs))
