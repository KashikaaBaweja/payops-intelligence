import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _path in (str(_ROOT / "packages"), str(_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from payops_core.data.seed import main as _main


def main() -> None:
    _main()
