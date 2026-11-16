"""Command line: ``batchlens serve``, ``check``, ``seed-demo``, ``demo-plant`` and ``benchmark``.

Settings come from the environment (``batchlens.config``).
"""

from __future__ import annotations

import argparse
import json
import os


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="batchlens", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Run the web application and the API.")
    serve.add_argument("--host", default=os.environ.get("BATCHLENS_HOST", "127.0.0.1"))
    serve.add_argument("--port", type=int, default=int(os.environ.get("BATCHLENS_PORT", "9100")))
    commands.add_parser("check", help="Check the app key and that PlantCraft answers.")
    commands.add_parser("seed-demo", help="Load the four synthetic demo batches into the database.")
    bench = commands.add_parser(
        "benchmark",
        help="Score the findings against ground truth over many seeded batches; write the report.",
    )
    bench.add_argument("--out", help="Where to write the report (Markdown).")
    bench.add_argument("--batches", type=int, default=None, help="Seeds of every variant.")
    bench.add_argument("--references", type=int, default=None, help="Reference batches.")
    plant = commands.add_parser(
        "demo-plant",
        help="Write the synthetic plant as files PlantCraft imports (a CSV and a plant map).",
    )
    plant.add_argument("--out", required=True, help="Folder PlantCraft's server can read.")
    plant.add_argument(
        "--time-zone",
        default="UTC",
        help="The zone PlantCraft reads CSV files in: its scenario's source time zone "
        "(America/Sao_Paulo in PlantCraft's local demo). Default: UTC.",
    )
    args = parser.parse_args(argv)
    from plantcraft_sdk.server.logs import configure_logging

    from batchlens import __version__
    from batchlens.config import Settings

    # JSON lines to standard error and, for the server, the rotating file in the data folder
    # (BATCHLENS_LOG_LEVEL sets the level).
    configure_logging(
        "batchlens",
        version=__version__,
        data_dir=Settings.from_environment().data_dir if args.command == "serve" else None,
    )

    if args.command == "serve":
        import uvicorn

        from batchlens.api.app import create_app

        uvicorn.run(
            create_app(),
            host=args.host,
            port=args.port,
            proxy_headers=True,
            log_config=None,
            access_log=False,
        )
        return 0

    if args.command == "benchmark":
        from pathlib import Path

        from batchlens.benchmark import run as benchmark
        from batchlens.benchmark.report import render

        result = benchmark.run(
            args.batches or benchmark.DEFAULT_BATCHES,
            args.references or benchmark.DEFAULT_REFERENCES,
        )
        if args.out:
            Path(args.out).write_text(render(result), encoding="utf-8")
        print(json.dumps({"status": "ok", **result["counts"], "report": args.out}))
        return 0

    if args.command == "demo-plant":
        from pathlib import Path

        from batchlens.demo.plant import recorded, write_plant_files

        try:
            files = write_plant_files(Path(args.out), args.time_zone)
        except ValueError as exc:
            print(json.dumps({"status": "error", "error": str(exc)}))
            return 1
        moments = sorted(recorded())
        print(
            json.dumps(
                {
                    "status": "ok",
                    "csv": str(files.csv),
                    "map": str(files.map),
                    "time_zone": args.time_zone,
                    "first": moments[0].isoformat(),
                    "last": moments[-1].isoformat(),
                }
            )
        )
        return 0

    from plantcraft_sdk.client import PlantCraftError

    from batchlens.api.runtime import Runtime
    from batchlens.config import Settings

    settings = Settings.from_environment()
    runtime = Runtime(settings)
    try:
        if args.command == "seed-demo":
            from batchlens.demo.seed import seed_demo

            print(json.dumps({"status": "ok", "batches": seed_demo(runtime.batches)}))
            return 0
        if runtime.service_client is None:
            print(json.dumps({"status": "error", "error": "PLANTCRAFT_APP_KEY is not set."}))
            return 1
        try:
            assets = runtime.service_client.assets()
            signals = runtime.service_client.signals()
        except PlantCraftError as exc:
            print(json.dumps({"status": "error", "error": str(exc)}))
            return 1
        print(
            json.dumps(
                {
                    "status": "ok",
                    "assets": len(assets),
                    "signals": len(signals),
                    "batches": len(runtime.batches.summaries()),
                }
            )
        )
        return 0
    finally:
        runtime.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
