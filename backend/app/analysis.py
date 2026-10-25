"""Read-only tools. Money is calculated with Decimal, never by the language model."""

import re
from bisect import bisect_right
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from .retrieval import rank

PAID = {"delivered", "completed"}
# A fee or unit-cost rise smaller than this percentage is treated as noise.
MATERIAL_CHANGE = 5
DISCOUNT_TERMS = re.compile(r"\b(discount\w*|promotion\w*|markdown\w*)", re.IGNORECASE)


def money(rows, column):
    return float(sum((Decimal(str(row[column])) for row in rows), Decimal(0)))


def change(current, previous):
    return round((current - previous) / previous * 100, 2) if previous else None


def amount(value):
    return float(round(value, 2))


class Tools:
    def __init__(self, sources):
        self.sources = sources
        self.tables = {source.kind: source for source in sources if source.kind != "document"}
        self.evidence = []
        self.catalog = {row["id"]: row for row in self.rows("products")}
        self._costs = None
        self._contribution = {}
        orders = self.rows("orders")
        self.end = date.fromisoformat(max(row["date"] for row in orders)) if orders else date.today()
        self.start = self.end - timedelta(days=27)
        self.previous_start = self.start - timedelta(days=28)

    def rows(self, kind):
        source = self.tables.get(kind)
        return source.content["rows"] if source else []

    def period(self, rows, field="date", previous=False):
        start, end = (self.previous_start, self.start - timedelta(days=1)) if previous else (self.start, self.end)
        return [row for row in rows if row.get(field) and str(start) <= row[field] <= str(end)]

    def cite(self, claim, kinds, value=None, unit=None, calculation=None, locator=None, evidence_type="calculation"):
        item = {
            "id": f"E{len(self.evidence) + 1}",
            "type": evidence_type,
            "claim": claim,
            "value": value,
            "unit": unit,
            "calculation": calculation,
            "sources": [
                {
                    "id": self.tables[kind].id,
                    "name": self.tables[kind].name,
                    "locator": locator
                    or f"All matching rows; current {self.start}–{self.end}; baseline {self.previous_start}–{self.start - timedelta(days=1)}",
                }
                for kind in kinds
                if kind in self.tables
            ],
        }
        self.evidence.append(item)
        return item["id"]

    def coverage(self):
        orders = self.rows("orders")
        if not orders:
            return ["Orders dataset is missing; revenue and comparison windows cannot be established."]
        issues = []
        if min(row["date"] for row in orders) > str(self.previous_start):
            issues.append(
                "The baseline is incomplete: upload at least 56 days of orders for comparable 28-day periods."
            )
        for kind in ("products", "inventory", "suppliers", "deliveries", "marketing"):
            if kind not in self.tables:
                issues.append(f"{kind.title()} data is missing.")
        products = {row["id"] for row in self.rows("products")}
        if products and any(row["product_id"] not in products for row in orders):
            issues.append("Some order product IDs have no matching product record.")
        return issues

    def detect_anomalies(self, query=""):
        orders = [row for row in self.rows("orders") if row["status"] in PAID]
        current, previous = self.period(orders), self.period(orders, previous=True)
        metrics = []
        for key, label, cur, prev, unit, direction in [
            ("revenue", "Recognized revenue", money(current, "revenue"), money(previous, "revenue"), "NPR", "up"),
            ("orders", "Completed orders", len(current), len(previous), "count", "up"),
        ]:
            delta = change(cur, prev)
            metric = {
                "key": key,
                "label": label,
                "current": cur,
                "previous": prev,
                "change": delta,
                "unit": unit,
                "direction": direction,
                "anomaly": delta is not None and delta <= -10,
            }
            metric["evidence_id"] = self.cite(
                f"{label}: NPR {cur:,.0f} vs NPR {prev:,.0f} in equal 28-day windows."
                if unit == "NPR"
                else f"{label}: {cur:,} vs {prev:,} in equal 28-day windows.",
                ["orders"],
                cur,
                unit,
                "Sum revenue for delivered/completed orders"
                if key == "revenue"
                else "Count delivered/completed orders",
            )
            metrics.append(metric)
        delivery = self.delivery_summary()
        if delivery["current"]["count"] and delivery["previous"]["count"]:
            cur, prev = delivery["current"]["late_rate"], delivery["previous"]["late_rate"]
            metric = {
                "key": "late_rate",
                "label": "Late delivery rate",
                "current": cur,
                "previous": prev,
                "change": round(cur - prev, 2),
                "unit": "%",
                "direction": "down",
                "anomaly": cur - prev >= 5,
            }
            metric["evidence_id"] = self.cite(
                f"Late delivery rate: {cur:.1f}% vs {prev:.1f}%.",
                ["orders", "deliveries"],
                cur,
                "%",
                "100 × late / matched deliveries, grouped by order purchase date; undelivered past promise counted late",
            )
            metrics.append(metric)
        parts = [self.contribution(), self.contribution(previous=True)]
        if all(parts):
            margins = [float(part["contribution"]) for part in parts]
            note, formula, kinds = self.contribution_terms(parts)
            metric = {
                "key": "contribution",
                "label": "Contribution estimate",
                "current": margins[0],
                "previous": margins[1],
                "change": change(*margins),
                "unit": "NPR",
                "direction": "up",
                "anomaly": margins[0] < margins[1] * 0.9,
            }
            metric["evidence_id"] = self.cite(note, kinds, margins[0], "NPR", formula)
            metrics.append(metric)
        return {
            "metrics": metrics,
            "period": {
                "current_start": str(self.start),
                "current_end": str(self.end),
                "previous_start": str(self.previous_start),
                "previous_end": str(self.start - timedelta(days=1)),
            },
            "coverage_issues": self.coverage(),
        }

    def purchase_costs(self):
        if self._costs is None:
            totals = defaultdict(lambda: [Decimal(0), Decimal(0)])
            for row in self.rows("purchases"):
                item = totals[row["product_id"], row["date"]]
                item[0] += Decimal(row["unit_cost"]) * Decimal(row["quantity"])
                item[1] += Decimal(row["quantity"])
            self._costs = {}
            for (product_id, day), (cost, quantity) in sorted(totals.items()):
                dates, costs = self._costs.setdefault(product_id, ([], []))
                dates.append(day)
                costs.append(cost / quantity)
        return self._costs

    def unit_cost(self, product_id, day):
        """Latest purchase cost on or before the sale date; the current catalog cost when none exists."""
        dates, costs = self.purchase_costs().get(product_id, ((), ()))
        index = bisect_right(dates, day)
        if index:
            return costs[index - 1], "purchases"
        product = self.catalog.get(product_id)
        return (Decimal(product["cost"]), "catalog") if product else (None, None)

    def contribution(self, previous=False):
        if previous in self._contribution:
            return self._contribution[previous]
        result = None
        if self.catalog or self.rows("purchases"):
            orders = self.period(self.rows("orders"), previous=previous)
            products = defaultdict(lambda: {"units": Decimal(0), "revenue": Decimal(0), "cost": Decimal(0)})
            basis = set()
            for row in orders:
                if row["status"] not in PAID:
                    continue
                cost, source = self.unit_cost(row["product_id"], row["date"])
                if cost is None:
                    break
                item = products[row["product_id"]]
                item["units"] += Decimal(row["quantity"])
                item["revenue"] += Decimal(row["revenue"])
                item["cost"] += cost * Decimal(row["quantity"])
                basis.add(source)
            else:
                ids = {row["id"] for row in orders}
                fees = [
                    Decimal(row["fee"])
                    for row in self.rows("deliveries")
                    if row["order_id"] in ids and row.get("fee") is not None
                ]
                categories = defaultdict(Decimal)
                for row in self.period(self.rows("expenses"), previous=previous):
                    categories[row["category"]] += Decimal(row["amount"])
                result = {
                    "revenue": sum((item["revenue"] for item in products.values()), Decimal(0)),
                    "product_cost": sum((item["cost"] for item in products.values()), Decimal(0)),
                    "delivery_fees": sum(fees, Decimal(0)),
                    "expenses": sum(categories.values(), Decimal(0)),
                    "products": products,
                    "categories": categories,
                    "basis": basis,
                    "fee_count": len(fees),
                }
                result["contribution"] = (
                    result["revenue"] - result["product_cost"] - result["delivery_fees"] - result["expenses"]
                )
        self._contribution[previous] = result
        return result

    def contribution_terms(self, parts):
        basis = set().union(*(part["basis"] for part in parts))
        fees = any(part["fee_count"] for part in parts)
        if "purchases" not in basis and not fees:
            return (
                "Contribution estimate uses current catalog costs and recorded expenses; historical costs and taxes are unknown.",
                "Recognized revenue − catalog cost × quantity − recorded expenses",
                ["orders", "products", "expenses"],
            )
        costs = "purchase costs at the time of sale" if "purchases" in basis else "current catalog costs"
        if basis == {"purchases", "catalog"}:
            costs += " (catalog costs where no earlier purchase exists)"
        return (
            f"Contribution estimate uses {costs}{', recorded courier fees' if fees else ''} and recorded expenses; taxes and unrecorded costs are unknown.",
            "Recognized revenue − unit cost × quantity" + (" − courier fees" if fees else "") + " − recorded expenses",
            ["orders"]
            + (["purchases"] if "purchases" in basis else [])
            + (["products"] if "catalog" in basis else [])
            + (["deliveries"] if fees else [])
            + ["expenses"],
        )

    def segment_performance(self, query=""):
        products = {row["id"]: row for row in self.rows("products")}
        grouped = defaultdict(lambda: {"current": Decimal(0), "previous": Decimal(0), "current_orders": 0})
        for prior in (False, True):
            for row in self.period(self.rows("orders"), previous=prior):
                if row["status"] not in PAID:
                    continue
                item = grouped[row["product_id"]]
                item["previous" if prior else "current"] += Decimal(row["revenue"])
                if not prior:
                    item["current_orders"] += 1
        result = []
        for product_id, value in grouped.items():
            product = products.get(product_id, {})
            cur, prev = float(value["current"]), float(value["previous"])
            item = {
                "product_id": product_id,
                "name": product.get("name", product_id),
                "category": product.get("category", "Unknown"),
                "current": cur,
                "previous": prev,
                "change": change(cur, prev),
                "difference": round(cur - prev, 2),
                "current_orders": value["current_orders"],
            }
            result.append(item)
        selected = sorted(result, key=lambda item: item["difference"])[:25]
        for item in selected:
            item["evidence_id"] = self.cite(
                f"{item['name']}: NPR {item['current']:,.0f} vs NPR {item['previous']:,.0f}; change {item['change']}%.",
                ["orders", "products"],
                item["difference"],
                "NPR",
                f"Sum recognized revenue where product_id={item['product_id']}; current minus baseline",
            )
        return {
            "segments": selected,
            "total_segments": len(result),
            "comparison_valid": not any("baseline" in issue for issue in self.coverage()),
        }

    def get_inventory(self, query=""):
        grouped = defaultdict(lambda: {"stockout_days": 0, "supplier_ids": set(), "dates": []})
        for row in self.period(self.rows("inventory")):
            if Decimal(row["stock"]) == 0:
                item = grouped[row["product_id"]]
                item["stockout_days"] += 1
                item["supplier_ids"].add(row["supplier_id"])
                item["dates"].append(row["date"])
        result = []
        for product_id, item in sorted(grouped.items(), key=lambda entry: -entry[1]["stockout_days"])[:25]:
            result.append(
                {
                    "product_id": product_id,
                    "stockout_days": item["stockout_days"],
                    "supplier_ids": sorted(item["supplier_ids"]),
                    "first_date": min(item["dates"]),
                    "last_date": max(item["dates"]),
                    "evidence_id": self.cite(
                        f"{self.catalog.get(product_id, {}).get('name', product_id)} ({product_id}) recorded zero stock on {item['stockout_days']} days.",
                        ["inventory"],
                        item["stockout_days"],
                        "days",
                        f"Count distinct daily inventory rows with stock=0 and product_id={product_id}",
                    ),
                }
            )
        return {
            "stockouts": result,
            "total_stockout_products": len(grouped),
            "available": bool(self.rows("inventory")),
            "limitation": "Top 25 stockout products shown. Daily snapshots do not measure intraday stock or unrecorded demand.",
        }

    def get_supplier_data(self, query=""):
        result = []
        for index, row in enumerate(self.rows("suppliers"), 2):
            if not str(self.start) <= row["promised_date"] <= str(self.end):
                continue
            actual = date.fromisoformat(row["received_date"]) if row["received_date"] else self.end
            days = max(0, (actual - date.fromisoformat(row["promised_date"])).days)
            if days:
                result.append(
                    {
                        **row,
                        "delay_days": days,
                        "evidence_id": self.cite(
                            f"{row['name']} ({row['id']}), {self.catalog.get(row['product_id'], {}).get('name', row['product_id'])}: shipment {days} days late.",
                            ["suppliers"],
                            days,
                            "days",
                            "max(0, received_date − promised_date); as-of date used for unreceived shipments",
                            locator=f"CSV row {index}; supplier {row['id']}; promised {row['promised_date']}",
                        ),
                    }
                )
        return {"delayed_shipments": result, "available": bool(self.rows("suppliers"))}

    def delivery_summary(self):
        result = {}
        for prior, key in [(False, "current"), (True, "previous")]:
            order_ids = {row["id"] for row in self.period(self.rows("orders"), previous=prior)}
            rows = [row for row in self.rows("deliveries") if row["order_id"] in order_ids]
            late = [row for row in rows if (row["delivered_date"] or str(self.end)) > row["promised_date"]]
            result[key] = {
                "count": len(rows),
                "late": len(late),
                "late_rate": round(100 * len(late) / len(rows), 2) if rows else 0,
                "matched_orders": len(order_ids),
            }
        return result

    def get_deliveries(self, query=""):
        summary = self.delivery_summary()
        routes = defaultdict(lambda: {"count": 0, "late": 0})
        ids = {row["id"] for row in self.period(self.rows("orders"))}
        for row in self.rows("deliveries"):
            if row["order_id"] in ids:
                routes[row["route"]]["count"] += 1
                routes[row["route"]]["late"] += int((row["delivered_date"] or str(self.end)) > row["promised_date"])
        selected = dict(sorted(routes.items(), key=lambda entry: -entry[1]["late"])[:25])
        for route, value in selected.items():
            value["late_rate"] = round(100 * value["late"] / value["count"], 2)
            value["evidence_id"] = self.cite(
                f"{route}: {value['late']} of {value['count']} deliveries late ({value['late_rate']}%).",
                ["deliveries", "orders"],
                value["late_rate"],
                "%",
                f"Late / matched deliveries on route={route}",
            )
        return {
            **summary,
            "routes": selected,
            "total_routes": len(routes),
            "limitation": "Top 25 routes by late count shown. Unmatched orders are excluded; pending orders use the dataset as-of date.",
        }

    def get_customer_signals(self, query=""):
        current = self.period(self.rows("orders"))
        statuses = defaultdict(int)
        for row in current:
            statuses[row["status"]] += 1
        eid = self.cite(
            f"Latest period contains {len(current)} orders across {len({r['customer_id'] for r in current})} customer IDs.",
            ["orders"],
            len(current),
            "orders",
            "Count all current orders and distinct customer_id values",
        )
        return {
            "statuses": dict(statuses),
            "evidence_id": eid,
            "limitation": "Order activity does not establish churn or satisfaction; consult complaint documents.",
            "documents": self.search_documents(query or "complaints customer late stock"),
        }

    def get_marketing(self, query=""):
        cur, prev = self.period(self.rows("marketing")), self.period(self.rows("marketing"), previous=True)
        result = {"available": bool(cur and prev)}
        for key in ("impressions", "clicks", "spend"):
            current, previous = money(cur, key), money(prev, key)
            result[key] = {"current": current, "previous": previous, "change": change(current, previous)}
            result[key]["evidence_id"] = self.cite(
                f"Marketing {key}: {current:,.0f} vs {previous:,.0f}.",
                ["marketing"],
                current,
                "NPR" if key == "spend" else "count",
                f"Sum {key} in equal 28-day periods",
            )
        result["limitation"] = "Aggregate traffic does not prove stable product demand or conversion."
        return result

    def get_margin_bridge(self, query=""):
        current, previous = self.contribution(), self.contribution(previous=True)
        if not current or not previous:
            return {
                "available": False,
                "limitation": "A margin bridge needs orders plus product costs from the products or purchases data.",
            }
        _, cost_formula, cost_kinds = self.contribution_terms([current, previous])
        basis = current["basis"] | previous["basis"]
        fees = bool(current["fee_count"] or previous["fee_count"])
        missing = []
        if "purchases" not in basis:
            missing.append(
                "Purchase costs are not recorded; cost of goods uses current catalog costs, so supplier price changes cannot be measured."
            )
        elif "catalog" in basis:
            missing.append("Some sales have no earlier purchase record and use current catalog costs.")
        if not fees:
            missing.append("Courier fees are not recorded; add courier and fee columns to the deliveries data.")
        if "expenses" not in self.tables:
            missing.append("Expenses data is missing.")
        steps = []
        for key, label, sign, kinds, formula, recorded in [
            ("revenue", "Recognized revenue", 1, ["orders"], "Sum revenue for delivered/completed orders", True),
            (
                "product_cost",
                "Cost of goods sold",
                -1,
                [kind for kind in cost_kinds if kind in {"orders", "purchases", "products"}],
                "Sum quantity × unit cost (latest purchase on or before the sale, else catalog cost)",
                True,
            ),
            (
                "delivery_fees",
                "Courier fees",
                -1,
                ["deliveries", "orders"],
                "Sum fee on deliveries for orders placed in each window",
                fees,
            ),
            (
                "expenses",
                "Other recorded expenses",
                -1,
                ["expenses"],
                "Sum expense amounts dated in each window",
                "expenses" in self.tables,
            ),
        ]:
            if not recorded:
                continue
            cur, prev = current[key], previous[key]
            effect = cur - prev if sign > 0 else prev - cur
            step = {
                "key": key,
                "label": label,
                "current": amount(cur),
                "previous": amount(prev),
                "change": change(float(cur), float(prev)),
                "effect": amount(effect),
                "evidence_id": self.cite(
                    f"{label}: NPR {cur:,.2f} vs NPR {prev:,.2f}; effect on contribution NPR {effect:+,.2f}.",
                    kinds,
                    amount(effect),
                    "NPR",
                    f"{formula}; effect = {'current − baseline' if sign > 0 else 'baseline − current'}",
                ),
            }
            if key == "expenses":
                step["categories"] = sorted(
                    (
                        {
                            "category": category,
                            "current": amount(current["categories"].get(category, Decimal(0))),
                            "previous": amount(previous["categories"].get(category, Decimal(0))),
                        }
                        for category in set(current["categories"]) | set(previous["categories"])
                    ),
                    key=lambda item: (item["previous"] - item["current"], item["category"]),
                )[:5]
            steps.append(step)
        price_effect, compared = Decimal(0), 0
        for product_id, item in current["products"].items():
            base = previous["products"].get(product_id)
            if base and base["units"]:
                price_effect += item["revenue"] - base["revenue"] / base["units"] * item["units"]
                compared += 1
        volume_effect = current["revenue"] - previous["revenue"] - price_effect
        pricing = {
            "price_effect": amount(price_effect),
            "volume_and_mix_effect": amount(volume_effect),
            "percent_of_baseline_revenue": round(float(price_effect / previous["revenue"] * 100), 2)
            if previous["revenue"] and compared
            else None,
            "evidence_id": self.cite(
                f"Like-for-like selling price effect: NPR {price_effect:+,.2f} across {compared} products sold in both windows; volume and mix effect NPR {volume_effect:+,.2f}.",
                ["orders"],
                amount(price_effect),
                "NPR",
                "Sum over products sold in both windows of (current revenue − baseline revenue per unit × current units)",
            ),
            "documents": self.search_documents(
                "discount promotion campaign offer selling price", require=DISCOUNT_TERMS, limit=3
            )["matches"],
        }

        def rate(part):
            return round(float(part["contribution"] / part["revenue"] * 100), 2) if part["revenue"] else None

        return {
            "available": True,
            "current": amount(current["contribution"]),
            "previous": amount(previous["contribution"]),
            "change": amount(current["contribution"] - previous["contribution"]),
            "change_percent": change(float(current["contribution"]), float(previous["contribution"])),
            "margin_rate": {"current": rate(current), "previous": rate(previous)},
            "steps": steps,
            "pricing": pricing,
            "cost_basis": "mixed" if len(basis) > 1 else next(iter(basis), "catalog"),
            "missing": missing,
            "limitation": "The bridge reconciles recorded figures: it shows where contribution changed, not why. Courier fees or stock purchases also recorded as expenses would be counted twice.",
        }

    def get_delivery_costs(self, query=""):
        couriers = defaultdict(lambda: {"current": [Decimal(0), 0], "previous": [Decimal(0), 0]})
        unpriced = 0
        for prior, key in [(False, "current"), (True, "previous")]:
            ids = {row["id"] for row in self.period(self.rows("orders"), previous=prior)}
            for row in self.rows("deliveries"):
                if row["order_id"] not in ids:
                    continue
                if row.get("fee") is None:
                    if not prior:
                        unpriced += 1
                    continue
                item = couriers[row.get("courier") or "Unassigned"][key]
                item[0] += Decimal(row["fee"])
                item[1] += 1
        result = []
        for name, value in couriers.items():
            (cur_total, cur_count), (prev_total, prev_count) = value["current"], value["previous"]
            cur_fee = cur_total / cur_count if cur_count else None
            prev_fee = prev_total / prev_count if prev_count else None
            rate_effect = cur_total - prev_fee * cur_count if prev_fee is not None else None
            result.append(
                {
                    "courier": name,
                    "current_deliveries": cur_count,
                    "previous_deliveries": prev_count,
                    "current_fees": amount(cur_total),
                    "previous_fees": amount(prev_total),
                    "current_fee_per_delivery": amount(cur_fee) if cur_fee is not None else None,
                    "previous_fee_per_delivery": amount(prev_fee) if prev_fee is not None else None,
                    "change": change(float(cur_fee), float(prev_fee)) if cur_fee is not None and prev_fee else None,
                    "rate_effect": amount(rate_effect) if rate_effect is not None else None,
                    "volume_effect": amount(cur_total - prev_total - rate_effect) if rate_effect is not None else None,
                }
            )
        result.sort(key=lambda item: (-(item["rate_effect"] or 0), item["courier"]))
        selected = result[:25]
        for item in selected:
            name = item["courier"]
            if item["rate_effect"] is not None and item["current_deliveries"]:
                percent = f" ({item['change']:+.1f}%)" if item["change"] is not None else ""
                claim = (
                    f"{name}: NPR {item['current_fee_per_delivery']:,.2f} per delivery vs NPR {item['previous_fee_per_delivery']:,.2f}"
                    f"{percent}; rate effect NPR {item['rate_effect']:,.2f} on {item['current_deliveries']} deliveries."
                )
            elif item["current_deliveries"]:
                claim = f"{name}: {item['current_deliveries']} deliveries at NPR {item['current_fee_per_delivery']:,.2f} each; no baseline deliveries."
            else:
                claim = f"{name}: no priced deliveries in the latest window ({item['previous_deliveries']} in the baseline)."
            item["evidence_id"] = self.cite(
                claim,
                ["deliveries", "orders"],
                item["rate_effect"],
                "NPR",
                f"(current − baseline fee per delivery) × current deliveries where courier={name}",
            )
        for item in [row for row in selected if (row["change"] or 0) >= MATERIAL_CHANGE][:3]:
            item["documents"] = self.search_documents(
                f"{item['courier']} courier delivery fee rate tariff charge",
                require=re.compile(re.escape(item["courier"]), re.IGNORECASE),
                limit=3,
            )["matches"]
        return {
            "available": bool(result),
            "couriers": selected,
            "total_couriers": len(result),
            "unpriced_deliveries": unpriced,
            "limitation": "Rate effect = (current − baseline fee per delivery) × current deliveries. Average fees also move with route and parcel mix; deliveries without a fee are excluded.",
        }

    def get_supplier_costs(self, query=""):
        names = {row["id"]: row["name"] for row in self.rows("suppliers")}
        pairs = defaultdict(lambda: {"current": [Decimal(0), Decimal(0)], "previous": [Decimal(0), Decimal(0)]})
        for prior, key in [(False, "current"), (True, "previous")]:
            for row in self.period(self.rows("purchases"), previous=prior):
                item = pairs[row["supplier_id"], row["product_id"]][key]
                item[0] += Decimal(row["unit_cost"]) * Decimal(row["quantity"])
                item[1] += Decimal(row["quantity"])
        prices = []
        for (supplier_id, product_id), value in pairs.items():
            (cur_total, cur_quantity), (prev_total, prev_quantity) = value["current"], value["previous"]
            cur = cur_total / cur_quantity if cur_quantity else None
            prev = prev_total / prev_quantity if prev_quantity else None
            prices.append(
                {
                    "supplier_id": supplier_id,
                    "supplier_name": names.get(supplier_id, supplier_id),
                    "product_id": product_id,
                    "product_name": self.catalog.get(product_id, {}).get("name", product_id),
                    "current_unit_cost": amount(cur) if cur is not None else None,
                    "previous_unit_cost": amount(prev) if prev is not None else None,
                    "change": change(float(cur), float(prev)) if cur is not None and prev else None,
                    "current_quantity": int(cur_quantity),
                }
            )
        prices.sort(key=lambda item: (-(item["change"] or 0), item["supplier_id"], item["product_id"]))
        prices = prices[:25]
        for item in prices:
            if item["current_unit_cost"] is not None and item["previous_unit_cost"] is not None:
                percent = f" ({item['change']:+.1f}%)" if item["change"] is not None else ""
                claim = (
                    f"{item['supplier_name']} ({item['supplier_id']}), {item['product_name']}: NPR {item['current_unit_cost']:,.2f} "
                    f"per unit vs NPR {item['previous_unit_cost']:,.2f}{percent}."
                )
            else:
                claim = f"{item['supplier_name']} ({item['supplier_id']}), {item['product_name']}: purchases in only one window; no price comparison."
            item["evidence_id"] = self.cite(
                claim,
                ["purchases", "suppliers"],
                item["current_unit_cost"],
                "NPR",
                f"Quantity-weighted unit_cost per window where supplier_id={item['supplier_id']} and product_id={item['product_id']}",
            )
        # One document search per supplier: a price letter usually covers all of that supplier's products.
        material = [row for row in prices if (row["change"] or 0) >= MATERIAL_CHANGE]
        for supplier in list(dict.fromkeys(row["supplier_name"] for row in material))[:3]:
            matches = self.search_documents(
                f"{supplier} supplier price cost invoice",
                require=re.compile(re.escape(supplier), re.IGNORECASE),
                limit=3,
            )["matches"]
            for row in material:
                if row["supplier_name"] == supplier:
                    row["documents"] = matches
        effects = []
        current, previous = self.contribution(), self.contribution(previous=True)
        if current and previous:
            for product_id, item in current["products"].items():
                base = previous["products"].get(product_id)
                if not base or not base["units"] or not item["units"]:
                    continue
                cur_unit, prev_unit = item["cost"] / item["units"], base["cost"] / base["units"]
                effects.append(
                    {
                        "product_id": product_id,
                        "name": self.catalog.get(product_id, {}).get("name", product_id),
                        "current_units": int(item["units"]),
                        "current_unit_cost": amount(cur_unit),
                        "previous_unit_cost": amount(prev_unit),
                        "change": change(float(cur_unit), float(prev_unit)),
                        "rate_effect": amount(item["cost"] - prev_unit * item["units"]),
                    }
                )
            effects.sort(key=lambda item: (-item["rate_effect"], item["product_id"]))
            effects = effects[:25]
            for item in effects:
                item["evidence_id"] = self.cite(
                    f"{item['name']}: cost per unit sold NPR {item['current_unit_cost']:,.2f} vs NPR {item['previous_unit_cost']:,.2f}; "
                    f"NPR {item['rate_effect']:,.2f} cost-of-goods rate effect on {item['current_units']} units.",
                    ["orders", "purchases", "products"],
                    item["rate_effect"],
                    "NPR",
                    f"Current cost of goods − baseline cost per unit × current units where product_id={item['product_id']}",
                )
        return {
            "available": bool(self.rows("purchases")),
            "price_changes": prices,
            "product_cost_effects": effects,
            "limitation": "Cost per unit sold uses the latest purchase on or before each sale. Without purchase records, catalog costs are current values and supplier price changes cannot be measured.",
        }

    def search_documents(self, query="", require=None, limit=5):
        chunks = [
            (source, chunk)
            for source in self.sources
            if source.kind == "document"
            for chunk in source.content["chunks"]
            if not require or require.search(chunk["text"])
        ]
        matches, method = rank(query, chunks, limit)
        result = []
        for match in matches:
            source, chunk = match["source"], match["chunk"]
            found = (
                f"Semantic similarity {match['similarity']:.2f} to the question"
                if "similarity" in match
                else f"Shares {match['overlap']} keyword(s) with the question"
            )
            eid = f"E{len(self.evidence) + 1}"
            self.evidence.append(
                {
                    "id": eid,
                    "type": "fact",
                    "claim": chunk["text"],
                    "value": None,
                    "unit": None,
                    "calculation": found,
                    "sources": [
                        {
                            "id": source.id,
                            "name": source.name,
                            "locator": f"Page {chunk['page']}, chunk {chunk['chunk']}",
                        }
                    ],
                }
            )
            result.append(
                {
                    "evidence_id": eid,
                    "source": source.name,
                    "excerpt": chunk["text"],
                    "page": chunk["page"],
                    "score": round(match["similarity"], 3) if "similarity" in match else match["overlap"],
                }
            )
        return {
            "matches": result,
            "method": method,
            "limitation": "Document statements are attributed claims, not independently verified facts.",
        }

    def call(self, name, query=""):
        if name not in TOOL_NAMES:
            raise ValueError("Tool is not allowed")
        return getattr(self, name)(query)


TOOL_NAMES = (
    "detect_anomalies",
    "segment_performance",
    "get_inventory",
    "get_supplier_data",
    "get_deliveries",
    "get_customer_signals",
    "get_marketing",
    "get_margin_bridge",
    "get_delivery_costs",
    "get_supplier_costs",
    "search_documents",
)
