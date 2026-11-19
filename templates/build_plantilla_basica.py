"""
Genera templates/inmobiliario_basico.pin — plantilla de ejemplo v2, con
Egresos, Ingresos, un sub-presupuesto (Instalación de Medidores) y el
P&L completo ya conectado (Utilidad antes/después de impuestos).

Correr con: python3 templates/build_plantilla_basica.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.storage import Archivo, EgresoLinea, IngresoLinea, Variable, crear_archivo

RUTA = Path(__file__).parent / "inmobiliario_basico.pin"

VARIABLES = [
    # -- inputs del proyecto (en blanco: se llenan al crear el proyecto) --
    Variable("Area_Vendible", "Área vendible total del proyecto", "", "m2", 1),
    Variable("Area_Construida_Total", "Área construida total (incluye sótanos)", "", "m2", 2),
    Variable("Cantidad_UI", "Número de unidades inmobiliarias (departamentos)", "", "unidades", 3),
    Variable("Cantidad_Estacionamientos", "Número de estacionamientos del proyecto", "", "unidades", 4),
    Variable("UIT", "Valor de la UIT vigente", "", "S/.", 5),
    Variable("Tipo_Cambio", "Soles por 1 dólar (usado para convertir partidas en USD)", "", "S//US$", 6),
    Variable("Precio_Venta_m2", "Precio de venta por m2, IGV de ventas incluido", "", "S/.", 7),
    Variable("Costo_m2_Construccion", "Costo directo de construcción por m2", "", "S/.", 8),
    Variable("Precio_Estacionamiento", "Precio de venta por estacionamiento, IGV incluido", "", "S/.", 9),

    # -- constantes de la convención tributaria (ya vienen con el valor de ley) --
    Variable("IGV_Compras", "Tasa de IGV en compras/gastos", "18%", "%", 10),
    Variable("IGV_Ventas_Efectivo", "Tasa efectiva de IGV en primera venta inmobiliaria (ley)", "9%", "%", 11),
    Variable("IGV_Ventas_Regular", "Tasa de IGV en ventas gravadas regulares (no inmobiliarias)", "18%", "%", 12),
    Variable("Tasa_Impuesto_Renta", "Tasa de impuesto a la renta empresarial", "29.5%", "%", 13),

    # -- base de costo directo, separada del egreso para que los fees no
    #    hereden el IGV de compras del costo directo (ver README) --
    Variable("Costo_Directo_Neto", "Costo directo de construcción, sin IGV", "[Area_Construida_Total]*[Costo_m2_Construccion]", "S/.", 20),

    # -- P&L: encadenado de variable a variable, editable como cualquier otra --
    Variable("Utilidad_Antes_Impuestos", "Ingresos netos menos egresos totales", "[Total_Ingresos]-[Total_Egresos]", "S/.", 90),
    Variable("Impuesto_Renta", "Impuesto a la renta sobre la utilidad antes de impuestos", "[Utilidad_Antes_Impuestos]*[Tasa_Impuesto_Renta]", "S/.", 91),
    Variable("Utilidad_Despues_Impuestos", "Utilidad neta del proyecto", "[Utilidad_Antes_Impuestos]-[Impuesto_Renta]", "S/.", 92),
    Variable("Margen_Neto", "Utilidad después de impuestos sobre ingresos", "([Utilidad_Despues_Impuestos]/[Total_Ingresos])*100", "%", 93),
]

EGRESOS_RAIZ = [
    EgresoLinea(codigo=None, codigo_estandarizado="", nombre_variable="Terreno",
                descripcion="Compra del terreno", unidad="glb", cantidad_formula="1",
                precio_formula="", moneda="PEN", afecto_igv=False, grupo="Inversión Inicial",
                orden=1, nota="Operación no gravada con IGV. Completa el precio al crear el proyecto."),
    EgresoLinea(codigo=None, nombre_variable="Alcabala", descripcion="Alcabala por compra de terreno",
                unidad="glb", cantidad_formula="1", precio_formula="([Terreno]-10*[UIT])*3%",
                moneda="PEN", afecto_igv=False, grupo="Inversión Inicial", orden=2,
                nota="Tramo de 10 UIT inafecto; 3% sobre el exceso. No gravada con IGV."),
    EgresoLinea(codigo=None, nombre_variable="Costo_Directo_Construccion",
                descripcion="Costo directo de construcción", unidad="m2", cantidad_formula="1",
                precio_formula="[Costo_Directo_Neto]", moneda="PEN", afecto_igv=True,
                grupo="Costos de Construcción", orden=3),
    EgresoLinea(codigo=None, nombre_variable="Gastos_Generales", descripcion="Gastos generales de obra",
                unidad="glb", cantidad_formula="1", precio_formula="[Costo_Directo_Neto]*10%",
                moneda="PEN", afecto_igv=True, grupo="Costos Indirectos", orden=4,
                nota="Ejemplo de fee como % de otra partida (costo directo neto, sin su IGV)."),
    EgresoLinea(codigo=None, nombre_variable="Instalacion_Medidores",
                descripcion="Obras complementarias — instalación de medidores", unidad="glb",
                moneda="PEN", es_subpresupuesto=True, factor_formula="1.05", grupo="Obras Complementarias",
                orden=5, nota="Sub-presupuesto: ENTRA a esta partida para ver/editar sus componentes. "
                              "El factor (1.05) es un 5% de contingencia interna sobre el subtotal de sus partidas hijas."),
    EgresoLinea(codigo=None, nombre_variable="Marketing_y_Ventas", descripcion="Marketing y fuerza de ventas",
                unidad="glb", cantidad_formula="1", precio_formula="[Total_Ingresos]*3%",
                moneda="PEN", afecto_igv=True, grupo="Costos Indirectos", orden=6,
                nota="Ejemplo de fee como % de INGRESOS (usa el total ya neto de IGV de ventas)."),
    EgresoLinea(codigo=None, nombre_variable="Contingencia", descripcion="Contingencia general del proyecto",
                unidad="glb", cantidad_formula="1", precio_formula="[Total_Ingresos]*3%",
                moneda="PEN", afecto_igv=False, grupo="Costos Indirectos", orden=7),
]

EGRESOS_HIJOS_MEDIDORES = [
    # padre_codigo se completa en tiempo de ejecucion (build), luego de crear al padre
    EgresoLinea(codigo=None, descripcion="Pago a la empresa de distribución eléctrica",
                unidad="glb", cantidad_formula="1", precio_formula="45000", moneda="PEN", orden=1),
    EgresoLinea(codigo=None, descripcion="Obras civiles en área pública", unidad="glb",
                cantidad_formula="1", precio_formula="30000", moneda="PEN", orden=2),
    EgresoLinea(codigo=None, descripcion="Trámites municipales", unidad="glb",
                cantidad_formula="1", precio_formula="5000", moneda="PEN", orden=3),
]

INGRESOS = [
    IngresoLinea(codigo=None, familia="Departamentos", nombre_variable="Venta_Departamentos",
                 descripcion="Venta de unidades inmobiliarias", cantidad_formula="[Area_Vendible]",
                 precio_formula="[Precio_Venta_m2]", moneda="PEN", tipo_igv="inmobiliario_9", orden=1),
    IngresoLinea(codigo=None, familia="Estacionamientos", nombre_variable="Venta_Estacionamientos",
                 descripcion="Venta de estacionamientos", cantidad_formula="[Cantidad_Estacionamientos]",
                 precio_formula="[Precio_Estacionamiento]", moneda="PEN", tipo_igv="inmobiliario_9", orden=2),
    IngresoLinea(codigo=None, familia="Otros Ingresos", nombre_variable="Renta_Temporal",
                 descripcion="Renta temporal de un local (no es venta inmobiliaria: IGV regular 18%)",
                 cantidad_formula="12", precio_formula="3500", moneda="PEN", tipo_igv="afecto_18", orden=3),
]


def main():
    if RUTA.exists():
        RUTA.unlink()
    crear_archivo(RUTA, tipo="plantilla")
    with Archivo(RUTA) as arch:
        for v in VARIABLES:
            arch.guardar_variable(v, registrar_historial=False)
        for e in EGRESOS_RAIZ:
            arch.guardar_egreso(e, registrar_historial=False)

        padre = next(e for e in arch.listar_egresos_todos() if e.nombre_variable == "Instalacion_Medidores")
        for hijo in EGRESOS_HIJOS_MEDIDORES:
            hijo.padre_codigo = padre.codigo
            arch.guardar_egreso(hijo, registrar_historial=False)

        for i in INGRESOS:
            arch.guardar_ingreso(i, registrar_historial=False)

    print(f"Plantilla creada: {RUTA}  ({RUTA.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
