"""Build the HimalayanMart Gadgets (Nepal) dataset zip, validated with SanketAI's own upload checks.

Usage: python scripts/export_gadgets.py [--out ~/Downloads/HimalayanMart_Gadgets_Nepal_dataset.zip]
"""

import argparse
import os
import sys
import zipfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
os.environ["SANKET_AGENT_MODE"] = (
    "deterministic"  # the answer key records the model-free result
)
os.environ["SANKET_LLM_PROVIDER"] = "ollama"

from app import agent, gadgets
from app.ingestion import parse_upload

FOLDER = "HimalayanMart_Gadgets_Nepal"
CAUSES = {
    "1_cod_refusals": "A free-delivery offer on cash-on-delivery orders (28 Dec – 24 Jan) brought many impulse and fake orders. A third of cash-on-delivery parcels were refused at the door, so orders rose while delivered sales fell, and courier return fees jumped.",
    "2_margin_squeeze": "From 1 March, Peakline Parcel raised its rates and Everest Tech Traders raised wholesale prices by 10%. Sales grew, but those two cost increases cut the contribution margin. The HOLI5 discount the finance note blames is a decoy.",
    "3_ad_campaign": "The agency more than doubled Facebook & Instagram and TikTok spend in May. Reach and clicks rose, but orders barely moved, so the extra spend did not pay for itself.",
    "4_monsoon_delays": "The monsoon slowed hill and far-western routes (Ilam, Karnali, Far west, Palpa, Pokhara); the Kathmandu valley stayed on time.",
    "5_dashain_stockout": "The consolidated Dashain shipment from Everest Tech Traders was held at Birgunj customs for 17 days, so earbuds, neckbands, speakers and smartwatches ran out during the festival rush. Demand was strong (ads and traffic were up).",
}


def windows(end):
    start = end - timedelta(days=27)
    return (start - timedelta(days=28), start - timedelta(days=1)), (start, end)


def placed(history, window):
    return [o for o in history["orders"] if window[0] <= o["date"] <= window[1]]


def expense(history, window, category):
    return sum(
        v
        for (d, c), v in history["expenses"].items()
        if c == category and window[0] <= d <= window[1]
    )


def ads(history, window, channels, field):
    index = {"spend": 2, "impressions": 3, "clicks": 4}[field]
    return sum(
        r[index]
        for r in history["marketing"]
        if r[1] in channels and window[0] <= r[0] <= window[1]
    )


def pct(new, old):
    return f"{(new - old) / old * 100:+.1f}%" if old else "n/a"


def npr(value):
    return f"NPR {value:,.0f}"


