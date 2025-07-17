import argparse
import hashlib
import re
from datetime import date
from pathlib import Path

try:
    from jinja2 import Template
except ImportError:  # pragma: no cover
    raise SystemExit('jinja2 is required')

ROOT = Path(__file__).resolve().parents[1]

PYPROJECT = ROOT / 'pyproject.toml'
CHANGELOG = ROOT / 'CHANGELOG.md'
WINGET_TEMPLATE = ROOT / '.github' / 'winget' / 'installer.yaml.jinja'
WINGET_OUTPUT = ROOT / '.github' / 'winget' / 'installer.yaml'


def read_pyproject_version() -> str:
    text = PYPROJECT.read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise RuntimeError('version not found')
    return m.group(1)


def write_pyproject_version(version: str) -> None:
    text = PYPROJECT.read_text()
    text = re.sub(r'(?m)^version\s*=\s*"[^"]+"', f'version = "{version}"', text)
    PYPROJECT.write_text(text)


def update_changelog(version: str) -> None:
    text = CHANGELOG.read_text()
    if '## [Unreleased]' in text:
        today = date.today().isoformat()
        text = text.replace('## [Unreleased]', f'## [{version}] - {today}', 1)
        CHANGELOG.write_text(text)


def render_winget(version: str, sha256: str) -> None:
    template = Template(WINGET_TEMPLATE.read_text())
    content = template.render(version=version, sha256=sha256)
    WINGET_OUTPUT.write_text(content)


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def commit_changes(version: str) -> None:
    import subprocess
    subprocess.run(['git', 'checkout', '-B', 'winget-update'], check=True)
    subprocess.run(['git', 'add', str(WINGET_OUTPUT), str(PYPROJECT), str(CHANGELOG)], check=True)
    subprocess.run(['git', 'commit', '-m', f'chore: prepare winget {version}'], check=True)


def check_versions() -> None:
    winget_version = None
    if WINGET_OUTPUT.exists():
        for line in WINGET_OUTPUT.read_text().splitlines():
            if line.startswith('PackageVersion:'):
                winget_version = line.split(':')[1].strip()
                break
    py_version = read_pyproject_version()
    if winget_version and winget_version != py_version:
        raise SystemExit(f'Version mismatch: winget {winget_version} vs pyproject {py_version}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Synchronise project versioning')
    parser.add_argument('version', nargs='?')
    parser.add_argument('exe', nargs='?')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()

    if args.check:
        check_versions()
        return

    if not args.version or not args.exe:
        parser.error('version tag and exe path required')
    version = args.version.lstrip('v')
    exe_path = Path(args.exe)
    sha256 = compute_sha256(exe_path)

    write_pyproject_version(version)
    update_changelog(version)
    render_winget(version, sha256)
    commit_changes(version)


if __name__ == '__main__':
    main()
