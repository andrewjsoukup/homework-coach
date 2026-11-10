"""Production dependencies must cover hosts without an OS timezone database."""
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_timezone_database_is_a_runtime_dependency():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    requirements = project['project']['dependencies']
    assert any(item.lower().startswith('tzdata') and ';' not in item for item in requirements), (
        'Family IANA timezones require tzdata in production, including Windows and minimal cloud images; '
        'a dev-only or Windows-only dependency is insufficient.'
    )


def test_family_timezone_works_without_system_zoneinfo():
    import zoneinfo
    original = zoneinfo.TZPATH
    try:
        zoneinfo.reset_tzpath([])
        zoneinfo.ZoneInfo.clear_cache()
        assert zoneinfo.ZoneInfo('America/Chicago').key == 'America/Chicago'
        assert zoneinfo.ZoneInfo('Europe/London').key == 'Europe/London'
    finally:
        zoneinfo.reset_tzpath(original)
        zoneinfo.ZoneInfo.clear_cache()
