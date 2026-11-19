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


class PantallaEgresos(Screen):
    """Tabla de Egresos, con subtotales por grupo y navegacion de
    entrar/salir de sub-presupuestos (una partida puede contener otras)."""

    BINDINGS = [
        ("f2", "nueva", "Nueva partida"),
        ("enter", "abrir", "Abrir / Entrar"),
        ("f5", "editar", "Editar datos"),
        ("f6", "historial", "Historial"),
        ("f8", "eliminar", "Eliminar"),
        ("f9", "recalcular", "Recalcular"),
        ("escape", "volver", "Volver"),
        ("f10", "volver", "Volver"),
    ]

    def __init__(self, archivo: Archivo, padre_codigo: int | None = None, nombre_padre: str = ""):
        super().__init__()
        self.archivo = archivo
        self.padre_codigo = padre_codigo
        self.nombre_padre = nombre_padre

    def compose(self) -> ComposeResult:
        yield Header()
        titulo = "EGRESOS" if self.padre_codigo is None else f"EGRESOS — dentro de: {self.nombre_padre}"
        yield Static(titulo, id="titulo")
        migaja = (
            "Presupuesto principal de egresos."
            if self.padre_codigo is None
            else "ESC para volver al nivel anterior."
        )
        yield Static(migaja, id="subtitulo", classes="migaja")
        with Vertical(classes="panel"):
            yield DataTable(id="tabla_egresos", cursor_type="row", zebra_stripes=False)
        with Horizontal():
            yield Button("+ Nueva (F2)", id="btn_nueva", variant="primary")
            yield Button("Editar datos (F5)", id="btn_editar")
            yield Button("Historial (F6)", id="btn_historial")
            yield Button("Eliminar (F8)", id="btn_eliminar")
            yield Button("Volver (Esc)", id="btn_volver")
        yield Footer()

    def on_mount(self) -> None:
        tabla = self.query_one("#tabla_egresos", DataTable)
        tabla.add_columns(
            "Código", "Nombre var.", "Descripción", "Unidad", "Cantidad", "Precio",
            "Monto", "Mon.", "IGV", "Parcial", "Parcial (ppal)",
        )
        tabla.focus()
        self.recargar()

    def on_screen_resume(self) -> None:
        self.recargar()

    def recargar(self) -> None:
        tabla = self.query_one("#tabla_egresos", DataTable)
        fila_previa = tabla.cursor_row
        tabla.clear()

        resultado = recalcular(self.archivo)
        lineas = self.archivo.listar_egresos_hijos(self.padre_codigo)

        grupos: dict[str, list] = {}
        for e in lineas:
            grupos.setdefault(e.grupo or "(sin grupo)", []).append(e)

        for grupo, items in grupos.items():
            tabla.add_row(Text(f"── {grupo} ──", style="bold black on cyan"), *[""] * 10, key=f"__grupo__{grupo}")
            subtotal = 0.0
            for e in items:
                r = resultado.egresos.get(e.codigo)
                error = bool(r and r.error)
                estilo = "bold red" if error else None
                nombre = e.nombre_variable or ""
                descripcion = e.descripcion + ("  ▶ sub-presupuesto" if e.es_subpresupuesto else "")
                if error:
                    descripcion += f"   ! {r.error}"
                fila = [
                    str(e.codigo), nombre, descripcion, e.unidad,
                    _fmt(r.cantidad) if r else "—",
                    _fmt(r.precio) if r else "—",
                    _fmt(r.monto) if r else "—",
                    e.moneda,
                    "sí" if e.afecto_igv else "",
                    _fmt(r.parcial) if r else "—",
                    _fmt(r.parcial_moneda_principal) if r else "—",
                ]
                if estilo:
                    fila = [Text(str(c), style=estilo) for c in fila]
                tabla.add_row(*fila, key=str(e.codigo))
                if r and r.parcial_moneda_principal is not None:
                    subtotal += r.parcial_moneda_principal
            tabla.add_row(
                Text("", style="bold"), "", Text(f"Subtotal {grupo}", style="bold yellow"),
                "", "", "", "", "", "", "", Text(_fmt(subtotal), style="bold yellow"),
                key=f"__subtotal__{grupo}",
            )

        if not lineas:
            tabla.add_row("—", "", "(sin partidas — F2 para agregar la primera)", *[""] * 8, key="__vacio__")

        if tabla.row_count and fila_previa is not None:
            tabla.move_cursor(row=min(fila_previa, tabla.row_count - 1))

    def _codigo_seleccionado(self) -> int | None:
        tabla = self.query_one("#tabla_egresos", DataTable)
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

    @on(Button.Pressed, "#btn_editar")
    def _click_editar(self) -> None:
        self.action_editar()

    @on(Button.Pressed, "#btn_historial")
    def _click_historial(self) -> None:
        self.action_historial()

    @on(Button.Pressed, "#btn_eliminar")
    def _click_eliminar(self) -> None:
        self.action_eliminar()

    @on(Button.Pressed, "#btn_volver")
    def _click_volver(self) -> None:
        self.action_volver()

    @on(DataTable.RowSelected, "#tabla_egresos")
    def _fila_activada(self, event: DataTable.RowSelected) -> None:
        # doble click / Enter sobre la tabla: mismo comportamiento que Enter
        self.action_abrir()

    def action_nueva(self) -> None:
        from .editar_egreso import PantallaEditarEgreso

        self.app.push_screen(
            PantallaEditarEgreso(self.archivo, None, padre_codigo=self.padre_codigo),
            lambda _=None: self.recargar(),
        )

    def action_abrir(self) -> None:
        codigo = self._codigo_seleccionado()
        if codigo is None:
            return
        e = self.archivo.obtener_egreso(codigo)
        if e is None:
            return
        if e.es_subpresupuesto:
            self.app.push_screen(PantallaEgresos(self.archivo, padre_codigo=e.codigo, nombre_padre=e.nombre_variable or e.descripcion))
        else:
            self._editar(codigo)

    def action_editar(self) -> None:
        codigo = self._codigo_seleccionado()
        if codigo is not None:
            self._editar(codigo)

    def _editar(self, codigo: int) -> None:
        from .editar_egreso import PantallaEditarEgreso

        e = self.archivo.obtener_egreso(codigo)
        self.app.push_screen(
            PantallaEditarEgreso(self.archivo, e, padre_codigo=self.padre_codigo),
            lambda _=None: self.recargar(),
        )

    def action_historial(self) -> None:
        from .historial import PantallaHistorial

        codigo = self._codigo_seleccionado()
        if codigo is not None:
            e = self.archivo.obtener_egreso(codigo)
            nombre = e.nombre_variable or f"Egreso #{codigo}"
            self.app.push_screen(PantallaHistorial(self.archivo, "egreso", codigo, nombre))

    def action_eliminar(self) -> None:
        codigo = self._codigo_seleccionado()
        if codigo is not None:
            self.archivo.eliminar_egreso(codigo)
            self.recargar()

    def action_recalcular(self) -> None:
        self.recargar()

    def action_volver(self) -> None:
        self.app.pop_screen()