def facts(slug, history, end, report):
    prev, cur = windows(end)
    metric = {m["key"]: m for m in report["metrics"]}
    revenue = metric["revenue"]
    lines = [
        f"**Planted cause:** {CAUSES[slug]}\n",
        f"- Comparison: latest 28 days **{cur[0]} → {cur[1]}** against **{prev[0]} → {prev[1]}**.",
        f"- Delivered revenue: {npr(revenue['previous'])} → {npr(revenue['current'])} ({pct(revenue['current'], revenue['previous'])}).",
    ]
    if slug == "1_cod_refusals":
        before, after = placed(history, prev), placed(history, cur)

        def refused(orders):
            cod = [
                o
                for o in orders
                if o["payment"] == "Cash on delivery" and not o.get("cancelled")
            ]
            return sum(1 for o in cod if o.get("refused")) / len(cod)

        campaign = [
            o for o in after if o["stream"] == "cod_campaign" and not o.get("cancelled")
        ]
        lines += [
            f"- Orders placed (all statuses): {len(before):,} → {len(after):,} ({pct(len(after), len(before))}).",
            f"- Cash-on-delivery parcels refused at the door: {refused(before):.1%} → {refused(after):.1%}.",
            f"- Free-delivery campaign orders: {len(campaign):,}, of which {sum(1 for o in campaign if o.get('refused')) / len(campaign):.0%} were refused.",
            f"- Courier return fees: {npr(expense(history, prev, 'Courier return fees'))} → {npr(expense(history, cur, 'Courier return fees'))}.",
        ]
    elif slug == "2_margin_squeeze":
        contribution = metric["contribution"]
        lines += [
            f"- Contribution estimate: {npr(contribution['previous'])} → {npr(contribution['current'])} ({pct(contribution['current'], contribution['previous'])}).",
            "- Peakline Parcel rate card from 1 Mar 2026: Kathmandu valley NPR 100 → 140, Pokhara 150 → 190, Chitwan & Makwanpur 140 → 175.",
            "- Everest Tech Traders: +10% unit cost on earbuds, neckbands, speakers and wearables received from 1 Mar 2026.",
            "- The finance note blames the HOLI5 discount code; it was used on about 3% of orders on 1–5 March only, so it is a decoy.",
        ]
    elif slug == "3_ad_campaign":
        social = {"Facebook & Instagram", "TikTok"}
        spend = ads(history, prev, social, "spend"), ads(history, cur, social, "spend")
        delivered = [
            o
            for o in placed(history, cur)
            if not o.get("cancelled") and not o.get("refused")
        ]
        cost = sum(
            gadgets.unit_cost(o["product_id"], o["date"]) * o["quantity"]
            for o in delivered
        )
        margin = 1 - cost / sum(o["revenue"] for o in delivered)
        per_rupee = (revenue["current"] - revenue["previous"]) / (spend[1] - spend[0])
        lines += [
            f"- Facebook & Instagram plus TikTok spend: {npr(spend[0])} → {npr(spend[1])} ({pct(spend[1], spend[0])}).",
            f"- Their impressions {pct(ads(history, cur, social, 'impressions'), ads(history, prev, social, 'impressions'))}, clicks {pct(ads(history, cur, social, 'clicks'), ads(history, prev, social, 'clicks'))}.",
            f"- Orders placed: {len(placed(history, prev)):,} → {len(placed(history, cur)):,}. Each extra rupee of social ad spend brought about NPR {per_rupee:.2f} of extra delivered revenue; at the {margin:.0%} gross margin that is NPR {per_rupee * margin:.2f} of gross profit, so the boost lost money.",
            "- The agency report only counts reach and clicks; it never mentions orders.",
        ]
    elif slug == "4_monsoon_delays":

        def late_by_route(window):
            totals = {}
            for o in placed(history, window):
                if o.get("cancelled"):
                    continue
                done, late = totals.get(o["route"], (0, 0))
                totals[o["route"]] = (done + 1, late + (o["attempt"] > o["promised"]))
            return totals

        before, after = late_by_route(prev), late_by_route(cur)
        rows = sorted(after, key=lambda r: -after[r][1] / after[r][0])
        late_rate = metric["late_rate"]
        lines.append(
            f"- Late delivery rate: {late_rate['previous']}% → {late_rate['current']}%."
        )
        lines.append(
            "- Revenue is also lower: monsoon demand is about 5% softer and the May ad boost ended. The planted problem is the delivery delay."
        )
        lines.append("- Late share by route (previous → latest):")
        lines += [
            f"  - {route}: {before[route][1] / before[route][0]:.0%} → {after[route][1] / after[route][0]:.0%}"
            for route in rows
            if route in before
        ]
    elif slug == "5_dashain_stockout":
        stockouts = {}
        for day, product_id, _, stock in history["inventory"]:
            if stock <= 0 and cur[0] <= day <= cur[1]:
                stockouts[product_id] = stockouts.get(product_id, 0) + 1
        lost_units = sum(
            n
            for p, days in history["lost"].items()
            for d, n in days.items()
            if cur[0] <= d <= cur[1]
        )
        lost_value = sum(
            n * gadgets.PRODUCT[p][3]
            for p, days in history["lost"].items()
            for d, n in days.items()
            if cur[0] <= d <= cur[1]
        )
        lines += [
            "- Everest Tech Traders' Dashain import shipment was promised 28 Sep 2026 and received 15 Oct 2026 (17 days late, held at Birgunj customs).",
            "- Stockout days in the latest window: "
            + ", ".join(
                f"{gadgets.PRODUCT[p][1]} {n}"
                for p, n in sorted(stockouts.items(), key=lambda i: -i[1])
            ),
            f"- Hidden truth SanketAI cannot see: about {lost_units:,} units ({npr(lost_value)} at list price) of demand went unserved.",
            "- Ad traffic was up about 60% (Dashain campaign), which rules out falling demand.",
        ]
    return lines


