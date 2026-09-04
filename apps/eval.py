import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _path in (str(_ROOT / "packages"), str(_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from payops_core.eval.harness import render_markdown, run_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PayOps investigation evaluation suite.")
    parser.add_argument(
        "--out-dir",
        default="eval",
        help="Directory for last_report.md and last_report.json",
    )
    args = parser.parse_args()
    report = run_suite()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "last_report.md").write_text(render_markdown(report), encoding="utf-8")
    (out / "last_report.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    print(render_markdown(report))
    if report.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
