"""
Capa de almacenamiento — filosofia "diskette": un proyecto o una plantilla
es UN SOLO ARCHIVO SQLite (.pin). Sin servidor, sin Docker, sin Postgres.

Esquema v2: tres tipos de renglon con nombre propio (Variables, Egresos,
Ingresos) que comparten un mismo espacio de nombres para referenciarse
entre si por [Nombre de variable] — nunca por posicion. Un Egreso puede
ser en si mismo un sub-presupuesto (contiene otros Egresos "hijos"); su
Monto sale de sumar a sus hijos y aplicarles un factor.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    clave   TEXT PRIMARY KEY,
    valor   TEXT
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave   TEXT PRIMARY KEY,
    valor   TEXT
);

CREATE TABLE IF NOT EXISTS variables (
    nombre_variable TEXT PRIMARY KEY,
    descripcion     TEXT,
    formula         TEXT,      -- valor literal o formula; NULL/'' = pendiente de llenar
    unidad          TEXT,
    orden           INTEGER
);

CREATE TABLE IF NOT EXISTS egresos (
    codigo              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_estandarizado TEXT,
    nombre_variable     TEXT UNIQUE,     -- NULL si esta partida no se referencia en otro lado
    descripcion         TEXT,
    unidad              TEXT,
    cantidad_formula    TEXT,
    precio_formula      TEXT,
    moneda              TEXT,
    afecto_igv          INTEGER DEFAULT 0,
    grupo               TEXT,
    es_subpresupuesto   INTEGER DEFAULT 0,
    factor_formula      TEXT,
    padre_codigo        INTEGER,          -- NULL = nivel raiz del presupuesto
    orden               INTEGER,
    nota                TEXT
);

CREATE TABLE IF NOT EXISTS ingresos (
    codigo              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_estandarizado TEXT,
    familia             TEXT,
    nombre_variable     TEXT UNIQUE,
    descripcion         TEXT,
    cantidad_formula    TEXT,
    precio_formula      TEXT,
    moneda              TEXT,
    tipo_igv            TEXT,             -- 'ninguno' | 'afecto_18' | 'inmobiliario_9'
    orden               INTEGER,
    nota                TEXT
);

CREATE TABLE IF NOT EXISTS historial (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo            TEXT,       -- 'variable' | 'egreso' | 'ingreso'
    identificador   TEXT,       -- nombre_variable o codigo, como texto
    campo           TEXT,       -- que campo cambio (formula, cantidad_formula, ...)
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    cuando          TEXT
);
"""

DEFAULT_METADATA = {
    "tipo": "plantilla",
    "version_esquema": "2",
    "creado": "",
    "origen_plantilla": "",
}

DEFAULT_CONFIG = {
    "moneda_principal": "PEN",
    "moneda_secundaria": "USD",
}

# Convencion de nombres de variables que el motor busca automaticamente
# para tipo de cambio e IGV — ver README para el detalle.
NOMBRE_TIPO_CAMBIO = "Tipo_Cambio"
NOMBRE_IGV_COMPRAS = "IGV_Compras"
NOMBRE_IGV_VENTAS_EFECTIVO = "IGV_Ventas_Efectivo"
NOMBRE_IGV_VENTAS_REGULAR = "IGV_Ventas_Regular"

NOMBRE_VARIABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validar_nombre_variable(nombre: str) -> bool:
    """Solo letras, numeros y '_' como separador; no puede empezar con numero."""
    return bool(NOMBRE_VARIABLE_RE.match(nombre))


@dataclass
class Variable:
    nombre_variable: str
    descripcion: str = ""
    formula: str | None = ""
    unidad: str = ""
    orden: int = 0


@dataclass
class EgresoLinea:
    codigo: int | None
    codigo_estandarizado: str = ""
    nombre_variable: str | None = None
    descripcion: str = ""
    unidad: str = ""
    cantidad_formula: str = ""
    precio_formula: str = ""
    moneda: str = "PEN"
    afecto_igv: bool = False
    grupo: str = ""
    es_subpresupuesto: bool = False
    factor_formula: str = "1"
    padre_codigo: int | None = None
    orden: int = 0
    nota: str = ""


@dataclass
class IngresoLinea:
    codigo: int | None
    codigo_estandarizado: str = ""
    familia: str = ""
    nombre_variable: str | None = None
    descripcion: str = ""
    cantidad_formula: str = ""
    precio_formula: str = ""
    moneda: str = "PEN"
    tipo_igv: str = "ninguno"  # 'ninguno' | 'afecto_18' | 'inmobiliario_9'
    orden: int = 0
    nota: str = ""


class NombreEnUso(ValueError):
    pass


