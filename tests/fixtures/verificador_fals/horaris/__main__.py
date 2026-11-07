"""Verificador FALSO: imita la interfaz de `python -m horaris check` sin calcular nada.

Acepta los mismos argumentos que el verificador real y escribe `--json` (un objeto con `veredicte`, `argv` y
`pythonutf8`) y `--violacions` (un CSV solo con cabecera). El comportamiento lo elige HORARIS_FALS_MODE:
no_valida (por defecto, sale 1), valida (sale 0), error (sale 2), lent (duerme 5 s y luego como no_valida) y
veredicte_raro (veredicto fuera de la lista, sale 0). No imprime datos; el modo error escribe un marcador fijo
en stderr para que los tests comprueben que no se filtra.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

MARCADOR_ERROR: str = "DADA-FALSA-9001"
CAPCALERA_VIOLACIONS: list[str] = ["regla", "sessions", "detall", "compta", "declarada", "heretada"]
OPCIONS_AMB_VALOR: frozenset[str] = frozenset(
    {"--paquet", "--json", "--violacions", "--semestre", "--escenari", "--referencia", "--relaxacions"}
)
OPCIONS_SENSE_VALOR: frozenset[str] = frozenset({"--nomes-aules"})
# mode -> (veredicte, código de salida)
RESULTAT_PER_MODE: dict[str, tuple[str, int]] = {
    "no_valida": ("NO VALIDA", 1),
    "lent": ("NO VALIDA", 1),
    "valida": ("VALIDA", 0),
    "veredicte_raro": ("QUIZA", 0),
}


def _parseja(args: list[str]) -> tuple[str, dict[str, str]] | None:
    """Devuelve (proposta, opciones) o None si los argumentos no encajan con la interfaz."""
    proposta: str | None = None
    valors: dict[str, str] = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in OPCIONS_SENSE_VALOR:
            valors[arg] = ""
            i += 1
        elif arg in OPCIONS_AMB_VALOR:
            if i + 1 >= len(args):
                return None
            valors[arg] = args[i + 1]
            i += 2
        elif proposta is None and not arg.startswith("--"):
            proposta = arg
            i += 1
        else:
            return None
    if proposta is None:
        return None
    return proposta, valors


def _escriu_json(ruta: str, veredicte: str, argv: list[str]) -> None:
    dades: dict[str, object] = {
        "veredicte": veredicte,
        "argv": argv,
        "pythonutf8": os.environ.get("PYTHONUTF8"),
    }
    Path(ruta).write_text(json.dumps(dades, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _escriu_violacions(ruta: str) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as fitxer:
        csv.writer(fitxer, lineterminator="\n").writerow(CAPCALERA_VIOLACIONS)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada; devuelve el código de salida."""
    args = sys.argv[1:] if argv is None else argv
    if not args or args[0] != "check":
        return 2
    parsejat = _parseja(args[1:])
    if parsejat is None:
        return 2
    proposta, valors = parsejat
    if not Path(proposta).is_file():
        return 2
    if "--semestre" in valors and valors["--semestre"] not in ("1", "2"):
        return 2
    mode = os.environ.get("HORARIS_FALS_MODE", "no_valida")
    if mode == "error":
        sys.stderr.write(MARCADOR_ERROR + "\n")
        return 2
    if mode not in RESULTAT_PER_MODE:
        return 2
    if mode == "lent":
        time.sleep(5)
    veredicte, codi = RESULTAT_PER_MODE[mode]
    if "--json" in valors:
        _escriu_json(valors["--json"], veredicte, args[1:])
    if "--violacions" in valors:
        _escriu_violacions(valors["--violacions"])
    return codi


if __name__ == "__main__":
    sys.exit(main())
