"""OL-001 run — strictly per PREREG. Seed 20260825 for null sampling."""
import json, gzip, re, numpy as np
import xml.etree.ElementTree as ET

HUB = "/home/claude/hub/hub_theory_bundle/"
COMP = ("_c", "_e", "_m", "_x", "_r", "_v", "_n", "_g", "_h", "_p")
INORG = set("""h h2o pi ppi pppi o2 co2 nh4 h2 h2s so4 so3 s no2 no3 no n2 n2o
fe2 fe3 k na1 cl ca2 mg2 zn2 cu cu2 mn2 cobalt2 ni2 mobd hco3 h2o2 co o2s cyan""".split())
TAG_IDS = set("""atp adp amp camp datp dadp damp nad nadh nadp nadph fad fadh2 coa dpcoa
amet ahcys adn dad_2 ap4a pap paps gtp gdp gmp dgtp dgdp dgmp gsn utp udp ump dutp dudp
dump uri ctp cdp cmp dctp dcdp dcmp cytd itp idp imp ins xmp xtp nmn nicrnt""".split())
ADE_IDS = set("""atp adp amp camp datp dadp damp nad nadh nadp nadph fad fadh2 coa dpcoa
amet ahcys adn dad_2 ap4a pap paps""".split())
TAG_NAME = re.compile(r"adenos|adenyl|guanos|uridin|cytidin|inosin|nicotinamide adenine|"
                      r"coenzyme a|flavin adenine|udp-|gdp-|cdp-|adp-", re.I)
ADE_NAME = re.compile(r"adenos|adenyl|adenine|coenzyme a|nicotinamide adenine|flavin adenine", re.I)

def base(mid):
    for c in COMP:
        if mid.endswith(c):
            return mid[: -len(c)]
    return mid

def is_tag(b, name):
    return (b in TAG_IDS or b.startswith(("udp", "gdp", "cdp")) or b.endswith("coa")
            or bool(TAG_NAME.search(name or "")))

def is_tag_idonly(b, name):
    return b in TAG_IDS or b.startswith(("udp", "gdp", "cdp")) or b.endswith("coa")

def is_ade(b, name):
    return b in ADE_IDS or b.endswith("coa") or bool(ADE_NAME.search(name or ""))

def parse_sbml(path):
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rb") as f:
        root = ET.parse(f).getroot()
    names, deg = {}, {}
    for sp in root.iter():
        if sp.tag.endswith("species"):
            sid = sp.get("id", "")
            if sid.startswith("M_"):
                b = base(sid[2:])
                names.setdefault(b, sp.get("name", ""))
                deg.setdefault(b, 0)
    for rx in root.iter():
        if rx.tag.endswith("reaction"):
            seen = set()
            for sr in rx.iter():
                if sr.tag.endswith("speciesReference"):
                    sid = sr.get("species", "")
                    if sid.startswith("M_"):
                        seen.add(base(sid[2:]))
            for b in seen:
                if b in deg: deg[b] += 1
    return names, deg

r6 = json.load(open(HUB + "results_hub_006.json"))
r7 = json.load(open(HUB + "results_hub_007.json"))
r8 = json.load(open(HUB + "results_hub_008.json"))
CUR = {"iIT341": r6["iIT341_Hpylori"]["R5"]["removed"],
       "iAF692": r6["iAF692_Mbarkeri"]["R5"]["removed"],
       "iND750": r7["detector"]["removed"],
       "iNJ661": r8["detector"]["removed"]}
MODELS = {"iIT341": HUB + "iIT341.xml", "iAF692": HUB + "iAF692.xml",
          "iND750": HUB + "iND750.xml", "iNJ661": HUB + "iNJ661.xml"}

