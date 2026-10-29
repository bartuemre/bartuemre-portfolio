"""Conservative privacy floor for special-use ranges fixed in Python 3.13.

Older supported Python patch releases can classify these ranges differently.
Keep the runtime's other exclusions, and never widen its eligibility decision.
Reference: https://docs.python.org/3.13/library/ipaddress.html#ipaddress.IPv4Address.is_private
"""

import ipaddress

SPECIAL = {
    4: [ipaddress.ip_network("192.0.0.0/24")],
    6: [
        ipaddress.ip_network(value)
        for value in (
            "64:ff9b:1::/48",
            "2002::/16",
            "2001::/23",
        )
    ],
}
EXCEPTIONS = {
    4: [ipaddress.ip_network(value) for value in ("192.0.0.9/32", "192.0.0.10/32")],
    6: [
        ipaddress.ip_network(value)
        for value in (
            "2001:1::1/128",
            "2001:1::2/128",
            "2001:3::/32",
            "2001:4:112::/48",
            "2001:20::/28",
            "2001:30::/28",
        )
    ],
}


def special_use_blocked(address):
    if isinstance(address, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
        return any(address in network for network in SPECIAL[address.version]) and not any(
            address in network for network in EXCEPTIONS[address.version]
        )
    return any(address.subnet_of(network) for network in SPECIAL[address.version]) and not any(
        address.subnet_of(network) for network in EXCEPTIONS[address.version]
    )
