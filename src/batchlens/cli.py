"""Command line: ``batchlens serve``, ``batchlens check`` and ``batchlens seed-demo``.

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
