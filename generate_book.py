"""Synthetic claim-level book for the LLM-AARS prototype, version 2.

Commercial Auto Liability, accident years 2016-2025, annual development, valued 31 Dec 2025.
Every triangle on the page is rolled up from this one claim list.

What is in the book (all calendar-year effects hit every open accident year in that year):
  * underlying severity trend of 4% a year by accident year (part of the base, not an event)
  * social inflation building on the last three calendar years: CY2023 +5%, CY2024 +8%, CY2025 +12%
    on a growing share of open files, with inflation language in the notes
  * CY2020 settlement slow-down (court closures): ~60% of that year's payments on half the open files
    are deferred into CY2021, with a backlog catch-up note the next year
  * CY2025 fast-track settlement programme closing small open claims a year early (timing only)
  * CY2025 reserve adequacy review raising case reserves on half the files still open (basis change)
  * a heavy severity tail: large losses appear in random cells whenever a large claim pays out
  * subrogation and salvage recoveries on ~3% of closing claims, plus one large recovery placed on
    AY2021 at 48->60 months so a hidden-volatility cell exists for certain
"""
import json, math, random
random.seed(20261002)

AYS = list(range(2016, 2026)); VAL = 2025; NDEV = 10
P = [0.25, 0.48, 0.65, 0.78, 0.87, 0.93, 0.97, 0.99, 1.0, 1.0]
DRIVERS = {
    "inflation":     {"label": "Emerging inflation",        "recurring": True,  "sign": +1},
    "large_loss":    {"label": "Large-loss outlier",        "recurring": False, "sign": +1},
    "recovery":      {"label": "One-time recovery",         "recurring": False, "sign": -1},
    "speedup":       {"label": "Settlement speed-up",       "recurring": False, "sign": +1},
    "strengthening": {"label": "Case reserve strengthening", "recurring": False, "sign": +1},
    "slowdown":      {"label": "Settlement slow-down",      "recurring": False, "sign": -1},
}
VEHICLES = ["box truck", "tractor-trailer", "delivery van", "flatbed", "refrigerated truck", "pickup (fleet)", "tow truck", "dump truck"]
INJ = ["soft-tissue neck/back", "fractured wrist", "lumbar disc herniation", "concussion", "knee ligament tear", "shoulder labral tear", "multiple fractures", "whiplash", "fractured clavicle", "rib fractures"]
STATES = ["TX", "GA", "FL", "IL", "OH", "PA", "NC", "CA", "NJ", "TN"]
ADJ = ["M. Okafor", "L. Petrov", "S. Ramirez", "J. Whitfield", "A. Banerjee", "K. Nguyen", "D. Holloway", "R. Castellano"]

def lognorm(mean, cv):
    s = math.sqrt(math.log(1 + cv * cv)); m = math.log(mean) - s * s / 2
    return math.exp(random.gauss(m, s))

# ---------------------------------------------------------------- claims
claims = []; cid = 0
for ay in AYS:
    n = int(round(62 * 1.03 ** (ay - 2016))) + random.randint(-4, 4)
    sev_level = 36000 * 1.04 ** (ay - 2016)          # underlying 4% severity trend by AY
    for _ in range(n):
        cid += 1
        r = random.choices([0, 1, 2], [0.80, 0.17, 0.03])[0]
        c = min(9, max(r, r + int(random.expovariate(1 / 3.0)) + (1 if random.random() < 0.75 else 0)))
        U = lognorm(sev_level, 0.8)
        large = random.random() < 0.025
        if large: U *= random.uniform(6, 14)
        claims.append(dict(id=f"CA-{ay}-{cid:04d}", ay=ay, r=r, c=c, U=U, large=large, state=random.choice(STATES),
                           vehicle=random.choice(VEHICLES), injury=random.choice(INJ) if not large else "multiple fractures",
                           adjuster=random.choice(ADJ), litigated=(random.random() < 0.18) or large,
                           noise=[random.uniform(0.92, 1.08) for _ in range(NDEV)], adeq=random.gauss(0.03, 0.04),
                           events=[], notes=[]))

def base_paid(cl, d, c=None):
    r = cl["r"]; c = cl["c"] if c is None else c
    if d < r: return 0.0
    if d >= c: return 1.0
    g = lambda i: P[i] if i >= 0 else 0.0
    denom = g(c) - g(r - 1)
    return (g(d) - g(r - 1)) / denom if denom > 0 else 1.0

