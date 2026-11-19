"""
Motor de calculo parametrico y relacional — v2.

Nodos del grafo: Variables, Egresos e Ingresos (cualquiera con un
"nombre_variable" queda disponible para que otras formulas lo referencien
como [Nombre]). Un Egreso marcado como sub-presupuesto depende
estructuralmente de sus hijos (padre_codigo), sin que haga falta
mencionarlos por formula. Dos nodos de sistema, [Total_Ingresos] y
[Total_Egresos], se recalculan solos sumando las lineas raiz — nunca hay
que mantener una formula manual de suma que se rompa al insertar filas.

Reglas de las formulas:
  - Referencian por nombre entre corchetes: [Nombre de variable].
  - Aceptan potencias con "^" (se traduce a **) ademas de "**".
  - Aceptan porcentajes escritos como "18%" (se traduce a (18/100)).
  - Se evaluan en una caja de arena (asteval): solo aritmetica y
    funciones explicitamente permitidas.
  - Un ciclo de dependencias se detecta ANTES de calcular y se reporta
    con el camino exacto involucrado — nunca un resultado incorrecto
    silencioso.
"""

from __future__ import annotations

import math
import re
from collections import deque
from dataclasses import dataclass, field

from asteval import Interpreter

from .storage import (
    NOMBRE_IGV_COMPRAS,
    NOMBRE_IGV_VENTAS_EFECTIVO,
    NOMBRE_IGV_VENTAS_REGULAR,
    NOMBRE_TIPO_CAMBIO,
    EgresoLinea,
    IngresoLinea,
    Variable,
)

REF_PATTERN = re.compile(r"\[([^\[\]]+)\]")
PORCENTAJE_PATTERN = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%")

NOMBRE_TOTAL_INGRESOS = "Total_Ingresos"
NOMBRE_TOTAL_EGRESOS = "Total_Egresos"

FUNCIONES_PERMITIDAS = {
    "max": max,
    "min": min,
    "round": round,
    "abs": abs,
    "sum": sum,
    "pow": pow,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
}


def referencias(formula: str | None) -> set[str]:
    if not formula:
        return set()
    return {m.group(1).strip() for m in REF_PATTERN.finditer(formula)}


def _preprocesar(expr: str) -> str:
    """Traduce ^ (potencia) y N% (porcentaje) a sintaxis Python, una vez
    que las referencias [Nombre] ya fueron sustituidas por identificadores
    seguros (asi nunca tocamos el texto de un nombre de partida)."""
    expr = PORCENTAJE_PATTERN.sub(r"(\1/100)", expr)
    expr = expr.replace("^", "**")
    return expr


def _nuevo_interprete() -> Interpreter:
    interp = Interpreter(minimal=True, use_numpy=False, no_print=True)
    interp.symtable.clear()
    interp.symtable.update(FUNCIONES_PERMITIDAS)
    return interp


class ErrorFormula(Exception):
    pass


def evaluar_formula(formula: str, valores: dict[str, float], interp: Interpreter) -> float:
    if formula is None:
        raise ErrorFormula("fórmula vacía")
    formula = formula.strip()
    if not formula:
        raise ErrorFormula("fórmula vacía")

    refs = list(dict.fromkeys(referencias(formula)))
    expr = formula
    temporales = []
    for i, nombre in enumerate(refs):
        ident = f"_ref{i}"
        expr = expr.replace(f"[{nombre}]", ident)
        interp.symtable[ident] = valores[nombre]
        temporales.append(ident)

    expr = _preprocesar(expr)

    interp.error = []
    resultado = interp.eval(expr, show_errors=False, raise_errors=False)

    for ident in temporales:
        interp.symtable.pop(ident, None)

    if interp.error:
        primero = interp.error[0]
        msg = getattr(primero, "get_error", lambda: (None, str(primero)))()
        detalle = msg[1] if isinstance(msg, tuple) else str(primero)
        raise ErrorFormula(detalle.strip().splitlines()[-1] if detalle else "expresión inválida")
    if resultado is None or isinstance(resultado, bool):
        raise ErrorFormula("la expresión no produjo un número")
    try:
        return float(resultado)
    except (TypeError, ValueError):
        raise ErrorFormula("la expresión no produjo un número")


