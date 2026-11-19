"""Utilidades compartidas por varias pantallas: recalcular todo el
proyecto, obtener la lista de nombres referenciables (para el panel de
autocompletado), e insertar una referencia [Nombre] en el campo de
formula que tenga el foco en ese momento."""

from __future__ import annotations

from textual.widgets import Input

from engine.motor import Motor, ResultadoCalculo
from engine.storage import Archivo


def recalcular(archivo: Archivo) -> ResultadoCalculo:
    variables = archivo.listar_variables()
    egresos = archivo.listar_egresos_todos()
    ingresos = archivo.listar_ingresos_todos()
    motor = Motor(variables, egresos, ingresos, archivo.moneda_principal, archivo.moneda_secundaria)
    return motor.calcular()


def nombres_disponibles(archivo: Archivo, excluir: str | None = None) -> list[str]:
    """Todo lo que hoy tiene nombre_variable: variables, egresos e
    ingresos nombrados, mas los totales del sistema. 'excluir' evita que
    una partida se ofrezca a si misma como referencia."""
    nombres = [v.nombre_variable for v in archivo.listar_variables()]
    nombres += [e.nombre_variable for e in archivo.listar_egresos_todos() if e.nombre_variable]
    nombres += [i.nombre_variable for i in archivo.listar_ingresos_todos() if i.nombre_variable]
    nombres += ["Total_Ingresos", "Total_Egresos"]
    if excluir:
        nombres = [n for n in nombres if n != excluir]
    return nombres


def insertar_referencia(screen, nombre: str, campo_id: str | None, mensaje_widget=None) -> None:
    """Inserta [nombre] en el campo de formula indicado (el ultimo que
    tuvo el foco, rastreado por la pantalla — ver CampoFormulaMixin).
    Asi un click en el panel de referencias no depende de que el Input
    siga enfocado en ese instante."""
    if not campo_id:
        if mensaje_widget is not None:
            mensaje_widget.update(
                "Haz click primero en un campo de fórmula (Cantidad, Precio, ...) y luego elige la referencia."
            )
        return
    try:
        campo = screen.query_one(f"#{campo_id}", Input)
    except Exception:
        return
    if campo.disabled:
        if mensaje_widget is not None:
            mensaje_widget.update("Ese campo no está activo con la configuración actual.")
        return
    texto = campo.value
    pos = campo.cursor_position if campo.cursor_position is not None else len(texto)
    campo.value = f"{texto[:pos]}[{nombre}]{texto[pos:]}"
    campo.cursor_position = pos + len(nombre) + 2
    campo.focus()
    if mensaje_widget is not None:
        mensaje_widget.update("")


class CampoFormulaMixin:
    """Mixin para pantallas con varios campos de formula: recuerda cual
    fue el ultimo enfocado (self._campo_activo) para que el panel de
    referencias sepa donde insertar, incluso si el foco ya se movio al
    panel mismo (por ejemplo, al hacer click en la lista)."""

    CAMPOS_FORMULA: set[str] = set()

    def _iniciar_campo_activo(self, valor_inicial: str | None) -> None:
        self._campo_activo = valor_inicial

    def on_focus(self, event) -> None:
        foco = getattr(self, "focused", None)
        if foco is not None and getattr(foco, "id", None) in self.CAMPOS_FORMULA:
            self._campo_activo = foco.id