def cum_paid_base(cl, d):
    if d < cl["r"]: return 0.0
    if d >= cl["c"]: return cl["U"]
    cpat = cl.get("c_pat", cl["c"])
    if d >= cpat: return cl["U"]
    return cl["U"] * min(0.98, base_paid(cl, d, cpat) * cl["noise"][d])

def inc_paid_base(cl, d):
    return cum_paid_base(cl, d) - (cum_paid_base(cl, d - 1) if d > 0 else 0.0)

def case_base(cl, d):
    """case reserve on an open claim: light early, catching up with age (reported losses develop upward)"""
    if cl["r"] <= d < cl["c"]:
        age = d - cl["r"]
        adequacy = min(1.0, 0.62 + 0.09 * age) * (1 + cl["adeq"])
        return max(0.0, (cl["U"] - cum_paid_base(cl, d)) * adequacy)
    return 0.0

def ndev_avail(ay): return VAL - ay + 1
def by_ay(ay): return [cl for cl in claims if cl["ay"] == ay]

def add_event(cl, d, driver, dpaid, dcase, note, amt=None, amt_inc=None):
    """dpaid/dcase change the book; amt/amt_inc are what the note explains (default: the same)."""
    cl["events"].append(dict(dev=d, driver=driver, dpaid=round(dpaid), dcase=round(dcase),
                             amt=round(dpaid if amt is None else amt), amtInc=round(dpaid + dcase if amt_inc is None else amt_inc)))
    cl["notes"].append(dict(dev=d, driver=driver, text=note))

