from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from engine.storage import Archivo
from ui.comunes import recalcular


def _fmt(v: float | None, sufijo: str = "") -> str:
    return "—" if v is None else f"{v:>18,.2f}{sufijo}"


class PantallaReportePnL(Screen):
    """Reporte de Perdidas y Ganancias: Ingresos - Egresos, utilidad
    antes y despues de impuestos. Se arma en vivo, no es un documento
    aparte — si cambias una partida, este reporte cambia con ella."""

    BINDINGS = [
        ("escape", "volver", "Volver"),
        ("f10", "volver", "Volver"),
        ("f2", "exportar", "Exportar a texto"),
    ]

    def __init__(self, archivo: Archivo):
        super().__init__()
        self.archivo = archivo

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("REPORTE P&L", id="titulo")
        yield Static("Se recalcula en vivo con cada cambio del proyecto.", id="subtitulo")
        with Vertical(classes="panel"):
            yield Static("", id="cuerpo_reporte")
        with Horizontal():
            yield Button("Exportar a .txt (F2)", id="btn_exportar", variant="primary")
            yield Button("Volver (Esc)", id="btn_volver")
        yield Footer()

    def on_mount(self) -> None:
        self._actualizar_reporte()

    def _texto_reporte(self) -> str:
        r = recalcular(self.archivo)
        egresos = self.archivo.listar_egresos_hijos(None)
        ingresos = self.archivo.listar_ingresos_todos()

        grupos_egr: dict[str, float] = {}
        for e in egresos:
            res = r.egresos.get(e.codigo)
            if res and res.parcial_moneda_principal is not None:
                grupos_egr[e.grupo or "(sin grupo)"] = grupos_egr.get(e.grupo or "(sin grupo)", 0) + res.parcial_moneda_principal

        familias_ing: dict[str, float] = {}
        for i in ingresos:
            res = r.ingresos.get(i.codigo)
            if res and res.monto_moneda_principal is not None:
                familias_ing[i.familia or "(sin familia)"] = familias_ing.get(i.familia or "(sin familia)", 0) + res.monto_moneda_principal

        u_antes = r.variables.get("Utilidad_Antes_Impuestos")
        impuesto = r.variables.get("Impuesto_Renta")
        u_despues = r.variables.get("Utilidad_Despues_Impuestos")
        margen = r.variables.get("Margen_Neto")

        lineas = []
        lineas.append(f"REPORTE P&L — {self.archivo.ruta.stem}")
        lineas.append("=" * 60)
        lineas.append("")
        lineas.append("INGRESOS (netos de IGV de ventas), por familia:")
        for familia, monto in familias_ing.items():
            lineas.append(f"  {familia:<40}{monto:>18,.2f}")
        lineas.append(f"  {'TOTAL INGRESOS':<40}{_fmt(r.total_ingresos)}")
        lineas.append("")
        lineas.append("EGRESOS (con IGV de compras no recuperable), por grupo:")
        for grupo, monto in grupos_egr.items():
            lineas.append(f"  {grupo:<40}{monto:>18,.2f}")
        lineas.append(f"  {'TOTAL EGRESOS':<40}{_fmt(r.total_egresos)}")
        lineas.append("")
        lineas.append("-" * 60)
        lineas.append(f"  {'UTILIDAD ANTES DE IMPUESTOS':<40}{_fmt(u_antes.valor if u_antes else None)}")
        lineas.append(f"  {'IMPUESTO A LA RENTA':<40}{_fmt(impuesto.valor if impuesto else None)}")
        lineas.append(f"  {'UTILIDAD DESPUÉS DE IMPUESTOS':<40}{_fmt(u_despues.valor if u_despues else None)}")
        lineas.append(f"  {'MARGEN NETO':<40}{_fmt(margen.valor if margen else None, '%')}")

        errores = [
            *(f"  Variable [{n}]: {v.error}" for n, v in r.variables.items() if v.error),
            *(f"  Egreso #{c}: {v.error}" for c, v in r.egresos.items() if v.error),
            *(f"  Ingreso #{c}: {v.error}" for c, v in r.ingresos.items() if v.error),
        ]
        if errores:
            lineas.append("")
            lineas.append("⚠ HAY PARTIDAS SIN CALCULAR — este reporte está incompleto:")
            lineas.extend(errores)

        return "\n".join(lineas)

    def _actualizar_reporte(self) -> None:
        self.query_one("#cuerpo_reporte", Static).update(self._texto_reporte())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_volver":
            self.action_volver()
        elif event.button.id == "btn_exportar":
            self.action_exportar()

    def action_exportar(self) -> None:
        destino = self.archivo.ruta.with_suffix(".pnl.txt")
        destino.write_text(self._texto_reporte(), encoding="utf-8")
        self.query_one("#subtitulo", Static).update(f"Exportado a {destino.name} ✓")

    def action_volver(self) -> None:
        self.app.pop_screen()
