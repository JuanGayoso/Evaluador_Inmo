from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Static

from engine.storage import Archivo
from ui.comunes import recalcular


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:,.2f}"


class PantallaIngresos(Screen):
    """Tabla de Ingresos, subtotalizada por familia."""

    BINDINGS = [
        ("f2", "nueva", "Nueva partida"),
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
        yield Static("INGRESOS", id="titulo")
        yield Static("ENTER edita, F2 agrega una partida nueva.", id="subtitulo", classes="migaja")
        with Vertical(classes="panel"):
            yield DataTable(id="tabla_ingresos", cursor_type="row", zebra_stripes=False)
        with Horizontal():
            yield Button("+ Nueva (F2)", id="btn_nueva", variant="primary")
            yield Button("Historial (F6)", id="btn_historial")
            yield Button("Eliminar (F8)", id="btn_eliminar")
            yield Button("Volver (Esc)", id="btn_volver")
        yield Footer()

    def on_mount(self) -> None:
        tabla = self.query_one("#tabla_ingresos", DataTable)
        tabla.add_columns(
            "Código", "Nombre var.", "Familia", "Descripción", "Cantidad", "Precio",
            "Monto", "Mon.", "Tipo IGV", "IGV", "Parcial", "Parcial (ppal)",
        )
        tabla.focus()
        self.recargar()

    def on_screen_resume(self) -> None:
        self.recargar()

    def recargar(self) -> None:
        tabla = self.query_one("#tabla_ingresos", DataTable)
        fila_previa = tabla.cursor_row
        tabla.clear()

        resultado = recalcular(self.archivo)
        lineas = self.archivo.listar_ingresos_todos()

        etiquetas_igv = {"ninguno": "no gravado", "afecto_18": "18% regular", "inmobiliario_9": "9% inmobiliario"}

        familias: dict[str, list] = {}
        for i in lineas:
            familias.setdefault(i.familia or "(sin familia)", []).append(i)

        for familia, items in familias.items():
            tabla.add_row(Text(f"── {familia} ──", style="bold black on cyan"), *[""] * 11, key=f"__familia__{familia}")
            subtotal = 0.0
            for i in items:
                r = resultado.ingresos.get(i.codigo)
                error = bool(r and r.error)
                estilo = "bold red" if error else None
                descripcion = i.descripcion + (f"   ! {r.error}" if error else "")
                fila = [
                    str(i.codigo), i.nombre_variable or "", i.familia, descripcion,
                    _fmt(r.cantidad) if r else "—",
                    _fmt(r.precio) if r else "—",
                    _fmt(r.monto) if r else "—",
                    i.moneda,
                    etiquetas_igv.get(i.tipo_igv, i.tipo_igv),
                    _fmt(r.igv) if r else "—",
                    _fmt(r.parcial) if r else "—",
                    _fmt(r.monto_moneda_principal) if r else "—",
                ]
                if estilo:
                    fila = [Text(str(c), style=estilo) for c in fila]
                tabla.add_row(*fila, key=str(i.codigo))
                if r and r.monto_moneda_principal is not None:
                    subtotal += r.monto_moneda_principal
            tabla.add_row(
                "", "", "", Text(f"Subtotal {familia} (neto)", style="bold yellow"),
                "", "", "", "", "", "", "", Text(_fmt(subtotal), style="bold yellow"),
                key=f"__subtotal__{familia}",
            )

        if not lineas:
            tabla.add_row("—", "", "", "(sin partidas — F2 para agregar la primera)", *[""] * 8, key="__vacio__")

        if tabla.row_count and fila_previa is not None:
            tabla.move_cursor(row=min(fila_previa, tabla.row_count - 1))

    def _codigo_seleccionado(self) -> int | None:
        tabla = self.query_one("#tabla_ingresos", DataTable)
        if tabla.row_count == 0 or tabla.cursor_row is None:
            return None
        row_key, _ = tabla.coordinate_to_cell_key(tabla.cursor_coordinate)
        valor = row_key.value if row_key else None
        if valor is None or not str(valor).isdigit():
            return None
        return int(valor)

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

    @on(DataTable.RowSelected, "#tabla_ingresos")
    def _fila_activada(self, event: DataTable.RowSelected) -> None:
        self.action_editar()

    def action_nueva(self) -> None:
        from .editar_ingreso import PantallaEditarIngreso

        self.app.push_screen(PantallaEditarIngreso(self.archivo, None), lambda _=None: self.recargar())

    def action_editar(self) -> None:
        from .editar_ingreso import PantallaEditarIngreso

        codigo = self._codigo_seleccionado()
        if codigo is None:
            return
        i = self.archivo.obtener_ingreso(codigo)
        self.app.push_screen(PantallaEditarIngreso(self.archivo, i), lambda _=None: self.recargar())

    def action_historial(self) -> None:
        from .historial import PantallaHistorial

        codigo = self._codigo_seleccionado()
        if codigo is not None:
            i = self.archivo.obtener_ingreso(codigo)
            nombre = i.nombre_variable or f"Ingreso #{codigo}"
            self.app.push_screen(PantallaHistorial(self.archivo, "ingreso", codigo, nombre))

    def action_eliminar(self) -> None:
        codigo = self._codigo_seleccionado()
        if codigo is not None:
            self.archivo.eliminar_ingreso(codigo)
            self.recargar()

    def action_recalcular(self) -> None:
        self.recargar()

    def action_volver(self) -> None:
        self.app.pop_screen()
