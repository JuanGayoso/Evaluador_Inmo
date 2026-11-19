from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from engine.storage import Archivo
from ui.comunes import recalcular


def _fmt(v) -> str:
    if v is None:
        return "—"
    return f"{v:,.4f}".rstrip("0").rstrip(".")


class PantallaVariables(Screen):
    """Variables generales del proyecto — ahora tambien pueden tener
    formula (no solo ser un input suelto), como cualquier partida."""

    BINDINGS = [
        ("f2", "nueva", "Nueva variable"),
        ("enter", "editar", "Editar"),
        ("f6", "historial", "Historial"),
        ("f8", "eliminar", "Eliminar"),
        ("f9", "recalcular", "Recalcular"),
        ("escape", "volver", "Volver"),
        ("f10", "volver", "Volver"),
    ]

    def __init__(self, archivo: Archivo):
        super().__init__()
        self.archivo = archivo

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("VARIABLES GENERALES DEL PROYECTO", id="titulo")
        yield Static("ENTER edita la variable seleccionada. F2 crea una nueva.", id="subtitulo")
        with Vertical(classes="panel"):
            yield DataTable(id="tabla_variables", cursor_type="row")
        with Horizontal():
            yield Button("+ Nueva (F2)", id="btn_nueva", variant="primary")
            yield Button("Historial (F6)", id="btn_historial")
            yield Button("Eliminar (F8)", id="btn_eliminar")
            yield Button("Volver (Esc)", id="btn_volver")
        yield Footer()

    def on_mount(self) -> None:
        tabla = self.query_one("#tabla_variables", DataTable)
        tabla.add_columns("Nombre", "Descripción", "Fórmula / Valor", "Unidad", "Resultado")
        tabla.focus()
        self.recargar()

    def on_screen_resume(self) -> None:
        self.recargar()

    def recargar(self) -> None:
        tabla = self.query_one("#tabla_variables", DataTable)
        fila_previa = tabla.cursor_row
        tabla.clear()
        resultado = recalcular(self.archivo)
        for v in self.archivo.listar_variables():
            r = resultado.variables.get(v.nombre_variable)
            valor_txt = _fmt(r.valor) if r and r.error is None else (f"! {r.error}" if r else "—")
            tabla.add_row(v.nombre_variable, v.descripcion, v.formula or "(en blanco)", v.unidad, valor_txt, key=v.nombre_variable)
        if not self.archivo.listar_variables():
            tabla.add_row("—", "(sin variables — F2 para agregar la primera)", "", "", "", key="__vacio__")
        if tabla.row_count and fila_previa is not None:
            tabla.move_cursor(row=min(fila_previa, tabla.row_count - 1))

    def _nombre_seleccionado(self) -> str | None:
        tabla = self.query_one("#tabla_variables", DataTable)
        if tabla.row_count == 0 or tabla.cursor_row is None:
            return None
        row_key, _ = tabla.coordinate_to_cell_key(tabla.cursor_coordinate)
        valor = str(row_key.value) if row_key else None
        return None if valor == "__vacio__" else valor

    @on(Button.Pressed, "#btn_nueva")
    def _click_nueva(self) -> None:
        self.action_nueva()

    @on(Button.Pressed, "#btn_historial")
    def _click_historial(self) -> None:
        self.action_historial()

    @on(Button.Pressed, "#btn_eliminar")
    def _click_eliminar(self) -> None:
        self.action_eliminar()

    @on(Button.Pressed, "#btn_volver")
    def _click_volver(self) -> None:
        self.action_volver()

    @on(DataTable.RowSelected, "#tabla_variables")
    def _fila_activada(self, event: DataTable.RowSelected) -> None:
        self.action_editar()

    def action_nueva(self) -> None:
        from .editar_variable import PantallaEditarVariable

        self.app.push_screen(PantallaEditarVariable(self.archivo, None), lambda _=None: self.recargar())

    def action_editar(self) -> None:
        from .editar_variable import PantallaEditarVariable

        nombre = self._nombre_seleccionado()
        if nombre is None:
            return
        v = self.archivo.obtener_variable(nombre)
        self.app.push_screen(PantallaEditarVariable(self.archivo, v), lambda _=None: self.recargar())

    def action_historial(self) -> None:
        from .historial import PantallaHistorial

        nombre = self._nombre_seleccionado()
        if nombre is not None:
            self.app.push_screen(PantallaHistorial(self.archivo, "variable", nombre, nombre))

    def action_eliminar(self) -> None:
        nombre = self._nombre_seleccionado()
        if nombre is not None:
            self.archivo.eliminar_variable(nombre)
            self.recargar()

    def action_recalcular(self) -> None:
        self.recargar()

    def action_volver(self) -> None:
        self.app.pop_screen()
