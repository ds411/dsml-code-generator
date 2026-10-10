"""Measure the start time of sysml-grpc and the parse time of OpenSysML.

Story #12 records the results in docs/notes/opensysml-0.9.2.md. CI runs this
script on each platform. Run it from the root of the repository:

    uv run python scripts/measure_opensysml.py
"""

import platform
import statistics
import time
from collections.abc import Callable
from pathlib import Path

from dsml.adapter.engine import Engine

ROOT = Path(__file__).resolve().parent.parent
RUNS = 5
MODELS = {
    "probe": [ROOT / "tests/models/opensysml/probe.sysml"],
    "order-service": [ROOT / "docs/model/examples/order-service.sysml"],
    "prd": sorted((ROOT / "docs/model/prd").glob("*.sysml")),
}


def _median_ms(action: Callable[[], object]) -> float:
    times: list[float] = []
    for _ in range(RUNS):
        start = time.perf_counter()
        action()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


def _start_and_stop() -> None:
    Engine().close()


def main() -> None:
    print(f"platform: {platform.system().lower()}-{platform.machine().lower()}")
    # The first start can include the download of sysml-grpc.
    start = time.perf_counter()
    _start_and_stop()
    print(f"first start: {(time.perf_counter() - start) * 1000:.0f} ms")
    print(f"start (median of {RUNS}): {_median_ms(_start_and_stop):.0f} ms")
    # The service keeps a parsed model, so each parse uses a new service.
    for name, paths in MODELS.items():
        lines = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in paths)
        times: list[float] = []
        diagnostics = 0
        for _ in range(RUNS):
            with Engine() as engine:
                start = time.perf_counter()
                diagnostics = len(engine.parse_files(paths, ROOT).diagnostics)
                times.append((time.perf_counter() - start) * 1000)
        print(
            f"parse {name} ({len(paths)} files, {lines} lines, median of {RUNS}): "
            f"{statistics.median(times):.0f} ms, {diagnostics} diagnostics"
        )


if __name__ == "__main__":
    main()
