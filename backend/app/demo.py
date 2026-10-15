import csv
import io
from datetime import date, timedelta

from .ingestion import store_source


def demo_pack():
    tables = {
        key: []
        for key in ("orders", "products", "inventory", "suppliers", "deliveries", "marketing", "customers", "expenses")
    }
    tables["products"] = [
        {"id": "P1", "name": "Wireless earbuds", "category": "Electronics", "price": "3500", "cost": "2100"},
        {"id": "P2", "name": "Himalayan tea set", "category": "Home & living", "price": "1500", "cost": "800"},
        {"id": "P3", "name": "Everyday essentials", "category": "Grocery", "price": "900", "cost": "600"},
    ]
    for i in range(100):
        tables["customers"].append(
            {
                "id": f"C{i}",
                "segment": "Repeat" if i % 3 else "New",
                "location": ["Kathmandu", "Pokhara", "Lalitpur"][i % 3],
                "signup_date": "2026-06-01",
            }
        )
    first = date(2026, 8, 6)
    for day in range(56):
        when = first + timedelta(days=day)
        current = day >= 28
        stockout = 35 <= day <= 48
        for product, count, amount in [
            ("P1", (1 if stockout else 4) if current else 5, 3500),
            ("P2", 4, 1500),
            ("P3", 3, 900),
        ]:
            tables["inventory"].append(
                {
                    "date": str(when),
                    "product_id": product,
                    "supplier_id": "S1" if product == "P1" else "S2",
                    "stock": 0 if stockout and product == "P1" else 85,
                }
            )
            for index in range(count):
                order_id = f"O{day:02}{product}{index}"
                late = product == "P1" and current and (index == 0 or stockout)
                tables["orders"].append(
                    {
                        "id": order_id,
                        "date": str(when),
                        "customer_id": f"C{(day * 7 + index) % 100}",
                        "product_id": product,
                        "quantity": 1,
                        "revenue": amount,
                        "status": "delivered",
                    }
                )
                tables["deliveries"].append(
                    {
                        "order_id": order_id,
                        "promised_date": str(when + timedelta(days=2)),
                        "delivered_date": str(when + timedelta(days=7 if late else 2)),
                        "route": "Kathmandu valley" if product == "P1" else "Pokhara",
                    }
                )
        tables["marketing"].append(
            {
                "date": str(when),
                "channel": "Search",
                "spend": 1800,
                "impressions": 11000 if current else 10000,
                "clicks": 550 if current else 500,
            }
        )
        tables["expenses"].append({"date": str(when), "category": "Logistics", "amount": 1900 if current else 1500})
    tables["suppliers"] = [
        {
            "id": "S1",
            "name": "Valley Electronics",
            "product_id": "P1",
            "promised_date": "2026-09-10",
            "received_date": "2026-09-24",
        },
        {
            "id": "S2",
            "name": "Nepal Essentials",
            "product_id": "P2",
            "promised_date": "2026-09-10",
            "received_date": "2026-09-10",
        },
        {
            "id": "S1",
            "name": "Valley Electronics",
            "product_id": "P1",
            "promised_date": "2026-08-10",
            "received_date": "2026-08-10",
        },
    ]
    files = []
    for kind, rows in tables.items():
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        files.append((kind, f"himalayanmart_{kind}.csv", buffer.getvalue().encode()))
    docs = {
        "supplier_incident.md": "# Supplier incident · 24 September 2026\nValley Electronics (S1) missed its 10 September shipment for P1 wireless earbuds. Customs clearance delayed receipt until 24 September. Warehouse recorded zero available stock from 10 to 23 September. This report is synthetic demo evidence, not an independently audited fact.",
        "customer_feedback.md": "# Customer feedback · September 2026\nOperations recorded complaints about late wireless earbuds deliveries and unavailable stock in Kathmandu. Customers could still order tea and groceries. Complaint sampling is incomplete; it does not establish customer churn.",
        "marketing_review.md": "# Marketing review · September 2026\nSearch impressions and clicks increased in the latest four weeks. There were no recorded campaign outages. Traffic alone cannot prove unchanged demand for a particular product. No historical competitor pricing data is available.",
        "operations_review.md": "# Operations review · September 2026\nElectronics revenue declined while home and grocery order volumes were steady. Late inbound supply and inventory availability need review. Current product prices are available but historical price changes were not recorded. Margin estimates exclude taxes and unrecorded costs.",
    }
    files.extend(("document", name, text.encode()) for name, text in docs.items())
    return files



def margin_demo_pack():
    """Synthetic documents explaining rising revenue but falling contribution."""
    return [
        (
            "document",
            "courier_rate_notice.md",
            (
                "# Courier Rate Notice - October 2026\n"
                "HimalayanMart's courier partner has increased delivery rates "
                "by 25% effective 1 October 2026. The revised rates apply to "
                "all standard deliveries, with additional charges for remote "
                "locations. These higher delivery expenses reduce contribution "
                "per order. This is synthetic demo data."
            ).encode(),
        ),
        (
            "document",
            "supplier_price_letter.md",
            (
                "# Supplier Price Revision - October 2026\n"
                "Valley Electronics has increased wholesale prices for "
                "wireless earbuds by 12% effective 1 October 2026. Retail "
                "prices have not changed, so the higher purchase cost reduces "
                "the contribution earned on each unit sold. This is synthetic "
                "demo data."
            ).encode(),
        ),
        (
            "document",
            "finance_margin_note.md",
            (
                "# Finance Note - October 2026\n"
                "HimalayanMart's revenue increased by approximately 10% "
                "compared with the previous period, but contribution fell. "
                "The main factors identified for this synthetic scenario are "
                "higher courier expenses and increased supplier prices. "
                "Management should review delivery costs and product-level "
                "contribution before changing retail prices. This is synthetic "
                "demo data, not audited financial information."
            ).encode(),
        ),
    ]



def seed_demo(db):
    return [store_source(db, data, name, kind)[0] for kind, name, data in demo_pack()]
