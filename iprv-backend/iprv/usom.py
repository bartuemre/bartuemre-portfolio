"""USOM / SGB public API: bounded, exact IP matches with original listing metadata."""

import ipaddress
from datetime import datetime

from iprv.live import LiveService

MAX_RECORDS = 1000


class UsomService(LiveService):
    provider = "live:usom"
    endpoint = "https://siberguvenlik.gov.tr/api/address/index"
    requires_api_key = False

    def request_options(self, indicator):
        return "GET", {
            "params": {
                "q": indicator,
                "type": "ip" if ipaddress.ip_address(indicator).version == 4 else "ip6",
                "page": 1,
                "per-page": MAX_RECORDS,
            },
            "headers": {"Accept": "application/json"},
        }

    @staticmethod
    def validate_record(item, indicator):
        address = ipaddress.ip_address(item["url"])
        if item["type"] != ("ip" if address.version == 4 else "ip6"):
            raise ValueError("Unexpected USOM record type")
        identifier = item["id"]
        if type(identifier) is not int or identifier <= 0:
            raise ValueError("Invalid USOM record ID")
        level = item["criticality_level"]
        if type(level) is not int or not 1 <= level <= 10:
            raise ValueError("Invalid USOM criticality")
        listed_at = item.get("date")
        if listed_at is not None:
            if not isinstance(listed_at, str) or len(listed_at) > 64:
                raise ValueError("Invalid USOM listing date")
            datetime.fromisoformat(listed_at)
        for key in ("desc", "source", "connectiontype"):
            if not isinstance(item.get(key), str) or len(item[key]) > 128:
                raise ValueError("Invalid USOM metadata")
        # q is a text search, not an equality filter. Never attribute substring hits.
        if str(address) != indicator:
            return None
        return {
            "id": identifier,
            "url": str(address),
            "type": item["type"],
            "desc": item["desc"],
            "source": item["source"],
            "date": listed_at,
            "criticality_level": level,
            "connectiontype": item["connectiontype"],
        }

    @classmethod
    def validate_payload(cls, body, indicator):
        records = body["models"]
        if not isinstance(records, list) or len(records) > MAX_RECORDS:
            raise ValueError("Invalid USOM records")
        for key in ("totalCount", "count", "page", "pageCount"):
            if type(body[key]) is not int or body[key] < 0:
                raise ValueError("Invalid USOM pagination")
        # A partial search must never be cached as a negative lookup. Exact host
        # searches normally fit on one page; reject oversized/inconsistent results.
        if (
            body["count"] != len(records)
            or body["totalCount"] != len(records)
            or body["page"] != 0
            or body["pageCount"] != (1 if records else 0)
        ):
            raise ValueError("Incomplete USOM search response")
        normalized = []
        seen = set()
        for item in records:
            record = cls.validate_record(item, indicator)
            if record is not None:
                if record["id"] in seen:
                    raise ValueError("Duplicate USOM record")
                seen.add(record["id"])
                normalized.append(record)
        return {"records": normalized}

    def validate_cached(self, data, indicator):
        records = data["records"]
        normalized = self.validate_payload(
            {
                "models": records,
                "count": len(records),
                "totalCount": len(records),
                "page": 0,
                "pageCount": 1 if records else 0,
            },
            indicator,
        )
        if len(normalized["records"]) != len(records):
            raise ValueError("Mismatched cached USOM record")
        return normalized

    @staticmethod
    def positive(data):
        return bool(data["records"])

    def evidence(self, data, indicator, retrieved, expires):
        return [
            {
                "source_id": self.provider,
                "kind": "ioc",
                "context": "UNCLASSIFIED",
                "indicator": indicator,
                "match_type": "EXACT_IP",
                "strength": "medium",
                # The API's date is a listing date with no documented timezone
                # or last-observed semantics. Keep it separate from event recency.
                "last_seen": None,
                "event_time_basis": "unknown",
                "provider_listed_at": record["date"],
                "provider_criticality": record["criticality_level"],
                "provider_category": record["desc"],
                "provider_source": record["source"],
                "provider_connection_type": record["connectiontype"],
                "reference": "https://siberguvenlik.gov.tr/zararli-baglantilar/detay/"
                + str(record["id"]),
                "lineage": "usom",
                "version_id": retrieved,
                "source_version": "sgb-api-v1.1-exact-ip",
                "retrieved_at": retrieved,
                "expires_at": expires,
                "stale": False,
            }
            for record in data["records"]
        ]
