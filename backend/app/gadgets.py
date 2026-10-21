"""Synthetic but realistic data for HimalayanMart Gadgets, a fictional mobile-accessories seller in Nepal.

One continuous business history (1 Oct 2025 – 16 Oct 2026) with five planted problems. Each scenario pack is
that history exported on a different date, so SanketAI's latest-28-days comparison lands on the problem.
Every business, courier, supplier and customer is fictional; festival dates follow the real 2025–26 calendar.
Stock, replenishment and deliveries are simulated day by day, so stockouts and delays emerge from the data.
"""

import csv
import io
import math
import random
from collections import defaultdict
from datetime import date, timedelta

START, END = date(2025, 10, 1), date(2026, 10, 16)
SEED = 2083

SUPPLIERS = {
    # id: (name, lead days, weekday orders are placed; Monday is 0, and Saturday is Nepal's weekly holiday)
    "S01": ("Everest Tech Traders", 5, 1),
    "S02": ("Himal Power Solutions", 3, 0),
    "S03": ("Bagmati Accessories Wholesale", 2, 6),
    "S04": ("Birgunj Import House", 6, 2),
}

# id, name, category, list price, unit cost, supplier, demand weight, warranty months, max quantity per order
PRODUCTS = [
    ("AUD-TWS-01", "TWS earbuds (basic)", "Audio", 1499, 820, "S01", 14, 6, 2),
    ("AUD-TWS-02", "TWS earbuds Pro with ANC", "Audio", 3999, 2350, "S01", 5, 12, 1),
    ("AUD-NB-01", "Bluetooth neckband", "Audio", 1299, 700, "S01", 6, 6, 2),
    ("AUD-WE-01", "Wired earphones with mic", "Audio", 349, 150, "S03", 5, 3, 3),
    ("AUD-SPK-01", "Mini Bluetooth speaker", "Audio", 1899, 1100, "S01", 3, 6, 1),
    ("AUD-SPK-02", "Party Bluetooth speaker", "Audio", 6499, 4100, "S01", 0.8, 12, 1),
    ("PWR-PB-10", "Power bank 10,000 mAh", "Power banks", 1599, 980, "S02", 6, 6, 2),
    ("PWR-PB-20", "Power bank 20,000 mAh PD", "Power banks", 2799, 1750, "S02", 3.5, 6, 1),
    ("PWR-CH-20", "20W Type-C fast charger", "Chargers", 899, 480, "S02", 6, 6, 2),
    ("PWR-CH-33", "33W dual-port charger", "Chargers", 1299, 760, "S02", 3.5, 6, 2),
    ("PWR-CH-65", "65W GaN laptop charger", "Chargers", 3499, 2200, "S02", 1.2, 12, 1),
    ("PWR-CAR-01", "Dual USB car charger", "Chargers", 699, 360, "S02", 1.2, 3, 2),
    ("CBL-TC-1M", "Type-C cable 1 m", "Cables", 299, 110, "S03", 8, 3, 3),
    ("CBL-TC-2B", "Braided Type-C cable 2 m", "Cables", 549, 240, "S03", 3, 6, 2),
    ("CBL-LT-1M", "Lightning cable 1 m", "Cables", 449, 190, "S03", 2.2, 3, 2),
    ("CBL-3IN1", "3-in-1 charging cable", "Cables", 599, 260, "S03", 2, 3, 2),
    ("CBL-OTG", "Type-C OTG adapter", "Cables", 199, 70, "S03", 1.5, 0, 3),
    ("PRT-CASE-01", "Silicone phone case", "Cases & protection", 349, 120, "S03", 6, 0, 2),
    ("PRT-CASE-02", "Rugged armour case", "Cases & protection", 799, 330, "S03", 2, 0, 1),
    ("PRT-GLS-01", "Tempered glass screen guard", "Cases & protection", 249, 60, "S03", 7, 0, 3),
    ("PRT-LENS-01", "Camera lens protector", "Cases & protection", 299, 90, "S03", 1.8, 0, 2),
    ("WRB-SW-01", "Smartwatch (basic)", "Wearables", 2499, 1500, "S01", 3, 6, 1),
    ("WRB-SW-02", "AMOLED smartwatch", "Wearables", 5499, 3500, "S01", 1.1, 12, 1),
    ("WRB-BAND-01", "Fitness band", "Wearables", 1799, 1050, "S01", 2, 6, 1),
    ("ACC-HLD-01", "Bike phone holder", "Accessories", 899, 430, "S04", 2, 3, 1),
    ("ACC-TRI-01", "Tripod with Bluetooth remote", "Accessories", 1199, 620, "S04", 1.5, 3, 1),
    ("ACC-RING-01", "10-inch ring light", "Accessories", 1499, 800, "S04", 1, 3, 1),
    ("ACC-SD-64", "64 GB microSD card", "Accessories", 899, 560, "S04", 2, 12, 2),
    ("ACC-USB-64", "64 GB USB flash drive", "Accessories", 799, 470, "S04", 1, 12, 2),
]
PRODUCT = {row[0]: row for row in PRODUCTS}

