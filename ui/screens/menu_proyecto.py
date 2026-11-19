from __future__ import annotations

import shutil

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from engine.storage import Archivo
from ui.comunes import recalcular


def _fmt(valor: float | None, sufijo: str = "") -> str:
    if valor is None:
        return "—"
    return f"{valor:,.2f}{sufijo}"


class PantallaMenuProyecto(Screen):
    """Panel principal del proyecto: resumen P&L en vivo + menu hacia
    Egresos / Ingresos / Variables / Configuracion / Reporte. Aqui vive
    tambien el temporizador de copia de seguridad automatica."""

    BINDINGS = [
        ("f2", "egresos", "Egresos"),
        ("f3", "ingresos", "Ingresos"),
        ("f4", "variables", "Variables"),
        ("f5", "configuracion", "Configuración"),
        ("f6", "reporte", "Reporte P&L"),
        ("escape", "cerrar", "Cerrar proyecto"),
        ("f10", "cerrar", "Cerrar proyecto"),
    ]

    INTERVALO_RESPALDO_SEGUNDOS = 180

    def __init__(self, archivo: Archivo):
        super().__init__()
        self.archivo = archivo

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"PROYECTO: {self.archivo.ruta.stem}", id="titulo")
        yield Static("", id="subtitulo")
        with Vertical(classes="panel"):
            yield Static("", id="resumen_pnl")
        with Horizontal():
            yield Button("Egresos (F2)", id="btn_egresos", variant="primary")
            yield Button("Ingresos (F3)", id="btn_ingresos", variant="primary")
            yield Button("Variables (F4)", id="btn_variables")
        with Horizontal():
            yield Button("Configuración (F5)", id="btn_config")
            yield Button("Reporte P&L (F6)", id="btn_reporte")
            yield Button("Cerrar proyecto (Esc)", id="btn_cerrar")
        yield Footer()

    def on_mount(self) -> None:
        self._actualizar_resumen()
        self.set_interval(self.INTERVALO_RESPALDO_SEGUNDOS, self._respaldo_automatico)

    def on_screen_resume(self) -> None:
        self._actualizar_resumen()

    def _actualizar_resumen(self) -> None:
        r = recalcular(self.archivo)
        u_antes = r.variables.get("Utilidad_Antes_Impuestos")
        impuesto = r.variables.get("Impuesto_Renta")
        u_despues = r.variables.get("Utilidad_Despues_Impuestos")
        margen = r.variables.get("Margen_Neto")

        lineas = [
            f"  Total Ingresos (neto):      {_fmt(r.total_ingresos)}",
            f"  Total Egresos:              {_fmt(r.total_egresos)}",
            "",
            f"  Utilidad antes de Impuestos:{_fmt(u_antes.valor if u_antes else None)}",
            f"  Impuesto a la Renta:        {_fmt(impuesto.valor if impuesto else None)}",
            f"  Utilidad después de Impuestos:{_fmt(u_despues.valor if u_despues else None)}",
            f"  Margen neto:                 {_fmt(margen.valor if margen else None, '%')}",
        ]
        self.query_one("#resumen_pnl", Static).update("\n".join(lineas))

        tam_kb = self.archivo.tamano_bytes() / 1024
        self.query_one("#subtitulo", Static).update(f"Archivo: {tam_kb:.1f} KB — se guarda al instante en cada cambio")

    def _respaldo_automatico(self) -> None:
        try:
            copia = self.archivo.ruta.with_suffix(".pin.bak")
            shutil.copy(self.archivo.ruta, copia)
            sub = self.query_one("#subtitulo", Static)
            tam_kb = self.archivo.tamano_bytes() / 1024
            sub.update(f"Archivo: {tam_kb:.1f} KB — copia de seguridad guardada ✓")
            self.set_timer(4, self._actualizar_resumen)
        except Exception:
            pass

    @on(Button.Pressed, "#btn_egresos")
    def _click_egresos(self) -> None:
        self.action_egresos()

    @on(Button.Pressed, "#btn_ingresos")
    def _click_ingresos(self) -> None:
        self.action_ingresos()

    @on(Button.Pressed, "#btn_variables")
    def _click_variables(self) -> None:
        self.action_variables()

    @on(Button.Pressed, "#btn_config")
    def _click_config(self) -> None:
        self.action_configuracion()

    @on(Button.Pressed, "#btn_reporte")
    def _click_reporte(self) -> None:
        self.action_reporte()

    @on(Button.Pressed, "#btn_cerrar")
    def _click_cerrar(self) -> None:
        self.action_cerrar()

    def action_egresos(self) -> None:
        from .egresos import PantallaEgresos

        self.app.push_screen(PantallaEgresos(self.archivo))

    def action_ingresos(self) -> None:
        from .ingresos import PantallaIngresos

        self.app.push_screen(PantallaIngresos(self.archivo))

    def action_variables(self) -> None:
        from .variables import PantallaVariables

        self.app.push_screen(PantallaVariables(self.archivo))

    def action_configuracion(self) -> None:
        from .configuracion import PantallaConfiguracion

        self.app.push_screen(PantallaConfiguracion(self.archivo))

    def action_reporte(self) -> None:
        from .reporte_pnl import PantallaReportePnL

        self.app.push_screen(PantallaReportePnL(self.archivo))

    def action_cerrar(self) -> None:
        self.archivo.close()
        self.app.pop_screen()
