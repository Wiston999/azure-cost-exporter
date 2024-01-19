#!/usr/bin/python
# -*- coding:utf-8 -*-
# Filename: exporter.py

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, MutableMapping, Union

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
)
from dateutil.relativedelta import relativedelta
from prometheus_client import Gauge

logger = logging.getLogger(__name__)


class MetricExporter:
    def __init__(
        self,
        polling_interval_seconds: int,
        group_by: Dict[str, Any],
        target: Dict[str, str],
    ) -> None:
        self.polling_interval_seconds = polling_interval_seconds
        self.group_by = group_by
        self.target = target
        self.labels = set(target.keys())
        # for now we only support exporting one type of cost (ActualCost)
        self.labels.add("ChargeType")
        self.labels.add("Currency")
        if group_by["enabled"]:
            for group in group_by["groups"]:
                self.labels.add(group["label_name"])
        self.azure_daily_cost = Gauge(
            "azure_daily_cost",
            "Daily cost of an Azure account",
            self.labels,
        )

    def run_metrics_loop(self) -> None:
        while True:
            self.fetch()
            time.sleep(self.polling_interval_seconds)

    def init_azure_client(self) -> CostManagementClient:
        client = CostManagementClient(credential=DefaultAzureCredential())
        logger.info(f"Created API Client {client}")
        return client

    def query_azure_cost_explorer(
        self,
        azure_client: CostManagementClient,
        subscription: str,
        group_by: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
    ) -> MutableMapping[str, Any]:
        scope = f"/subscriptions/{subscription}"

        groups = list()
        if group_by["enabled"]:
            for group in group_by["groups"]:
                groups.append(QueryGrouping(type=group["type"], name=group["name"]))

        query = QueryDefinition(
            type="ActualCost",
            dataset=QueryDataset(
                granularity="Daily",
                aggregation={
                    "totalCost": QueryAggregation(name="Cost", function="Sum"),
                    "totalCostUSD": QueryAggregation(name="CostUSD", function="Sum"),
                },
                grouping=groups,
            ),
            timeframe="Custom",
            time_period=QueryTimePeriod(
                from_property=datetime(
                    start_date.year,
                    start_date.month,
                    start_date.day,
                    tzinfo=timezone.utc,
                ),
                to=datetime(
                    end_date.year,
                    end_date.month,
                    end_date.day,
                    tzinfo=timezone.utc,
                ),
            ),
        )
        result = azure_client.query.usage(scope, query)
        result_dict: MutableMapping[str, Any] = {}
        if result is not None:
            result_dict = result.as_dict()
        logger.debug(f"Performed query {query}")
        logger.debug(f"Got result {result_dict}")
        return result_dict

    def expose_metrics(
        self,
        azure_account: Dict[str, str],
        result: List[Union[str, int, float]],
        columns: Dict[str, int],
    ) -> None:
        logger.debug(f"Processing result {result} - {columns}")
        cost_usd = float(result[columns["CostUSD"]])
        cost_local = float(result[columns["Cost"]])
        local_currency = result[columns["Currency"]]
        if not self.group_by["enabled"]:
            self.azure_daily_cost.labels(
                **azure_account,
                ChargeType="ActualCost",
                Currency="USD",
            ).set(cost_usd)
            self.azure_daily_cost.labels(
                **azure_account,
                ChargeType="ActualCost",
                Currency=local_currency,
            ).set(cost_local)
        else:
            merged_minor_cost_usd = 0.0
            merged_minor_cost_local = 0.0
            group_key_values = {
                group["label_name"]: result[columns[group["name"]]]
                for group in self.group_by["groups"]
                if group["name"] in columns
            }

            if (
                self.group_by["merge_minor_cost"]["enabled"]
                and cost_usd < self.group_by["merge_minor_cost"]["threshold"]
            ):
                merged_minor_cost_usd += cost_usd
                merged_minor_cost_local += cost_local
            else:
                self.azure_daily_cost.labels(
                    **azure_account,
                    **group_key_values,
                    ChargeType="ActualCost",
                    Currency="USD",
                ).set(cost_usd)
                self.azure_daily_cost.labels(
                    **azure_account,
                    **group_key_values,
                    ChargeType="ActualCost",
                    Currency=local_currency,
                ).set(cost_local)

            if merged_minor_cost_usd > 0:
                # Group everything under the same label name
                group_key_values = {
                    group["label_name"]: self.group_by["merge_minor_cost"]["tag_value"]
                    for group in self.group_by["groups"]
                }
                self.azure_daily_cost.labels(
                    **azure_account,
                    **group_key_values,
                    ChargeType="ActualCost",
                    Currency="USD",
                ).set(merged_minor_cost_usd)
                self.azure_daily_cost.labels(
                    **azure_account,
                    **group_key_values,
                    ChargeType="ActualCost",
                    Currency=local_currency,
                ).set(merged_minor_cost_local)

    def fetch(self) -> None:
        logger.info(
            "Querying cost data for Azure "
            f'subscription {self.target["Subscription"]}'
        )
        azure_client = self.init_azure_client()

        try:
            end_date = datetime.today()
            start_date = end_date - relativedelta(days=1)
            cost_response = self.query_azure_cost_explorer(
                azure_client,
                self.target["Subscription"],
                self.group_by,
                start_date,
                end_date,
            )
        except HttpResponseError:
            logger.exception("An HTTP error happened")
            return

        columns_map = {
            column["name"]: index
            for index, column in enumerate(cost_response["columns"])
        }
        for result in cost_response["rows"]:
            if result[columns_map["UsageDate"]] == int(start_date.strftime("%Y%m%d")):
                # it is possible that Azure returns cost data which is different than
                # the specified date for example, the query time period is
                # 2023-07-10 00:00:00+00:00 to 2023-07-11 00:00:00+00:00
                # Azure still returns some records for date 2023-07-11
                self.expose_metrics(self.target, result, columns_map)
            else:
                logger.warning(f"Found out-of-time samples at {result}")
