import json
import time
import urllib.request
import urllib.parse

from .config import get_currency_info

STEAM_STORE_API = "https://store.steampowered.com/api/appdetails"
STEAM_SEARCH_API = "https://store.steampowered.com/api/storesearch"
STEAM_FEATURED_API = "https://store.steampowered.com/api/featuredcategories"
STEAM_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"

def fetch_json(url, retries=4, delay=2):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[ERROR] fetch attempt {i+1}/{retries} for {url}: {e}")
            if i < retries - 1:
                time.sleep(delay)
    return None

def search_game_by_name(name, cc="US"):
    params = urllib.parse.urlencode({"term": name, "l": "english", "cc": cc})
    url = f"{STEAM_SEARCH_API}?{params}"
    data = fetch_json(url)
    if not data or "items" not in data:
        return []
    return [{"appid": str(item["id"]), "name": item["name"]} for item in data["items"]]

def get_game_details(appid, cc="US"):
    params = urllib.parse.urlencode({"appids": appid, "cc": cc, "l": "english"})
    url = f"{STEAM_STORE_API}?{params}"
    data = fetch_json(url)
    if not data or appid not in data:
        return None
    app_data = data[appid]
    if not app_data.get("success"):
        return None
    return app_data["data"]

def fetch_featured_games(cc="US"):
    url = f"{STEAM_FEATURED_API}?cc={cc}&l=english"
    data = fetch_json(url)
    if not data:
        return []
    specials = data.get("specials", {})
    items = specials.get("items", []) if isinstance(specials, dict) else specials if isinstance(specials, list) else []
    results = []
    for item in items[:8]:
        appid = str(item.get("id", ""))
        if not appid:
            continue
        name = item.get("name", "Unknown")
        discount = item.get("discount", 0)
        if isinstance(discount, str):
            try: discount = int(discount)
            except: discount = 0
        final_price = item.get("final_price", 0)
        if isinstance(final_price, str):
            try: final_price = int(final_price)
            except: final_price = 0
        final_price = final_price / 100
        original_price = item.get("original_price", final_price * 100)
        if isinstance(original_price, str):
            try: original_price = int(original_price)
            except: original_price = int(final_price * 100)
        original_price = original_price / 100
        header_image = item.get("header_image", f"{STEAM_CDN}/{appid}/header.jpg")
        results.append({
            "appid": appid, "name": name, "discount": discount,
            "final_price": final_price, "original_price": original_price,
            "header_image": header_image
        })
    return results

def get_editions(appid, cc="US"):
    details = get_game_details(appid, cc)
    if not details:
        return [], None, None
    game_name = details.get("name", "Unknown")
    app_type = details.get("type", "game")
    editions = []
    if details.get("is_free"):
        editions.append({"name": "Free to Play", "packageid": None, "price_final": 0, "price_original": 0, "discount_pct": 0, "is_free": True})
        return editions, game_name, app_type

    price_overview = details.get("price_overview", {})
    reliable_discount = 0
    if price_overview:
        reliable_discount = price_overview.get("discount_percent", 0)
        if isinstance(reliable_discount, str):
            try: reliable_discount = int(reliable_discount)
            except: reliable_discount = 0

    package_groups = details.get("package_groups", [])
    if not package_groups:
        if price_overview:
            editions.append({
                "name": "Standard Edition", "packageid": None,
                "price_final": price_overview.get("final", 0) / 100,
                "price_original": price_overview.get("initial", 0) / 100,
                "discount_pct": reliable_discount, "is_free": False
            })
        else:
            editions.append({"name": "Standard Edition", "packageid": None, "price_final": 0, "price_original": 0, "discount_pct": 0, "is_free": False})
        return editions, game_name, app_type

    for group in package_groups:
        for sub in group.get("subs", []):
            edition_name = sub.get("option_text", sub.get("name", "Standard Edition"))
            if " - " in edition_name:
                edition_name = edition_name.rsplit(" - ", 1)[0]
            if edition_name.lower().startswith("buy "):
                edition_name = edition_name[4:].strip()
            if edition_name.strip().lower() == game_name.strip().lower():
                edition_name = "Standard Edition"

            price_final = sub.get("price_in_cents_with_discount", 0)
            if isinstance(price_final, str):
                try: price_final = int(price_final)
                except: price_final = 0
            price_final = price_final / 100

            discount_pct = reliable_discount
            if discount_pct == 0:
                discount_pct = sub.get("percent_savings", 0)
                if isinstance(discount_pct, str):
                    try: discount_pct = int(discount_pct)
                    except: discount_pct = 0

            if discount_pct > 0 and price_final > 0:
                price_original = round(price_final / (1 - discount_pct / 100), 2)
            else:
                price_original = price_final

            editions.append({
                "name": edition_name, "packageid": str(sub.get("packageid", "")),
                "price_final": price_final, "price_original": price_original,
                "discount_pct": discount_pct, "is_free": False
            })

    seen = set()
    unique_editions = []
    for ed in editions:
        if ed["name"] not in seen:
            seen.add(ed["name"])
            unique_editions.append(ed)
    return unique_editions, game_name, app_type

