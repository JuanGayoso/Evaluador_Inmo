"""Llena la plantilla de fabrica con datos de un proyecto ficticio y
verifica que el P&L completo calcula sin ningun error. Se corre con:
python3 tests/test_plantilla_e2e.py"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.motor import Motor
from engine.storage import Archivo, nuevo_proyecto_desde_plantilla

fallos = []


def check(nombre, cond):
    estado = "OK " if cond else "FALLO"
    print(f"[{estado}] {nombre}")
    if not cond:
        fallos.append(nombre)


PLANTILLA = Path(__file__).parent.parent / "templates" / "inmobiliario_basico.pin"

ENTRADAS = {
    "Area_Vendible": 3000.0,
    "Area_Construida_Total": 4200.0,
    "Cantidad_UI": 40.0,
    "Cantidad_Estacionamientos": 45.0,
    "UIT": 5350.0,
    "Tipo_Cambio": 3.75,
    "Precio_Venta_m2": 6500.0,
    "Costo_m2_Construccion": 1800.0,
    "Precio_Estacionamiento": 25000.0,
}

with tempfile.TemporaryDirectory() as tmp:
    proyecto = Path(tmp) / "torres_del_mar.pin"
    nuevo_proyecto_desde_plantilla(PLANTILLA, proyecto)

    with Archivo(proyecto) as arch:
        for nombre, valor in ENTRADAS.items():
            v = arch.obtener_variable(nombre)
            v.formula = str(valor)
            arch.guardar_variable(v)

        terreno = next(e for e in arch.listar_egresos_todos() if e.nombre_variable == "Terreno")
        terreno.precio_formula = "950000"
        arch.guardar_egreso(terreno)

        variables = arch.listar_variables()
        egresos = arch.listar_egresos_todos()
        ingresos = arch.listar_ingresos_todos()
        motor = Motor(variables, egresos, ingresos, arch.moneda_principal, arch.moneda_secundaria)
        r = motor.calcular()

        errores_var = {n: res.error for n, res in r.variables.items() if res.error}
        errores_egr = {c: res.error for c, res in r.egresos.items() if res.error}
        errores_ing = {c: res.error for c, res in r.ingresos.items() if res.error}

        check("ninguna variable con error", not errores_var)
        check("ningun egreso con error", not errores_egr)
        check("ningun ingreso con error", not errores_ing)
        if errores_var:
            print("   errores en variables:", errores_var)
        if errores_egr:
            print("   errores en egresos:", errores_egr)
        if errores_ing:
            print("   errores en ingresos:", errores_ing)

        check("Total_Ingresos calculado", r.total_ingresos is not None)
        check("Total_Egresos calculado", r.total_egresos is not None)

        utilidad_antes = r.variables["Utilidad_Antes_Impuestos"].valor
        impuesto = r.variables["Impuesto_Renta"].valor
        utilidad_despues = r.variables["Utilidad_Despues_Impuestos"].valor
        margen = r.variables["Margen_Neto"].valor

        check("utilidad antes de impuestos = ingresos - egresos",
              abs(utilidad_antes - (r.total_ingresos - r.total_egresos)) < 0.01)
        check("impuesto a la renta = utilidad antes * tasa", abs(impuesto - utilidad_antes * 0.295) < 0.5)
        check("utilidad despues = utilidad antes - impuesto", abs(utilidad_despues - (utilidad_antes - impuesto)) < 0.01)

        medidores = r.egresos[[e.codigo for e in egresos if e.nombre_variable == "Instalacion_Medidores"][0]]
        subtotal_hijos = 45000 + 30000 + 5000
        check("sub-presupuesto de medidores aplica el factor 1.05 sobre sus hijos",
              abs(medidores.monto - subtotal_hijos * 1.05) < 0.01)

        print()
        print(f"      Total Ingresos (neto):  {r.total_ingresos:>15,.2f}")
        print(f"      Total Egresos:          {r.total_egresos:>15,.2f}")
        print(f"      Utilidad antes de Imp.: {utilidad_antes:>15,.2f}")
        print(f"      Impuesto a la Renta:    {impuesto:>15,.2f}")
        print(f"      Utilidad despues Imp.:  {utilidad_despues:>15,.2f}")
        print(f"      Margen neto:            {margen:>14,.2f}%")

print()
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron: {fallos}")
    sys.exit(1)
else:
    print("Todas las pruebas pasaron.")
