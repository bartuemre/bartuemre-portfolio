"""Input normalization without expanding potentially enormous networks."""

import csv
import io
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from iprv.json_input import AmbiguousJSON, strict_json_loads
from iprv.network_policy import special_use_blocked

MAX_INPUT_RECORDS = 100000
MAX_PARSE_ERRORS = 100


class Occurrence(BaseModel):
    row: int
    field: str | None = None
    original: str
    normalized: str
    kind: str
    is_global: bool


class ParsedInput(BaseModel):
    occurrences: list[Occurrence] = Field(default_factory=list)
    unique_indicators: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    error_count: int = 0
    errors_truncated: bool = False
    columns: list[str] = Field(default_factory=list)


def externally_routable(address) -> bool:
    return (
        address.is_global
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not getattr(address, "is_site_local", False)
        and not special_use_blocked(address)
    )


def normalize(value: str) -> tuple[str, str, bool]:
    value = value.strip()
    if not 1 <= len(value) <= 128:
        raise ValueError("Indicator must contain 1 to 128 characters")
    if "%" in value:
        raise ValueError("Scoped IPv6 addresses are not supported")
    if "/" in value:
        network = ipaddress.ip_network(value, strict=False)
        return str(network), "CIDR", externally_routable(network)
    address = ipaddress.ip_address(value)
    return str(address), f"IPv{address.version}", externally_routable(address)


def candidates(value: str):
    try:
        normalize(value)
        yield value.strip()
        return
    except ValueError:
        pass
    # URL hosts are parsed locally; paths, credentials and domains are never resolved.
    tokens = re.finditer(
        r"(?P<url>[a-zA-Z][a-zA-Z0-9+.-]*://[^\s,;\"'<>]+)"
        r"|(?P<token>[^\s,;=\[\]\(\)\"'<>]+)",
        value,
    )
    for match in tokens:
        token = match.group().strip(".")
        if match.group("url"):
            try:
                parsed = urlsplit(token.rstrip(")."))
                port = parsed.port
                token = parsed.hostname or ""
                if port is not None and not 1 <= port <= 65535:
                    continue
                normalize(token)
            except ValueError:
                continue
            yield token
            continue
        host_port = re.fullmatch(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})", token)
        if host_port and 1 <= int(host_port[2]) <= 65535:
            token = host_port[1]
        if "." in token or ":" in token:
            try:
                normalize(token)
            except ValueError:
                continue
            yield token


def parse_input(content: bytes, filename: str, column: str | None = None) -> ParsedInput:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Input must be UTF-8 encoded") from exc
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".json", ".jsonl", ".txt", ".log"}:
        raise ValueError("Supported formats: CSV, JSON, JSONL, TXT, LOG")
    result = ParsedInput()

    def record_error(message):
        result.error_count += 1
        if len(result.errors) < MAX_PARSE_ERRORS:
            result.errors.append(message)
        else:
            result.errors_truncated = True

    def check_record_count(count):
        if count > MAX_INPUT_RECORDS:
            raise ValueError("Input exceeds 100000 records; split the file")

    def visit(value, row, field=None, depth=0):
        if depth > 64:
            raise ValueError("Input nesting exceeds 64 levels")
        if field and len(field) > 512:
            raise ValueError("Field path exceeds 512 characters")
        if isinstance(value, dict):
            for key, child in value.items():
                if len(str(key)) > 128:
                    raise ValueError("Field names must not exceed 128 characters")
                visit(child, row, f"{field}.{key}" if field else str(key), depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, row, f"{field or ''}[{index}]", depth + 1)
        elif isinstance(value, str):
            for candidate in candidates(value):
                if len(result.occurrences) >= 10000:
                    raise ValueError("Input exceeds 10000 IP occurrences")
                normalized, kind, global_address = normalize(candidate)
                result.occurrences.append(
                    Occurrence(
                        row=row,
                        field=field,
                        original=candidate,
                        normalized=normalized,
                        kind=kind,
                        is_global=global_address,
                    )
                )

    try:
        if suffix == ".csv":
            try:
                dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
            reader = csv.reader(io.StringIO(text), dialect=dialect, strict=True)
            headers = next(reader, [])
            result.columns = headers
            if len(headers) > 256 or any(not h or len(h) > 128 for h in headers):
                raise ValueError(
                    "CSV requires non-empty headers up to 128 characters and at most 256 columns"
                )
            if len(set(headers)) != len(headers):
                raise ValueError("Duplicate CSV headers are ambiguous; rename the columns")
            if column and column not in headers:
                raise ValueError(f"Unknown CSV column: {column}")
            previous_line = reader.line_num
            for count, values in enumerate(reader, 1):
                check_record_count(count)
                row = previous_line + 1
                previous_line = reader.line_num
                if not values:
                    continue
                if len(values) != len(headers):
                    record_error(f"Row {row}: CSV field count differs from header")
                record = dict(zip(headers, values, strict=False))
                extras = values[len(headers) :]
                if column:
                    visit(record.get(column), row, column)
                else:
                    visit(record, row)
                    visit(extras, row, "$extra")
        elif suffix == ".json":
            data = strict_json_loads(text)
            for row, record in enumerate(data if isinstance(data, list) else [data], 1):
                check_record_count(row)
                visit(record, row)
        elif suffix == ".jsonl":
            for row, line in enumerate(text.splitlines(), 1):
                check_record_count(row)
                if line.strip():
                    try:
                        visit(strict_json_loads(line), row)
                    except (json.JSONDecodeError, AmbiguousJSON):
                        record_error(f"Row {row}: invalid JSON")
        else:
            for row, line in enumerate(text.splitlines(), 1):
                check_record_count(row)
                visit(line, row)
    except (json.JSONDecodeError, AmbiguousJSON, csv.Error, RecursionError) as exc:
        raise ValueError("Malformed input document") from exc
    result.unique_indicators = list(dict.fromkeys(item.normalized for item in result.occurrences))
    return result