# route: (courier, promised days after dispatch, fee before 1 Mar 2026, fee from 1 Mar 2026, risk class)
ROUTES = {
    "Kathmandu valley": ("Peakline Parcel", 1, 100, 140, "valley"),
    "Pokhara": ("Peakline Parcel", 3, 150, 190, "pokhara"),
    "Chitwan & Makwanpur": ("Peakline Parcel", 2, 140, 175, "plains"),
    "Koshi plains": ("Riverbend Couriers", 3, 170, 170, "plains"),
    "Ilam hills": ("Riverbend Couriers", 5, 220, 220, "hills"),
    "Madhesh": ("Riverbend Couriers", 3, 170, 170, "plains"),
    "Lumbini plains": ("Westline Logistics", 3, 185, 185, "plains"),
    "Palpa hills": ("Westline Logistics", 4, 230, 230, "hills"),
    "Far west": ("Westline Logistics", 5, 240, 240, "farwest"),
    "Karnali": ("Westline Logistics", 6, 260, 260, "hills"),
}
# city: (province, route, weight)
CITIES = {
    "Kathmandu": ("Bagmati", "Kathmandu valley", 28),
    "Lalitpur": ("Bagmati", "Kathmandu valley", 9),
    "Bhaktapur": ("Bagmati", "Kathmandu valley", 5),
    "Pokhara": ("Gandaki", "Pokhara", 7),
    "Bharatpur": ("Bagmati", "Chitwan & Makwanpur", 4.5),
    "Hetauda": ("Bagmati", "Chitwan & Makwanpur", 1.5),
    "Biratnagar": ("Koshi", "Koshi plains", 5.5),
    "Itahari": ("Koshi", "Koshi plains", 2.5),
    "Dharan": ("Koshi", "Koshi plains", 3),
    "Birtamod": ("Koshi", "Koshi plains", 1.5),
    "Damak": ("Koshi", "Koshi plains", 1),
    "Ilam": ("Koshi", "Ilam hills", 1),
    "Janakpur": ("Madhesh", "Madhesh", 2.5),
    "Birgunj": ("Madhesh", "Madhesh", 3.5),
    "Butwal": ("Lumbini", "Lumbini plains", 4),
    "Siddharthanagar": ("Lumbini", "Lumbini plains", 2),
    "Nepalgunj": ("Lumbini", "Lumbini plains", 2.5),
    "Tansen": ("Lumbini", "Palpa hills", 0.8),
    "Dhangadhi": ("Sudurpashchim", "Far west", 2.5),
    "Mahendranagar": ("Sudurpashchim", "Far west", 1),
    "Birendranagar": ("Karnali", "Karnali", 1.2),
}
LATE_BASE = {"valley": 0.03, "pokhara": 0.05, "plains": 0.05, "hills": 0.09, "farwest": 0.07}
MONSOON_LATE = {"valley": 1.8, "pokhara": 6.0, "plains": 2.6, "hills": 6.5, "farwest": 5.5}
CHANNELS = {"Marketplace": 52, "Website": 18, "Facebook & Instagram": 22, "TikTok": 8}
PAYMENTS = {
    "Marketplace": {"Cash on delivery": 70, "eSewa": 12, "Khalti": 10, "Card": 8},
    "Website": {"Cash on delivery": 55, "eSewa": 20, "Khalti": 15, "Fonepay QR": 10},
    "Facebook & Instagram": {"Cash on delivery": 85, "Fonepay QR": 15},
    "TikTok": {"Cash on delivery": 88, "Fonepay QR": 12},
}
# channel: (base daily spend NPR, impressions per rupee, click-through rate)
ADS = {
    "Facebook & Instagram": (1600, 9.0, 0.016),
    "TikTok": (600, 14.0, 0.011),
    "Marketplace sponsored": (1100, 6.0, 0.032),
    "Google search": (250, 3.0, 0.045),
}
TIHAR_2025 = (date(2025, 10, 20), date(2025, 10, 23))
MONSOON = (date(2026, 6, 12), date(2026, 9, 27))
COD_CAMPAIGN = (date(2025, 12, 28), date(2026, 1, 24))
AD_BOOST = (date(2026, 5, 3), date(2026, 5, 30))
PRICE_RISE = date(2026, 3, 1)
DASHAIN_ORDER, DASHAIN_PROMISED, DASHAIN_RECEIVED = date(2026, 9, 14), date(2026, 9, 28), date(2026, 10, 15)

