# Evaluador de Proyectos Inmobiliarios — modo texto

Software de escritorio, de pantalla completa — filosofía WordStar /
WordPerfect / S10 en DOS. Sin distracciones, sin servidor, sin base de
datos externa. Cada proyecto es **un solo archivo** (`.pin`) de pocos KB
que se copia, se envía por correo o se guarda en un USB, igual que en las
bases de datos de esa época (dBase, FoxPro).

Se maneja con teclado (rápido, como el software original: **ENTER**
confirma/guarda, **ESC** cancela/regresa) o con mouse (clicks en botones,
en las filas de las tablas, en la lista de referencias) — lo que sea más
cómodo en cada momento.

Por dentro es el mismo motor de cálculo paramétrico del diseño original:
cada partida tiene su propia fórmula en texto, referenciando otras
partidas o variables por nombre (`[Terreno]`, `[UIT]`), con resolución
automática del orden de cálculo, detección de ciclos **en el momento en
que se guardan** (no hay que esperar a un recálculo aparte), historial de
cambios por partida, y evaluación en una caja de arena segura (sin
acceso a archivos, red ni comandos del sistema).

## Por qué es tan liviano

No hay Postgres ni Docker. Cada plantilla o proyecto es un archivo SQLite
(`.pin`) autocontenido: la plantilla trae las fórmulas y dependencias, en
blanco de datos; "crear un proyecto nuevo" es literalmente copiar ese
archivo. La plantilla de ejemplo (`templates/inmobiliario_basico.pin`)
pesa **52 KB** — cabrían más de 25 plantillas completas en un diskette de
1.44 MB.

Si en algún momento se necesita multiusuario o acceso remoto real, esta
misma capa de motor (`engine/`) se puede envolver con una API (FastAPI +
Postgres) sin tocar las fórmulas ni la lógica de cálculo — son piezas
independientes a propósito.

## Instalación (Windows, macOS y Linux)

Descarga el código (botón **Code → Download ZIP** en GitHub, o con git):

```bash
git clone https://github.com/JuanGayoso/Evaluador_Inmo.git
cd Evaluador_Inmo
```

La forma más simple es hacer doble click en:

- **macOS / Linux**: `iniciar.command`
- **Windows**: `iniciar.bat`

La primera vez, el script crea automáticamente un entorno aislado
(`venv/`) e instala las dependencias ahí — así nunca pelea con permisos
del Python del sistema (el error típico de macOS: *"Lacking write
permission to .../Python.framework/..."* al hacer `pip install`
directamente sobre el Python del sistema).

Si prefieres la línea de comandos:

```bash
python3 -m venv venv
source venv/bin/activate      # en Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Requiere Python 3.9 o superior (ya viene instalado en macOS/Linux; en
Windows se instala gratis desde python.org, marcando "Add to PATH"). Se
recomienda una terminal moderna (Windows Terminal, iTerm2, la Terminal de
macOS) para que los colores y bordes de línea se vean correctamente.

## Uso

Al abrir, aparece la pantalla de arranque con la lista de proyectos
(`proyectos/*.pin`). Las teclas de función abajo de cada pantalla son
siempre visibles, como en WordPerfect, y cada acción también tiene su
botón equivalente para hacer click con el mouse.

- **F4** — Nuevo proyecto desde una plantilla (`templates/*.pin`). El
  nombre y la ubicación del archivo se fijan en ese momento y ya no
  cambian: todo el trabajo posterior se autoguarda ahí.
- **ENTER** — Abrir el proyecto seleccionado (o doble click)

Dentro de un proyecto, el menú principal muestra un resumen de P&L en
vivo y da acceso a:

- **F2 Egresos** — costos y gastos, organizados por grupo (el grupo
  funciona como título de sección en la tabla; subtotaliza solo).
- **F3 Ingresos** — ventas y otros ingresos, organizados por familia.
- **F4 Variables** — valores generales del proyecto (UIT, tipo de
  cambio, tasas de IGV, área vendible, etc.) — también pueden llevar
  fórmula, no solo un número suelto.
- **F5 Configuración** — moneda principal y secundaria del proyecto.
- **F6 Reporte P&L** — Ingresos − Egresos → Utilidad antes de impuestos →
  Impuesto a la Renta → Utilidad después de impuestos, exportable a
  `.txt` con F2 desde esa pantalla.
- **ESC** — regresar un nivel (de un formulario a su lista, de una lista
  al menú, del menú al inicio — cada ESC sube un escalón).

Dentro de cada tabla (Egresos, Ingresos, Variables): **F2** nueva
partida, **ENTER** o doble click para abrir/editar, **F6** historial de
cambios, **F8** eliminar, **F9** recalcular manualmente (aunque el
cálculo ya es automático en cada guardado).

### Fórmulas

Cualquier campo de valor (Cantidad, Precio, el Valor de una Variable)
acepta un número simple o una fórmula completa — así queda un rastro de
cualquier cálculo mental que hagas, en vez de escribir un resultado ya
calculado a mano. Soporta operaciones básicas, potencias (`^`) y
porcentajes (`%`):

```
[Terreno]*0.10                      <- 10% de otra partida
([Terreno]-10*[UIT])*3%             <- Alcabala, tramo de 10 UIT + %
[Area_Techada]^1.0*[Costo_m2]       <- potencia
[Ingresos_Ventas]/(1+[IGV_Ventas_Efectivo])   <- IGV "hacia atrás"
```

Las referencias van entre corchetes, por nombre — nunca por posición, así
que reordenar o insertar partidas nunca rompe una fórmula existente. En
cada formulario hay un panel a la derecha con todos los nombres
disponibles (variables, egresos e ingresos ya definidos): se puede
escribir para filtrar y hacer click o ENTER para insertarlo en el campo
activo, en vez de tener que recordar el nombre exacto de memoria.

Si al guardar una fórmula se genera un ciclo (dos partidas que dependen
una de la otra, directa o indirectamente), el programa lo detecta al
instante, señala los nombres involucrados y no deja salir del formulario
hasta corregirlo — ESC en ese momento cancela y descarta el cambio en vez
de dejar guardada una fórmula rota.

### Sub-presupuestos

Una partida de Egresos puede marcarse como "sub-presupuesto": en vez de
Cantidad/Precio propios, contiene otras partidas (ENTER sobre ella entra
a su propia tabla, ESC regresa al nivel de arriba). Su monto es la suma
de sus hijos multiplicada por un **factor** — que también puede ser
valor, fórmula, o ambos. Por ejemplo, un sub-presupuesto de instalación
de medidores (Luz del Sur + obras civiles + trámites municipales) con
`factor = 1/[Cantidad_UI]` termina expresado por Unidad Inmobiliaria en
el presupuesto del padre.

### Autoguardado

Cada cambio se guarda al instante en el archivo `.pin` del proyecto (no
hay un botón "Guardar" aparte que se pueda olvidar). Además, cada 3
minutos se genera una copia de seguridad (`nombre.pin.bak`) junto al
archivo original, por si el proceso se interrumpe a media edición.

## Estructura del proyecto

```
app.py                          punto de entrada
engine/
  motor.py                      grafo de dependencias, orden topológico,
                                 detección de ciclos, evaluación segura
  storage.py                    lectura/escritura de archivos .pin (SQLite)
ui/
  theme.tcss                    tema "pantalla azul" (16 colores, bordes
                                 de línea, sin adornos)
  comunes.py                    recalculo compartido, panel de referencias
  widgets/
    selector_referencias.py     panel filtrable de nombres disponibles
  screens/                      cada pantalla de la aplicación
templates/
  inmobiliario_basico.pin       plantilla de ejemplo (proyecto inmobiliario
                                 peruano: Terreno, Alcabala, IGV, fees,
                                 sub-presupuesto, P&L...)
  build_plantilla_basica.py     script que genera esa plantilla
proyectos/                      aquí se guardan los proyectos que crees
                                 (se genera automáticamente)
tests/                          pruebas del motor, del storage y de la
                                 interfaz (simulan teclado y mouse reales)
```

## Pruebas

```bash
python3 tests/test_motor.py         # motor de cálculo
python3 tests/test_storage.py       # plantilla -> proyecto -> persistencia
python3 tests/test_plantilla_e2e.py # plantilla completa, cero errores, P&L
python3 tests/test_app_smoke.py     # interfaz completa, simulando teclado y mouse
```

## Decisiones de diseño (para quien vaya a extender esto)

- **Qué valor expone cada partida al ser referenciada por otra**:
  Egresos exponen su `Parcial en moneda principal` (con IGV incluido);
  Ingresos exponen su `Monto en moneda principal` (neto, sin IGV de
  ventas). La razón: el IGV de ventas es un pasivo con el Estado, no
  ingreso real del proyecto; el IGV de muchas compras inmobiliarias no es
  recuperable, así que conservadoramente se trata como costo real. Por
  este motivo, si necesitas que una comisión o fee se calcule sobre el
  costo **sin** el IGV que ya trae ese costo, primero pásalo por una
  Variable intermedia (ver `Costo_Directo_Neto` en la plantilla) en vez
  de referenciar directamente la partida de Egreso.
- **Nombres de variable convencionales** que el motor reconoce para
  conversión de moneda e IGV: `Tipo_Cambio`, `IGV_Compras`,
  `IGV_Ventas_Efectivo`, `IGV_Ventas_Regular` (ver `engine/storage.py`).
  Si tu plantilla usa otro nombre para el tipo de cambio o las tasas de
  IGV, esas conversiones automáticas no van a activarse.
- **El grupo/familia es el título** de cada sección en Egresos/Ingresos —
  no hay una entidad "título" separada; se subtotaliza automáticamente
  por el texto que escribas en ese campo.
- **`_render` es un nombre reservado de Textual** (`Widget._render()`):
  si en algún momento agregas un método con ese nombre a una pantalla,
  vas a pisar el renderizado interno del framework y vas a ver un
  `AttributeError` críptico en el compositor. Usa cualquier otro nombre
  (`_actualizar_reporte`, `_refrescar`, etc.).

Estos son solo el ejemplo de fábrica — la plantilla se edita como
cualquier proyecto para ajustarla a tu forma de evaluar.

## Despliegue y distribución

**Requisitos:** Python 3.9 o superior y conexión a internet solo la primera
vez (para instalar `textual` y `asteval` dentro de `venv/`).

**Uso en un equipo nuevo:** clonar o descargar el repositorio y ejecutar
`iniciar.command` (macOS/Linux) o `iniciar.bat` (Windows). No hay servidor,
base de datos ni configuración adicional.

**Dónde quedan los datos:** cada proyecto es un archivo `.pin` en la carpeta
`proyectos/`. Esa carpeta está en `.gitignore`: los proyectos de cada usuario
no se suben al repositorio. Para compartir uno, copia el `.pin`.

**Solución de problemas**

- *`ModuleNotFoundError: No module named 'textual'`*: el `venv/` está dañado
  (por ejemplo, se movió la carpeta después de crearlo). Borra la carpeta
  `venv/` y vuelve a ejecutar el launcher: se recrea sola.
- *`Lacking write permission ... Python.framework`*: `pip` está instalando en
  el Python del sistema en vez del `venv/`. Mismo arreglo: borrar `venv/`.
- *Colores o bordes extraños*: usa una terminal moderna (Windows Terminal,
  iTerm2, Terminal de macOS).

**Hoja de ruta (distribución sin instalar Python):** empaquetar con
PyInstaller un ejecutable por sistema operativo (`.exe` para Windows y
binario/`.app` para macOS), compilado con GitHub Actions. Requerirá mover la
carpeta de proyectos a una ruta del usuario (p. ej. `Documentos/Evaluador`).