# ---------------------------------------------------------------- note text
INFL_NOTES = [
    lambda cl, y: f"Medical specials received for {cl['injury']}: billed charges running {random.randint(14, 24)}% above the fee schedule we priced at. Physical therapy extended. Reserve increased.",
    lambda cl, y: f"Repair estimate on third-party {cl['vehicle']} revised upward; parts and labor rates up ~{random.randint(12, 20)}% year on year, shop quoting a {random.randint(4, 8)}-week backlog. Rental days extended accordingly.",
    lambda cl, y: f"Plaintiff counsel demand letter references two recent {cl['state']} verdicts on comparable {cl['injury']} claims, both well above our historical settlement range. Adjusted evaluation upward.",
    lambda cl, y: f"Surgical recommendation for {cl['injury']}; hospital facility fee quoted {random.randint(18, 30)}% above what we saw on similar claims two years ago. Case reserve revised.",
    lambda cl, y: f"Settlement authority increased after mediation. Mediator noted {cl['state']} juries trending higher on pain-and-suffering awards; our offer at prior benchmarks was rejected twice.",
    lambda cl, y: f"Wage-loss component recalculated at current wage levels; claimant's employer confirms a {random.randint(6, 11)}% raise since DOL. Future medical priced at {y} CPT rates rather than policy-year rates.",
    lambda cl, y: f"Attorney-represented claimant declined our evaluated offer; counsel citing nuclear verdict trend in {cl['state']} venue. Authority raised {random.randint(15, 35)}% to resolve.",
]
LARGE_NOTES = [
    lambda cl: f"Jury verdict returned in {cl['state']} against insured on {cl['injury']}, well in excess of policy limits with a punitive component. Limits paid plus defense costs. Single-claim event; no other open file shares this fact pattern.",
    lambda cl: f"Catastrophic loss: {cl['vehicle']} crossed median, multi-vehicle, fatalities. Full policy limits tendered to avoid bad-faith exposure. Flagged as large loss for reinsurance notification.",
    lambda cl: f"Policy limits tendered on {cl['injury']} claim following life-care plan; excess exposure referred to umbrella carrier. Large-loss report filed.",
]
RECOV_NOTES = [
    lambda cl: f"Subrogation recovery received from at-fault carrier following arbitration award; one-time credit applied against paid loss. Recovery is not expected to repeat on other files.",
    lambda cl: f"Salvage proceeds on the insured {cl['vehicle']} and a contribution from the co-defendant's carrier credited to the file. One-time credit against paid loss.",
    lambda cl: f"Deductible reimbursement and partial subrogation recovery from the third-party carrier received; file credited. Non-recurring.",
]
SPEED_NOTES = [
    lambda cl: f"File moved to the new fast-track settlement program (launched Q1 2025). Settled {cl['injury']} within 45 days of demand at evaluated value; no change to estimated ultimate, payment simply made earlier than the historical pattern.",
    lambda cl: f"Fast-track: pre-suit resolution with plaintiff firm under the 2025 early-settlement protocol. Paid at reserve. Closing file.",
    lambda cl: f"Settled under the early-resolution initiative. Claim paid roughly one year ahead of where our historical payment pattern would have placed it; indemnity consistent with original case reserve.",
    lambda cl: f"Early-settlement protocol applied: adjuster authority raised, claim closed without litigation. Severity unchanged versus case reserve; timing accelerated.",
]
STRENGTH_NOTES = [
    lambda cl: f"Case reserve reviewed under the 2025 reserve adequacy initiative. Increased to full expected value including future medical on {cl['injury']}. No new information received on the claim itself; this is a change in reserving basis.",
    lambda cl: f"Reserve adequacy review (claims leadership directive, 2025): case reserve raised to the upper end of the evaluation range. Claim facts unchanged.",
    lambda cl: f"Supervisor audit under the new adequacy guidelines: case reserve increased to include defence costs and a litigation contingency. No change in expected settlement value from the adjuster's view.",
]
SLOW_NOTES = [
    lambda cl: f"{cl['state']} courts closed for in-person proceedings (COVID-19); trial date vacated and settlement conference postponed to 2021. No indemnity payment this period; evaluation unchanged.",
    lambda cl: f"Claimant's treatment and IME delayed by pandemic restrictions; demand package not expected until next year. Payment deferred, reserve unchanged.",
    lambda cl: f"Mediation rescheduled to 2021 due to court backlog. Settlement value unchanged; timing slipped.",
]
CATCHUP_NOTES = [
    lambda cl: f"Backlog cleared: {cl['injury']} claim settled at the rescheduled 2021 mediation. Payment includes the amount deferred from 2020; no change to evaluated value.",
    lambda cl: f"Court calendar reopened; settlement finalised at the evaluation reached before the 2020 delays. Payment this period reflects the deferred 2020 instalment as well.",
]
OPEN_NOTES = [
    lambda cl: f"FNOL received. Insured {cl['vehicle']} rear-ended claimant vehicle at signalled intersection, {cl['state']}. Claimant reports {cl['injury']}. Liability appears clear against insured. Initial reserve set.",
    lambda cl: f"New loss. Insured driver of {cl['vehicle']} changed lanes into claimant. Police report obtained, insured cited. Claimant treating for {cl['injury']}. Reserve posted on initial information.",
    lambda cl: f"Claim reported. Low-speed contact in parking lot involving insured {cl['vehicle']}; claimant alleges {cl['injury']}. Liability disputed, investigating.",
]
MID_NOTES = [
    lambda cl: f"Medical records received; treatment for {cl['injury']} consistent with mechanism. Reserve reviewed, no change.",
    lambda cl: f"Status: claimant still treating. Demand not yet received. Diary 90 days.",
    lambda cl: f"Attorney representation letter received ({cl['state']} plaintiff firm). Reserve reviewed in light of representation.",
    lambda cl: f"Partial payment issued for property damage to claimant vehicle. Bodily injury component remains open.",
    lambda cl: f"IME scheduled for {cl['injury']}. Case reserve held pending IME findings.",
]
CLOSE_NOTES = [
    lambda cl: f"Settled {cl['injury']} claim within authority. Release executed, payment issued. File closed.",
    lambda cl: f"Resolved at mediation. Final indemnity paid, defense closed. Closing file.",
    lambda cl: f"Claim closed. Settlement in line with case reserve.",
]
LIT_NOTE = lambda cl: f"Suit filed in {cl['state']} state court. Defense counsel assigned. Reserve reviewed for litigation expense."

# ---------------------------------------------------------------- calendar-year effects
def dev_of(cl, cy): return cy - cl["ay"]

# 1. CY2020 slow-down with CY2021 catch-up
for cl in claims:
    d = dev_of(cl, 2020)
    if d < 0 or not (cl["r"] <= d < cl["c"]) or random.random() > 0.35: continue
    inc = inc_paid_base(cl, d)
    if inc <= 0 or d + 1 >= ndev_avail(cl["ay"]): continue
    defer = 0.7 * inc
    add_event(cl, d, "slowdown", -defer, 0.0, random.choice(SLOW_NOTES)(cl))          # case reserve stays (reported unchanged)
    add_event(cl, d + 1, "slowdown", +defer, 0.0, random.choice(CATCHUP_NOTES)(cl))