# ---------------------------------------------------------------------------
# resultados
# ---------------------------------------------------------------------------

@dataclass
class ResultadoVariable:
    valor: float | None
    error: str | None


@dataclass
class ResultadoLinea:
    cantidad: float | None = None
    precio: float | None = None
    monto: float | None = None
    monto_moneda_principal: float | None = None
    igv: float | None = None
    parcial: float | None = None
    parcial_moneda_principal: float | None = None
    error: str | None = None


@dataclass
class ResultadoCalculo:
    variables: dict[str, ResultadoVariable] = field(default_factory=dict)
    egresos: dict[int, ResultadoLinea] = field(default_factory=dict)
    ingresos: dict[int, ResultadoLinea] = field(default_factory=dict)
    total_ingresos: float | None = None
    total_egresos: float | None = None
    error_total_ingresos: str | None = None
    error_total_egresos: str | None = None

    def error_de(self, tipo: str, identificador) -> str | None:
        if tipo == "variable":
            r = self.variables.get(identificador)
        elif tipo == "egreso":
            r = self.egresos.get(identificador)
        elif tipo == "ingreso":
            r = self.ingresos.get(identificador)
        else:
            return None
        return r.error if r else None


NodoKey = tuple  # ("variable"|"egreso"|"ingreso"|"sistema", str|int)


