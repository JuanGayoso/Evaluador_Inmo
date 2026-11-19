from __future__ import annotations

import re
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from engine.storage import nuevo_proyecto_desde_plantilla

DIR_PLANTILLAS = Path(__file__).resolve().parent.parent.parent / "templates"


class FilaPlantilla(ListItem):
    def __init__(self, ruta: Path):
        self.ruta = ruta
        super().__init__(Label(f"  {ruta.stem}"))


class PantallaNuevoProyecto(Screen):
    """Elegir plantilla + nombre -> duplica el archivo."""

    BINDINGS = [
        ("enter", "crear", "Crear proyecto"),
        ("escape", "cancelar", "Cancelar"),
    ]

    def __init__(self, dir_proyectos: Path):
        super().__init__()
        self.dir_proyectos = dir_proyectos
        self.plantilla_elegida: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("NUEVO PROYECTO DESDE PLANTILLA", id="titulo")
        yield Static("Elige la plantilla (click o flechas), escribe el nombre y ENTER.", id="subtitulo")
        with Vertical(classes="panel"):
            yield Label(" PLANTILLAS DISPONIBLES ", classes="etiqueta")
            yield ListView(id="lista_plantillas")
        with Vertical(classes="panel"):
            yield Label(" NOMBRE DEL PROYECTO ", classes="etiqueta")
            yield Input(placeholder="ej: torres_del_mar", id="nombre_proyecto")
            yield Static("", id="mensaje", classes="error")
        with Horizontal():
            yield Button("Crear (Enter)", id="btn_crear", variant="primary")
            yield Button("Cancelar (Esc)", id="btn_cancelar")
        yield Footer()

    def on_mount(self) -> None:
        lista = self.query_one("#lista_plantillas", ListView)
        plantillas = sorted(DIR_PLANTILLAS.glob("*.pin"))
        for ruta in plantillas:
            lista.append(FilaPlantilla(ruta))
        if plantillas:
            self.plantilla_elegida = plantillas[0]
            lista.index = 0
        lista.focus()

    @on(ListView.Highlighted, "#lista_plantillas")
    def _marcar(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, FilaPlantilla):
            self.plantilla_elegida = event.item.ruta

    @on(Button.Pressed, "#btn_crear")
    def _click_crear(self) -> None:
        self.action_crear()

    @on(Button.Pressed, "#btn_cancelar")
    def _click_cancelar(self) -> None:
        self.action_cancelar()

    def action_crear(self) -> None:
        mensaje = self.query_one("#mensaje", Static)
        nombre = self.query_one("#nombre_proyecto", Input).value.strip()

        if not self.plantilla_elegida:
            mensaje.update("No hay ninguna plantilla seleccionada.")
            return
        if not nombre:
            mensaje.update("Escribe un nombre para el proyecto.")
            return
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", nombre).strip("_").lower()
        if not slug:
            mensaje.update("El nombre no tiene caracteres validos.")
            return

        destino = self.dir_proyectos / f"{slug}.pin"
        if destino.exists():
            mensaje.update(f"Ya existe un proyecto llamado '{slug}'.")
            return

        self.dir_proyectos.mkdir(exist_ok=True)
        nuevo_proyecto_desde_plantilla(self.plantilla_elegida, destino)
        self.app.pop_screen()

    def action_cancelar(self) -> None:
        self.app.pop_screen()
