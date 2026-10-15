"""Read-only tools. Money is calculated with Decimal, never by the language model."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from .retrieval import search as retrieve_documents

PAID = {"delivered", "completed"}


def money(rows, column):
    return float(sum((Decimal(str(row[column])) for row in rows), Decimal(0)))


def change(current, previous):
    return round((current - previous) / previous * 100, 2) if previous else None


class Tools:
    def __init__(self, sources):
        self.sources = sources
        self.tables = {source.kind: source for source in sources if source.kind != "document"}
        self.evidence = []
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
                f"{label}: {cur:,.2f} vs {prev:,.2f} in equal 28-day windows.",
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
        products = {row["id"]: row for row in self.rows("products")}
        if products and all(row["product_id"] in products for row in current + previous):
            margins = []
            for rows, prior in [(current, False), (previous, True)]:
                costs = sum(
                    (Decimal(products[row["product_id"]]["cost"]) * Decimal(row["quantity"]) for row in rows),
                    Decimal(0),
                )
                expenses = sum(
                    (Decimal(row["amount"]) for row in self.period(self.rows("expenses"), previous=prior)), Decimal(0)
                )
                revenue = sum((Decimal(row["revenue"]) for row in rows), Decimal(0))
                margins.append(float(revenue - costs - expenses))
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
            metric["evidence_id"] = self.cite(
                "Contribution estimate uses current catalog costs and recorded expenses; historical costs and taxes are unknown.",
                ["orders", "products", "expenses"],
                margins[0],
                "NPR",
                "Recognized revenue − catalog cost × quantity − recorded expenses",
            )
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
                        f"{product_id} recorded zero stock on {item['stockout_days']} days.",
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
                            f"{row['name']} ({row['id']}), product {row['product_id']}: shipment {days} days late.",
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

    def search_documents(self, query=""):
        retrieval = retrieve_documents(
            [source for source in self.sources if source.kind == "document"],
            query,
        )
        result = []
        for match in retrieval["results"]:
            source = match["source"]
            chunk = match["chunk"]
            eid = f"E{len(self.evidence) + 1}"
            self.evidence.append(
                {
                    "id": eid,
                    "type": "fact",
                    "claim": chunk["text"],
                    "value": None,
                    "unit": None,
                    "calculation": None,
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
                    "score": match["score"],
                }
            )
        return {
            "matches": result,
            "method": retrieval["method"],
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
    "search_documents",
)
