import json
import re
import concurrent.futures
import time
import urllib.parse
import urllib.request
import urllib.error


def normalize_wishlist_profile(value):
    value = value.strip()
    if re.fullmatch(r"\d{17}", value):
        return f"profiles/{value}"
    if re.fullmatch(r"[A-Za-z0-9_-]+", value):
        return f"id/{value}"

    candidate = value if "://" in value else f"https://{value}"
    parsed = urllib.parse.urlparse(candidate)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host and host not in {"steamcommunity.com", "store.steampowered.com"}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "profiles" and re.fullmatch(r"\d{17}", parts[1]):
        return f"profiles/{parts[1]}"
    if len(parts) >= 2 and parts[0] == "id" and re.fullmatch(r"[A-Za-z0-9_-]+", parts[1]):
        return f"id/{parts[1]}"
    return None


def fetch_wishlist(profile, cc="US"):
    steamid = resolve_steamid(profile)
    query = urllib.parse.urlencode({"steamid": steamid})
    url = f"https://api.steampowered.com/IWishlistService/GetWishlist/v1/?{query}"
    payload = json.loads(_read_url(url, 20))

    items = payload.get("response", {}).get("items")
    if not isinstance(items, list):
        raise ValueError("Steam did not return a wishlist. Check that your wishlist is public.")

    appids = list(dict.fromkeys(
        str(item["appid"])
        for item in items
        if isinstance(item, dict) and str(item.get("appid", "")).isdigit()
    ))
    names = get_app_names(appids, cc)
    return [{"appid": appid, "name": names.get(appid, f"Steam App {appid}")} for appid in appids]


def resolve_steamid(profile):
    profile_type, value = profile.split("/", 1)
    if profile_type == "profiles":
        return value

    url = f"https://steamcommunity.com/id/{urllib.parse.quote(value)}/?xml=1"
    content = _read_url(url, 20).decode("utf-8", errors="replace")

    match = re.search(r"<steamID64>(\d{17})</steamID64>", content)
    if not match:
        raise ValueError("Steam could not resolve that custom profile URL.")
    return match.group(1)


def get_app_names(appids, cc):
    def fetch_name(appid):
        query = urllib.parse.urlencode({"appids": appid, "cc": cc, "l": "english"})
        url = f"https://store.steampowered.com/api/appdetails?{query}"
        try:
            payload = json.loads(_read_url(url, 15))
            item = payload.get(appid, {})
            if item.get("success"):
                return appid, item.get("data", {}).get("name")
        except Exception:
            pass
        return appid, None

    names = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        for appid, name in executor.map(fetch_name, appids):
            if name:
                names[appid] = name
    return names


def _read_url(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            if error.code == 429:
                raise ValueError("Steam is rate limiting requests. Please wait a few minutes and try again.") from error
            raise
