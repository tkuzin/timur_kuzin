"""Build and verify a portable source archive without local secrets."""
from pathlib import Path
import hashlib
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts' / 'timur_kuzin_project.zip'


def main():
    names = subprocess.check_output(
        ['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT
    ).decode('utf-8').split('\0')
    paths = sorted(set(name for name in names if name))
    forbidden = {'.git', '.venv', '.local', '__pycache__', '.pytest_cache'}
    secrets = []
    env = ROOT / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            key, sep, value = line.partition('=')
            if sep and key in {'DATABASE_URL', 'SESSION_SECRET'} and value:
                secrets.append(value.encode())
                if key == 'DATABASE_URL':
                    from urllib.parse import urlsplit
                    password = urlsplit(value).password
                    if password:
                        secrets.append(password.encode())
    for name in paths:
        path = Path(name)
        assert not forbidden.intersection(path.parts), name
        assert path.name != '.env' and path.suffix != '.zip', name
        assert not name.startswith('artifacts/qa/'), name
        data = (ROOT / name).read_bytes()
        assert not any(secret in data for secret in secrets), f'Secret detected: {name}'
    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in paths:
            archive.write(ROOT / name, 'timur_kuzin/' + name)
    with zipfile.ZipFile(OUTPUT) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(paths)
        for name in paths:
            assert archive.read('timur_kuzin/' + name) == (ROOT / name).read_bytes()
    print(f'Archive verified: {len(paths)} files, {OUTPUT.stat().st_size} bytes')
    print('SHA-256:', hashlib.sha256(OUTPUT.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
