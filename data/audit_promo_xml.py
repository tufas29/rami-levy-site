"""
Audits a Rami Levy PromoFull XML file against the exact same filtering logic
used in the React app, and reports:
  - total <PromotionItem> elements found in the file
  - how many were excluded because their promotion is a coupon
  - how many were overwritten because the same ItemCode appears in more
    than one promotion (expected/intentional - "keep newest" wins)
  - the final count that should appear in the app
  - a list of any promotion descriptions containing "קופון" (to sanity-check
    the coupon-detection heuristic isn't too broad or too narrow)

Usage:
    python audit_promo_xml.py /path/to/PromoFull*.xml
"""

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


def audit(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    total_items_in_file = 0
    items_excluded_coupon = 0
    coupon_descriptions = set()
    item_to_latest = {}  # itemCode -> (updateTime, promotionDescription)
    duplicate_item_count = 0  # any repeat encounter of an item code, regardless of which timestamp wins

    promotions = root.findall(".//Promotion")

    for promo in promotions:
        desc_el = promo.find("PromotionDescription")
        description = desc_el.text.strip() if desc_el is not None and desc_el.text else "(no description)"

        coupon_el = promo.find("AdditionalIsCoupon")
        is_coupon_flag = coupon_el is not None and coupon_el.text == "1"
        is_coupon_word = "קופון" in description
        is_coupon = is_coupon_flag or is_coupon_word

        update_el = promo.find("PromotionUpdateTime")
        update_time = update_el.text.strip() if update_el is not None and update_el.text else ""

        items = promo.findall("./Groups/Group/PromotionItems/PromotionItem")
        total_items_in_file += len(items)

        if is_coupon:
            items_excluded_coupon += len(items)
            coupon_descriptions.add(description)
            continue

        for item in items:
            code_el = item.find("ItemCode")
            if code_el is None or not code_el.text:
                continue
            item_code = code_el.text.strip()

            existing = item_to_latest.get(item_code)
            if existing is not None:
                duplicate_item_count += 1
                if existing[0] >= update_time:
                    continue  # keep the existing (newer-or-equal) entry
            item_to_latest[item_code] = (update_time, description)

    final_count = len(item_to_latest)

    print(f"File: {xml_path}")
    print(f"Total <Promotion> blocks:            {len(promotions)}")
    print(f"Total <PromotionItem> elements:      {total_items_in_file}")
    print(f"Excluded as coupons:                  -{items_excluded_coupon}")
    print(f"Duplicate item-code encounters:       -{duplicate_item_count} (expected/intentional - same item in multiple promotions)")
    print(f"Final unique items the app should show: {final_count}")
    print()
    computed = total_items_in_file - items_excluded_coupon - duplicate_item_count
    match = "✓ MATCH" if computed == final_count else "✗ MISMATCH - investigate!"
    print(f"Sanity check: {total_items_in_file} - {items_excluded_coupon} - {duplicate_item_count} = {computed} "
          f"(should equal final count {final_count}) -> {match}")
    print()

    if coupon_descriptions:
        print(f"--- {len(coupon_descriptions)} unique promotion description(s) flagged as coupons ---")
        for d in sorted(coupon_descriptions):
            print(f"  - {d}")
    else:
        print("No promotions were flagged as coupons.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python audit_promo_xml.py /path/to/PromoFull*.xml")
        sys.exit(1)
    audit(sys.argv[1])
