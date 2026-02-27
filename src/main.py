from __future__ import annotations

from pathlib import Path
import sys

from src.ecb_etl import (
    TARGET_CURRENCIES,
    RatesSnapshot,
    compute_historical_means,
    load_daily_snapshot,
    load_historical_snapshots,
    render_markdown_table,
    select_currencies,
    write_text,
)

def main() -> int:
    project_root: Path = Path(__file__).resolve().parents[1]
    output_path: Path = project_root / "exchange_rates.md"

    try:
        daily: RatesSnapshot = load_daily_snapshot()
        historical: list[RatesSnapshot] = load_historical_snapshots()

        daily_selected: RatesSnapshot = RatesSnapshot(
            as_of=daily.as_of,
            rates=select_currencies(daily.rates, TARGET_CURRENCIES),
        )

        historical_selected: list[RatesSnapshot] = [
            RatesSnapshot(
                as_of=snap.as_of,
                rates=select_currencies(snap.rates, TARGET_CURRENCIES),
            )
            for snap in historical
        ]

        means: dict[str, float] = compute_historical_means(historical_selected, TARGET_CURRENCIES)

        md: str = render_markdown_table(daily_selected, means, TARGET_CURRENCIES)
        write_text(output_path, md)

        print(f"Wrote: {output_path}")
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())