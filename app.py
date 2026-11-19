#!/usr/bin/env python3
"""
EVALUADOR DE PROYECTOS INMOBILIARIOS — modo texto
====================================================
Software de escritorio, pantalla completa, filosofia WordStar /
WordPerfect / S10 en DOS: sin distracciones, archivos livianos (un
proyecto es UN archivo .pin de pocos KB). Se maneja con teclado (ENTER
confirma, ESC cancela/regresa) o con mouse, lo que sea mas comodo.

Uso:
    python3 app.py

Requiere: Python 3.9+, textual, asteval  (ver requirements.txt)
Funciona igual en Windows, macOS y Linux — corre dentro de la terminal.
"""

from pathlib import Path

from textual.app import App

from ui.screens.inicio import PantallaInicio

DIR_APP = Path(__file__).resolve().parent
DIR_PROYECTOS = DIR_APP / "proyectos"


class SoftwareInmobiliarioApp(App):
    CSS_PATH = "ui/theme.tcss"
    TITLE = "EVALUADOR DE PROYECTOS INMOBILIARIOS"
    SUB_TITLE = "modo texto — ENTER confirma, ESC regresa, mouse opcional"

    def on_mount(self) -> None:
        DIR_PROYECTOS.mkdir(exist_ok=True)
        self.push_screen(PantallaInicio(DIR_PROYECTOS))


def main() -> None:
    SoftwareInmobiliarioApp().run()


if __name__ == "__main__":
    main()
