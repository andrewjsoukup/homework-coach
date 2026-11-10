"""Install-time contract for native PDF and photo previews."""
from pathlib import Path
import tomllib


def test_preview_dependencies_ship_in_runtime_not_only_dev():
    data = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    runtime = data["project"]["dependencies"]
    assert any(d.lower().startswith("pypdfium2") for d in runtime)
    assert any(d.lower().startswith("pillow") for d in runtime)