PACKS = [
    {
        "slug": "1_cod_refusals",
        "end": date(2026, 1, 24),
        "title": "Orders up, delivered sales down",
        "question": "Why did our delivered sales fall even though we received more orders?",
    },
    {
        "slug": "2_margin_squeeze",
        "end": date(2026, 3, 28),
        "title": "Revenue up, margin down",
        "question": "Revenue increased, so why is our margin falling?",
    },
    {
        "slug": "3_ad_campaign",
        "end": date(2026, 5, 30),
        "title": "Ad spend doubled, sales flat",
        "question": "We doubled our social media ad budget. Why didn't sales grow?",
    },
    {
        "slug": "4_monsoon_delays",
        "end": date(2026, 7, 11),
        "title": "Late deliveries",
        "question": "Why are our deliveries late?",
    },
    {
        "slug": "5_dashain_stockout",
        "end": END,
        "title": "Dashain sales drop",
        "question": "Why did our sales drop just before Dashain?",
    },
]


def within(day, window):
    return window[0] <= day <= window[1]


def ramp(day, start, end, low, high):
    return low + (high - low) * (day - start).days / max(1, (end - start).days)


def season(day):
    """Demand multiplier from the real 2025–26 festival calendar and the monsoon."""
    if day <= date(2025, 10, 5):
        return 0.85  # lull after Dashain 2025 (Tika was 2 Oct)
    if day <= date(2025, 10, 19):
        return ramp(day, date(2025, 10, 6), date(2025, 10, 19), 1.0, 1.45)  # Tihar shopping
    if within(day, TIHAR_2025):
        return 0.7
    if day in (date(2025, 11, 9), date(2025, 11, 10)):
        return 1.7
    if day == date(2025, 11, 11):
        return 3.6  # 11.11 sale
    if day in (date(2025, 11, 12), date(2025, 11, 13)):
        return 1.5
    if date(2025, 12, 20) <= day <= date(2025, 12, 31):
        return 1.06
    if date(2026, 1, 1) <= day <= date(2026, 2, 10):
        return 0.86  # winter lull
    if day in (date(2026, 3, 2), date(2026, 3, 3)):
        return 0.75  # Holi: 2 Mar in the hills, 3 Mar in the Terai
    if date(2026, 3, 5) <= day <= date(2026, 3, 22):
        return 1.15  # spring sale
    if date(2026, 4, 9) <= day <= date(2026, 4, 14):
        return 1.2  # Nepali New Year 2083 on 14 Apr
    if date(2026, 9, 9) <= day <= date(2026, 9, 14):
        return 1.1  # Teej on 14 Sep
    if date(2026, 9, 22) <= day <= END:
        return ramp(day, date(2026, 9, 22), END, 1.1, 1.6)  # Dashain shopping; Ghatasthapana 11 Oct
    if within(day, MONSOON):
        return 0.95
    return 1.0


def product_season(product_id, day):
    category = PRODUCT[product_id][2]
    if category == "Wearables" and (
        date(2026, 9, 9) <= day <= date(2026, 9, 14) or date(2026, 4, 9) <= day <= date(2026, 4, 14)
    ):
        return 2.0  # Teej and New Year gifts
    if category == "Power banks" and date(2026, 9, 28) <= day <= END:
        return 1.4  # travelling home for Dashain
    if product_id == "ACC-HLD-01" and within(day, MONSOON):
        return 0.7
    return 1.0


def base_orders(day):
    weekday = (0.98, 0.97, 0.98, 1.0, 1.08, 1.12, 0.95)[day.weekday()]
    months = (day - START).days / 30.4
    return 62 * 1.018**months * weekday * season(day)


def expected_orders(day):
    orders = base_orders(day)
    if within(day, COD_CAMPAIGN):
        orders *= 1.45
    if within(day, AD_BOOST):
        orders *= 1.06
    return orders


def courier_fee(route, day):
    _, _, before, after, _ = ROUTES[route]
    return after if day >= PRICE_RISE else before


def unit_cost(product_id, day):
    cost = PRODUCT[product_id][4]
    # Everest Tech Traders' price revision for stock received from 1 Mar 2026.
    return round(cost * 1.10) if PRODUCT[product_id][5] == "S01" and day >= PRICE_RISE else cost


def discount_rate(product_id, day, rng):
    category = PRODUCT[product_id][2]
    if date(2025, 10, 12) <= day <= date(2025, 10, 19) and rng.random() < 0.4:
        return 0.05  # TIHAR5
    if date(2025, 11, 9) <= day <= date(2025, 11, 13) and category in {"Audio", "Power banks", "Chargers"}:
        return 0.10 if rng.random() < 0.7 else 0
    if date(2026, 3, 1) <= day <= date(2026, 3, 5) and rng.random() < 0.03:
        return 0.05  # HOLI5, rarely used
    if date(2026, 4, 10) <= day <= date(2026, 4, 14) and category == "Wearables" and rng.random() < 0.5:
        return 0.08
    if date(2026, 9, 28) <= day <= END and rng.random() < 0.5:
        return 0.05  # DASHAIN5
    return 0


