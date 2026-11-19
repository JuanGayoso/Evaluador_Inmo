from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from engine.storage import Archivo, IngresoLinea, NombreEnUso
from ui.comunes import CampoFormulaMixin, insertar_referencia, nombres_disponibles, recalcular
from ui.widgets.selector_referencias import SelectorReferencias

CAMPOS_FORMULA = {"cantidad", "precio"}

OPCIONES_IGV = [
    ("Sin IGV (no gravado)", "ninguno"),
    ("Afecto 18% regular (monto → IGV → parcial)", "afecto_18"),
    ("Venta inmobiliaria 9% efectivo (IGV incluido, cálculo hacia atrás)", "inmobiliario_9"),
]


class PantallaEditarIngreso(CampoFormulaMixin, Screen):
    CAMPOS_FORMULA = CAMPOS_FORMULA
    BINDINGS = [("escape", "cancelar", "Cancelar")]

    def __init__(self, archivo: Archivo, ingreso: IngresoLinea | None):
        super().__init__()
        self.archivo = archivo
        self.ingreso = ingreso
        self.es_nuevo = ingreso is None
        self._ciclo_pendiente = False
        self._codigo_guardado: int | None = None
        self._iniciar_campo_activo("precio")

    def compose(self) -> ComposeResult:
        i = self.ingreso
        yield Header()
        titulo = "NUEVA PARTIDA DE INGRESO" if self.es_nuevo else f"EDITAR INGRESO #{i.codigo}"
        yield Static(titulo, id="titulo")
        yield Static("ENTER guarda. Elige una referencia a la derecha para insertarla en Cantidad/Precio.", id="subtitulo")
        with Horizontal():
            with Vertical(classes="col-campos panel"):
                yield Label(" NOMBRE DE VARIABLE (opcional; sin espacios) ", classes="etiqueta")
                yield Input(value=i.nombre_variable if i and i.nombre_variable else "", id="nombre_variable")
                yield Label(" CÓDIGO ESTANDARIZADO (opcional) ", classes="etiqueta")
                yield Input(value=i.codigo_estandarizado if i else "", id="codigo_estandarizado")
                yield Label(" FAMILIA (organiza y subtotaliza el resumen) ", classes="etiqueta")
                yield Input(value=i.familia if i else "", id="familia")
                yield Label(" DESCRIPCIÓN ", classes="etiqueta")
                yield Input(value=i.descripcion if i else "", id="descripcion")
                yield Label(" CANTIDAD (valor o fórmula) ", classes="etiqueta")
                yield Input(value=i.cantidad_formula if i else "1", id="cantidad")
                yield Label(" PRECIO (valor o fórmula) ", classes="etiqueta")
                yield Input(value=i.precio_formula if i else "", id="precio")
                yield Label(" MONEDA ", classes="etiqueta")
                yield Select(
                    [(self.archivo.moneda_principal, self.archivo.moneda_principal),
                     (self.archivo.moneda_secundaria, self.archivo.moneda_secundaria)],
                    value=(i.moneda if i else self.archivo.moneda_principal),
                    id="moneda", allow_blank=False,
                )
                yield Label(" TRATAMIENTO DE IGV ", classes="etiqueta")
                yield Select(OPCIONES_IGV, value=(i.tipo_igv if i else "inmobiliario_9"), id="tipo_igv", allow_blank=False)
                yield Label(" NOTA (opcional) ", classes="etiqueta")
                yield Input(value=i.nota if i else "", id="nota")
                yield Static("", id="mensaje", classes="error")
                with Horizontal():
                    yield Button("Guardar (Enter)", id="btn_guardar", variant="primary")
                    yield Button("Cancelar (Esc)", id="btn_cancelar")
            excluir = i.nombre_variable if i else None
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
        nombre_variable = self.query_one("#nombre_variable", Input).value.strip() or None

        nueva = IngresoLinea(
            codigo=self.ingreso.codigo if self.ingreso else None,
            codigo_estandarizado=self.query_one("#codigo_estandarizado", Input).value.strip(),
            familia=self.query_one("#familia", Input).value.strip(),
            nombre_variable=nombre_variable,
            descripcion=self.query_one("#descripcion", Input).value.strip(),
            cantidad_formula=self.query_one("#cantidad", Input).value.strip(),
            precio_formula=self.query_one("#precio", Input).value.strip(),
            moneda=self.query_one("#moneda", Select).value,
            tipo_igv=self.query_one("#tipo_igv", Select).value,
            orden=self.ingreso.orden if self.ingreso else 0,
            nota=self.query_one("#nota", Input).value.strip(),
        )

        if not nueva.descripcion:
            mensaje.update("La descripción no puede estar vacía.")
            return
        if not nueva.precio_formula:
            mensaje.update("El precio no puede estar vacío.")
            return

        try:
            codigo = self.archivo.guardar_ingreso(nueva)
        except (NombreEnUso, ValueError) as ex:
            mensaje.update(str(ex))
            return

        resultado = recalcular(self.archivo)
        error = resultado.error_de("ingreso", codigo)
        if error and "ciclo" in error:
            self._ciclo_pendiente = True
            self._codigo_guardado = codigo
            mensaje.update(f"⚠ {error} — corrige la fórmula antes de continuar.")
            return
        self._ciclo_pendiente = False

        self.app.pop_screen()

    def action_cancelar(self) -> None:
        if self._ciclo_pendiente and self._codigo_guardado is not None:
            if self.es_nuevo:
                self.archivo.eliminar_ingreso(self._codigo_guardado)
            elif self.ingreso is not None:
                self.archivo.guardar_ingreso(self.ingreso, registrar_historial=False)
            recalcular(self.archivo)
        self.app.pop_screen()
