from dataclasses import dataclass, field
from datetime import date

from .models import Domain

SSL_SOON_DAYS = 30

STATUS_DISPLAY = {
    Domain.STATUS_ACTIVE: ("利用中", "active"),
    Domain.STATUS_EXPIRED: ("失効疑い", "expired"),
    Domain.STATUS_DELETED: ("廃止", "deleted"),
    Domain.STATUS_PENDING: ("承認待ち", "pending"),
}

AVATAR_COLORS = [
    "#0ea5e9", "#6366f1", "#10b981", "#f59e0b", "#ef4444",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#64748b",
]


def classify_ssl(expires_at, today):
    """Return 'expired' | 'soon' | 'ok' for a cert expiry date, or None if no date."""
    if expires_at is None:
        return None
    delta = (expires_at - today).days
    if delta < 0:
        return "expired"
    if delta <= SSL_SOON_DAYS:
        return "soon"
    return "ok"


def latest_cert_expiry(domain):
    """Max expires_at among non-revoked certs (uses prefetched .certificates)."""
    dates = [c.expires_at for c in domain.certificates.all() if not c.is_revoked and c.expires_at]
    return max(dates) if dates else None


@dataclass
class DomainNode:
    domain: object
    children: list = field(default_factory=list)
    depth: int = 0
    child_count: int = 0
    descendant_count: int = 0
    ssl_expiry: date = None
    ssl_state: str = None


@dataclass
class DomainGroup:
    root: DomainNode
    rows: list = field(default_factory=list)  # preorder descendants of root


def _parent_fqdn(fqdn):
    return fqdn.split(".", 1)[1] if "." in fqdn else None


def build_forest(domains, today):
    """Build a display forest from a Domain set using FQDN suffix parentage.

    Returns (roots, index) where roots is a list[DomainNode] sorted by
    fqdn_reversed and index maps domain.id -> DomainNode.
    """
    present = {d.fqdn: d for d in domains}
    index = {}
    nodes = {}
    for d in domains:
        node = DomainNode(domain=d)
        node.ssl_expiry = latest_cert_expiry(d)
        node.ssl_state = classify_ssl(node.ssl_expiry, today)
        nodes[d.fqdn] = node
        index[d.id] = node

    roots = []
    for d in sorted(domains, key=lambda x: x.fqdn_reversed):
        node = nodes[d.fqdn]
        parent = _parent_fqdn(d.fqdn)
        while parent and parent not in present:
            parent = _parent_fqdn(parent)
        if parent and parent in nodes:
            nodes[parent].children.append(node)
        else:
            roots.append(node)

    def finalize(node, depth):
        node.depth = depth
        node.child_count = len(node.children)
        total = 0
        for child in node.children:
            total += 1 + finalize(child, depth + 1)
        node.descendant_count = total
        return total

    for root in roots:
        finalize(root, 0)
    return roots, index


def _preorder(node):
    """Descendants of node in pre-order (excludes node itself)."""
    out = []
    for child in node.children:
        out.append(child)
        out.extend(_preorder(child))
    return out


def build_domain_groups(domains, today):
    roots, index = build_forest(domains, today)
    groups = [DomainGroup(root=r, rows=_preorder(r)) for r in roots]
    return groups, index


def domain_owner(domain):
    unit = domain.management_unit
    if unit is None:
        return None
    return unit.primary_owner or unit.mgmt_owner


def domain_dept(domain):
    unit = domain.management_unit
    return unit.mgmt_dept if unit else None


def avatar_color(name):
    h = 0
    for ch in name or "?":
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return AVATAR_COLORS[h % len(AVATAR_COLORS)]


def ledger_counts(domains, today):
    counts = {"all": len(domains), "active": 0, "expired": 0, "deleted": 0,
              "pending": 0, "ssl_soon": 0, "ssl_expired": 0}
    for d in domains:
        if d.status in counts:
            counts[d.status] += 1
        state = classify_ssl(latest_cert_expiry(d), today)
        if state == "soon":
            counts["ssl_soon"] += 1
        elif state == "expired":
            counts["ssl_expired"] += 1
    return counts


_STATUS_KEYS = {Domain.STATUS_ACTIVE, Domain.STATUS_EXPIRED, Domain.STATUS_DELETED, Domain.STATUS_PENDING}


def row_matches(node, fkey, q):
    if q and q.lower() not in node.domain.fqdn.lower():
        return False
    if not fkey or fkey == "all":
        return True
    if fkey in _STATUS_KEYS:
        return node.domain.status == fkey
    if fkey == "ssl_soon":
        return node.ssl_state == "soon"
    if fkey == "ssl_expired":
        return node.ssl_state == "expired"
    return True


def visible_groups(groups, fkey, q):
    """Filter each group's rows; keep a group if its root or any row matches."""
    out = []
    for group in groups:
        rows = [n for n in group.rows if row_matches(n, fkey, q)]
        if rows or row_matches(group.root, fkey, q):
            out.append(DomainGroup(root=group.root, rows=rows))
    return out
