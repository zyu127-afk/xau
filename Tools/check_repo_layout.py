from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REQUIRED=['Start','MT5','ATAS','Engine','UI','AI','Config','Data','Logs','Backup','Runtime','Version','Tools','Docs','Tests']
missing=[x for x in REQUIRED if not (ROOT/x).exists()]
if missing:
    raise SystemExit('Missing required directories: '+', '.join(missing))
print('OK: portable root layout present')