def poisson(rng, lam):
    if lam > 30:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def pick(rng, weights):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def next_working_day(day):
    day += timedelta(days=1)
    while day.weekday() == 5 or within(day, TIHAR_2025):
        day += timedelta(days=1)
    return day


def simulate(seed=SEED):
    # Each day draws from its own seeded stream, so tuning one period leaves the rest of the year unchanged.
    rng = random.Random(seed)
    days = [START + timedelta(days=i) for i in range((END - START).days + 1)]
    weights = {p[0]: p[6] for p in PRODUCTS}
    total_weight = sum(weights.values())

    def expected_units(product_id, day, festive=True):
        orders = expected_orders(day) if festive else 62 * 1.018 ** ((day - START).days / 30.4)
        share = weights[product_id] / total_weight * (product_season(product_id, day) if festive else 1)
        return orders * share * (1 + (PRODUCT[product_id][8] - 1) * 0.15)

    stock = {p: round(sum(expected_units(p, START + timedelta(days=i)) for i in range(21))) + 5 for p in weights}
    on_order = defaultdict(int)
    arrivals = defaultdict(list)
    restock = defaultdict(lambda: defaultdict(int))
    shipments, orders, inventory, marketing, expenses = [], [], [], [], defaultdict(float)
    customers, buyers, lost = [], [], defaultdict(lambda: defaultdict(int))
    po_number = 0

    def place_order(supplier_id, day, quantities, promised, received):
        nonlocal po_number
        po_number += 1
        for product_id, quantity in quantities.items():
            if quantity <= 0:
                continue
            on_order[product_id] += quantity
            shipment = {
                "po_number": f"PO-{po_number:04d}",
                "supplier_id": supplier_id,
                "product_id": product_id,
                "ordered": day,
                "promised": promised,
                "received": received,
                "quantity": quantity,
                "unit_cost": unit_cost(product_id, received),
            }
            shipments.append(shipment)
            arrivals[received].append(shipment)

    def new_customer(day, city=None):
        city = city or pick(rng, {name: row[2] for name, row in CITIES.items()})
        created = day - timedelta(days=rng.randint(0, 400)) if rng.random() < 0.4 else day
        customer = {"id": f"CUS-{len(customers) + 1:05d}", "city": city, "created": created, "orders": []}
        customers.append(customer)
        return customer

    for day in days:
        rng = random.Random(f"{seed}:{day.isoformat()}")
        for shipment in arrivals.pop(day, []):
            stock[shipment["product_id"]] += shipment["quantity"]
            on_order[shipment["product_id"]] -= shipment["quantity"]
        for product_id, quantity in restock.pop(day, {}).items():
            stock[product_id] += quantity  # refused parcels back on the shelf
        # Weekly replenishment on each supplier's order day.
        for supplier_id, (_, lead, weekday) in SUPPLIERS.items():
            if day.weekday() != weekday or day >= END - timedelta(days=lead):
                continue
            if supplier_id == "S01" and DASHAIN_ORDER <= day < DASHAIN_RECEIVED:
                continue  # consolidated into the Dashain import shipment
            quantities = {}
            consolidating = supplier_id == "S01" and DASHAIN_ORDER - timedelta(days=7) <= day < DASHAIN_ORDER
            for product_id in [p[0] for p in PRODUCTS if p[5] == supplier_id]:
                if consolidating:
                    # Last regular order before the Dashain shipment: cover normal demand until its promised date.
                    horizon = [day + timedelta(days=i) for i in range(lead, (DASHAIN_PROMISED - day).days + 1)]
                    target = sum(expected_units(product_id, d, festive=False) for d in horizon)
                else:
                    horizon = [day + timedelta(days=i) for i in range(lead + 10)]
                    target = 1.3 * sum(expected_units(product_id, d) for d in horizon) + 4  # safety stock
                gap = target - stock[product_id] - on_order[product_id]
                quantities[product_id] = math.ceil(gap / 10) * 10 if gap > 0 else 0
            delay = rng.choices([0, 1, 2], weights=[85, 11, 4])[0]
            place_order(supplier_id, day, quantities, day + timedelta(days=lead), day + timedelta(days=lead + delay))
        if day == DASHAIN_ORDER:
            horizon = [DASHAIN_PROMISED + timedelta(days=i) for i in range(35)]
            quantities = {
                p[0]: math.ceil(1.2 * sum(expected_units(p[0], d) for d in horizon) / 10) * 10
                for p in PRODUCTS
                if p[5] == "S01"
            }
            # Held at Birgunj customs: promised 28 Sep, received 15 Oct.
            place_order("S01", day, quantities, DASHAIN_PROMISED, DASHAIN_RECEIVED)

        # Orders: regular demand plus campaign traffic.
        streams = [("regular", poisson(rng, base_orders(day) * rng.lognormvariate(0, 0.08)))]
        if within(day, COD_CAMPAIGN):
            streams.append(("cod_campaign", poisson(rng, 0.45 * base_orders(day))))
        if within(day, AD_BOOST):
            streams.append(("ad_boost", poisson(rng, 0.06 * base_orders(day))))
        sequence = 0
        for stream, count in streams:
            for _ in range(count):
                if stream == "regular":
                    channel = pick(rng, CHANNELS)
                else:
                    channel = pick(rng, {"Facebook & Instagram": 62, "TikTok": 38})
                payment = "Cash on delivery" if stream == "cod_campaign" else pick(rng, PAYMENTS[channel])
                product_weights = {p: weights[p] * product_season(p, day) for p in weights}
                product_id = pick(rng, product_weights)
                quantity = 1 if rng.random() < 0.85 else rng.randint(1, PRODUCT[product_id][8])
                if stock[product_id] < quantity:
                    lost[product_id][day] += quantity
                    continue
                repeat = min(0.45, 0.15 + 0.02 * (day - START).days / 30.4)
                if stream == "regular" and buyers and rng.random() < repeat:
                    customer = customers[rng.choice(buyers)]
                else:
                    customer = new_customer(day)
                sequence += 1
                price = PRODUCT[product_id][3]
                discount = round(price * quantity * discount_rate(product_id, day, rng))
                order = {
                    "id": f"HMG-{day:%y%m%d}-{sequence:04d}",
                    "date": day,
                    "customer": customer,
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": price,
                    "discount": discount,
                    "revenue": price * quantity - discount,
                    "channel": channel,
                    "payment": payment,
                    "stream": stream,
                }
                customer["orders"].append(day)
                buyers.append(int(customer["id"][4:]) - 1)
                cancel = 0.05 if stream == "cod_campaign" else 0.025
                if rng.random() < cancel:
                    order["cancelled"] = True
                    orders.append(order)
                    continue
                stock[product_id] -= quantity
                route = CITIES[customer["city"]][1]
                courier, promise_days, _, _, risk = ROUTES[route]
                dispatch = next_working_day(day)
                promised = dispatch + timedelta(days=promise_days)
                late = LATE_BASE[risk]
                if within(dispatch, MONSOON):
                    late *= MONSOON_LATE[risk]
                if date(2025, 10, 10) <= day <= date(2025, 10, 19) or date(2025, 11, 9) <= day <= date(2025, 11, 15):
                    late *= 1.6
                if date(2026, 10, 1) <= day <= END:
                    late *= 1.6
                attempt = promised
                if rng.random() < min(0.6, late):
                    heavy = within(dispatch, MONSOON) and risk in {"hills", "pokhara", "farwest"}
                    attempt += timedelta(days=rng.randint(2, 6) if heavy else rng.randint(1, 3))
                while within(attempt, TIHAR_2025):
                    attempt += timedelta(days=1)
                refuse = 0.0
                if payment == "Cash on delivery":
                    refuse = 0.06 if channel in {"Marketplace", "Website"} else 0.09
                    if stream == "cod_campaign":
                        refuse = 0.72  # impulse and fake orders during the free-delivery offer
                    elif within(day, COD_CAMPAIGN):
                        refuse += 0.05
                order.update(route=route, courier=courier, dispatch=dispatch, promised=promised, attempt=attempt)
                order["fee"] = courier_fee(route, dispatch)
                if rng.random() < refuse:
                    order["refused"] = True
                    restock[attempt + timedelta(days=2)][product_id] += quantity
                elif rng.random() < {"Audio": 0.02, "Power banks": 0.018, "Wearables": 0.025}.get(
                    PRODUCT[product_id][2], 0.008
                ):
                    order["defect_return"] = attempt + timedelta(days=rng.randint(2, 7))
                orders.append(order)

        for product_id in weights:
            inventory.append((day, product_id, PRODUCT[product_id][5], stock[product_id]))
        for channel, (spend, reach, ctr) in ADS.items():
            boost = 1.0
            if date(2025, 10, 8) <= day <= date(2025, 10, 19) or date(2025, 11, 5) <= day <= date(2025, 11, 11):
                boost = 1.6
            if date(2026, 9, 25) <= day <= END:
                boost = 1.6  # Dashain campaign
            if within(day, COD_CAMPAIGN) and channel in {"Facebook & Instagram", "TikTok"}:
                boost = 1.4
            reach_boost = click_boost = boost
            if within(day, AD_BOOST) and channel in {"Facebook & Instagram", "TikTok"}:
                # The May boost buys reach, but clicks grow less and orders barely move.
                boost, reach_boost, click_boost = (
                    (2.3, 2.6, 1.9) if channel == "Facebook & Instagram" else (2.5, 2.8, 2.0)
                )
            normal_spend = spend * rng.uniform(0.92, 1.08)
            normal_reach = normal_spend * reach * rng.uniform(0.9, 1.1)
            clicks = normal_reach * ctr * click_boost * rng.uniform(0.9, 1.1)
            marketing.append(
                (day, channel, round(normal_spend * boost), round(normal_reach * reach_boost), round(clicks))
            )

    # Expenses are recorded when they are incurred; fixed costs accrue daily so every 28-day window is comparable.
    for day in days:
        expenses[day, "Rent (warehouse & office)"] += 85000 * 12 / 365
        expenses[day, "Salaries"] += 183000 * 12 / 365
        expenses[day, "Internet & utilities"] += 9000 * 12 / 365
        expenses[day, "Software subscriptions"] += 3500 * 12 / 365
    expenses[date(2026, 10, 5), "Festival allowance (Dashain)"] += 183000
    for order in orders:
        if order.get("cancelled"):
            continue
        expenses[order["dispatch"], "Packaging"] += 22 * order["quantity"]
        if order.get("refused"):
            expenses[order["attempt"], "Courier return fees"] += order["fee"] * 0.5
        else:
            if order["channel"] == "Marketplace":
                expenses[order["attempt"], "Marketplace commission"] += order["revenue"] * 0.12
            if order["payment"] in {"eSewa", "Khalti", "Fonepay QR", "Card"}:
                expenses[order["attempt"], "Payment gateway fees"] += order["revenue"] * 0.015
    return {
        "orders": orders,
        "customers": customers,
        "shipments": shipments,
        "inventory": inventory,
        "marketing": marketing,
        "expenses": expenses,
        "lost": lost,
    }


