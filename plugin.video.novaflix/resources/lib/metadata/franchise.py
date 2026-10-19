"""Whole-franchise walk for Related & sequels (M14, DEC-062). Pure: the caller passes a fetch
function (ids -> {id: RelationNode}), so this runs without Kodi or the network.

Sequel/prequel links are followed through every format, one fetch per level; extras linked from
chain members are fetched once and never walked. Rows are by format first, then by relation."""

from dataclasses import dataclass, field

from resources.lib import errors
from resources.lib.models import RelationNode

ROWS = ("sequels", "prequels", "side_stories", "ovas", "movies", "other")
CAP = 60  # extras besides the opened show; the sequel/prequel chain has its own budget of the same size

AFTER, BEFORE, DATED, EXTRA = "after", "before", "dated", "extra"
CHAIN_LINKS = {"SEQUEL": AFTER, "PREQUEL": BEFORE}


@dataclass
class Franchise:
    title: str
    rows: dict = field(default_factory=dict)   # row name -> [RelationNode], every name in ROWS
    partial: bool = False                       # AniList failed mid-walk: rows hold what was found
    capped: bool = False

    def to_dict(self):
        return {"title": self.title, "partial": self.partial, "capped": self.capped,
                "rows": {name: [n.to_dict() for n in entries] for name, entries in self.rows.items()}}

    @classmethod
    def from_dict(cls, data):
        return cls(title=data["title"], partial=data["partial"], capped=data["capped"],
                   rows={name: [RelationNode.from_dict(n) for n in entries] for name, entries in data["rows"].items()})


def _parent_mode(node):
    """An OVA or side story opened on its own: walk its parent's chain instead (spec §4.2 step 3)."""
    relations = {relation for relation, _ in node.edges}
    return not relations & set(CHAIN_LINKS) and "PARENT" in relations


def _chain_role(role, relation):
    """Side of a newly found chain entry. A link pointing back the other way (a prequel found from the
    sequel side) gives no reliable side, so that entry is placed by start date instead."""
    if relation == "PARENT" or role == DATED:
        return DATED
    if role is None:
        return CHAIN_LINKS[relation]
    return role if CHAIN_LINKS[relation] == role else DATED


def walk(start_id, fetch):
    start_id = int(start_id)
    place = {start_id: (None, None)}  # id -> (role, relation); insertion order = found order
    nodes, chain = {}, {start_id}
    pending, partial, capped = [start_id], False, False
    extras = 0
    while pending:
        try:
            nodes.update(fetch(pending))
        except (errors.HttpError, errors.NetworkError):
            if not nodes:
                raise
            partial = True
            break
        if start_id not in nodes:
            raise errors.HttpError(f"AniList has no anime {start_id}", 404)
        found = []
        for node_id in pending:
            node = nodes.get(node_id)
            if node is None or node_id not in chain:
                continue
            role = place[node_id][0]
            for relation, other in node.edges:
                if other in place:
                    continue
                if relation in CHAIN_LINKS or (relation == "PARENT" and node_id == start_id and _parent_mode(node)):
                    if len(chain) - 1 >= CAP:
                        capped = True
                        continue
                    new_role = _chain_role(role, relation)
                    chain.add(other)
                else:
                    if extras >= CAP:  # extras never take the chain's places (review M14)
                        capped = True
                        continue
                    new_role = EXTRA
                    extras += 1
                place[other] = (new_role, relation)
                found.append(other)
        pending = found
    return Franchise(title=nodes[start_id].title, rows=_rows(place, nodes, nodes[start_id]),
                     partial=partial, capped=capped)


def _row(role, relation, node, opened):
    if node.format == "MOVIE":
        return "movies"
    if node.format in ("OVA", "SPECIAL"):
        return "ovas"
    if role == DATED:
        if not node.start or not opened.start:
            return "other"
        role = BEFORE if node.start < opened.start else AFTER
    if role == AFTER:
        return "sequels"
    if role == BEFORE:
        return "prequels"
    if relation == "SIDE_STORY":
        return "side_stories"
    return "other"


def _rows(place, nodes, opened):
    rows = {name: [] for name in ROWS}
    for node_id, (role, relation) in place.items():
        node = nodes.get(node_id)
        if node_id == opened.anilist_id or node is None:  # opened show, or AniList returned nothing
            continue
        rows[_row(role, relation, node, opened)].append(node)
    for entries in rows.values():
        entries.sort(key=lambda n: (n.start is None, n.start or ()))  # stable: ties keep found order
    return rows