rng = np.random.default_rng(20260825)
out = {}
pool_first, pool_second = [0, 0], [0, 0]   # [tagged, total]
for org in MODELS:
    names, deg = parse_sbml(MODELS[org])
    cur_bases = []
    for c in CUR[org]:
        b = base(c)
        if b not in cur_bases:
            cur_bases.append(b)
    cur_org = [b for b in cur_bases if b not in INORG]
    skel_org = [b for b in names if b not in INORG and b not in cur_bases]
    ctag = [is_tag(b, names.get(b)) for b in cur_org]
    stag = [is_tag(b, names.get(b)) for b in skel_org]
    f_cur, f_skel = np.mean(ctag), np.mean(stag)
    # adenine among tagged currencies
    tagged = [b for b, t in zip(cur_org, ctag) if t]
    ade = [is_ade(b, names.get(b)) for b in tagged]
    f_ade = np.mean(ade) if tagged else np.nan
    # degree-matched null
    def log2bin(d): return int(np.log2(max(d, 1)))
    skel_by_bin = {}
    for b in skel_org:
        skel_by_bin.setdefault(log2bin(deg[b]), []).append(b)
    bins_sorted = sorted(skel_by_bin)
    null_fracs = []
    for _ in range(1000):
        chosen, used = [], set()
        for b in cur_org:
            tb = log2bin(deg[b])
            cands = None
            for delta in range(0, 12):
                for t2 in (tb - delta, tb + delta):
                    if t2 in skel_by_bin:
                        avail = [x for x in skel_by_bin[t2] if x not in used]
                        if avail: cands = avail; break
                if cands: break
            pick = cands[rng.integers(len(cands))]
            used.add(pick); chosen.append(pick)
        null_fracs.append(np.mean([is_tag(x, names.get(x)) for x in chosen]))
    null_fracs = np.array(null_fracs)
    # unmatched permutation null
    perm = np.array([np.mean([is_tag(x, names.get(x))
                    for x in rng.choice(skel_org, size=len(cur_org), replace=False)])
                    for _ in range(1000)])
    # halves by removal order (organic only)
    half = (len(cur_org) + 1) // 2
    fh, sh = cur_org[:half], cur_org[half:]
    pool_first[0] += sum(is_tag(b, names.get(b)) for b in fh); pool_first[1] += len(fh)
    pool_second[0] += sum(is_tag(b, names.get(b)) for b in sh); pool_second[1] += len(sh)
    # id-only sensitivity
    f_cur_id = np.mean([is_tag_idonly(b, names.get(b)) for b in cur_org])
    out[org] = dict(
        cur_org=cur_org, cur_tags=[bool(t) for t in ctag],
        n_cur=len(cur_org), n_skel=len(skel_org),
        f_cur=float(f_cur), f_skel=float(f_skel), diff_pp=float(100 * (f_cur - f_skel)),
        deg_null_q50=float(np.quantile(null_fracs, .5)),
        deg_null_q95=float(np.quantile(null_fracs, .95)),
        deg_null_mean=float(null_fracs.mean()),
        above_q95=bool(f_cur >= np.quantile(null_fracs, .95)),
        below_q50=bool(f_cur <= np.quantile(null_fracs, .5)),
        perm_q95=float(np.quantile(perm, .95)),
        f_ade_among_tagged=float(f_ade), n_tagged=len(tagged),
        f_cur_idonly=float(f_cur_id),
        cur_degrees={b: int(deg[b]) for b in cur_org},
    )
    print(f"{org}: валют(орг)={len(cur_org)} метка={f_cur:.2f} каркас={f_skel:.3f} "
          f"Δ={100*(f_cur-f_skel):+.0f}пп  degnull q50/q95={np.quantile(null_fracs,.5):.2f}/"
          f"{np.quantile(null_fracs,.95):.2f} -> {'>q95' if out[org]['above_q95'] else 'ниже'}  "
          f"аденин|метка={f_ade:.2f} ({len(tagged)} шт)  idonly={f_cur_id:.2f}", flush=True)
    print("   валюты:", {b: ('TAG' if t else '—') for b, t in zip(cur_org, ctag)})

# verdicts
d20 = sum(1 for o in out.values() if o["diff_pp"] >= 20)
q95 = sum(1 for o in out.values() if o["above_q95"])
q50 = sum(1 for o in out.values() if o["below_q50"])
a60 = sum(1 for o in out.values() if o["f_ade_among_tagged"] >= 0.60)
a40 = sum(1 for o in out.values() if o["f_ade_among_tagged"] < 0.40)
pf = pool_first[0] / pool_first[1]; ps = pool_second[0] / pool_second[1]
print(f"\nP-O1: Δ>=+20пп в {d20}/4; >=q95(deg-matched) в {q95}/4  "
      f"-> {'ПОДТВЕРЖДЁН' if (d20>=3 and q95>=3) else ('УБИТ' if q50>=3 else 'не установлен')}")
print(f"P-O2: аденин>=60% в {a60}/4 (убийца <40% в {a40}/4) "
      f"-> {'ПОДТВЕРЖДЁН' if a60>=3 else ('УБИТ' if a40>=3 else 'не установлен')}")
print(f"P-O3 (вторичный): первая половина {pf:.2f} ({pool_first[0]}/{pool_first[1]}) "
      f"vs вторая {ps:.2f} ({pool_second[0]}/{pool_second[1]}) -> {'направление +' if pf>=ps else 'направление −'}")
# LOO
for skip in out:
    d = sum(1 for k, o in out.items() if k != skip and o["diff_pp"] >= 20)
    q = sum(1 for k, o in out.items() if k != skip and o["above_q95"])
    print(f"  LOO без {skip}: Δ20 {d}/3, q95 {q}/3")
json.dump(out, open("/home/claude/ol001_results.json", "w"))
print("-> ol001_results.json")