def status(order, end):
    """An order's status as known on `end`."""
    if order.get("cancelled"):
        return "cancelled"
    if order["dispatch"] > end:
        return "pending"
    if order["attempt"] > end:
        return "shipped"
    if order.get("refused"):
        return "returned"
    if "defect_return" in order and order["defect_return"] <= end:
        return "returned"
    return "delivered"


def table(header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode()


def export(history, end):
    """Orders placed up to `end`, exported ten days later once their deliveries have settled.

    SanketAI recognises revenue only for delivered orders, so an export taken on `end` itself would show a
    false drop from parcels still in transit. Stock, purchases, ads and expenses stop at `end`.
    """
    settled = end + timedelta(days=10)
    orders = [o for o in history["orders"] if o["date"] <= end]
    customers = [c for c in history["customers"] if c["orders"] and c["orders"][0] <= end]
    files = {}
    files["orders"] = table(
        [
            "id",
            "date",
            "customer_id",
            "product_id",
            "quantity",
            "revenue",
            "status",
            "channel",
            "payment_method",
            "unit_price",
            "discount",
        ],
        [
            [
                o["id"],
                o["date"],
                o["customer"]["id"],
                o["product_id"],
                o["quantity"],
                o["revenue"],
                status(o, settled),
                o["channel"],
                o["payment"],
                o["unit_price"],
                o["discount"],
            ]
            for o in orders
        ],
    )
    files["products"] = table(
        ["id", "name", "category", "price", "cost", "supplier_id", "warranty_months"],
        [[p[0], p[1], p[2], p[3], unit_cost(p[0], end), p[5], p[7]] for p in PRODUCTS],
    )
    files["customers"] = table(
        ["id", "segment", "location", "signup_date", "city", "province"],
        [
            [
                c["id"],
                "New" if (n := sum(d <= end for d in c["orders"])) == 1 else "Repeat" if n < 5 else "Loyal",
                f"{c['city']}, {CITIES[c['city']][0]} Province",
                min(c["created"], c["orders"][0]),
                c["city"],
                CITIES[c["city"]][0],
            ]
            for c in customers
        ],
    )
    files["deliveries"] = table(
        ["order_id", "promised_date", "delivered_date", "route", "courier", "fee", "city", "outcome"],
        [
            [
                o["id"],
                o["promised"],
                o["attempt"] if o["attempt"] <= settled else "",
                o["route"],
                o["courier"],
                o["fee"],
                o["customer"]["city"],
                "in transit" if o["attempt"] > settled else "refused at door" if o.get("refused") else "delivered",
            ]
            for o in orders
            if not o.get("cancelled") and o["dispatch"] <= settled
        ],
    )
    files["inventory"] = table(
        ["date", "product_id", "supplier_id", "stock"], [list(row) for row in history["inventory"] if row[0] <= end]
    )
    shipments = [s for s in history["shipments"] if s["ordered"] <= end]
    files["suppliers"] = table(
        ["id", "name", "product_id", "promised_date", "received_date", "po_number", "ordered_date", "quantity"],
        [
            [
                s["supplier_id"],
                SUPPLIERS[s["supplier_id"]][0],
                s["product_id"],
                s["promised"],
                s["received"] if s["received"] <= end else "",
                s["po_number"],
                s["ordered"],
                s["quantity"],
            ]
            for s in shipments
        ],
    )
    files["purchases"] = table(
        ["date", "supplier_id", "product_id", "quantity", "unit_cost", "po_number"],
        [
            [s["received"], s["supplier_id"], s["product_id"], s["quantity"], s["unit_cost"], s["po_number"]]
            for s in shipments
            if s["received"] <= end
        ],
    )
    files["marketing"] = table(
        ["date", "channel", "spend", "impressions", "clicks"],
        [list(row) for row in history["marketing"] if row[0] <= end],
    )
    files["expenses"] = table(
        ["date", "category", "amount"],
        [
            [day, category, round(amount, 2)]
            for (day, category), amount in sorted(history["expenses"].items())
            if day <= end
        ],
    )
    return files


SYNTHETIC = (
    "\n\n_Synthetic demo document. HimalayanMart Gadgets and every company and person named here are fictional._"
)
DOCUMENTS = [
    (
        date(2025, 10, 1),
        "company_profile.md",
        """# HimalayanMart Gadgets · company profile
HimalayanMart Gadgets is a small online seller of mobile and electronics accessories, run from a warehouse in Kathmandu with six staff. It sells earbuds, neckbands, speakers, power banks, chargers, cables, phone cases, screen guards, smartwatches and small accessories.

Sales channels: an online marketplace store (about half of orders), our own website, Facebook & Instagram messages, and TikTok. About two thirds of customers pay cash on delivery; the rest pay with eSewa, Khalti, Fonepay QR or card.

Couriers: Peakline Parcel delivers in the Kathmandu valley, Pokhara and Chitwan & Makwanpur. Riverbend Couriers covers Koshi, Ilam and Madhesh. Westline Logistics covers Lumbini, Palpa, the Far west and Karnali.

Suppliers: Everest Tech Traders (earbuds, neckbands, speakers and smartwatches, imported through Birgunj), Himal Power Solutions (power banks and chargers), Bagmati Accessories Wholesale (cables, cases, screen guards, wired earphones) and Birgunj Import House (holders, tripods, ring lights, memory cards).

Policies: 7-day returns for defects, warranty 3 to 12 months by product, festival allowance of one month's salary paid before Dashain.""",
    ),
    (
        date(2025, 11, 14),
        "11_11_sale_recap.md",
        """# 11.11 sale recap · 14 November 2025
11 November was our biggest day of the year so far, with about three and a half times a normal day's orders. Audio, power banks and chargers carried a 10% discount from 9 to 13 November. Deliveries outside the valley ran one to two days late during the rush. No stock ran out.""",
    ),
    (
        date(2025, 12, 22),
        "marketing_plan_free_delivery.md",
        """# Marketing plan · free delivery on cash-on-delivery orders
From 28 December 2025 to 24 January 2026 we will offer free delivery on every cash-on-delivery order placed through Facebook & Instagram and TikTok, to win new customers in the winter lull. Ad spend on those two channels rises by about 40% during the offer. Goal: more first-time buyers outside the Kathmandu valley.""",
    ),
    (
        date(2026, 1, 20),
        "operations_note_refused_parcels.md",
        """# Operations note · refused parcels · 20 January 2026
Since the free-delivery offer started, many more cash-on-delivery parcels are refused at the door or the customer does not answer the courier's calls. Several orders used fake names or numbers. Peakline Parcel, Riverbend Couriers and Westline Logistics charge a return fee of half the delivery fee for every refused parcel, and the stock comes back two days later. The warehouse team asks whether first-time cash-on-delivery orders should be confirmed by phone before dispatch.""",
    ),
    (
        date(2026, 2, 12),
        "peakline_parcel_rate_notice.md",
        """# Peakline Parcel rate notice · 12 February 2026
From 1 March 2026, Peakline Parcel will charge NPR 140 per parcel inside the Kathmandu valley (up from NPR 100), NPR 190 for Pokhara (up from NPR 150) and NPR 175 for Chitwan & Makwanpur (up from NPR 140). The notice cites higher fuel, vehicle and staff costs. Riverbend Couriers and Westline Logistics have not announced changes.""",
    ),
    (
        date(2026, 2, 18),
        "everest_tech_price_letter.md",
        """# Everest Tech Traders price letter · 18 February 2026
Everest Tech Traders will raise wholesale prices by 10% on earbuds, neckbands, speakers and smartwatches for all stock delivered from 1 March 2026. The letter cites a weaker rupee against the US dollar and a revised customs valuation on imported electronics.""",
    ),
    (
        date(2026, 3, 25),
        "finance_note_march.md",
        """# Finance note · 25 March 2026
Sales in March are well ahead of February, but the margin looks thinner. The owner suspects the HOLI5 discount code is eating into profit. Courier invoices and supplier invoices for March have not yet been reconciled against the order data.""",
    ),
    (
        date(2026, 4, 28),
        "social_ads_plan.md",
        """# Social media ads plan · May 2026
Our agency will boost Facebook & Instagram and TikTok ads from 3 to 30 May 2026, roughly doubling daily spend, to grow reach among students and young professionals. Marketplace and Google search ads stay the same.""",
    ),
    (
        date(2026, 5, 24),
        "agency_weekly_report.md",
        """# Agency weekly report · 24 May 2026
Reach is up more than 150% and link clicks have almost doubled since the boost started. The agency calls the campaign a success and recommends keeping the higher budget through June. The report does not include orders or revenue.""",
    ),
    (
        date(2026, 6, 10),
        "peakline_monsoon_advisory.md",
        """# Peakline Parcel monsoon advisory · 10 June 2026
With the monsoon arriving, landslides and flooded roads are expected on highway routes. Deliveries to Pokhara may take two to four extra days. Our partner couriers report the same risk for the hill and far-western routes (Ilam, Palpa, Karnali and the Far west). Kathmandu valley deliveries should be largely unaffected.""",
    ),
    (
        date(2026, 7, 6),
        "customer_complaints_june.md",
        """# Customer complaints log · June to early July 2026
- 18 Jun, Pokhara: "Order came 5 days late, I had already bought a charger from a local shop."
- 21 Jun, Ilam: "Saman ekdam dhilo aayo, courier le phone pani uthaudaina." (The parcel came very late and the courier does not answer the phone.)
- 24 Jun, Dhangadhi: "Promised 5 days, took 10. Please give a correct delivery date."
- 27 Jun, Kathmandu: "Earbuds arrived on time, good packing."
- 30 Jun, Birendranagar: "Delivery late again. Last time also late."
- 2 Jul, Pokhara: "Road blocked by landslide they said, but no update for three days."
- 5 Jul, Tansen: "Dherai dhilo bhayo, arko choti order gardina hola." (It was very late, I may not order next time.)""",
    ),
    (
        date(2026, 9, 15),
        "dashain_purchase_plan.md",
        """# Dashain purchase plan · 15 September 2026
To get better prices for Dashain we placed one large import order with Everest Tech Traders on 14 September for all earbuds, neckbands, speakers and smartwatches, instead of the usual weekly orders. Promised delivery: 28 September 2026. Weekly orders from Everest Tech Traders are paused until it arrives. Other suppliers continue weekly.""",
    ),
    (
        date(2026, 10, 3),
        "everest_tech_customs_delay.md",
        """# Email from Everest Tech Traders · 3 October 2026
Your Dashain shipment of earbuds, neckbands, speakers and smartwatches is held at Birgunj customs for document verification and revaluation. We expect clearance around 13 October and delivery to your warehouse by 15 October. We have no other stock of these models in Kathmandu before then. Sorry for the delay.""",
    ),
    (
        date(2026, 10, 9),
        "customer_complaints_dashain.md",
        """# Customer messages · Dashain 2026
- 29 Sep: "TWS earbuds out of stock again? I wanted them as a Dashain gift."
- 2 Oct: "Kahile aauchha neckband? Dashain aghi chahiyeko thiyo." (When will the neckband be back? I needed it before Dashain.)
- 4 Oct: "Smartwatch shows sold out on the marketplace."
- 6 Oct: "Ordered a power bank instead because earbuds were not available."
- 8 Oct: "Fast delivery for the charger, thank you." """,
    ),
    (
        date(2026, 10, 12),
        "dashain_campaign_update.md",
        """# Dashain campaign update · 12 October 2026
Since 25 September our Dashain ads have run about 60% above normal spend on every channel. Impressions and clicks are up by a similar amount, and the DASHAIN5 code has been used on about half of orders. Traffic is strong; the team says the drop in sales comes from products that are sold out, not from fewer visitors.""",
    ),
    (
        date(2026, 10, 14),
        "finance_note_dashain.md",
        """# Finance note · 14 October 2026
The Dashain festival allowance of one month's salary (NPR 183,000) was paid to all staff on 5 October.""",
    ),
]


def documents(end):
    return {name: (f"{day.isoformat()}_{name}", text + SYNTHETIC) for day, name, text in DOCUMENTS if day <= end}


def generate(seed=SEED):
    history = simulate(seed)
    packs = {}
    for pack in PACKS:
        files = {f"hmg_{pack['end']}_{kind}.csv": data for kind, data in export(history, pack["end"]).items()}
        packs[pack["slug"]] = {"csv": files, "documents": {f: t.encode() for f, t in documents(pack["end"]).values()}}
    return history, packs
