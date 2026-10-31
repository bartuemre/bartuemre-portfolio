---
title: Literatür Tarama
summary: A browser-based academic literature search tool with OpenAlex results, paper inspection, source links, and CSV export.
category: Software & research
status: Live · Browser app
stage: demo
demo: https://bartuemre.com/literatur-tarama/
repository: https://github.com/bartuemre/literatur-tarama
tags: [OpenAlex, Literature search, Web application]
featured: false
order: 3
visual: research
---

## What it does

Literatür Tarama helps explore academic publications in a browser. Enter one or more search queries, choose the earliest publication year and a result limit, and retrieve publication records from OpenAlex. The results show titles, venues, publication years, citation counts, DOI links, and available open-access PDF links.

You can filter the returned records, inspect one paper's authors, institutions, available abstract, and method terms detected in that abstract. Selected results can be opened or copied in bulk, and the visible results can be downloaded as CSV. The tool also creates search links for Google Scholar, DergiPark, ScienceDirect, Semantic Scholar, and the Turkish thesis database.

## Current release

The latest version runs directly on this site, with a responsive results layout and selection that persists while filtering. Its source is available in the repository. Live publication search needs an internet connection and access to the OpenAlex API; an API key can be entered in the browser if required.

The inspection panel uses OpenAlex metadata and abstract text. Method terms are simple text matches, **not AI analysis or verification of a paper's methods**. Other academic platforms are opened through search links; the tool does not retrieve their records directly. PDF links appear only when the source provides them.
