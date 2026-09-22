#!/usr/bin/env python3
import argparse
from pathlib import Path

CARD_ID = 'executive-final-sync-history-public-smoke-trend'


def validate(html: str) -> list[str]:
    errors = []
    if html.count(f'id="{CARD_ID}"') != 1:
        errors.append('card must exist exactly once')
    if 'data-mode="report-only"' not in html:
        errors.append('mode must be report-only')
    if 'data-production-blocker="false"' not in html:
        errors.append('production blocker must be false')
    lowered = html.lower()
    if 'fetch(' in lowered or 'xmlhttprequest' in lowered:
        errors.append('external browser calls are not allowed')
    return errors


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--html', required=True)
    args = p.parse_args()
    errors = validate(Path(args.html).read_text(encoding='utf-8'))
    if errors:
        raise SystemExit('; '.join(errors))
    print('OK')


if __name__ == '__main__':
    main()
