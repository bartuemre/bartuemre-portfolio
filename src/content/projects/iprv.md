---
title: IPRV — IP Reputation Validator
summary: A defensive IP investigation workspace that keeps evidence, context, and uncertainty visible.
category: Software & research
status: Local working release · v0.4.7
tags: [IP reputation, Evidence, Blue Team]
featured: true
order: 2
repository: https://github.com/bartuemre
visual: iprv
---

## The project

IPRV (IP Reputation Validator) is a defensive investigation tool for IPv4, IPv6, and CIDR inputs. It compares indicators with local warning lists, IOC sources, and allowlists, then presents the evidence and context behind a result.

The current working release is **v0.4.7**. The portfolio includes a lightweight in-page validator so the core workflow can be tried without leaving this site.

## What it keeps visible

- evidence and source coverage instead of a black-box score;
- private, reserved, and non-global address context;
- the difference between an indicator lookup and a confident security verdict.

The full application remains a local Python/FastAPI project; this page is its small, browser-safe demonstration surface.
