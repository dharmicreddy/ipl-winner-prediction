# ADR-005: Data Source Compliance Policy

**Status:** Accepted
**Date:** Phase 1 (revised)
**Supersedes:** The scraping-heavy approach implied in earlier planning

## Context

The initial plan named ESPNCricinfo and Cricbuzz as scraping targets for fixtures, squads, and toss data. Review of their Terms of Use revealed both prohibit automated access — ESPNCricinfo explicitly, Cricbuzz implicitly (no permissive license; community scrapers rely on "educational use" disclaimers that carry no legal weight).

Continuing down that path would create three problems:
1. **Legal exposure** — even for a personal project, breaching a site's ToS can result in IP blocks and cease-and-desist letters.
2. **Portfolio signal** — a reviewer who knows the sources will recognise the compliance issue. A reviewer who does not will not distinguish our project from the dozens of ToS-breaching IPL scrapers on GitHub.
3. **Project durability** — scraping pipelines break when target sites update HTML, deploy anti-bot measures, or tighten enforcement. An API-based pipeline is more stable.

## Decision

**Every data source must have an affirmative legal basis.** Three acceptable bases:

1. An **open-data license** (ODbL, CC-BY, CC-BY-SA, etc.)
2. A **published API ToS** that permits the usage pattern
3. **Data we generate or curate ourselves** (reference YAML files)

Everything else is rejected, regardless of how convenient it would be.

The approved source list is maintained in `docs/data-sources.md`. Adding a new source requires an ADR update and explicit verification of its license or ToS.

## Rationale

- **Legal discipline is non-negotiable** for any project that might be linked from a public resume.
- **API-based ingestion demonstrates the same engineering skills** as HTML scraping — rate limits, retries, idempotency, bronze landing — often more cleanly.
- **Reframing the project** as "open-data + API integration" is a differentiator, not a limitation. Most IPL-prediction portfolios on GitHub are in quiet ToS breach; this one explicitly is not.

## Consequences

- Phase 3 is renamed "Incremental API ingestion" (from "Incremental scrapers"). Same engineering patterns.
- Playwright is removed from the stack; not needed for API access.
- The README project description emphasises "open-data pipeline" over "web scraping."
- For the "upcoming match prediction" feature, we choose between CricketData.org's free API (requires signup + key management) or a manually-maintained `fixtures.yaml`. Default: start with YAML, upgrade to API only if weekly maintenance becomes painful.
- A compliance review becomes a mandatory item on the Phase 1 checklist and for any future source addition.

## Alternatives considered

- **Scrape anyway, hide attribution.** Rejected — dishonest, and undermines the whole portfolio purpose.
- **Scrape only "for educational use."** Rejected — this disclaimer has no legal force when the source ToS prohibits automated access.
- **Pay for a commercial API (Sportmonks, Roanuz).** Rejected — project constraint is free-tier only; also creates vendor dependency for a portfolio piece with no budget.
