"""Prueba de humo de la interfaz v2: simula teclado y navegacion real
sobre Egresos, Ingresos, Variables, sub-presupuesto, picker de
referencias y deteccion de ciclos en caliente.
Se corre con: python3 tests/test_app_smoke.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import SoftwareInmobiliarioApp, DIR_PROYECTOS  # noqa: E402
from engine.storage import Archivo, EgresoLinea, Variable, crear_archivo  # noqa: E402
from textual.widgets import DataTable, Input  # noqa: E402

fallos = []


def check(nombre, cond):
    estado = "OK " if cond else "FALLO"
    print(f"[{estado}] {nombre}")
    if not cond:
        fallos.append(nombre)


PROYECTO_PRUEBA = DIR_PROYECTOS / "prueba_smoke_v2.pin"


def preparar_proyecto():
    if PROYECTO_PRUEBA.exists():
        PROYECTO_PRUEBA.unlink()
    DIR_PROYECTOS.mkdir(exist_ok=True)
    crear_archivo(PROYECTO_PRUEBA, tipo="proyecto")
    with Archivo(PROYECTO_PRUEBA) as arch:
        arch.guardar_variable(Variable("IGV_Compras", "IGV de compras", "18%", "%"), registrar_historial=False)
        arch.guardar_variable(Variable("Tipo_Cambio", "Tipo de cambio", "3.75", ""), registrar_historial=False)
        arch.guardar_egreso(
            EgresoLinea(codigo=None, nombre_variable="Base_Existente", descripcion="Partida ya existente",
                        cantidad_formula="1", precio_formula="1000", moneda="PEN"),
            registrar_historial=False,
        )


async def escribir(pilot, texto):
    for ch in texto:
        if ch == "_":
            await pilot.press("underscore")
        elif ch == ".":
            await pilot.press("full_stop")
        elif ch == "/":
            await pilot.press("slash")
        elif ch == "[":
            await pilot.press("left_square_bracket")
        elif ch == "]":
            await pilot.press("right_square_bracket")
        elif ch == "*":
            await pilot.press("asterisk")
        elif ch == " ":
            await pilot.press("space")
        else:
            await pilot.press(ch)
        await pilot.pause()


async def correr():
    preparar_proyecto()

    app = SoftwareInmobiliarioApp()
    async with app.run_test(size=(150, 45)) as pilot:
        await pilot.pause()
        check("arranca en la pantalla de inicio", type(app.screen).__name__ == "PantallaInicio")

        lista = app.screen.query_one("#lista_proyectos")
        lista.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        check("ENTER sobre el proyecto abre el menu principal", type(app.screen).__name__ == "PantallaMenuProyecto")

        # -- Egresos: la partida existente aparece, y F2 crea una nueva --
        await pilot.press("f2")
        await pilot.pause()
        check("F2 en el menu abre Egresos", type(app.screen).__name__ == "PantallaEgresos")

        await pilot.press("f2")
        await pilot.pause()
        check("F2 en Egresos abre el formulario de nueva partida", type(app.screen).__name__ == "PantallaEditarEgreso")

        campo_nombre = app.screen.query_one("#nombre_variable", Input)
        campo_nombre.focus()
        await escribir(pilot, "Costo_Nuevo")

        campo_precio = app.screen.query_one("#precio", Input)
        campo_precio.focus()
        await pilot.pause()
        await escribir(pilot, "100*")

        # -- usar el panel de referencias: filtrar y elegir "Base_Existente" --
        filtro = app.screen.query_one("#filtro_referencias", Input)
        filtro.focus()
        await escribir(pilot, "Base_Existente")
        await pilot.pause()
        lista_refs = app.screen.query_one("#lista_referencias")
        lista_refs.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        check("el panel de referencias insertó [Base_Existente] en el campo activo (Precio)",
              "[Base_Existente]" in app.screen.query_one("#precio", Input).value)

        campo_desc = app.screen.query_one("#descripcion", Input)
        campo_desc.focus()
        await escribir(pilot, "Prueba de referencia")

        await pilot.press("enter")
        await pilot.pause()
        check("ENTER en el formulario guarda y regresa a Egresos", type(app.screen).__name__ == "PantallaEgresos")

        # -- sub-presupuesto: crear uno y entrar/salir --
        await pilot.press("f2")
        await pilot.pause()
        campo_nombre2 = app.screen.query_one("#nombre_variable", Input)
        campo_nombre2.focus()
        await escribir(pilot, "Obra_Complementaria")
        campo_desc2 = app.screen.query_one("#descripcion", Input)
        campo_desc2.focus()
        await escribir(pilot, "Sub presupuesto de prueba")
        chk = app.screen.query_one("#es_subpresupuesto")
        chk.value = True
        await pilot.pause()
        check("marcar 'es sub-presupuesto' deshabilita Cantidad y Precio",
              app.screen.query_one("#cantidad", Input).disabled and app.screen.query_one("#precio", Input).disabled)

        campo_desc2.focus()
        await pilot.press("enter")
        await pilot.pause()
        check("ENTER guarda el sub-presupuesto y volvemos a Egresos", type(app.screen).__name__ == "PantallaEgresos")

        with Archivo(PROYECTO_PRUEBA) as arch:
            padre = next(e for e in arch.listar_egresos_todos() if e.nombre_variable == "Obra_Complementaria")
            check("el sub-presupuesto quedo marcado como tal en el archivo", padre.es_subpresupuesto)

        # -- Escape para volver al menu principal --
        await pilot.press("escape")
        await pilot.pause()
        check("ESC en Egresos regresa al menu del proyecto", type(app.screen).__name__ == "PantallaMenuProyecto")

        # -- Ingresos --
        await pilot.press("f3")
        await pilot.pause()
        check("F3 abre Ingresos", type(app.screen).__name__ == "PantallaIngresos")
        await pilot.press("escape")
        await pilot.pause()

        # -- Variables: click con mouse para abrir Variables --
        await pilot.click("#btn_variables")
        await pilot.pause()
        check("click en el boton abre Variables", type(app.screen).__name__ == "PantallaVariables")

        tabla_vars = app.screen.query_one("#tabla_variables", DataTable)
        check("las variables existentes aparecen en la tabla", tabla_vars.row_count == 2)
        await pilot.press("escape")
        await pilot.pause()

        # -- Reporte P&L --
        await pilot.press("f6")
        await pilot.pause()
        check("F6 abre el Reporte P&L", type(app.screen).__name__ == "PantallaReportePnL")
        await pilot.press("escape")
        await pilot.pause(0.3)
        check("ESC en Reporte P&L regresa al menu del proyecto", type(app.screen).__name__ == "PantallaMenuProyecto")

        # -- deteccion de ciclo en caliente, en la pantalla de variables --
        await pilot.press("f4")
        await pilot.pause()
        await pilot.press("f2")
        await pilot.pause()
        check("F2 en Variables abre el formulario de nueva variable", type(app.screen).__name__ == "PantallaEditarVariable")
        campo_n = app.screen.query_one("#nombre_variable", Input)
        campo_n.focus()
        await escribir(pilot, "Ciclo_A")
        campo_f = app.screen.query_one("#formula", Input)
        campo_f.focus()
        await escribir(pilot, "[Ciclo_A]")
        await pilot.press("enter")
        await pilot.pause()
        check("un ciclo consigo misma NO deja salir del formulario (bloquea con mensaje claro)",
              type(app.screen).__name__ == "PantallaEditarVariable")
        mensaje = app.screen.query_one("#mensaje")
        texto_mensaje = mensaje.content
        check("el mensaje de error menciona 'ciclo'", "ciclo" in str(texto_mensaje).lower())
        await pilot.press("escape")
        await pilot.pause()
        check("ESC cancela y regresa a Variables sin guardar el ciclo", type(app.screen).__name__ == "PantallaVariables")

        with Archivo(PROYECTO_PRUEBA) as arch:
            check("la variable con ciclo NO quedo guardada (Escape cancelo)", arch.obtener_variable("Ciclo_A") is None)

        # -- ESC en Variables regresa al menu del proyecto --
        await pilot.press("escape")
        await pilot.pause()
        check("ESC en Variables regresa al menu del proyecto", type(app.screen).__name__ == "PantallaMenuProyecto")

        # -- cerrar proyecto --
        await pilot.press("escape")
        await pilot.pause()
        check("ESC en el menu del proyecto cierra y regresa al inicio", type(app.screen).__name__ == "PantallaInicio")

    if PROYECTO_PRUEBA.exists():
        PROYECTO_PRUEBA.unlink()
    respaldo = PROYECTO_PRUEBA.with_suffix(".pin.bak")
    if respaldo.exists():
        respaldo.unlink()


asyncio.run(correr())

print()
if fallos:
    print(f"{len(fallos)} prueba(s) fallaron: {fallos}")
    sys.exit(1)
else:
    print("Todas las pruebas de interfaz pasaron.")
