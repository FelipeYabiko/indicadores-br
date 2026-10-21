"""Linha de comando: `indicadores atualizar` e `indicadores resumo`."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import analysis
from .bcb import BCBClient, BCBError
from .pipeline import update_all
from .series import SERIES
from .storage import CsvStore

DEFAULT_DATA_DIR = Path("data")
log = logging.getLogger("indicadores")


def cmd_update(store: CsvStore, keys: list[str] | None) -> int:
    try:
        results = update_all(BCBClient(), store, keys=keys)
    except BCBError as exc:
        log.error("%s", exc)
        return 1
    for r in results:
        log.info("%-6s desde %s: %5d recebidas, %4d novas", r.key, r.start.isoformat(), r.fetched, r.added)
    return 0


def cmd_summary(store: CsvStore) -> int:
    for key, serie in SERIES.items():
        snap = analysis.snapshot(analysis.to_series(store.load(key)))
        if snap["value"] is None:
            print(f"{serie.name:<20} sem dados (rode `indicadores atualizar`)")
            continue
        print(f"{serie.name:<20} {snap['value']:>9.4f} {serie.unit:<9} em {snap['date']:%d/%m/%Y}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="indicadores", description="Indicadores econômicos do Banco Central.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_DIR, help="Pasta dos CSVs.")
    sub = parser.add_subparsers(dest="command", required=True)
    update = sub.add_parser("atualizar", help="Baixa dados novos da API do Banco Central.")
    update.add_argument("series", nargs="*", help=f"Séries: {', '.join(SERIES)} (padrão: todas).")
    sub.add_parser("resumo", help="Mostra o valor mais recente de cada série.")
    args = parser.parse_args(argv)
    unknown = set(getattr(args, "series", [])) - set(SERIES)
    if unknown:
        parser.error(f"série desconhecida: {', '.join(sorted(unknown))}")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    store = CsvStore(args.data)
    if args.command == "atualizar":
        return cmd_update(store, args.series or None)
    return cmd_summary(store)


if __name__ == "__main__":
    raise SystemExit(main())
