from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from engine.storage import (
    NOMBRE_IGV_COMPRAS,
    NOMBRE_IGV_VENTAS_EFECTIVO,
    NOMBRE_IGV_VENTAS_REGULAR,
    NOMBRE_TIPO_CAMBIO,
    Archivo,
)


class PantallaConfiguracion(Screen):
    """Moneda principal / secundaria del proyecto. Las tasas de IGV y el
    tipo de cambio se manejan como Variables normales (ver pantalla de
    Variables) — aca solo se define el codigo de cada moneda."""

    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, archivo: Archivo):
        super().__init__()
        self.archivo = archivo

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("CONFIGURACIÓN DEL PROYECTO", id="titulo")
        yield Static("ENTER guarda.", id="subtitulo")
        with Vertical(classes="panel"):
            yield Label(" MONEDA PRINCIPAL (código, ej: PEN) ", classes="etiqueta")
            yield Input(value=self.archivo.moneda_principal, id="moneda_principal")
            yield Label(" MONEDA SECUNDARIA (código, ej: USD) ", classes="etiqueta")
            yield Input(value=self.archivo.moneda_secundaria, id="moneda_secundaria")
            yield Static(
                f"El motor busca automáticamente estas variables (créalas en la pantalla de "
                f"Variables si no existen):\n"
                f"  [{NOMBRE_TIPO_CAMBIO}]  — unidades de moneda principal por 1 de la secundaria\n"
                f"  [{NOMBRE_IGV_COMPRAS}]  — tasa de IGV en compras (ej. 0.18)\n"
                f"  [{NOMBRE_IGV_VENTAS_EFECTIVO}]  — tasa efectiva en venta inmobiliaria (ej. 0.09)\n"
                f"  [{NOMBRE_IGV_VENTAS_REGULAR}]  — tasa de IGV en ventas gravadas regulares (ej. 0.18)",
                classes="ayuda",
            )
            yield Static("", id="mensaje", classes="error")
        with Horizontal():
            yield Button("Guardar (Enter)", id="btn_guardar", variant="primary")
            yield Button("Cancelar (Esc)", id="btn_cancelar")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_guardar()

    @on(Button.Pressed, "#btn_guardar")
    def _click_guardar(self) -> None:
        self.action_guardar()

    @on(Button.Pressed, "#btn_cancelar")
    def _click_cancelar(self) -> None:
        self.action_cancelar()

    def action_guardar(self) -> None:
        principal = self.query_one("#moneda_principal", Input).value.strip().upper()
        secundaria = self.query_one("#moneda_secundaria", Input).value.strip().upper()
        mensaje = self.query_one("#mensaje", Static)
        if not principal or not secundaria:
            mensaje.update("Ambos códigos de moneda son obligatorios.")
            return
        if principal == secundaria:
            mensaje.update("La moneda principal y la secundaria no pueden ser la misma.")
            return
        self.archivo.set_config("moneda_principal", principal)
        self.archivo.set_config("moneda_secundaria", secundaria)
        self.app.pop_screen()

    def action_cancelar(self) -> None:
        self.app.pop_screen()
