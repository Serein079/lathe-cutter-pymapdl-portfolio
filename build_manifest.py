"""Explicitly regenerate SHA256 publication manifest after intentional changes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IGNORED = {'.git', '.venv', '__pycache__', 'results', 'work', 'dist', 'build', '.pytest_cache', '.ruff_cache', '.vscode', '.idea', '.mplconfig'}


def publication_files(root=ROOT):
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if not path.is_file() or any(p in IGNORED or p.startswith('.venv') for p in relative.parts):
            continue
        if relative.as_posix() == 'evidence/file_manifest.json' or path.suffix in ('.pyc', '.pyo'):
            continue
        if (path.name.startswith('.env') and path.name != '.env.example') or path.suffix.lower() in ('.db','.rst','.rth','.esav','.full','.r001','.rdb','.dsp','.mntr','.lock'):
            continue
        yield relative.as_posix(), path


def main():
    entries = {name:dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
               for name,path in publication_files()}
    target = ROOT/'evidence/file_manifest.json'
    target.write_text(json.dumps(dict(algorithm='SHA256', scope='Publication files; excludes itself and generated runtime data',
                                     files=entries),indent=2),encoding='utf-8')
    print(f'Manifest generated: {len(entries)} files')


if __name__ == '__main__':
    main()