class Motor:
    def __init__(
        self,
        variables: list[Variable],
        egresos: list[EgresoLinea],
        ingresos: list[IngresoLinea],
        moneda_principal: str = "PEN",
        moneda_secundaria: str = "USD",
    ):
        for e in egresos:
            if e.codigo is None:
                raise ValueError("Motor requiere egresos ya guardados (con código asignado)")
        for i in ingresos:
            if i.codigo is None:
                raise ValueError("Motor requiere ingresos ya guardados (con código asignado)")
        self.variables = {v.nombre_variable: v for v in variables}
        self.egresos = {e.codigo: e for e in egresos}
        self.ingresos = {i.codigo: i for i in ingresos}
        self.moneda_principal = moneda_principal
        self.moneda_secundaria = moneda_secundaria

    # -- construccion del grafo -------------------------------------------
    def _mapa_nombres(self) -> dict[str, NodoKey]:
        mapa: dict[str, NodoKey] = {}
        for nombre in self.variables:
            mapa[nombre] = ("variable", nombre)
        for e in self.egresos.values():
            if e.nombre_variable:
                mapa[e.nombre_variable] = ("egreso", e.codigo)
        for i in self.ingresos.values():
            if i.nombre_variable:
                mapa[i.nombre_variable] = ("ingreso", i.codigo)
        mapa[NOMBRE_TOTAL_INGRESOS] = ("sistema", NOMBRE_TOTAL_INGRESOS)
        mapa[NOMBRE_TOTAL_EGRESOS] = ("sistema", NOMBRE_TOTAL_EGRESOS)
        return mapa

    def nombre_visible(self, nodo: NodoKey) -> str:
        tipo, ident = nodo
        if tipo == "variable" or tipo == "sistema":
            return ident
        if tipo == "egreso":
            e = self.egresos.get(ident)
            return e.nombre_variable if (e and e.nombre_variable) else f"Egreso #{ident}"
        if tipo == "ingreso":
            i = self.ingresos.get(ident)
            return i.nombre_variable if (i and i.nombre_variable) else f"Ingreso #{ident}"
        return str(nodo)

    def _resolver_refs(self, mapa: dict[str, NodoKey], texto: str) -> tuple[set[NodoKey], set[str]]:
        deps, faltan = set(), set()
        for r in referencias(texto):
            if r in mapa:
                deps.add(mapa[r])
            else:
                faltan.add(r)
        return deps, faltan

    def calcular(self) -> ResultadoCalculo:
        mapa = self._mapa_nombres()
        hijos_de: dict[int, list[EgresoLinea]] = {}
        for e in self.egresos.values():
            if e.padre_codigo is not None:
                hijos_de.setdefault(e.padre_codigo, []).append(e)

        nodos: list[NodoKey] = (
            [("variable", n) for n in self.variables]
            + [("egreso", c) for c in self.egresos]
            + [("ingreso", c) for c in self.ingresos]
            + [("sistema", NOMBRE_TOTAL_INGRESOS), ("sistema", NOMBRE_TOTAL_EGRESOS)]
        )

        dependencias: dict[NodoKey, set[NodoKey]] = {}
        faltantes: dict[NodoKey, set[str]] = {}

        for nombre, v in self.variables.items():
            deps, falt = self._resolver_refs(mapa, v.formula or "")
            dependencias[("variable", nombre)] = deps
            faltantes[("variable", nombre)] = falt

        for codigo, e in self.egresos.items():
            nodo = ("egreso", codigo)
            deps: set[NodoKey] = set()
            falt: set[str] = set()
            if e.es_subpresupuesto:
                for hijo in hijos_de.get(codigo, []):
                    deps.add(("egreso", hijo.codigo))
                d2, f2 = self._resolver_refs(mapa, e.factor_formula or "1")
                deps |= d2
                falt |= f2
            else:
                d1, f1 = self._resolver_refs(mapa, e.cantidad_formula or "")
                d2, f2 = self._resolver_refs(mapa, e.precio_formula or "")
                deps |= d1 | d2
                falt |= f1 | f2
            if e.afecto_igv:
                if NOMBRE_IGV_COMPRAS in mapa:
                    deps.add(mapa[NOMBRE_IGV_COMPRAS])
                else:
                    falt.add(NOMBRE_IGV_COMPRAS)
            if e.moneda == self.moneda_secundaria:
                if NOMBRE_TIPO_CAMBIO in mapa:
                    deps.add(mapa[NOMBRE_TIPO_CAMBIO])
                else:
                    falt.add(NOMBRE_TIPO_CAMBIO)
            dependencias[nodo] = deps
            faltantes[nodo] = falt

        for codigo, i in self.ingresos.items():
            nodo = ("ingreso", codigo)
            d1, f1 = self._resolver_refs(mapa, i.cantidad_formula or "")
            d2, f2 = self._resolver_refs(mapa, i.precio_formula or "")
            deps = d1 | d2
            falt = f1 | f2
            nombre_tasa = None
            if i.tipo_igv == "afecto_18":
                nombre_tasa = NOMBRE_IGV_VENTAS_REGULAR
            elif i.tipo_igv == "inmobiliario_9":
                nombre_tasa = NOMBRE_IGV_VENTAS_EFECTIVO
            if nombre_tasa:
                if nombre_tasa in mapa:
                    deps.add(mapa[nombre_tasa])
                else:
                    falt.add(nombre_tasa)
            if i.moneda == self.moneda_secundaria:
                if NOMBRE_TIPO_CAMBIO in mapa:
                    deps.add(mapa[NOMBRE_TIPO_CAMBIO])
                else:
                    falt.add(NOMBRE_TIPO_CAMBIO)
            dependencias[nodo] = deps
            faltantes[nodo] = falt

        raices_egresos = [c for c, e in self.egresos.items() if e.padre_codigo is None]
        raices_ingresos = list(self.ingresos.keys())
        dependencias[("sistema", NOMBRE_TOTAL_EGRESOS)] = {("egreso", c) for c in raices_egresos}
        dependencias[("sistema", NOMBRE_TOTAL_INGRESOS)] = {("ingreso", c) for c in raices_ingresos}
        faltantes[("sistema", NOMBRE_TOTAL_EGRESOS)] = set()
        faltantes[("sistema", NOMBRE_TOTAL_INGRESOS)] = set()

        # -- orden topologico (Kahn) -------------------------------------------
        grado_entrada = {n: 0 for n in nodos}
        adyacencia: dict[NodoKey, list[NodoKey]] = {n: [] for n in nodos}
        for n, deps in dependencias.items():
            for d in deps:
                adyacencia[d].append(n)
                grado_entrada[n] += 1

        cola = deque(sorted((n for n in nodos if grado_entrada[n] == 0), key=str))
        orden: list[NodoKey] = []
        while cola:
            n = cola.popleft()
            orden.append(n)
            for m in sorted(adyacencia[n], key=str):
                grado_entrada[m] -= 1
                if grado_entrada[m] == 0:
                    cola.append(m)

        en_ciclo = [n for n in nodos if n not in orden]

        # -- calculo en orden -------------------------------------------------
        interp = _nuevo_interprete()
        valores_por_nodo: dict[NodoKey, float | None] = {}
        namespace: dict[str, float | None] = {}  # nombre visible -> valor, para evaluar_formula

        resultado = ResultadoCalculo()

        def marcar_error(nodo: NodoKey, mensaje: str) -> None:
            valores_por_nodo[nodo] = None
            self._guardar_error(resultado, nodo, mensaje)

        for nodo in orden:
            tipo, ident = nodo

            if faltantes.get(nodo):
                faltan = ", ".join(sorted(faltantes[nodo]))
                marcar_error(nodo, f"referencia inexistente: [{faltan}]")
                continue

            deps_rotas = sorted(
                self.nombre_visible(d) for d in dependencias.get(nodo, set()) if valores_por_nodo.get(d) is None
            )
            if deps_rotas:
                marcar_error(nodo, f"depende de [{', '.join(deps_rotas)}], que no tiene valor")
                continue

            # namespace con TODO lo que ya se calculo, indexado por nombre visible
            for n2, val in valores_por_nodo.items():
                namespace[self.nombre_visible(n2)] = val

            try:
                if tipo == "variable":
                    v = self.variables[ident]
                    val = evaluar_formula(v.formula or "", namespace, interp)
                    valores_por_nodo[nodo] = val
                    resultado.variables[ident] = ResultadoVariable(val, None)

                elif tipo == "egreso":
                    val = self._calcular_egreso(ident, namespace, interp, hijos_de, resultado)
                    valores_por_nodo[nodo] = val

                elif tipo == "ingreso":
                    val = self._calcular_ingreso(ident, namespace, interp, resultado)
                    valores_por_nodo[nodo] = val

                elif tipo == "sistema":
                    if ident == NOMBRE_TOTAL_EGRESOS:
                        total = 0.0
                        for c in raices_egresos:
                            r = resultado.egresos.get(c)
                            if r is None or r.error is not None or r.parcial_moneda_principal is None:
                                raise ErrorFormula(f"egreso #{c} sin calcular")
                            total += r.parcial_moneda_principal
                        valores_por_nodo[nodo] = total
                        resultado.total_egresos = total
                    else:
                        total = 0.0
                        for c in raices_ingresos:
                            r = resultado.ingresos.get(c)
                            if r is None or r.error is not None or r.monto_moneda_principal is None:
                                raise ErrorFormula(f"ingreso #{c} sin calcular")
                            total += r.monto_moneda_principal
                        valores_por_nodo[nodo] = total
                        resultado.total_ingresos = total
            except ErrorFormula as ex:
                marcar_error(nodo, f"error en fórmula: {ex}")
                if tipo == "sistema" and ident == NOMBRE_TOTAL_EGRESOS:
                    resultado.error_total_egresos = str(ex)
                elif tipo == "sistema" and ident == NOMBRE_TOTAL_INGRESOS:
                    resultado.error_total_ingresos = str(ex)
            except Exception as ex:  # cinturon de seguridad
                marcar_error(nodo, f"error inesperado: {ex}")

        if en_ciclo:
            nombres = sorted(self.nombre_visible(n) for n in en_ciclo)
            mensaje = f"ciclo de dependencias entre: {', '.join(nombres)}"
            for nodo in en_ciclo:
                self._guardar_error(resultado, nodo, mensaje)

        return resultado

    def _guardar_error(self, resultado: ResultadoCalculo, nodo: NodoKey, mensaje: str) -> None:
        tipo, ident = nodo
        if tipo == "variable":
            resultado.variables[ident] = ResultadoVariable(None, mensaje)
        elif tipo == "egreso":
            resultado.egresos[ident] = ResultadoLinea(error=mensaje)
        elif tipo == "ingreso":
            resultado.ingresos[ident] = ResultadoLinea(error=mensaje)
        elif tipo == "sistema" and ident == NOMBRE_TOTAL_EGRESOS:
            resultado.error_total_egresos = mensaje
        elif tipo == "sistema" and ident == NOMBRE_TOTAL_INGRESOS:
            resultado.error_total_ingresos = mensaje

    def _convertir_a_principal(self, monto: float, moneda: str, namespace: dict) -> float:
        if moneda == self.moneda_principal:
            return monto
        tc = namespace.get(NOMBRE_TIPO_CAMBIO)
        if tc is None:
            raise ErrorFormula(f"falta la variable [{NOMBRE_TIPO_CAMBIO}] para convertir de {moneda}")
        return monto * tc

    def _calcular_egreso(self, codigo, namespace, interp, hijos_de, resultado) -> float:
        e = self.egresos[codigo]

        if e.es_subpresupuesto:
            subtotal = 0.0
            for hijo in hijos_de.get(codigo, []):
                rh = resultado.egresos.get(hijo.codigo)
                if rh is None or rh.error is not None or rh.parcial_moneda_principal is None:
                    raise ErrorFormula(f"sub-presupuesto con partidas sin calcular")
                subtotal += rh.parcial_moneda_principal
            factor = evaluar_formula(e.factor_formula or "1", namespace, interp)
            cantidad, precio = None, None
            monto = subtotal * factor
        else:
            cantidad = evaluar_formula(e.cantidad_formula or "", namespace, interp)
            precio = evaluar_formula(e.precio_formula or "", namespace, interp)
            monto = cantidad * precio

        igv = monto * namespace[NOMBRE_IGV_COMPRAS] if e.afecto_igv else 0.0
        parcial = monto + igv
        parcial_mp = self._convertir_a_principal(parcial, e.moneda, namespace)
        monto_mp = self._convertir_a_principal(monto, e.moneda, namespace)

        resultado.egresos[codigo] = ResultadoLinea(
            cantidad=cantidad, precio=precio, monto=monto, monto_moneda_principal=monto_mp,
            igv=igv, parcial=parcial, parcial_moneda_principal=parcial_mp, error=None,
        )
        return parcial_mp

    def _calcular_ingreso(self, codigo, namespace, interp, resultado) -> float:
        i = self.ingresos[codigo]
        cantidad = evaluar_formula(i.cantidad_formula or "", namespace, interp)
        precio = evaluar_formula(i.precio_formula or "", namespace, interp)
        bruto = cantidad * precio

        if i.tipo_igv == "afecto_18":
            monto = bruto
            igv = monto * namespace[NOMBRE_IGV_VENTAS_REGULAR]
            parcial = monto + igv
        elif i.tipo_igv == "inmobiliario_9":
            parcial = bruto
            monto = parcial / (1 + namespace[NOMBRE_IGV_VENTAS_EFECTIVO])
            igv = parcial - monto
        else:  # ninguno
            monto = bruto
            igv = 0.0
            parcial = bruto

        parcial_mp = self._convertir_a_principal(parcial, i.moneda, namespace)
        monto_mp = self._convertir_a_principal(monto, i.moneda, namespace)

        resultado.ingresos[codigo] = ResultadoLinea(
            cantidad=cantidad, precio=precio, monto=monto, monto_moneda_principal=monto_mp,
            igv=igv, parcial=parcial, parcial_moneda_principal=parcial_mp, error=None,
        )
        return monto_mp
