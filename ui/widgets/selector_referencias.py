"""Panel reutilizable: lista de variables/partidas disponibles, filtrable
mientras se escribe (el 'predictor'), que inserta [Nombre] en el campo de
formula que tenga el foco. Funciona con mouse (click) y con teclado."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Label, ListItem, ListView


class SelectorReferencias(Vertical):
    class ReferenciaElegida(Message):
        def __init__(self, nombre: str) -> None:
            self.nombre = nombre
            super().__init__()

    def __init__(self, nombres: list[str] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._nombres_todos: list[str] = sorted(nombres or [])

    def compose(self) -> ComposeResult:
        yield Label(" REFERENCIAS DISPONIBLES — clic o Enter inserta ", classes="etiqueta")
        yield Input(placeholder="escribe para filtrar...", id="filtro_referencias")
        yield ListView(id="lista_referencias")

    def on_mount(self) -> None:
        self._refrescar("")

    def actualizar_nombres(self, nombres: list[str]) -> None:
        self._nombres_todos = sorted(nombres)
        filtro = self.query_one("#filtro_referencias", Input).value
        self._refrescar(filtro)

    def _refrescar(self, filtro: str) -> None:
        lista = self.query_one("#lista_referencias", ListView)
        lista.clear()
        filtro_l = filtro.strip().lower()
        coincidencias = (
            [n for n in self._nombres_todos if filtro_l in n.lower()] if filtro_l else self._nombres_todos
        )
        if not coincidencias:
            lista.append(ListItem(Label("  (sin coincidencias)")))
            return
        for nombre in coincidencias[:60]:
            item = ListItem(Label(f"  [{nombre}]"))
            item.nombre_referencia = nombre
            lista.append(item)
        lista.index = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filtro_referencias":
            self._refrescar(event.value)
            event.stop()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        nombre = getattr(event.item, "nombre_referencia", None)
        if nombre:
            self.post_message(self.ReferenciaElegida(nombre))
        event.stop()
