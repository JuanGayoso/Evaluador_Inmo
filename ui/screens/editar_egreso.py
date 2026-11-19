from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select, Static

from engine.storage import Archivo, EgresoLinea, NombreEnUso
from ui.comunes import CampoFormulaMixin, insertar_referencia, nombres_disponibles, recalcular
from ui.widgets.selector_referencias import SelectorReferencias

CAMPOS_FORMULA = {"cantidad", "precio", "factor"}


class PantallaEditarEgreso(CampoFormulaMixin, Screen):
    """Formulario de una partida de Egresos. ENTER guarda, ESC cancela.
    El panel de la derecha permite insertar referencias [Nombre] sin
    tener que recordarlas de memoria — asi el calculo nunca falla por
    falta de una partida predecesora."""

    CAMPOS_FORMULA = CAMPOS_FORMULA

    BINDINGS = [
        ("escape", "cancelar", "Cancelar"),
    ]

    def __init__(self, archivo: Archivo, egreso: EgresoLinea | None, padre_codigo: int | None):
        super().__init__()
        self.archivo = archivo
        self.egreso = egreso
        self.padre_codigo = padre_codigo
        self.es_nuevo = egreso is None
        self._ciclo_pendiente = False
        self._codigo_guardado: int | None = None
        self._iniciar_campo_activo("precio")

    def compose(self) -> ComposeResult:
        e = self.egreso
        yield Header()
        titulo = "NUEVA PARTIDA DE EGRESO" if self.es_nuevo else f"EDITAR EGRESO #{e.codigo}"
        yield Static(titulo, id="titulo")
        yield Static(
            "ENTER guarda. Escribe en Cantidad/Precio/Factor y elige una referencia a la derecha para insertarla.",
            id="subtitulo",
        )
        with Horizontal():
            with Vertical(classes="col-campos panel"):
                yield Label(" NOMBRE DE VARIABLE (opcional; sin espacios) ", classes="etiqueta")
                yield Input(value=e.nombre_variable if e and e.nombre_variable else "", id="nombre_variable")
                yield Label(" CÓDIGO ESTANDARIZADO (opcional) ", classes="etiqueta")
                yield Input(value=e.codigo_estandarizado if e else "", id="codigo_estandarizado")
                yield Label(" DESCRIPCIÓN ", classes="etiqueta")
                yield Input(value=e.descripcion if e else "", id="descripcion")
                yield Label(" UNIDAD ", classes="etiqueta")
                yield Input(value=e.unidad if e else "", id="unidad")
                yield Label(" GRUPO (organiza y subtotaliza el resumen) ", classes="etiqueta")
                yield Input(value=e.grupo if e else "", id="grupo")
                yield Label(" MONEDA ", classes="etiqueta")
                yield Select(
                    [(self.archivo.moneda_principal, self.archivo.moneda_principal),
                     (self.archivo.moneda_secundaria, self.archivo.moneda_secundaria)],
                    value=(e.moneda if e else self.archivo.moneda_principal),
                    id="moneda", allow_blank=False,
                )
                yield Checkbox("Es un sub-presupuesto (contiene otras partidas)",
                                value=e.es_subpresupuesto if e else False, id="es_subpresupuesto")
                yield Label(" CANTIDAD (valor o fórmula) ", classes="etiqueta")
                yield Input(value=e.cantidad_formula if e else "1", id="cantidad")
                yield Label(" PRECIO (valor o fórmula) ", classes="etiqueta")
                yield Input(value=e.precio_formula if e else "", id="precio")
                yield Label(" FACTOR sobre el subtotal de sus hijos (solo si es sub-presupuesto) ", classes="etiqueta")
                yield Input(value=e.factor_formula if e else "1", id="factor")
                yield Checkbox("Afecto a IGV de compras (18%)", value=e.afecto_igv if e else False, id="afecto_igv")
                yield Label(" NOTA (opcional) ", classes="etiqueta")
                yield Input(value=e.nota if e else "", id="nota")
                yield Static("", id="mensaje", classes="error")
                with Horizontal():
                    yield Button("Guardar (Enter)", id="btn_guardar", variant="primary")
                    yield Button("Cancelar (Esc)", id="btn_cancelar")
            excluir = e.nombre_variable if e else None
            yield SelectorReferencias(nombres_disponibles(self.archivo, excluir=excluir), classes="col-selector")
        yield Footer()

    def on_mount(self) -> None:
        self._actualizar_disponibilidad()

    @on(Checkbox.Changed, "#es_subpresupuesto")
    def _toggle_subpresupuesto(self, event: Checkbox.Changed) -> None:
        self._actualizar_disponibilidad()

    def _actualizar_disponibilidad(self) -> None:
        es_sub = self.query_one("#es_subpresupuesto", Checkbox).value
        self.query_one("#cantidad", Input).disabled = es_sub
        self.query_one("#precio", Input).disabled = es_sub
        self.query_one("#factor", Input).disabled = not es_sub

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in CAMPOS_FORMULA or event.input.id in {
            "nombre_variable", "codigo_estandarizado", "descripcion", "unidad", "grupo", "nota",
        }:
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
        es_subpresupuesto = self.query_one("#es_subpresupuesto", Checkbox).value

        nueva = EgresoLinea(
            codigo=self.egreso.codigo if self.egreso else None,
            codigo_estandarizado=self.query_one("#codigo_estandarizado", Input).value.strip(),
            nombre_variable=nombre_variable,
            descripcion=self.query_one("#descripcion", Input).value.strip(),
            unidad=self.query_one("#unidad", Input).value.strip(),
            cantidad_formula=self.query_one("#cantidad", Input).value.strip(),
            precio_formula=self.query_one("#precio", Input).value.strip(),
            moneda=self.query_one("#moneda", Select).value,
            afecto_igv=self.query_one("#afecto_igv", Checkbox).value,
            grupo=self.query_one("#grupo", Input).value.strip(),
            es_subpresupuesto=es_subpresupuesto,
            factor_formula=self.query_one("#factor", Input).value.strip() or "1",
            padre_codigo=self.padre_codigo if self.es_nuevo else (self.egreso.padre_codigo if self.egreso else None),
            orden=self.egreso.orden if self.egreso else 0,
            nota=self.query_one("#nota", Input).value.strip(),
        )

        if not nueva.descripcion:
            mensaje.update("La descripción no puede estar vacía.")
            return
        if not es_subpresupuesto and not nueva.precio_formula:
            mensaje.update("El precio no puede estar vacío (o marca 'es un sub-presupuesto').")
            return

        try:
            codigo = self.archivo.guardar_egreso(nueva)
        except NombreEnUso as ex:
            mensaje.update(str(ex))
            return
        except ValueError as ex:
            mensaje.update(str(ex))
            return

        resultado = recalcular(self.archivo)
        error = resultado.error_de("egreso", codigo)
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
                self.archivo.eliminar_egreso(self._codigo_guardado)
            elif self.egreso is not None:
                self.archivo.guardar_egreso(self.egreso, registrar_historial=False)
            recalcular(self.archivo)
        self.app.pop_screen()
