from __future__ import annotations
from pathlib import Path
import sys, yaml

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/'Config'/'config.yaml'
EXAMPLE=ROOT/'Config'/'config.example.yaml'


def fail(msg:str)->None:
    print('ERROR:',msg); raise SystemExit(2)


def main()->None:
    path=CFG if CFG.exists() else EXAMPLE
    data=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if data.get('system',{}).get('max_position_logics')!=2: fail('V1 requires max_position_logics=2')
    for section in ('mt5','atas','ai','engine'):
        if section not in data: fail(f'missing config section: {section}')
    atas=data['atas']
    if atas.get('require_mbo') not in (True,False): fail('atas.require_mbo must be boolean')
    secrets=ROOT/'Config'/'secrets.local'
    if secrets.exists() and secrets.stat().st_size>0:
        print('OK: local secrets file present and gitignored')
    else:
        print('WARN: Config/secrets.local is absent; AI will remain offline')
    print('OK:',path)

if __name__=='__main__': main()
