---
title: IPRV — IP Reputation Validator
summary: A defensive IP investigation workspace that keeps evidence, context, and uncertainty visible.
category: Software & research
status: Live workspace · v0.4.7
stage: demo
tags: [IP reputation, Evidence, Blue Team]
featured: true
order: 2
repository: https://github.com/bartuemre
demo: https://iprv.bartuemre.com/
visual: iprv
---

## The project

IPRV (IP Reputation Validator) is a defensive investigation tool for IPv4, IPv6, and CIDR inputs. It compares indicators with local warning lists, IOC sources, and allowlists, then presents the evidence and context behind a result.

The current release is **v0.4.7**. The portfolio embeds the latest application interface, including network lookup, and the workspace also opens as a separate site at [iprv.bartuemre.com](https://iprv.bartuemre.com/). It includes its own English/Turkish language selection.

## What it keeps visible

- evidence and source coverage instead of a black-box score;
- private, reserved, and non-global address context;
- the difference between an indicator lookup and a confident security verdict.

IPRV uses a Python/FastAPI backend. Data availability and live-query options depend on the connected service; the interface shows its current state. A result should be read alongside its source coverage and evidence.