# the deferred money is still owed: keep case reserve for it in 2020 (handled in dev_series via dcase=0 on base case)

# 2. social inflation, CY2023-2025
for cy, rate, share in [(2023, 0.05, 0.30), (2024, 0.08, 0.45), (2025, 0.12, 0.60)]:
    for cl in claims:
        d = dev_of(cl, cy)
        if d < 0 or not (cl["r"] <= d - 1 < cl["c"]) or d >= ndev_avail(cl["ay"]): continue
        inc = inc_paid_base(cl, d)
        if inc <= 0 or random.random() > share: continue
        remaining_prev = max(0.0, cl["U"] - cum_paid_base(cl, d - 1))
        lit = 3.0 if cl["litigated"] else 1.0                        # social inflation bites hardest on litigated files
        dp = lit * rate * remaining_prev * random.uniform(0.5, 1.0)  # costs on everything still to be paid are higher
        dc = (lit * 0.6 * rate * max(0.0, cl["U"] - cum_paid_base(cl, d))) if cl["c"] > d else 0.0
        add_event(cl, d, "inflation", dp, dc, random.choice(INFL_NOTES)(cl, cy))

# 3. CY2025 fast-track: close small open claims a year early
for cl in claims:
    d = dev_of(cl, 2025)
    if d < 1 or not (cl["r"] <= d < cl["c"]) or d >= ndev_avail(cl["ay"]): continue
    remaining = cl["U"] - cum_paid_base(cl, d)
    if remaining <= 0 or remaining > 30000 or random.random() > 0.5: continue
    cl["c_pat"] = cl["c"]; cl["c"] = d
    add_event(cl, d, "speedup", 0.0, 0.0, random.choice(SPEED_NOTES)(cl), amt=remaining, amt_inc=0.0)

# 4. CY2025 reserve adequacy review on files still open
for cl in claims:
    d = dev_of(cl, 2025)
    if d < 0 or not (cl["r"] <= d < cl["c"]) or d >= ndev_avail(cl["ay"]) or random.random() > 0.7: continue
    cb = case_base(cl, d)
    if cb <= 0: continue
    add_event(cl, d, "strengthening", 0.0, random.uniform(0.20, 0.35) * cb, random.choice(STRENGTH_NOTES)(cl))

# 5. large losses: tag every period in which a large claim pays well above a typical claim
LARGE_CONT = [
    lambda cl: f"Continuing payments on the large loss: structured settlement instalment and ongoing medical on {cl['injury']} paid this period. Amount in line with the life-care plan; no new development.",
    lambda cl: f"Large-loss file: defence costs and partial indemnity paid pending final resolution. Excess carrier notified; reinsurance recoverable tracked separately.",
]
for cl in claims:
    if not cl["large"]: continue
    nd = ndev_avail(cl["ay"]); first = True
    for d in range(cl["r"], min(nd, cl["c"] + 1)):
        inc = inc_paid_base(cl, d)
        typical = 36000 * 1.04 ** (cl["ay"] - 2016) * (base_paid(cl, d) - (base_paid(cl, d - 1) if d > cl["r"] else 0.0))
        excess = inc - max(typical, 0.0)
        if excess > 30000:
            add_event(cl, d, "large_loss", 0.0, 0.0, (random.choice(LARGE_NOTES) if first else random.choice(LARGE_CONT))(cl), amt=excess, amt_inc=excess)
            first = False

# 6. recoveries on ~3% of closing claims, plus one large recovery on AY2021 at 48->60 months
for cl in claims:
    if cl["c"] >= ndev_avail(cl["ay"]) or cl["c"] == cl["r"] or random.random() > 0.03: continue
    if any(e["dev"] == cl["c"] and e["driver"] in ("speedup", "slowdown") for e in cl["events"]): continue
    rec = -random.uniform(0.2, 0.6) * cl["U"]
    add_event(cl, cl["c"], "recovery", rec, 0.0, random.choice(RECOV_NOTES)(cl))
