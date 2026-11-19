"""Prueba de storage v2: guardar/leer egresos, ingresos y variables reales,
validaciones de nombre, historial, sub-presupuestos, independencia
plantilla/proyecto. Se corre con: python3 tests/test_storage.py"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.motor import Motor
from engine.storage import (
    Archivo,
    EgresoLinea,
    IngresoLinea,
    NombreEnUso,
    Variable,
    crear_archivo,
    nuevo_proyecto_desde_plantilla,
    validar_nombre_variable,
)

fallos = []


def check(nombre, cond):
    estado = "OK " if cond else "FALLO"
    print(f"[{estado}] {nombre}")
    if not cond:
        fallos.append(nombre)


check("nombre valido: letras/numeros/guion bajo", validar_nombre_variable("Area_Vendible_2"))
check("nombre invalido: con espacio", not validar_nombre_variable("Area Vendible"))
check("nombre invalido: empieza con numero", not validar_nombre_variable("2Area"))
check("nombre invalido: caracter especial", not validar_nombre_variable("Área"))

with tempfile.TemporaryDirectory() as tmp:
    ruta = Path(tmp) / "prueba.pin"
    crear_archivo(ruta, tipo="proyecto")

    with Archivo(ruta) as arch:
        arch.guardar_variable(Variable("Cantidad_UI", "Número de unidades inmobiliarias", "40", ""))
        arch.guardar_variable(Variable("Tipo_Cambio", "Tipo de cambio", "3.75", ""))
        arch.guardar_variable(Variable("IGV_Compras", "IGV de compras", "18%", "%"))
        arch.guardar_variable(Variable("IGV_Ventas_Efectivo", "IGV efectivo en venta inmobiliaria", "9%", "%"))

        # -- nombres unicos en TODO el archivo, no solo dentro de su tabla --
        cod1 = arch.guardar_egreso(EgresoLinea(codigo=None, nombre_variable="Costo_Directo",
                                                cantidad_formula="100", precio_formula="200", moneda="PEN"))
        try:
            arch.guardar_variable(Variable("Costo_Directo", "choca con el egreso", "1", ""))
            check("no se puede repetir un nombre de variable entre variables y egresos", False)
        except NombreEnUso:
            check("no se puede repetir un nombre de variable entre variables y egresos", True)

        try:
            arch.guardar_egreso(EgresoLinea(codigo=None, nombre_variable="Costo Directo malo",
                                             cantidad_formula="1", precio_formula="1", moneda="PEN"))
            check("egreso con nombre de variable invalido es rechazado", False)
        except ValueError:
            check("egreso con nombre de variable invalido es rechazado", True)

        # -- ingresos --
        cod_ing1 = arch.guardar_ingreso(IngresoLinea(codigo=None, familia="Departamentos",
                                                       nombre_variable="Venta_Deptos", cantidad_formula="20",
                                                       precio_formula="450000", moneda="PEN", tipo_igv="inmobiliario_9"))

        # -- sub-presupuesto persistido: padre + hijos --
        cod_padre = arch.guardar_egreso(EgresoLinea(codigo=None, nombre_variable="Instalacion_Medidores",
                                                      es_subpresupuesto=True, factor_formula="1/[Cantidad_UI]",
                                                      moneda="PEN", grupo="Obras Complementarias"))
        arch.guardar_egreso(EgresoLinea(codigo=None, padre_codigo=cod_padre, descripcion="Luz del Sur",
                                         cantidad_formula="1", precio_formula="45000", moneda="PEN"))
        arch.guardar_egreso(EgresoLinea(codigo=None, padre_codigo=cod_padre, descripcion="Municipalidad",
                                         cantidad_formula="1", precio_formula="5000", moneda="PEN"))

        raices = arch.listar_egresos_hijos(None)
        hijos = arch.listar_egresos_hijos(cod_padre)
        check("listar egresos raiz no incluye a los hijos del sub-presupuesto", len(raices) == 2)  # Costo_Directo + Instalacion_Medidores
        check("listar egresos hijos devuelve exactamente los 2 hijos", len(hijos) == 2)

        # -- calculo completo end-to-end via storage --
        variables = arch.listar_variables()
        egresos = arch.listar_egresos_todos()
        ingresos = arch.listar_ingresos_todos()
        motor = Motor(variables, egresos, ingresos, arch.moneda_principal, arch.moneda_secundaria)
        resultado = motor.calcular()
        check("calculo completo sin errores", all(r.error is None for r in resultado.egresos.values()))
        check("calculo completo sin errores (ingresos)", all(r.error is None for r in resultado.ingresos.values()))
        check("Total_Egresos y Total_Ingresos calculados", resultado.total_egresos is not None and resultado.total_ingresos is not None)

        # -- eliminar el padre borra tambien los hijos (borrado en cascada) --
        arch.eliminar_egreso(cod_padre)
        check("eliminar un sub-presupuesto elimina tambien a sus hijos", len(arch.listar_egresos_hijos(cod_padre)) == 0)
        check("el hijo huerfano ya no aparece en la lista completa", cod_padre not in [e.codigo for e in arch.listar_egresos_todos()])

        # -- historial --
        c = next(e for e in arch.listar_egresos_todos() if e.nombre_variable == "Costo_Directo")
        c.precio_formula = "250"
        arch.guardar_egreso(c)
        hist = arch.historial_de("egreso", c.codigo)
        check("editar un egreso registra historial", any(h["campo"] == "precio_formula" for h in hist))

    # -- plantilla -> proyecto: independencia --
    ruta_plantilla = Path(tmp) / "plantilla.pin"
    crear_archivo(ruta_plantilla, tipo="plantilla")
    with Archivo(ruta_plantilla) as p:
        p.guardar_variable(Variable("Area_Vendible", "", "", "m2"))  # en blanco, como plantilla

    ruta_proyecto2 = Path(tmp) / "proyecto2.pin"
    nuevo_proyecto_desde_plantilla(ruta_plantilla, ruta_proyecto2)
    with Archivo(ruta_proyecto2) as proy:
        v = proy.obtener_variable("Area_Vendible")
        v.formula = "5000"
        proy.guardar_variable(v)

    with Archivo(ruta_plantilla) as p2:
        check("editar el proyecto no afecta la plantilla original", p2.obtener_variable("Area_Vendible").formula == "")

print()
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron: {fallos}")
    sys.exit(1)
else:
    print("Todas las pruebas pasaron.")
