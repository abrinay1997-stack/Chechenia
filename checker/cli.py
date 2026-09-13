from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import load_config, load_emails, run_checks, write_results

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chechenia checker: comprueba emails contra TU API (no servicios de terceros)."
    )
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--emails", default=str(ROOT / "data" / "emails.example.txt"))
    parser.add_argument("--out", default=str(ROOT / "results"))
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        example = ROOT / "config.example.json"
        if example.exists() and not config_path.exists():
            config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"Creé {config_path} desde config.example.json")
        else:
            print(f"No existe {config_path}", file=sys.stderr)
            return 1

    cfg = load_config(config_path)
    emails = load_emails(args.emails)
    print(f"API: {cfg['api_base_url']}{cfg['exists_path']}")
    print(f"Emails: {len(emails)}")

    def on_progress(result, stats):
        mark = {
            "registered": "REG",
            "available": "LIB",
            "invalid": "INV",
            "error": "ERR",
            "blocked": "BLK",
        }.get(result.status, result.status)
        print(f"[{mark}] {result.email} ({result.detail})  {stats.registered}/{stats.available}/{stats.invalid}/{stats.errors}")

    results, stats = run_checks(emails, cfg, on_progress=on_progress)
    write_results(results, args.out)
    print(
        f"\nListo. registered={stats.registered} available={stats.available} "
        f"invalid={stats.invalid} errors={stats.errors + stats.blocked}"
    )
    print(f"Resultados en {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