big = sorted([cl for cl in by_ay(2021) if cl["r"] == 0 and cl["c"] >= 5 and not cl["large"]], key=lambda c: -c["U"])[0]
base21 = sum(cum_paid_base(cl, 3) for cl in by_ay(2021))
infl21 = sum(e["dpaid"] for cl in by_ay(2021) for e in cl["events"] if e["dev"] == 4 and e["driver"] == "inflation")
big["events"] = [e for e in big["events"] if e["dev"] != 4]; big["notes"] = [n for n in big["notes"] if n["dev"] != 4]
add_event(big, 4, "recovery", -min(infl21 * random.uniform(0.95, 1.05), 0.6 * cum_paid_base(big, 3)), 0.0, RECOV_NOTES[0](big))

# ---------------------------------------------------------------- routine notes
for cl in claims:
    nd = ndev_avail(cl["ay"])
    cl["notes"].append(dict(dev=cl["r"], driver=None, text=random.choice(OPEN_NOTES)(cl)))
    for d in range(cl["r"] + 1, min(cl["c"], nd)):
        if random.random() < 0.5 and not any(n["dev"] == d for n in cl["notes"]):
            cl["notes"].append(dict(dev=d, driver=None, text=random.choice(MID_NOTES)(cl)))
    if cl["litigated"] and cl["c"] > cl["r"] + 1 and cl["r"] + 1 < nd and not any(n["dev"] == cl["r"] + 1 for n in cl["notes"]):
        cl["notes"].append(dict(dev=cl["r"] + 1, driver=None, text=LIT_NOTE(cl)))
    if cl["c"] < nd and not any(n["dev"] == cl["c"] and n["driver"] for n in cl["notes"]):
        cl["notes"].append(dict(dev=cl["c"], driver=None, text=random.choice(CLOSE_NOTES)(cl)))
    cl["notes"].sort(key=lambda n: n["dev"])

# ---------------------------------------------------------------- development with events
for cl in claims:
    nd = ndev_avail(cl["ay"]); paid, case, status = [], [], []
    for d in range(nd):
        p = cum_paid_base(cl, d) + sum(e["dpaid"] for e in cl["events"] if e["dev"] <= d)
        if d < cl["r"]: cs, st = 0.0, "unreported"
        elif d >= cl["c"]: cs, st = 0.0, "closed"
        else:
            cs = case_base(cl, d) + sum(e["dcase"] for e in cl["events"] if e["dev"] <= d)
            # money deferred by the slow-down is still owed: hold it in case reserve while open
            cs += -sum(e["dpaid"] for e in cl["events"] if e["driver"] == "slowdown" and e["dev"] <= d)
            st = "open"
        paid.append(round(p)); case.append(round(max(0.0, cs))); status.append(st)
    cl["paid"], cl["case"], cl["status"] = paid, case, status
    cl["incurred"] = [a + b for a, b in zip(paid, case)]

# ---------------------------------------------------------------- triangles
def tri(fn):
    out = []
    for ay in AYS:
        nd = ndev_avail(ay); out.append([fn(ay, d) for d in range(nd)] + [None] * (NDEV - nd))
    return out
T = {
    "reported": tri(lambda ay, d: sum(1 for cl in by_ay(ay) if cl["r"] <= d)),
    "closed":   tri(lambda ay, d: sum(1 for cl in by_ay(ay) if cl["c"] <= d)),
    "paid":     tri(lambda ay, d: sum(cl["paid"][d] for cl in by_ay(ay))),
    "incurred": tri(lambda ay, d: sum(cl["incurred"][d] for cl in by_ay(ay))),
}
T["severity"] = tri(lambda ay, d: round(T["incurred"][AYS.index(ay)][d] / max(1, T["reported"][AYS.index(ay)][d])))
T["open"] = tri(lambda ay, d: T["reported"][AYS.index(ay)][d] - T["closed"][AYS.index(ay)][d])
T["avgcase"] = tri(lambda ay, d: round(sum(cl["case"][d] for cl in by_ay(ay)) / max(1, T["open"][AYS.index(ay)][d])))

def factors(M):
    return [[(round(r[d + 1] / r[d], 4) if (r[d] and r[d + 1] is not None and r[d] > 0) else None) for d in range(NDEV - 1)] for r in M]

def tagged_amount(kind, ay, d):
    """all movement explained by driver notes in AY ay during dev d (recurring and one-off alike)"""
    return sum((e["amt"] if kind == "paid" else e["amtInc"]) for cl in by_ay(ay) for e in cl["events"] if e["dev"] == d)

