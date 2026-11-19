"""Pruebas del motor v2 (en aislamiento, sin pasar por storage — por eso
asignamos 'codigo' a mano, como lo haria storage tras un INSERT).
Se corren con: python3 tests/test_motor.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.motor import Motor, evaluar_formula, _nuevo_interprete
from engine.storage import EgresoLinea, IngresoLinea, Variable

fallos = []


def check(nombre, cond):
    estado = "OK " if cond else "FALLO"
    print(f"[{estado}] {nombre}")
    if not cond:
        fallos.append(nombre)


# --- potencias y porcentajes en formulas sueltas -----------------------------
interp = _nuevo_interprete()
check("potencia con ^", evaluar_formula("2^10", {}, interp) == 1024)
check("potencia con ** sigue funcionando", evaluar_formula("2**3", {}, interp) == 8)
check("porcentaje simple", abs(evaluar_formula("18%", {}, interp) - 0.18) < 1e-9)
check("porcentaje combinado con otra operacion", abs(evaluar_formula("1000*18%", {}, interp) - 180) < 1e-9)
check("porcentaje decimal", abs(evaluar_formula("2.5%", {}, interp) - 0.025) < 1e-9)

# --- variables con formula (ya no son solo hojas) ----------------------------
variables = [
    Variable("Area_Vendible", formula="3000", unidad="m2"),
    Variable("Costo_m2", formula="1800", unidad="S/."),
    Variable("Costo_Construccion_Total", formula="[Area_Vendible]*[Costo_m2]", unidad="S/."),
    Variable("Tipo_Cambio", formula="3.75"),
    Variable("IGV_Compras", formula="18%"),
    Variable("IGV_Ventas_Efectivo", formula="9%"),
    Variable("IGV_Ventas_Regular", formula="18%"),
]
m = Motor(variables, [], [])
r = m.calcular()
check("variable puede depender de otra variable via formula", r.variables["Costo_Construccion_Total"].valor == 3000 * 1800)
check("IGV_Compras interpretado como 0.18 via %", abs(r.variables["IGV_Compras"].valor - 0.18) < 1e-9)

# --- egresos: cantidad/precio en formula, IGV, moneda secundaria --------------
egresos = [
    EgresoLinea(codigo=1, nombre_variable="Costo_Directo", descripcion="Costo directo de construccion",
                cantidad_formula="[Area_Vendible]", precio_formula="[Costo_m2]", moneda="PEN",
                afecto_igv=True, grupo="Costos de Construccion"),
    EgresoLinea(codigo=2, nombre_variable="Consultoria_USD", descripcion="Consultoria en dolares",
                cantidad_formula="10", precio_formula="500", moneda="USD", afecto_igv=False,
                grupo="Costos Indirectos"),
    EgresoLinea(codigo=3, nombre_variable=None, descripcion="Sin nombre de variable",
                cantidad_formula="1", precio_formula="[Costo_Directo]*0.05", moneda="PEN",
                afecto_igv=False, grupo="Costos Indirectos"),
]
m2 = Motor(variables, egresos, [])
r2 = m2.calcular()
costo_directo = r2.egresos[1]
consultoria = r2.egresos[2]
sin_nombre = r2.egresos[3]

check("egreso: monto = cantidad * precio", costo_directo.monto == 3000 * 1800)
check("egreso: IGV explicito sobre el monto", abs(costo_directo.igv - 3000 * 1800 * 0.18) < 1e-6)
check("egreso: parcial = monto + igv", abs(costo_directo.parcial - (costo_directo.monto + costo_directo.igv)) < 1e-6)
check("egreso en moneda principal: parcial_mp == parcial", costo_directo.parcial_moneda_principal == costo_directo.parcial)
check("egreso en moneda secundaria se convierte con Tipo_Cambio", abs(consultoria.parcial_moneda_principal - (10*500*3.75)) < 1e-6)
check("egreso puede referenciar a otro egreso por su nombre_variable (expone Parcial Moneda Principal)",
      abs(sin_nombre.precio - costo_directo.parcial_moneda_principal*0.05) < 1e-6)
check("Total_Egresos suma todos los egresos raiz (parcial en moneda principal)",
      abs(r2.total_egresos - (costo_directo.parcial_moneda_principal + consultoria.parcial_moneda_principal + sin_nombre.parcial_moneda_principal)) < 1e-6)

# --- ingresos: los 3 tratamientos de IGV --------------------------------------
ingresos = [
    IngresoLinea(codigo=1, familia="Departamentos", nombre_variable="Venta_Deptos",
                 cantidad_formula="20", precio_formula="450000", moneda="PEN", tipo_igv="inmobiliario_9"),
    IngresoLinea(codigo=2, familia="Otros ingresos", nombre_variable="Servicio_Extra",
                 cantidad_formula="1", precio_formula="100000", moneda="PEN", tipo_igv="afecto_18"),
    IngresoLinea(codigo=3, familia="Otros ingresos", nombre_variable="Donacion",
                 cantidad_formula="1", precio_formula="5000", moneda="PEN", tipo_igv="ninguno"),
]
m3 = Motor(variables, [], ingresos)
r3 = m3.calcular()
deptos = r3.ingresos[1]
extra = r3.ingresos[2]
donacion = r3.ingresos[3]

bruto_deptos = 20 * 450000
check("venta inmobiliaria: parcial es el bruto (IGV incluido)", deptos.parcial == bruto_deptos)
check("venta inmobiliaria: monto neto = parcial / 1.09", abs(deptos.monto - bruto_deptos/1.09) < 1e-6)
check("venta inmobiliaria: igv = parcial - monto", abs(deptos.igv - (deptos.parcial - deptos.monto)) < 1e-6)

check("venta afecta 18%: monto es la base (cantidad*precio)", extra.monto == 100000)
check("venta afecta 18%: igv = monto*0.18", abs(extra.igv - 18000) < 1e-6)
check("venta afecta 18%: parcial = monto + igv", abs(extra.parcial - 118000) < 1e-6)

check("venta sin igv: monto == parcial, igv == 0", donacion.monto == 5000 and donacion.igv == 0)

check("Total_Ingresos suma el NETO (monto, no el bruto con IGV)",
      abs(r3.total_ingresos - (deptos.monto + extra.monto + donacion.monto)) < 1e-6)

# --- sub-presupuesto: hijos que se agregan con un factor ----------------------
egresos_sub = [
    EgresoLinea(codigo=1, nombre_variable="Instalacion_Medidores", descripcion="Obra complementaria",
                es_subpresupuesto=True, factor_formula="1/[Cantidad_UI]", moneda="PEN", grupo="Obras Complementarias"),
    EgresoLinea(codigo=2, padre_codigo=1, descripcion="Pago a Luz del Sur",
                cantidad_formula="1", precio_formula="45000", moneda="PEN"),
    EgresoLinea(codigo=3, padre_codigo=1, descripcion="Obras civiles en area publica",
                cantidad_formula="1", precio_formula="30000", moneda="PEN"),
    EgresoLinea(codigo=4, padre_codigo=1, descripcion="Tramites municipales",
                cantidad_formula="1", precio_formula="5000", moneda="PEN"),
]
variables_ui = variables + [Variable("Cantidad_UI", formula="40")]
m4 = Motor(variables_ui, egresos_sub, [])
r4 = m4.calcular()
padre = r4.egresos[1]
subtotal_esperado = 45000 + 30000 + 5000
check("sub-presupuesto: el padre no tiene error", padre.error is None)
check("sub-presupuesto: monto = suma de hijos * factor (aqui, dividido entre 40 UI)",
      abs(padre.monto - subtotal_esperado/40) < 1e-6)
check("Total_Egresos NO duplica a los hijos del sub-presupuesto (solo cuenta la raiz)",
      abs(r4.total_egresos - padre.parcial_moneda_principal) < 1e-6)

# --- deteccion de ciclos, con nombres visibles claros --------------------------
egresos_ciclo = [
    EgresoLinea(codigo=1, nombre_variable="A", cantidad_formula="1", precio_formula="[B]+1", moneda="PEN"),
    EgresoLinea(codigo=2, nombre_variable="B", cantidad_formula="1", precio_formula="[A]+1", moneda="PEN"),
]
m5 = Motor(variables, egresos_ciclo, [])
r5 = m5.calcular()
check("ciclo entre dos egresos detectado", r5.egresos[1].error is not None and "ciclo" in r5.egresos[1].error)
check("mensaje de ciclo usa los nombres de variable visibles (A y B), no los codigos internos",
      "A" in r5.egresos[1].error and "B" in r5.egresos[1].error)

# ciclo variable <-> egreso
variables_ciclo = [Variable("X", formula="[Y]+1")]
egresos_ciclo2 = [EgresoLinea(codigo=1, nombre_variable="Y", cantidad_formula="1", precio_formula="[X]+1", moneda="PEN")]
m6 = Motor(variables_ciclo, egresos_ciclo2, [])
r6 = m6.calcular()
check("ciclo cruzado entre variable y egreso detectado", r6.variables["X"].error is not None and "ciclo" in r6.variables["X"].error)

# --- referencia inexistente no tumba el resto ---------------------------------
egresos_falta = [
    EgresoLinea(codigo=1, nombre_variable="Bueno", cantidad_formula="1", precio_formula="100", moneda="PEN"),
    EgresoLinea(codigo=2, nombre_variable="Malo", cantidad_formula="1", precio_formula="[NoExiste]", moneda="PEN"),
]
m7 = Motor(variables, egresos_falta, [])
r7 = m7.calcular()
check("referencia inexistente no tumba el resto del calculo", r7.egresos[2].error is not None and r7.egresos[1].error is None)

# --- sandbox de seguridad ------------------------------------------------------
egresos_hack = [EgresoLinea(codigo=1, cantidad_formula="1", precio_formula="__import__('os').system('echo hackeado')", moneda="PEN")]
m8 = Motor(variables, egresos_hack, [])
r8 = m8.calcular()
check("sandbox bloquea intentos de ejecutar codigo del sistema", r8.egresos[1].error is not None)

print()
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron: {fallos}")
    sys.exit(1)
else:
    print("Todas las pruebas pasaron.")
