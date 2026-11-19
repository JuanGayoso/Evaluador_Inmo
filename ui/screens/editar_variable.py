from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from engine.storage import Archivo, NombreEnUso, Variable, validar_nombre_variable
from ui.comunes import CampoFormulaMixin, insertar_referencia, nombres_disponibles, recalcular
from ui.widgets.selector_referencias import SelectorReferencias

CAMPOS_FORMULA = {"formula"}


class PantallaEditarVariable(CampoFormulaMixin, Screen):
    CAMPOS_FORMULA = CAMPOS_FORMULA
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, archivo: Archivo, variable: Variable | None):
        super().__init__()
        self.archivo = archivo
        self.variable = variable
        self.es_nueva = variable is None
        self._advertencia_confirmada = False
        self._ciclo_pendiente = False
        self._iniciar_campo_activo("formula")

    def compose(self) -> ComposeResult:
        v = self.variable
        yield Header()
        titulo = "NUEVA VARIABLE" if self.es_nueva else f"EDITAR VARIABLE: {v.nombre_variable}"
        yield Static(titulo, id="titulo")
        yield Static("ENTER guarda. El valor puede ser un número o una fórmula, igual que en una partida.", id="subtitulo")
        with Horizontal():
            with Vertical(classes="col-campos panel"):
                yield Label(" NOMBRE DE VARIABLE (sin espacios, solo letras/números/_) ", classes="etiqueta")
                yield Input(value=v.nombre_variable if v else "", id="nombre_variable", disabled=not self.es_nueva)
                yield Label(" DESCRIPCIÓN ", classes="etiqueta")
                yield Input(value=v.descripcion if v else "", id="descripcion")
                yield Label(" VALOR (número o fórmula) ", classes="etiqueta")
                yield Input(value=v.formula if v and v.formula else "", id="formula", placeholder="ej: 3.75  ó  [Area]*[Costo_m2]")
                yield Label(" UNIDAD (si escribes % , el valor debe ir en decimal: 18% = 0.18) ", classes="etiqueta")
                yield Input(value=v.unidad if v else "", id="unidad")
                yield Static("", id="advertencia", classes="advertencia")
                yield Static("", id="mensaje", classes="error")
                with Horizontal():
                    yield Button("Guardar (Enter)", id="btn_guardar", variant="primary")
                    yield Button("Cancelar (Esc)", id="btn_cancelar")
            excluir = v.nombre_variable if v else None
            yield SelectorReferencias(nombres_disponibles(self.archivo, excluir=excluir), classes="col-selector")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_guardar()

    def on_selector_referencias_referencia_elegida(self, event: SelectorReferencias.ReferenciaElegida) -> None:
        insertar_referencia(self, event.nombre, self._campo_activo, self.query_one("#mensaje", Static))

    @on(Button.Pressed, "#btn_guardar")
    def _click_guardar(self) -> None:
        self.action_guardar()

    @on(Button.Pressed, "#btn_cancelar")
    def _click_cancelar(self) -> None:
        self.action_cancelar()

    def action_guardar(self) -> None:
        mensaje = self.query_one("#mensaje", Static)
        advertencia = self.query_one("#advertencia", Static)
        nombre = self.query_one("#nombre_variable", Input).value.strip()
        formula = self.query_one("#formula", Input).value.strip()
        unidad = self.query_one("#unidad", Input).value.strip()
        descripcion = self.query_one("#descripcion", Input).value.strip()

        if not nombre:
            mensaje.update("El nombre de la variable no puede estar vacío.")
            return
        if not validar_nombre_variable(nombre):
            mensaje.update(f"'{nombre}' no es válido: solo letras, números y '_' , sin empezar con número.")
            return

        nueva = Variable(nombre_variable=nombre, descripcion=descripcion, formula=formula, unidad=unidad,
                          orden=self.variable.orden if self.variable else 0)
        try:
            self.archivo.guardar_variable(nueva)
        except NombreEnUso as ex:
            mensaje.update(str(ex))
            return

        resultado = recalcular(self.archivo)
        r = resultado.variables.get(nombre)
        if r and r.error and "ciclo" in r.error:
            self._ciclo_pendiente = True
            mensaje.update(f"⚠ {r.error} — corrige la fórmula antes de continuar.")
            return
        self._ciclo_pendiente = False

        if "%" in unidad and r and r.valor is not None and abs(r.valor) > 1 and not self._advertencia_confirmada:
            advertencia.update(
                f"⚠ La unidad es '%' pero el valor calculado es {r.valor:,.4g} (mayor a 1). "
                "Verifica si querías escribirlo en decimal, ej. 18% en vez de 18. "
                "Pulsa Guardar de nuevo para guardarlo igual."
            )
            self._advertencia_confirmada = True
            return

        self.app.pop_screen()

    def action_cancelar(self) -> None:
        if self._ciclo_pendiente:
            nombre = self.query_one("#nombre_variable", Input).value.strip()
            if self.es_nueva:
                self.archivo.eliminar_variable(nombre)
            elif self.variable is not None:
                self.archivo.guardar_variable(self.variable, registrar_historial=False)
            recalcular(self.archivo)
        self.app.pop_screen()