def decompose(kind):
    M = T[kind]; cells = {}
    for i, ay in enumerate(AYS):
        for d in range(NDEV - 1):
            if M[i][d + 1] is None or not M[i][d]: continue
            obs = M[i][d + 1] / M[i][d]
            # norm: clean development of the other accident years, every tagged movement stripped out
            num = den = 0.0; others = []
            for j, row in enumerate(M):
                if j == i or row[d + 1] is None or not row[d]: continue
                adj = row[d + 1] - tagged_amount(kind, AYS[j], d + 1)
                num += adj; den += row[d]; others.append(adj / row[d])
            base = num / den if den else obs
            contrib = {}; cls = set()
            for cl in by_ay(ay):
                for e in cl["events"]:
                    if e["dev"] != d + 1: continue
                    amt = e["amt"] if kind == "paid" else e["amtInc"]
                    if not amt: continue
                    contrib[e["driver"]] = contrib.get(e["driver"], 0) + amt; cls.add(cl["id"])
            parts = {k: round(v / M[i][d], 4) for k, v in contrib.items()}
            explained = sum(parts.values()); resid = round(obs - base - explained, 4)
            sugg = base + sum(v for k, v in parts.items() if DRIVERS[k]["recurring"])
            gross = sum(abs(v) for v in parts.values()); dev_pct = (obs - base) / base
            sd = (sum((x - base) ** 2 for x in others) / max(1, len(others) - 1)) ** 0.5 if len(others) > 1 else 0
            z = (obs - base) / sd if sd > 0 else 0
            flag = None
            if abs(dev_pct) > 0.05 and (abs(z) > 1.8 or abs(dev_pct) > 0.065): flag = "spike" if dev_pct > 0 else "drop"
            elif gross > 0.08 and abs(obs - base) < 0.05: flag = "hidden"
            key = "paid" if kind == "paid" else "incurred"
            movers = sorted(((cl[key][d + 1] - cl[key][d], cl["id"]) for cl in by_ay(ay)), key=lambda t: -abs(t[0]))[:5]
            cells[f"{ay}-{d}"] = dict(ay=ay, dev=d, observed=round(obs, 4), baseline=round(base, 4), parts=parts, residual=resid,
                                      suggested=round(sugg, 4), gross=round(gross, 4), flag=flag, z=round(z, 2),
                                      claims=sorted(cls), movers=[dict(id=m[1], amt=round(m[0])) for m in movers], incr=M[i][d + 1] - M[i][d])
    return cells

CELLS = {"paid": decompose("paid"), "incurred": decompose("incurred")}
out = dict(
    meta=dict(line="Commercial Auto Liability", valuation="31 Dec 2025", ays=AYS, ndev=NDEV,
              devLabels=[f"{12*(d+1)}" for d in range(NDEV)], drivers=DRIVERS, generated="synthetic v2; calendar-year effects seeded for demonstration"),
    triangles=T, factors={k: factors(T[k]) for k in ["reported", "closed", "paid", "incurred", "severity", "avgcase"]}, cells=CELLS,
    claims=[dict(id=cl["id"], ay=cl["ay"], r=cl["r"], c=cl["c"], state=cl["state"], vehicle=cl["vehicle"], injury=cl["injury"],
                 adjuster=cl["adjuster"], litigated=cl["litigated"], paid=cl["paid"], case=cl["case"], status=cl["status"],
                 events=cl["events"], notes=cl["notes"]) for cl in claims],
)
import sys
path = sys.argv[1] if len(sys.argv) > 1 else "data/book.json"
json.dump(out, open(path, "w"))
if __name__ == "__main__":
    import collections
    print("claims", len(claims), "notes", sum(len(c["notes"]) for c in claims), "events", collections.Counter(e["driver"] for c in claims for e in c["events"]))
    print("paid flags:", [(k, v["flag"]) for k, v in CELLS["paid"].items() if v["flag"]])
    print("incurred flags:", [(k, v["flag"]) for k, v in CELLS["incurred"].items() if v["flag"]])
    for ay in AYS:
        nd = ndev_avail(ay)
        if nd >= 2:
            c = CELLS["paid"][f"{ay}-{nd-2}"]; print(ay, f"d{nd-2}", "obs", c["observed"], "base", c["baseline"], {k: round(v, 3) for k, v in c["parts"].items()}, "resid", c["residual"], c["flag"])
