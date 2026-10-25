import csv
import io
from datetime import date, timedelta

from .ingestion import store_source


def pack_files(prefix, tables, docs):
    files = []
    for kind, rows in tables.items():
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        files.append((kind, f"{prefix}_{kind}.csv", buffer.getvalue().encode()))
    files.extend(("document", name, text.encode()) for name, text in docs.items())
    return files


def supply_pack():
    """Supplier delay → stockout → product revenue decline."""
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
    docs = {
        "supplier_incident.md": "# Supplier incident · 24 September 2026\nValley Electronics (S1) missed its 10 September shipment for P1 wireless earbuds. Customs clearance delayed receipt until 24 September. Warehouse recorded zero available stock from 10 to 23 September. This report is synthetic demo evidence, not an independently audited fact.",
        "customer_feedback.md": "# Customer feedback · September 2026\nOperations recorded complaints about late wireless earbuds deliveries and unavailable stock in Kathmandu. Customers could still order tea and groceries. Complaint sampling is incomplete; it does not establish customer churn.",
        "marketing_review.md": "# Marketing review · September 2026\nSearch impressions and clicks increased in the latest four weeks. There were no recorded campaign outages. Traffic alone cannot prove unchanged demand for a particular product. No historical competitor pricing data is available.",
        "operations_review.md": "# Operations review · September 2026\nElectronics revenue declined while home and grocery order volumes were steady. Late inbound supply and inventory availability need review. Current product prices are available but historical price changes were not recorded. Margin estimates exclude taxes and unrecorded costs.",
    }
    return pack_files("himalayanmart", tables, docs)


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
# Route → courier. Fictional couriers and suppliers: never put real company names on synthetic notices.
ROUTES = [
    ("Kathmandu valley", "Peakline Parcel"),
    ("Kathmandu valley", "Peakline Parcel"),
    ("Pokhara", "Peakline Parcel"),
    ("Biratnagar", "Riverbend Couriers"),
    ("Butwal", "Riverbend Couriers"),
]


def margin_pack():
    """Revenue rises while a courier rate rise and a supplier price rise cut contribution."""
    tables = {
        key: []
        for key in (
            "orders",
            "products",
            "inventory",
            "suppliers",
            "deliveries",
            "marketing",
            "customers",
            "expenses",
            "purchases",
        )
    }
    tables["products"] = [
        {"id": "P1", "name": "Pashmina shawl", "category": "Apparel", "price": "4500", "cost": "2600"},
        {"id": "P2", "name": "Ilam tea gift box", "category": "Gifts", "price": "1800", "cost": "1150"},
        {"id": "P3", "name": "Dhaka topi", "category": "Apparel", "price": "1200", "cost": "650"},
    ]
    suppliers = {
        "P1": ("S1", "Valley Weavers Co-op"),
        "P2": ("S2", "Hillside Tea Traders"),
        "P3": ("S3", "Lalitpur Craft Supply"),
    }
    cities = ["Kathmandu", "Lalitpur", "Pokhara", "Biratnagar", "Butwal"]
    for i in range(120):
        tables["customers"].append(
            {
                "id": f"C{i}",
                "segment": "Repeat" if i % 3 else "New",
                "location": cities[i % 5],
                "signup_date": "2026-05-01",
            }
        )
    first = date(2026, 8, 20)
    parcel = 0
    for day in range(56):
        when = first + timedelta(days=day)
        current = day >= 28
        for product, count, price, cost, restock in [
            ("P1", 2, 4500, 2600, 14),
            ("P2", 5 if current else 4, 1800, 1150 if current else 1000, 36 if current else 30),
            ("P3", 4 if when.weekday() == 5 else 3, 1200, 650, 24),
        ]:
            supplier_id, supplier = suppliers[product]
            tables["inventory"].append(
                {"date": str(when), "product_id": product, "supplier_id": supplier_id, "stock": 40 + day % 7 * 2}
            )
            if day % 7 == 0:
                tables["purchases"].append(
                    {
                        "date": str(when),
                        "supplier_id": supplier_id,
                        "product_id": product,
                        "quantity": restock,
                        "unit_cost": cost,
                    }
                )
                tables["suppliers"].append(
                    {
                        "id": supplier_id,
                        "name": supplier,
                        "product_id": product,
                        "promised_date": str(when),
                        "received_date": str(when),
                    }
                )
            for index in range(count):
                order_id = f"M{day:02}{product}{index}"
                route, courier = ROUTES[parcel % len(ROUTES)]
                parcel += 1
                promised = when + timedelta(days=2 if route == "Kathmandu valley" else 4)
                tables["orders"].append(
                    {
                        "id": order_id,
                        "date": str(when),
                        "customer_id": f"C{(day * 11 + index * 7 + int(product[1])) % 120}",
                        "product_id": product,
                        "quantity": 1,
                        "revenue": price,
                        "status": "delivered",
                    }
                )
                tables["deliveries"].append(
                    {
                        "order_id": order_id,
                        "promised_date": str(promised),
                        "delivered_date": str(promised + timedelta(days=1 if parcel % 9 == 0 else 0)),
                        "route": route,
                        "courier": courier,
                        "fee": (210 if current else 150) if courier == "Peakline Parcel" else 180,
                    }
                )
        tables["marketing"].append(
            {
                "date": str(when),
                "channel": "Social",
                "spend": 2200,
                "impressions": 15400 if current else 14000,
                "clicks": 770 if current else 700,
            }
        )
        for category, amount in [("Salaries", 3000), ("Rent", 1200), ("Packaging", 400)]:
            tables["expenses"].append({"date": str(when), "category": category, "amount": amount})
    docs = {
        "courier_rate_notice.md": "# Peakline Parcel rate notice · 3 September 2026\nFrom 17 September 2026, Peakline Parcel will charge NPR 210 per parcel for Kathmandu valley and Pokhara deliveries, up from NPR 150. The notice cites higher fuel and vehicle maintenance costs. This notice is synthetic demo evidence, not an independently audited fact.",
        "supplier_price_letter.md": "# Hillside Tea Traders price letter · 10 September 2026\nHillside Tea Traders will invoice the Ilam tea gift box at NPR 1,150 per unit, up from NPR 1,000, for all deliveries from 17 September 2026. The letter cites a smaller autumn harvest and higher packaging costs. This letter is synthetic demo evidence, not an independently audited fact.",
        "finance_note.md": "# Finance note · October 2026\nOnline sales rose in the latest four weeks, mainly from Ilam tea gift box orders, yet the monthly margin looked weaker. The team suspects the festival discount campaign is eroding margin, although no discount amounts were recorded in the order system. Courier and supplier invoices have not yet been reconciled against the order data. This note is synthetic demo evidence.",
    }
    return pack_files("himalayanmart_margin", tables, docs)


PACKS = {"supply": supply_pack, "margin": margin_pack}


def demo_pack(pack="supply"):
    return PACKS[pack]()


def seed_demo(db, pack="supply"):
    return [store_source(db, data, name, kind)[0] for kind, name, data in demo_pack(pack)]
