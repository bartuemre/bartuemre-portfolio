---
title: SOC Decision Lab
summary: A thesis model and interactive demo for assigning and scheduling SOC alerts under skill, shift, and SLA constraints.
category: Security & optimization
status: Thesis model · Interactive demo
stage: in-progress
tags: [SOC scheduling, Decision support, Optimization]
featured: true
order: 1
repository: https://github.com/bartuemre/soc-decision-lab
demo: https://bartuemre.github.io/soc-decision-lab/
visual: soc
---

## The problem

SOC alerts arrive over time, require different skill levels, and have different response targets. Analysts vary in skill, availability, and estimated review time. The thesis frames assigning and ordering alerts as an unrelated parallel-machine scheduling problem with analyst eligibility, shifts, and sequence-dependent preparation times.

## The model

The proposed objective minimizes **risk-weighted delay in starting an alert review** relative to its SLA target. It does not measure delay in completing the review. Each alert is assigned to one eligible analyst, and preparation and review must fit within that analyst's shift without overlap. SLA delay is penalized rather than treated as a hard deadline.

Additional preparation time depends on the skill level required by the previous alert and the next one. The asymmetric transition rule is a thesis assumption to test, not an observed law of analyst behavior. When a new alert arrives, the model keeps preparation and reviews already in progress fixed and can reassign or reorder pending alerts.

## Interactive demo and current state

The live Turkish demo explains the parameters, decision variables, objective, and constraints, then shows a small synthetic scheduling example. You can add an urgent alert and inspect the revised schedule, preparation times, and a FIFO reference. The demo searches the small example exhaustively; it is **not a general MILP solver**.

The mathematical model and evaluation plan are still being developed. The demo's values and comparisons are illustrative, with no measured SOC performance or validated operational improvement claimed. Planned evaluation includes SLA delay, preparation time, workload distribution, solve time, and infeasible cases.
