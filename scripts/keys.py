#!/usr/bin/env python3
"""Credential discovery for voice/media providers. Values are returned to callers only; nothing here prints them.
common.py deliberately reads no secrets; every provider adapter goes through this module instead."""
import os, subprocess
from pathlib import Path
from common import ROOT

ENV = {
    'fish': ['FISH_API_KEY', 'FISH_AUDIO_API_KEY'],
    'seed2': ['SEED_AUDIO_KEY'],
    'dashscope': ['DASHSCOPE_API_KEY'],
}
KEYCHAIN = {'fish': 'fish-audio-api-key', 'seed2': 'seed-audio-key', 'dashscope': 'dashscope-api-key'}


def _dotenv(path):
    values = {}
    try:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k, v = line.split('=', 1); values[k.strip()] = v.strip().strip('"').strip("'")
    except (OSError, UnicodeDecodeError):
        pass
    return values


def _keychain(service):
    try:
        r = subprocess.run(['security', 'find-generic-password', '-a', os.environ.get('USER', ''), '-s', service, '-w'],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def lookup(provider):
    """Return (value, source_label). value is '' when nothing is configured."""
    for name in ENV.get(provider, []):
        v = os.environ.get(name, '').strip()
        if v and not v.startswith('$('): return v, f'env:{name}'
    service = KEYCHAIN.get(provider)
    if service:
        v = _keychain(service)
        if v: return v, f'keychain:{service}'
    env_file = _dotenv(ROOT / '.env')
    for name in ENV.get(provider, []):
        if env_file.get(name): return env_file[name], 'file:<skill>/.env'
    return '', None


def key_status(provider):
    if provider == 'grok':
        auth = Path.home() / '.grok/auth.json'
        present = auth.is_file() and auth.stat().st_size > 2
        return {'available': present, 'source': 'grok-auth' if present else None}
    if provider.startswith('host-'):
        return {'available': None, 'source': 'host-tool', 'note': 'Provided by the agent host; verified only by an actual tool call'}
    value, source = lookup(provider)
    return {'available': bool(value), 'source': source, 'env': ENV.get(provider, [None])[0]}


def provider_key(provider):
    value, source = lookup(provider)
    if not value:
        names = ' or '.join(ENV.get(provider, [])) or provider
        raise ValueError(f'{provider} credential missing: export {names}, or store it in the macOS keychain as {KEYCHAIN.get(provider, provider)}, or put it in <skill>/.env')
    return value, source