def readme(history):
    daily = {}
    for o in history["orders"]:
        daily[o["date"]] = daily.get(o["date"], 0) + 1
    rows = "\n".join(
        f"| `{p['slug']}_{p['end']}` | {p['title']} | {p['end'] - timedelta(days=27)} → {p['end']} | “{p['question']}” |"
        for p in gadgets.PACKS
    )
    return f"""# HimalayanMart Gadgets · synthetic Nepal e-commerce dataset

A realistic, **fully synthetic** dataset for SanketAI: one year of a fictional mobile-accessories seller in Nepal that sells through an online marketplace, its own website, Facebook & Instagram and TikTok. Every business, courier, supplier and customer is fictional. Festival dates follow the real 2025–26 Nepali calendar.

## The business
- **HimalayanMart Gadgets**, Kathmandu warehouse, six staff, 29 products in seven sub-categories: Audio, Power banks, Chargers, Cables, Cases & protection, Wearables, Accessories.
- {len(history["orders"]):,} orders from 1 Oct 2025 to 16 Oct 2026 ({min(daily.values())} to {max(daily.values())} a day; the peak is the 11.11 sale), {len(history["customers"]):,} customers in all seven provinces.
- Payments: about two thirds cash on delivery, the rest eSewa, Khalti, Fonepay QR and card.
- Couriers (fictional): Peakline Parcel (Kathmandu valley, Pokhara, Chitwan & Makwanpur), Riverbend Couriers (Koshi, Ilam, Madhesh), Westline Logistics (Lumbini, Palpa, Far west, Karnali).
- Suppliers (fictional): Everest Tech Traders (audio and wearables, imported through Birgunj), Himal Power Solutions, Bagmati Accessories Wholesale, Birgunj Import House.
- Seasonality: Tihar 2025 (Laxmi Puja 20 Oct, Bhai Tika 23 Oct), the 11.11 sale, the winter lull, Holi (2–3 Mar 2026), Nepali New Year 2083 (14 Apr 2026), the monsoon (mid-June to late September, slower hill routes), Teej (14 Sep 2026) and the Dashain 2026 rush (Ghatasthapana 11 Oct).

## Five scenario packs
SanketAI compares the latest 28 days with the 28 days before. Each folder is the same business history exported on a different date, so that comparison lands on one planted problem. The answers are in `ANSWER_KEY.md`; read it after you have investigated.

| Folder | Story | Latest 28 days | Question to ask |
| --- | --- | --- | --- |
{rows}

Packs 2 and 5 are fully explained by SanketAI's deterministic engine. Packs 1, 3 and 4 need the AI planner (`SANKET_AGENT_MODE=auto` with Ollama or a hosted model); the deterministic engine reports the measured change and says it cannot isolate a cause, by design.

## Loading a pack into SanketAI
1. Workspace & audit → **Reset workspace** (or start with an empty workspace).
2. Data sources → **Upload evidence** for each CSV in the pack's `datasets/` folder, choosing the type that matches the file name (orders, products, inventory, suppliers, deliveries, marketing, customers, expenses, purchases).
3. Upload every file in `documents/` as a **Business document**.
4. Ask the pack's question on the Overview page.

To try outcome monitoring, approve the recommended action in a pack, then upload the next pack's CSVs as new versions and select **Check outcome**.

## Files and columns
Columns in **bold** are required by SanketAI. The others are kept for realism and are ignored by the current version.

- `orders.csv`: **id, date, customer_id, product_id, quantity, revenue, status**, channel, payment_method, unit_price, discount. One product per order line; revenue = unit_price × quantity − discount, in NPR including VAT. Status: delivered, returned (refused at the door, or a defect return within 7 days), cancelled, shipped or pending.
- `products.csv`: **id, name, category, price, cost**, supplier_id, warranty_months. `cost` is the current wholesale cost on the export date.
- `inventory.csv`: **date, product_id, supplier_id, stock**. End-of-day stock for every product.
- `suppliers.csv`: **id, name, product_id, promised_date, received_date**, po_number, ordered_date, quantity. One row per purchase-order line; blank received_date means not yet received.
- `purchases.csv`: **date, supplier_id, product_id, quantity, unit_cost**, po_number. Stock received and what it cost (drives cost of goods).
- `deliveries.csv`: **order_id, promised_date, delivered_date, route**, courier, fee, city, outcome. `delivered_date` is the delivery attempt; for refused cash-on-delivery parcels the order status is returned. `fee` is the outbound courier fee.
- `marketing.csv`: **date, channel, spend, impressions, clicks** for Facebook & Instagram, TikTok, Marketplace sponsored and Google search.
- `customers.csv`: **id, segment, location, signup_date**, city, province. Segment: New (1 order), Repeat (2–4), Loyal (5+).
- `expenses.csv`: **date, category, amount**. Rent, salaries, utilities and software accrue daily; packaging, marketplace commission (12%), payment gateway fees (1.5%), courier return fees and the Dashain festival allowance are recorded when incurred. Ad spend lives only in marketing.csv and courier fees only in deliveries.csv, so nothing is counted twice.
- `documents/`: dated notices, letters, emails, plans and complaint logs (some in Romanized Nepali), only those written on or before the pack's end date.

## How the data was made
`backend/app/gadgets.py` simulates every day: demand by festival and weekday, stock and weekly replenishment, supplier lead times and delays, courier promises, monsoon and festival delays, cash-on-delivery refusals, returns, discounts, ads and costs. Stockouts and delays emerge from that simulation rather than being typed in. Each pack lists orders placed up to its end date with delivery outcomes as of ten days later, once parcels have settled. Re-create the zip with `python scripts/export_gadgets.py`; the same seed gives the same files. Every CSV and document in this zip passed SanketAI's upload validation when it was built.

_Synthetic data for testing and demonstration only. It is not real data from any marketplace, courier, payment provider or person._
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path.home() / "Downloads" / f"{FOLDER}_dataset.zip"
    )
    args = parser.parse_args()
    history, packs = gadgets.generate()
    key = [
        "# Answer key · HimalayanMart Gadgets\n",
        "What was planted in each pack, the numbers behind it, and what SanketAI's deterministic engine concluded when this zip was built. Investigate first, then compare.\n",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as archive:
        for pack in gadgets.PACKS:
            folder = f"{FOLDER}/{pack['slug']}_{pack['end']}"
            files, sources = packs[pack["slug"]], []
            for name, data in files["csv"].items():
                kind = name.rsplit("_", 1)[1].removesuffix(".csv")
                content, _ = parse_upload(
                    data, name, kind
                )  # raises if SanketAI would reject the file
                sources.append(
                    SimpleNamespace(id=name, name=name, kind=kind, content=content)
                )
                archive.writestr(f"{folder}/datasets/{name}", data)
            for name, data in files["documents"].items():
                content, _ = parse_upload(data, name, "document")
                sources.append(
                    SimpleNamespace(
                        id=name, name=name, kind="document", content=content
                    )
                )
                archive.writestr(f"{folder}/documents/{name}", data)
            report = agent.investigate(
                sources, pack["question"], "question", lambda *_: None
            )
            key += [
                f"\n## {pack['slug']} · {pack['title']}\n",
                f"Question: “{pack['question']}”\n",
                *facts(pack["slug"], history, pack["end"], report),
                "",
                f"**SanketAI deterministic result** ({report['scenario']} scenario, {report['confidence']} confidence):",
                f"> {report['root_cause']}",
                "",
                *[
                    f"- {h['id']} {h['status']}: {h['claim']}"
                    for h in report["hypotheses"]
                ],
                "",
            ]
            print(
                f"{pack['slug']}: {len(files['csv'])} datasets, {len(files['documents'])} documents · {report['confidence']} · {report['root_cause'][:90]}…"
            )
        archive.writestr(f"{FOLDER}/README.md", readme(history))
        archive.writestr(f"{FOLDER}/ANSWER_KEY.md", "\n".join(key))
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
