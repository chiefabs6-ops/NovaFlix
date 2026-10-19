"""Nyaa RSS fallback search (DEC-003). Text search, so every hit is labelled
"best guess" unless its name clearly states the wanted episode.

RSS is not formally documented; fields used (fixture nyaa_frieren_03.xml):
title, nyaa:infoHash, nyaa:seeders, nyaa:size. Category 1_2 = Anime, English-translated.
"""

import xml.etree.ElementTree as ET

from resources.lib.models import Candidate
from resources.lib.sources import matcher
from resources.lib.sources.torrentio import parse_size

URL = "https://nyaa.si/"
NS = {"nyaa": "https://nyaa.si/xmlns/nyaa"}
MAX_RESULTS = 40


def query_for(title, number, is_movie):
    return title if is_movie else f"{title} {number:02d}"


def parse_rss(xml_text, number, absolute=None, tvdb=None, is_movie=False):
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        info_hash = (item.findtext("nyaa:infoHash", namespaces=NS) or "").lower()
        if not title or len(info_hash) != 40:
            continue
        rel = matcher.parse(title)
        verdict = None if is_movie else matcher.matches(rel, number, absolute, tvdb)
        if verdict is False:
            continue
        seeders = item.findtext("nyaa:seeders", namespaces=NS)
        out.append(Candidate(
            origin="nyaa",
            release_name=title,
            info_hash=info_hash,
            size_bytes=parse_size(item.findtext("nyaa:size", namespaces=NS)),
            seeders=int(seeders) if seeders and seeders.isdigit() else None,
            site="Nyaa",
            resolution=rel.resolution,
            codec=rel.codec,
            release_group=rel.group,
            audio=rel.audio,
            # Text search: only a stated single-episode number counts as exact.
            match="exact" if verdict and rel.episode is not None else "best_guess",
        ))
        if len(out) >= MAX_RESULTS:
            break
    return out
