from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static

from engine.storage import Archivo


class FilaProyecto(ListItem):
    def __init__(self, ruta: Path):
        self.ruta = ruta
        tam_kb = ruta.stat().st_size / 1024
        super().__init__(Label(f"  {ruta.stem:<40} {tam_kb:>8.1f} KB"))


class PantallaInicio(Screen):
    """Pantalla de arranque: elegir un proyecto existente o crear uno
    nuevo. Funciona con teclado (ENTER abre, F4 nuevo, ESC sale) y con
    mouse (doble click / click en los botones)."""

    BINDINGS = [
        ("f4", "nuevo_proyecto", "Nuevo proyecto"),
        ("escape", "salir", "Salir"),
        ("f10", "salir", "Salir"),
        ("enter", "abrir", "Abrir"),
    ]

    def __init__(self, dir_proyectos: Path):
        super().__init__()
        self.dir_proyectos = dir_proyectos

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "EVALUADOR DE PROYECTOS INMOBILIARIOS — pantalla de arranque",
            id="titulo",
        )
        yield Static(
            "Doble click o ENTER para abrir un proyecto. F4 o el botón para crear uno nuevo.",
            id="subtitulo",
        )
        with Vertical(classes="panel"):
            yield Label(" PROYECTOS (.pin) ", classes="etiqueta")
            yield ListView(id="lista_proyectos")
        with Horizontal():
            yield Button("Abrir (Enter)", id="btn_abrir", variant="primary")
            yield Button("Nuevo proyecto (F4)", id="btn_nuevo")
            yield Button("Salir (Esc)", id="btn_salir")
        yield Footer()

    def on_mount(self) -> None:
        self._recargar()

    def on_screen_resume(self) -> None:
        self._recargar()

    def _recargar(self) -> None:
        lista = self.query_one("#lista_proyectos", ListView)
        lista.clear()
        archivos = sorted(self.dir_proyectos.glob("*.pin"))
        if not archivos:
            lista.append(ListItem(Label("  (sin proyectos todavia — pulsa F4 para crear el primero)")))
        else:
            for ruta in archivos:
                lista.append(FilaProyecto(ruta))
            lista.index = 0
        lista.focus()

    @on(ListView.Selected, "#lista_proyectos")
    def _abrir_seleccionado(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, FilaProyecto):
            self._abrir(item.ruta)

    @on(Button.Pressed, "#btn_abrir")
    def _click_abrir(self) -> None:
        self.action_abrir()

    @on(Button.Pressed, "#btn_nuevo")
    def _click_nuevo(self) -> None:
        self.action_nuevo_proyecto()

    @on(Button.Pressed, "#btn_salir")
    def _click_salir(self) -> None:
        self.action_salir()

    def action_abrir(self) -> None:
        lista = self.query_one("#lista_proyectos", ListView)
        item = lista.highlighted_child
        if isinstance(item, FilaProyecto):
            self._abrir(item.ruta)

    def _abrir(self, ruta: Path) -> None:
        from .menu_proyecto import PantallaMenuProyecto

        archivo = Archivo(ruta)
        self.app.push_screen(PantallaMenuProyecto(archivo))

    def action_nuevo_proyecto(self) -> None:
        from .nuevo_proyecto import PantallaNuevoProyecto

        self.app.push_screen(PantallaNuevoProyecto(self.dir_proyectos))

    def action_salir(self) -> None:
        self.app.exit()
