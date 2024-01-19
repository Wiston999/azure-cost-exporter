#!/usr/bin/python
# -*- coding:utf-8 -*-
# Filename: main.py

import argparse
import logging
import os
import sys
from typing import Any, Dict, List

import coloredlogs  # type: ignore
from envyaml import EnvYAML  # type: ignore
from prometheus_client import start_http_server

from .exporter import MetricExporter

LOG_LEVELS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

logger = logging.getLogger(__name__)


def get_args(args: List[str] = sys.argv[1:]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Azure Cost Exporter, "
        "exposing Azure cost data as Prometheus metrics."
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="The config file (exporter_config.yaml) for the exporter",
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        choices=LOG_LEVELS,
        default=logging.INFO,
        type=str.upper,
        help="Logging level to be used",
    )
    return parser.parse_args(args)


def get_configs(args: argparse.Namespace) -> Dict[str, Any]:
    if not os.path.exists(args.config):
        logger.critical(f"Azure Cost Exporter config file {args.config} does not exist")
        sys.exit(1)

    if not os.path.isfile(args.config):
        logger.critical(f"Azure Cost Exporter config file {args.config} is not a file")
        sys.exit(1)

    config = EnvYAML(args.config)

    # config validation
    if len(config["target_azure_account"]) == 0:
        logger.error("target_azure_account should be present in configuration file!")
        sys.exit(1)

    labels = config["target_azure_account"].keys()

    if "Subscription" not in labels:
        logger.error(
            "Subscription is mandatory key in target_azure_account configuration item!"
        )
        sys.exit(1)

    return config


def main() -> None:
    args = get_args()
    logger_format = "%(asctime)-15s %(levelname)-8s %(message)s"
    coloredlogs.install(level=args.loglevel, fmt=logger_format)
    config = get_configs(args)
    app_metrics = MetricExporter(
        polling_interval_seconds=config["polling_interval_seconds"],
        group_by=config["group_by"],
        target=config["target_azure_account"],
    )
    logger.info(f"Starting HTTP server at {config['exporter_port']}")
    start_http_server(config["exporter_port"])
    app_metrics.run_metrics_loop()
    logger.info("Started HTTP server and main metrics loop")


if __name__ == "__main__":
    main()
