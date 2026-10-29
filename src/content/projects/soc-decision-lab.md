---
title: SOC Decision Lab
summary: Exploring how security teams can prioritize alerts and assign analysts under real-world constraints.
category: Security & optimization
status: Academic project · In progress
tags: [SOC workflows, Decision support, Optimization]
featured: true
order: 1
repository: https://github.com/bartuemre/soc-decision-lab
demo: https://bartuemre.github.io/soc-decision-lab/
visual: soc
---

## The problem

Security operations involve competing priorities: alerts need attention, analysts have different skills and availability, and response commitments introduce time constraints. This academic project explores how to represent those competing needs as a decision-support problem.

## The approach

The work considers SOC alert prioritization and analyst assignment together. The proposed model takes analyst skills, availability, and service-level agreement (SLA) constraints into account.

Mathematical programming, including mixed-integer linear programming (MILP), is under consideration. The optimization approach is still being developed; an implemented or validated optimizer is not claimed.

## Current state

This is an in-progress academic optimization and decision-support project. The repository is available for reviewing the work as it develops. No performance results or production deployment are claimed.

## Questions guiding the work

- How should alert priority influence assignment decisions?
- How can analyst skills and availability be represented as constraints?
- How should SLA requirements affect a feasible assignment?
- What would a useful evaluation of the proposed model require?
