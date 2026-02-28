\
from __future__ import annotations
import re
from typing import List, Optional, Tuple

from ddgpt.io.loaders import Page
from ddgpt.extract.base import Extractor
from ddgpt.extract.schemas import ExtractedDoc
from ddgpt.provenance.evidence import Evidence

def _find_in_pages(pages: List[Page], pattern: str) -> Tuple[Optional[str], Optional[int], str]:
    rgx = re.compile(pattern, flags=re.IGNORECASE)
    for pg in pages:
        m = rgx.search(pg.text)
        if m:
            start = max(0, m.start() - 50)
            end = min(len(pg.text), m.end() + 50)
            snippet = re.sub(r"\s+", " ", pg.text[start:end]).strip()
            words = snippet.split()
            snippet = " ".join(words[:20])
            return m.group(1), pg.page_num, snippet
    return None, None, ""

def _parse_billion_to_usd(x: str) -> float:
    return float(x) * 1e9

class RegexExtractor(Extractor):
    def extract(self, doc_name: str, pages: List[Page]) -> ExtractedDoc:
        out = ExtractedDoc(doc_name=doc_name)

        date, p, snip = _find_in_pages(pages, r"As-of Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")
        if date is None:
            date, p, snip = _find_in_pages(pages, r"Effective Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})")
        out.doc_date = date

        aum_b, p_aum, sn_aum = _find_in_pages(pages, r"AUM\).*?\$([0-9]+\.[0-9]+)B")
        if aum_b is None:
            aum_b, p_aum, sn_aum = _find_in_pages(pages, r"Assets Under Management.*?\$([0-9]+\.[0-9]+)B")
        if aum_b is not None:
            out.aum.value = _parse_billion_to_usd(aum_b)
            out.aum.confidence = 0.55
            out.aum.evidence = Evidence(doc_name=doc_name, page=p_aum, snippet=sn_aum)
        else:
            out.missing_fields.append("aum.value")

        net_irr, p_irr, sn_irr = _find_in_pages(pages, r"Net IRR.*?:\s*([0-9]+\.[0-9]+)%")
        if net_irr is not None:
            out.net_irr.value = float(net_irr)
            out.net_irr.confidence = 0.55
            out.net_irr.evidence = Evidence(doc_name=doc_name, page=p_irr, snippet=sn_irr)
        else:
            out.missing_fields.append("net_irr.value")

        tvpi, p_tvpi, sn_tvpi = _find_in_pages(pages, r"TVPI.*?:\s*([0-9]+\.[0-9]+)x")
        if tvpi is not None:
            out.tvpi.value = float(tvpi)
            out.tvpi.confidence = 0.55
            out.tvpi.evidence = Evidence(doc_name=doc_name, page=p_tvpi, snippet=sn_tvpi)
        else:
            out.missing_fields.append("tvpi.value")

        target, p_t, sn_t = _find_in_pages(pages, r"Target IRR:\s*([0-9]+)%")
        if target is not None:
            out.target_irr.value = float(target)
            out.target_irr.confidence = 0.55
            out.target_irr.evidence = Evidence(doc_name=doc_name, page=p_t, snippet=sn_t)
        else:
            out.missing_fields.append("target_irr.value")

        fee, p_f, sn_f = _find_in_pages(pages, r"Management Fee.*?:\s*([0-9]+\.[0-9]+)%")
        if fee is None:
            fee, p_f, sn_f = _find_in_pages(pages, r"Management Fee.*?([0-9]+\.[0-9]+)%")
        if fee is not None:
            out.mgmt_fee.value = float(fee)
            out.mgmt_fee.confidence = 0.55
            out.mgmt_fee.evidence = Evidence(doc_name=doc_name, page=p_f, snippet=sn_f)
        else:
            out.missing_fields.append("mgmt_fee.value")

        carry, p_c, sn_c = _find_in_pages(pages, r"Carry:\s*([0-9]+)%")
        if carry is None:
            carry, p_c, sn_c = _find_in_pages(pages, r"carried interest.*?([0-9]+)%")
        hurdle, p_h, sn_h = _find_in_pages(pages, r"over an\s*([0-9]+)%\s*preferred")
        if hurdle is None:
            hurdle, p_h, sn_h = _find_in_pages(pages, r"hurdle.*?([0-9]+)%")

        if carry is not None:
            out.carry.value = float(carry)
            out.carry.confidence = 0.55
            sn = sn_c or sn_h
            pg = p_c or p_h
            out.carry.evidence = Evidence(doc_name=doc_name, page=pg, snippet=sn)
        else:
            out.missing_fields.append("carry.value")

        if hurdle is not None:
            out.carry.hurdle = float(hurdle)
        else:
            out.missing_fields.append("carry.hurdle")

        return out
