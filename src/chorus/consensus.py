"""Deterministic consensus over reviewer findings.

The whole point: this is plain Python, not an LLM. Same input → same output.
Tested by unit tests without mocking any model. The job is to:

  1. Take only successful reviews (status == "ok")
  2. Group findings across reviewers when they look like the same issue
  3. Classify each group: consensus / unique / disagreement
"""

from __future__ import annotations

import re
from collections import defaultdict

from rapidfuzz import fuzz

from chorus.models import (
    Consensus,
    Finding,
    FindingGroup,
    ProviderReview,
    Severity,
)

# Two findings are "the same issue" if they're in the same file and their
# normalized titles fuzzy-match above this threshold.
TITLE_SIMILARITY_THRESHOLD = 75  # 0-100, rapidfuzz token_set_ratio

SEVERITY_RANK: dict[Severity, int] = {
    "critical": 4,
    "major": 3,
    "minor": 2,
    "nit": 1,
}


def _normalize_title(title: str) -> str:
    """Lowercase + strip punctuation — better fuzzy-match base."""
    return re.sub(r"[^\w\s]", " ", title.lower()).strip()


def _max_severity(findings: list[Finding]) -> Severity:
    return max((f.severity for f in findings), key=lambda s: SEVERITY_RANK[s])


def _sev_spread(findings: list[Finding]) -> int:
    """Distance between highest and lowest severity in a group."""
    ranks = [SEVERITY_RANK[f.severity] for f in findings]
    return max(ranks) - min(ranks)


def _group_findings(reviews: list[ProviderReview]) -> list[list[tuple[str, Finding]]]:
    """Cluster findings by (file, similar title). Each cluster is a list of
    (provider_key, finding) tuples preserving which reviewer raised it.
    """
    by_file: dict[str, list[tuple[str, Finding]]] = defaultdict(list)
    for r in reviews:
        if r.status != "ok":
            continue
        for f in r.findings:
            by_file[f.file].append((r.provider, f))

    groups: list[list[tuple[str, Finding]]] = []
    for items in by_file.values():
        # Greedy clustering — first finding seeds a cluster, subsequent ones
        # join the first matching cluster, else start their own. Good enough
        # for the typical 1-10 findings per file scale.
        clusters: list[list[tuple[str, Finding]]] = []
        for provider, finding in items:
            placed = False
            norm_title = _normalize_title(finding.title)
            for cluster in clusters:
                cluster_title = _normalize_title(cluster[0][1].title)
                score = fuzz.token_set_ratio(norm_title, cluster_title)
                if score >= TITLE_SIMILARITY_THRESHOLD:
                    cluster.append((provider, finding))
                    placed = True
                    break
            if not placed:
                clusters.append([(provider, finding)])
        groups.extend(clusters)

    return groups


def _classify(cluster: list[tuple[str, Finding]]) -> tuple[str, Severity]:
    """Return (classification, consensus_severity).

    - 'consensus'     — 2+ distinct providers agree
    - 'unique'        — only one provider raised it
    - 'disagreement'  — 2+ providers but their severities differ by >=2 ranks
    """
    findings = [f for _, f in cluster]
    distinct_providers = {p for p, _ in cluster}
    severity = _max_severity(findings)

    if len(distinct_providers) < 2:
        return "unique", severity
    if _sev_spread(findings) >= 2:
        return "disagreement", severity
    return "consensus", severity


def consolidate(reviews: list[ProviderReview]) -> Consensus:
    """Build the deterministic Consensus from all reviewer outputs."""
    groups_raw = _group_findings(reviews)

    finding_groups: list[FindingGroup] = []
    for cluster in groups_raw:
        classification, severity = _classify(cluster)
        # Pick the title from the highest-confidence finding for display.
        rep_finding = max((f for _, f in cluster), key=lambda f: f.confidence)
        finding_groups.append(
            FindingGroup(
                file=rep_finding.file,
                title=rep_finding.title,
                severity=severity,
                classification=classification,
                findings=[f for _, f in cluster],
                providers=sorted({p for p, _ in cluster}),
            )
        )

    # Stable order: classification (consensus first), then severity, then file.
    classification_rank = {"consensus": 0, "disagreement": 1, "unique": 2}
    finding_groups.sort(
        key=lambda g: (
            classification_rank[g.classification],
            -SEVERITY_RANK[g.severity],
            g.file,
        )
    )

    return Consensus(
        groups=finding_groups,
        total_reviews_attempted=len(reviews),
        total_reviews_ok=sum(1 for r in reviews if r.status == "ok"),
    )