def crear_archivo(ruta: Path, tipo: str = "plantilla") -> None:
    ruta = Path(ruta)
    if ruta.exists():
        raise FileExistsError(f"Ya existe: {ruta}")
    con = sqlite3.connect(ruta)
    try:
        con.executescript(SCHEMA)
        meta = dict(DEFAULT_METADATA)
        meta["tipo"] = tipo
        meta["creado"] = datetime.now(timezone.utc).isoformat()
        con.executemany("INSERT INTO metadata (clave, valor) VALUES (?, ?)", meta.items())
        con.executemany("INSERT INTO configuracion (clave, valor) VALUES (?, ?)", DEFAULT_CONFIG.items())
        con.commit()
    finally:
        con.close()


def nuevo_proyecto_desde_plantilla(plantilla: Path, destino: Path) -> None:
    plantilla, destino = Path(plantilla), Path(destino)
    if destino.exists():
        raise FileExistsError(f"Ya existe: {destino}")
    shutil.copy(plantilla, destino)
    con = sqlite3.connect(destino)
    try:
        con.execute("UPDATE metadata SET valor = ? WHERE clave = 'tipo'", ("proyecto",))
        con.execute(
            "INSERT OR REPLACE INTO metadata (clave, valor) VALUES ('origen_plantilla', ?)",
            (plantilla.name,),
        )
        con.execute(
            "INSERT OR REPLACE INTO metadata (clave, valor) VALUES ('creado', ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
        con.commit()
    finally:
        con.close()


class Archivo:
    """Envoltorio sobre un archivo .pin abierto (plantilla o proyecto)."""

    def __init__(self, ruta: Path):
        self.ruta = Path(ruta)
        self.con = sqlite3.connect(self.ruta)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    def close(self):
        self.con.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # -- metadata / configuracion -----------------------------------------
    def get_meta(self, clave: str) -> str | None:
        row = self.con.execute("SELECT valor FROM metadata WHERE clave = ?", (clave,)).fetchone()
        return row["valor"] if row else None

    def get_config(self, clave: str, default: str = "") -> str:
        row = self.con.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
        return row["valor"] if row else default

    def set_config(self, clave: str, valor: str) -> None:
        self.con.execute(
            "INSERT INTO configuracion (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, valor),
        )
        self.con.commit()

    @property
    def moneda_principal(self) -> str:
        return self.get_config("moneda_principal", "PEN")

    @property
    def moneda_secundaria(self) -> str:
        return self.get_config("moneda_secundaria", "USD")

    # -- validacion de nombres, unica en TODO el archivo --------------------
    def nombre_en_uso(self, nombre: str, excluir: tuple[str, str | int] | None = None) -> bool:
        if excluir != ("variable", nombre):
            fila = self.con.execute(
                "SELECT 1 FROM variables WHERE nombre_variable = ?", (nombre,)
            ).fetchone()
            if fila:
                return True

        fila = self.con.execute(
            "SELECT codigo FROM egresos WHERE nombre_variable = ?", (nombre,)
        ).fetchone()
        if fila and excluir != ("egreso", fila["codigo"]):
            return True

        fila = self.con.execute(
            "SELECT codigo FROM ingresos WHERE nombre_variable = ?", (nombre,)
        ).fetchone()
        if fila and excluir != ("ingreso", fila["codigo"]):
            return True

        return False

    def _registrar_historial(self, tipo: str, identificador, campo: str, anterior, nuevo) -> None:
        if anterior == nuevo:
            return
        self.con.execute(
            """INSERT INTO historial (tipo, identificador, campo, valor_anterior, valor_nuevo, cuando)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tipo, str(identificador), campo, anterior, nuevo, datetime.now(timezone.utc).isoformat()),
        )

    # -- variables -----------------------------------------------------------
    def listar_variables(self) -> list[Variable]:
        rows = self.con.execute("SELECT * FROM variables ORDER BY orden, nombre_variable").fetchall()
        return [
            Variable(r["nombre_variable"], r["descripcion"] or "", r["formula"], r["unidad"] or "", r["orden"] or 0)
            for r in rows
        ]

    def obtener_variable(self, nombre: str) -> Variable | None:
        r = self.con.execute("SELECT * FROM variables WHERE nombre_variable = ?", (nombre,)).fetchone()
        if not r:
            return None
        return Variable(r["nombre_variable"], r["descripcion"] or "", r["formula"], r["unidad"] or "", r["orden"] or 0)

    def guardar_variable(self, v: Variable, registrar_historial: bool = True) -> None:
        if self.nombre_en_uso(v.nombre_variable, excluir=("variable", v.nombre_variable)):
            raise NombreEnUso(f"El nombre '{v.nombre_variable}' ya está en uso en este archivo.")
        anterior = self.con.execute(
            "SELECT formula FROM variables WHERE nombre_variable = ?", (v.nombre_variable,)
        ).fetchone()
        self.con.execute(
            """INSERT INTO variables (nombre_variable, descripcion, formula, unidad, orden)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(nombre_variable) DO UPDATE SET
                 descripcion=excluded.descripcion, formula=excluded.formula,
                 unidad=excluded.unidad, orden=excluded.orden""",
            (v.nombre_variable, v.descripcion, v.formula, v.unidad, v.orden),
        )
        if registrar_historial:
            self._registrar_historial(
                "variable", v.nombre_variable, "formula",
                anterior["formula"] if anterior else None, v.formula,
            )
        self.con.commit()

    def eliminar_variable(self, nombre: str) -> None:
        self.con.execute("DELETE FROM variables WHERE nombre_variable = ?", (nombre,))
        self.con.commit()

    # -- egresos ---------------------------------------------------------------
    def _fila_a_egreso(self, r) -> EgresoLinea:
        return EgresoLinea(
            codigo=r["codigo"],
            codigo_estandarizado=r["codigo_estandarizado"] or "",
            nombre_variable=r["nombre_variable"],
            descripcion=r["descripcion"] or "",
            unidad=r["unidad"] or "",
            cantidad_formula=r["cantidad_formula"] or "",
            precio_formula=r["precio_formula"] or "",
            moneda=r["moneda"] or "PEN",
            afecto_igv=bool(r["afecto_igv"]),
            grupo=r["grupo"] or "",
            es_subpresupuesto=bool(r["es_subpresupuesto"]),
            factor_formula=r["factor_formula"] or "1",
            padre_codigo=r["padre_codigo"],
            orden=r["orden"] or 0,
            nota=r["nota"] or "",
        )

    def listar_egresos_todos(self) -> list[EgresoLinea]:
        rows = self.con.execute("SELECT * FROM egresos ORDER BY orden, codigo").fetchall()
        return [self._fila_a_egreso(r) for r in rows]

    def listar_egresos_hijos(self, padre_codigo: int | None) -> list[EgresoLinea]:
        if padre_codigo is None:
            rows = self.con.execute(
                "SELECT * FROM egresos WHERE padre_codigo IS NULL ORDER BY orden, codigo"
            ).fetchall()
        else:
            rows = self.con.execute(
                "SELECT * FROM egresos WHERE padre_codigo = ? ORDER BY orden, codigo", (padre_codigo,)
            ).fetchall()
        return [self._fila_a_egreso(r) for r in rows]

    def obtener_egreso(self, codigo: int) -> EgresoLinea | None:
        r = self.con.execute("SELECT * FROM egresos WHERE codigo = ?", (codigo,)).fetchone()
        return self._fila_a_egreso(r) if r else None

    def guardar_egreso(self, e: EgresoLinea, registrar_historial: bool = True) -> int:
        if e.nombre_variable:
            if not validar_nombre_variable(e.nombre_variable):
                raise ValueError(
                    f"'{e.nombre_variable}' no es un nombre de variable válido "
                    "(solo letras, números y '_' , sin empezar con número)."
                )
            if self.nombre_en_uso(e.nombre_variable, excluir=("egreso", e.codigo)):
                raise NombreEnUso(f"El nombre '{e.nombre_variable}' ya está en uso en este archivo.")

        if e.codigo is None:
            cur = self.con.execute(
                """INSERT INTO egresos (codigo_estandarizado, nombre_variable, descripcion, unidad,
                     cantidad_formula, precio_formula, moneda, afecto_igv, grupo,
                     es_subpresupuesto, factor_formula, padre_codigo, orden, nota)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (e.codigo_estandarizado, e.nombre_variable, e.descripcion, e.unidad,
                 e.cantidad_formula, e.precio_formula, e.moneda, int(e.afecto_igv), e.grupo,
                 int(e.es_subpresupuesto), e.factor_formula, e.padre_codigo, e.orden, e.nota),
            )
            self.con.commit()
            return cur.lastrowid

        anterior = self.obtener_egreso(e.codigo)
        self.con.execute(
            """UPDATE egresos SET codigo_estandarizado=?, nombre_variable=?, descripcion=?, unidad=?,
                 cantidad_formula=?, precio_formula=?, moneda=?, afecto_igv=?, grupo=?,
                 es_subpresupuesto=?, factor_formula=?, padre_codigo=?, orden=?, nota=?
               WHERE codigo=?""",
            (e.codigo_estandarizado, e.nombre_variable, e.descripcion, e.unidad,
             e.cantidad_formula, e.precio_formula, e.moneda, int(e.afecto_igv), e.grupo,
             int(e.es_subpresupuesto), e.factor_formula, e.padre_codigo, e.orden, e.nota, e.codigo),
        )
        if registrar_historial and anterior:
            self._registrar_historial("egreso", e.codigo, "cantidad_formula", anterior.cantidad_formula, e.cantidad_formula)
            self._registrar_historial("egreso", e.codigo, "precio_formula", anterior.precio_formula, e.precio_formula)
            self._registrar_historial("egreso", e.codigo, "factor_formula", anterior.factor_formula, e.factor_formula)
        self.con.commit()
        return e.codigo

    def eliminar_egreso(self, codigo: int) -> None:
        for hijo in self.listar_egresos_hijos(codigo):
            self.eliminar_egreso(hijo.codigo)
        self.con.execute("DELETE FROM egresos WHERE codigo = ?", (codigo,))
        self.con.commit()

    # -- ingresos --------------------------------------------------------------
    def _fila_a_ingreso(self, r) -> IngresoLinea:
        return IngresoLinea(
            codigo=r["codigo"],
            codigo_estandarizado=r["codigo_estandarizado"] or "",
            familia=r["familia"] or "",
            nombre_variable=r["nombre_variable"],
            descripcion=r["descripcion"] or "",
            cantidad_formula=r["cantidad_formula"] or "",
            precio_formula=r["precio_formula"] or "",
            moneda=r["moneda"] or "PEN",
            tipo_igv=r["tipo_igv"] or "ninguno",
            orden=r["orden"] or 0,
            nota=r["nota"] or "",
        )

    def listar_ingresos_todos(self) -> list[IngresoLinea]:
        rows = self.con.execute("SELECT * FROM ingresos ORDER BY orden, codigo").fetchall()
        return [self._fila_a_ingreso(r) for r in rows]

    def obtener_ingreso(self, codigo: int) -> IngresoLinea | None:
        r = self.con.execute("SELECT * FROM ingresos WHERE codigo = ?", (codigo,)).fetchone()
        return self._fila_a_ingreso(r) if r else None

    def guardar_ingreso(self, i: IngresoLinea, registrar_historial: bool = True) -> int:
        if i.nombre_variable:
            if not validar_nombre_variable(i.nombre_variable):
                raise ValueError(
                    f"'{i.nombre_variable}' no es un nombre de variable válido "
                    "(solo letras, números y '_' , sin empezar con número)."
                )
            if self.nombre_en_uso(i.nombre_variable, excluir=("ingreso", i.codigo)):
                raise NombreEnUso(f"El nombre '{i.nombre_variable}' ya está en uso en este archivo.")

        if i.codigo is None:
            cur = self.con.execute(
                """INSERT INTO ingresos (codigo_estandarizado, familia, nombre_variable, descripcion,
                     cantidad_formula, precio_formula, moneda, tipo_igv, orden, nota)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (i.codigo_estandarizado, i.familia, i.nombre_variable, i.descripcion,
                 i.cantidad_formula, i.precio_formula, i.moneda, i.tipo_igv, i.orden, i.nota),
            )
            self.con.commit()
            return cur.lastrowid

        anterior = self.obtener_ingreso(i.codigo)
        self.con.execute(
            """UPDATE ingresos SET codigo_estandarizado=?, familia=?, nombre_variable=?, descripcion=?,
                 cantidad_formula=?, precio_formula=?, moneda=?, tipo_igv=?, orden=?, nota=?
               WHERE codigo=?""",
            (i.codigo_estandarizado, i.familia, i.nombre_variable, i.descripcion,
             i.cantidad_formula, i.precio_formula, i.moneda, i.tipo_igv, i.orden, i.nota, i.codigo),
        )
        if registrar_historial and anterior:
            self._registrar_historial("ingreso", i.codigo, "cantidad_formula", anterior.cantidad_formula, i.cantidad_formula)
            self._registrar_historial("ingreso", i.codigo, "precio_formula", anterior.precio_formula, i.precio_formula)
        self.con.commit()
        return i.codigo

    def eliminar_ingreso(self, codigo: int) -> None:
        self.con.execute("DELETE FROM ingresos WHERE codigo = ?", (codigo,))
        self.con.commit()

    # -- historial ---------------------------------------------------------------
    def historial_de(self, tipo: str, identificador) -> list[sqlite3.Row]:
        return self.con.execute(
            "SELECT * FROM historial WHERE tipo = ? AND identificador = ? ORDER BY id DESC",
            (tipo, str(identificador)),
        ).fetchall()

    def tamano_bytes(self) -> int:
        return self.ruta.stat().st_size
