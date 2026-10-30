"""Bounded WHOIS (RDAP) and reverse DNS lookups for an IP address."""

import asyncio
import ipaddress
import math
from datetime import UTC, datetime

import httpx

from iprv.parser import normalize

RDAP_URL = "https://rdap.org/ip/"
DNS_URL = "https://cloudflare-dns.com/dns-query"
GEO_URL = "https://ipwho.is/"
GEO_CHECK_URL = "https://ipinfo.io/"
MAX_RESPONSE = 256 * 1024


async def _json(client, url, **kwargs):
    async with client.stream("GET", url, **kwargs) as response:
        response.raise_for_status()
        content = bytearray()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > MAX_RESPONSE:
                raise ValueError("Lookup response is too large")
        return httpx.Response(200, content=bytes(content)).json()


async def _whois(indicator):
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, trust_env=False) as client:
            data = await _json(
                client, RDAP_URL + indicator, headers={"Accept": "application/rdap+json"}
            )
        if not isinstance(data, dict):
            raise ValueError("Invalid RDAP response")
        cidrs = data.get("cidr0_cidrs") or []
        networks = [
            f"{entry[key]}/{entry['length']}"
            for entry in cidrs[:10]
            if isinstance(entry, dict)
            for key in ("v4prefix", "v6prefix")
            if key in entry and isinstance(entry.get("length"), int)
        ]
        return {
            "status": "OK",
            "source": "RDAP",
            "name": str(data.get("name") or "")[:256],
            "handle": str(data.get("handle") or "")[:256],
            "country": str(data.get("country") or "")[:32],
            "start_address": str(data.get("startAddress") or "")[:64],
            "end_address": str(data.get("endAddress") or "")[:64],
            "networks": networks,
        }
    except (httpx.HTTPError, ValueError, KeyError, TypeError, TimeoutError):
        return {"status": "ERROR", "source": "RDAP"}


async def _dns(indicator):
    try:
        reverse = ipaddress.ip_address(indicator).reverse_pointer
        async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
            data = await _json(
                client,
                DNS_URL,
                params={"name": reverse, "type": "PTR"},
                headers={"Accept": "application/dns-json"},
            )
        if not isinstance(data, dict) or type(data.get("Status")) is not int:
            raise ValueError("Invalid DNS response")
        if data["Status"] not in {0, 3}:
            raise ValueError("DNS lookup failed")
        names = sorted(
            {
                str(answer["data"]).rstrip(".")[:253]
                for answer in (data.get("Answer") or [])[:20]
                if isinstance(answer, dict)
                and answer.get("type") == 12
                and isinstance(answer.get("data"), str)
            }
        )
        return {"status": "OK" if names else "NO_RECORD", "ptr": names}
    except (httpx.HTTPError, ValueError, KeyError, TypeError, TimeoutError):
        return {"status": "ERROR", "ptr": []}


async def _geo(indicator):
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=False, trust_env=False) as client:
            data = await _json(client, GEO_URL + indicator)
        if not isinstance(data, dict) or data.get("success") is not True:
            raise ValueError("Geolocation lookup failed")
        if ipaddress.ip_address(data.get("ip")) != ipaddress.ip_address(indicator):
            raise ValueError("Mismatched geolocation IP")
        latitude, longitude = data.get("latitude"), data.get("longitude")
        if (
            type(latitude) not in {float, int}
            or type(longitude) not in {float, int}
            or not math.isfinite(latitude)
            or not math.isfinite(longitude)
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise ValueError("Invalid geolocation coordinates")
        result = {
            "status": "OK",
            "source": "ipwho.is",
            "country": str(data.get("country") or "")[:128],
            "region": str(data.get("region") or "")[:128],
            "city": str(data.get("city") or "")[:128],
            "latitude": latitude,
            "longitude": longitude,
            "network_org": str((data.get("connection") or {}).get("org") or "")[:256]
            if isinstance(data.get("connection"), dict)
            else "",
            "asn": str((data.get("connection") or {}).get("asn") or "")[:32]
            if isinstance(data.get("connection"), dict)
            else "",
        }
        try:
            async with httpx.AsyncClient(
                timeout=8, follow_redirects=False, trust_env=False
            ) as client:
                check = await _json(client, GEO_CHECK_URL + indicator + "/json")
            if isinstance(check, dict) and ipaddress.ip_address(
                check.get("ip")
            ) == ipaddress.ip_address(indicator):
                if check.get("anycast") is True or check.get("is_anycast") is True:
                    result["status"] = "ANYCAST"
                elif isinstance(check.get("country"), str) and len(check["country"]) == 2:
                    country_code = str(data.get("country_code") or "").upper()
                    if country_code and check["country"].upper() != country_code:
                        result["status"] = "CONFLICT"
                if result["status"] == "OK" and isinstance(check.get("loc"), str):
                    try:
                        other_lat, other_lon = (float(part) for part in check["loc"].split(","))
                        if not (-90 <= other_lat <= 90 and -180 <= other_lon <= 180):
                            raise ValueError("Invalid comparison coordinates")
                        angle = (
                            math.sin(math.radians(other_lat - latitude) / 2) ** 2
                            + math.cos(math.radians(latitude))
                            * math.cos(math.radians(other_lat))
                            * math.sin(math.radians(other_lon - longitude) / 2) ** 2
                        )
                        if 12742 * math.asin(min(1, math.sqrt(angle))) > 50:
                            result["status"] = "CONFLICT"
                    except (ValueError, TypeError):
                        pass
                result["alternate_city"] = str(check.get("city") or "")[:128]
                result["alternate_country"] = str(check.get("country") or "")[:32]
                result["verification_source"] = "ipinfo.io"
                if isinstance(check.get("org"), str) and check["org"].strip():
                    result["network_org"] = check["org"].strip()[:256]
        except (httpx.HTTPError, ValueError, TypeError, TimeoutError):
            pass
        return result
    except (httpx.HTTPError, ValueError, TypeError, TimeoutError):
        return {"status": "ERROR", "source": "ipwho.is"}


async def lookup(indicator, mode, allow_external, enabled):
    """Return informational data; lookup failures never change the threat verdict."""
    normalized, _, is_global = normalize(indicator)
    stamp = datetime.now(UTC).isoformat()
    if "/" in normalized or not is_global:
        status = "SKIPPED_NETWORK" if "/" in normalized else "SKIPPED_NON_GLOBAL"
    elif mode == "offline":
        status = "OFFLINE"
    elif not (allow_external and enabled):
        status = "CONSENT_REQUIRED"
    else:
        try:
            async with asyncio.timeout(15):
                whois, dns, geo = await asyncio.gather(
                    _whois(normalized), _dns(normalized), _geo(normalized)
                )
        except TimeoutError:
            whois = {"status": "ERROR", "source": "RDAP"}
            dns = {"status": "ERROR", "ptr": []}
            geo = {"status": "ERROR", "source": "ipwho.is"}
        return {"checked_at": stamp, "whois": whois, "dns": dns, "geo": geo}
    return {
        "checked_at": stamp,
        "whois": {"status": status, "source": "RDAP"},
        "dns": {"status": status, "ptr": []},
        "geo": {"status": status, "source": "ipwho.is"},
    }
