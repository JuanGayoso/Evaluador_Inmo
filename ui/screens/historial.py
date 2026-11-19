from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from engine.storage import Archivo


class PantallaHistorial(Screen):
    """Historial de cambios de una variable/egreso/ingreso: que formula
    tenia antes, cual tiene ahora, y cuando cambio."""

    BINDINGS = [("escape", "volver", "Volver"), ("f10", "volver", "Volver")]

    def __init__(self, archivo: Archivo, tipo: str, identificador, nombre_visible: str):
        super().__init__()
        self.archivo = archivo
        self.tipo = tipo
        self.identificador = identificador
        self.nombre_visible = nombre_visible

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"HISTORIAL DE CAMBIOS: {self.nombre_visible}", id="titulo")
        with Vertical(classes="panel"):
            yield DataTable(id="tabla_historial", cursor_type="row")
        with Horizontal():
            yield Button("Volver (Esc)", id="btn_volver")
        yield Footer()

    def on_mount(self) -> None:
        tabla = self.query_one("#tabla_historial", DataTable)
        tabla.add_columns("Cuándo", "Campo", "Valor anterior", "Valor nuevo")
        filas = self.archivo.historial_de(self.tipo, self.identificador)
        for fila in filas:
            tabla.add_row(fila["cuando"] or "", fila["campo"] or "", fila["valor_anterior"] or "(vacío)", fila["valor_nuevo"] or "(vacío)")
        if not filas:
            tabla.add_row("—", "—", "sin cambios registrados todavía", "—")
        tabla.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_volver":
            self.action_volver()

    def action_volver(self) -> None:
        self.app.pop_screen()