def fetch_price_for_game(appid, edition_name, cc):
    details = get_game_details(appid, cc)
    if not details:
        return None

    game_name = details.get("name", "Unknown")
    currency, symbol = get_currency_info(cc)

    if details.get("is_free"):
        return {"is_free": True, "on_sale": False, "discount_pct": 0,
                "price_final": 0, "price_original": 0,
                "symbol": symbol, "currency": currency, "game_name": game_name}

    price_overview = details.get("price_overview")
    if price_overview:
        discount = price_overview.get("discount_percent", 0)
        if isinstance(discount, str):
            try: discount = int(discount)
            except: discount = 0
        final = price_overview.get("final", 0)
        if isinstance(final, str):
            try: final = int(final)
            except: final = 0
        initial = price_overview.get("initial", 0)
        if isinstance(initial, str):
            try: initial = int(initial)
            except: initial = 0

        if edition_name.lower() == "standard edition":
            return {"is_free": False, "on_sale": discount > 0,
                    "discount_pct": discount,
                    "price_final": final / 100,
                    "price_original": initial / 100,
                    "symbol": symbol, "currency": currency,
                    "game_name": game_name}

        package_groups = details.get("package_groups", [])
        for group in package_groups:
            for sub in group.get("subs", []):
                ed_name = sub.get("option_text", sub.get("name", "Standard Edition"))
                if " - " in ed_name:
                    ed_name = ed_name.rsplit(" - ", 1)[0]
                if ed_name.lower().startswith("buy "):
                    ed_name = ed_name[4:].strip()
                if ed_name.strip().lower() == game_name.strip().lower():
                    ed_name = "Standard Edition"

                if ed_name.lower() == edition_name.lower():
                    sub_price = sub.get("price_in_cents_with_discount", 0)
                    if isinstance(sub_price, str):
                        try: sub_price = int(sub_price)
                        except: sub_price = 0
                    sub_price = sub_price / 100

                    if discount > 0 and sub_price > 0:
                        sub_original = round(sub_price / (1 - discount / 100), 2)
                    else:
                        sub_original = sub_price

                    return {"is_free": False, "on_sale": discount > 0,
                            "discount_pct": discount,
                            "price_final": sub_price,
                            "price_original": sub_original,
                            "symbol": symbol, "currency": currency,
                            "game_name": game_name}

        return {"is_free": False, "on_sale": discount > 0,
                "discount_pct": discount,
                "price_final": final / 100,
                "price_original": initial / 100,
                "symbol": symbol, "currency": currency,
                "game_name": game_name}

    package_groups = details.get("package_groups", [])
    for group in package_groups:
        for sub in group.get("subs", []):
            ed_name = sub.get("option_text", sub.get("name", "Standard Edition"))
            if " - " in ed_name:
                ed_name = ed_name.rsplit(" - ", 1)[0]
            if ed_name.lower().startswith("buy "):
                ed_name = ed_name[4:].strip()
            if ed_name.strip().lower() == game_name.strip().lower():
                ed_name = "Standard Edition"

            if ed_name.lower() == edition_name.lower() or edition_name.lower() == "standard edition":
                discount = sub.get("percent_savings", 0)
                if isinstance(discount, str):
                    try: discount = int(discount)
                    except: discount = 0
                price_final = sub.get("price_in_cents_with_discount", 0)
                if isinstance(price_final, str):
                    try: price_final = int(price_final)
                    except: price_final = 0
                price_final = price_final / 100
                if discount > 0 and price_final > 0:
                    price_original = round(price_final / (1 - discount / 100), 2)
                else:
                    price_original = price_final
                return {"is_free": False, "on_sale": discount > 0,
                        "discount_pct": discount,
                        "price_final": price_final,
                        "price_original": price_original,
                        "symbol": symbol, "currency": currency,
                        "game_name": game_name}

    return None