"""Reject ambiguous JSON imports and provider responses instead of losing fields."""

import json


class AmbiguousJSON(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AmbiguousJSON("Duplicate JSON object key")
        result[key] = value
    return result


def reject_constant(value):
    raise AmbiguousJSON("Non-finite JSON constants are not supported")


def strict_json_loads(content):
    return json.loads(content, object_pairs_hook=unique_object, parse_constant=reject_constant)
