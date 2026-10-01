"""Synthetic claim-level book for the LLM-AARS prototype.
Commercial Auto Liability, AY 2016-2025, valued 31 Dec 2025, annual development.
Every triangle is derived from the same claim list, so the views reconcile.
"""
import json, random, math
random.seed(20261001)

AYS = list(range(2016, 2026))
VAL = 2025
NDEV = 10
# cumulative paid pattern (fraction of ultimate) by dev index 0..9  (12m..120m)
P = [0.40, 0.62, 0.76, 0.836, 0.90, 0.945, 0.975, 0.99, 1.0, 1.0]
DRIVERS = {
    "inflation":  {"label": "Emerging inflation", "recurring": True,  "sign": +1},
    "large_loss": {"label": "Large-loss outlier", "recurring": False, "sign": +1},
    "recovery":   {"label": "One-time recovery",  "recurring": False, "sign": -1},
    "speedup":    {"label": "Settlement speed-up", "recurring": False, "sign": +1},
    "strengthening": {"label": "Case reserve strengthening", "recurring": False, "sign": +1},
}

VEHICLES = ["box truck", "tractor-trailer", "delivery van", "flatbed", "refrigerated truck", "pickup (fleet)", "tow truck", "dump truck"]
INJ = ["soft-tissue neck/back", "fractured wrist", "lumbar disc herniation", "concussion", "knee ligament tear", "shoulder labral tear", "multiple fractures", "whiplash", "fractured clavicle", "rib fractures"]
STATES = ["TX", "GA", "FL", "IL", "OH", "PA", "NC", "CA", "NJ", "TN"]
ADJ = ["M. Okafor", "L. Petrov", "S. Ramirez", "J. Whitfield", "A. Banerjee", "K. Nguyen", "D. Holloway", "R. Castellano"]

def lognorm(mean, cv):
    s = math.sqrt(math.log(1 + cv * cv)); m = math.log(mean) - s * s / 2
    return math.exp(random.gauss(m, s))

claims = []
cid = 0
for ay in AYS:
    n = random.randint(68, 80)
    for _ in range(n):
        cid += 1
        r = random.choices([0, 1, 2], [0.80, 0.17, 0.03])[0]
        # close dev: geometric after report, capped
        c = r + min(9, int(random.expovariate(1 / 2.2)) + (1 if random.random() < 0.5 else 0))
        c = min(9, max(c, r))
        U = lognorm(38000, 0.7)
        state = random.choice(STATES)
        claims.append(dict(
            id=f"CA-{ay}-{cid:04d}", ay=ay, r=r, c=c, U=U, state=state,
            vehicle=random.choice(VEHICLES), injury=random.choice(INJ),
            adjuster=random.choice(ADJ), litigated=random.random() < 0.18,
            events=[], notes=[]))

def base_paid(cl, d, c=None):
    """cumulative paid fraction at dev d, no events"""
    r = cl["r"]; c = cl["c"] if c is None else c
    if d < r: return 0.0
    if d >= c: return 1.0
    g = lambda i: P[i] if i >= 0 else 0.0
    denom = g(c) - g(r - 1)
    return (g(d) - g(r - 1)) / denom if denom > 0 else 1.0

for cl in claims:
    # per-claim noise on the pattern
    cl["noise"] = [random.uniform(0.92, 1.08) for _ in range(NDEV)]
    cl["adeq"] = random.gauss(0.03, 0.04)  # case reserve adequacy noise

def cum_paid_base(cl, d):
    if d < cl["r"]: return 0.0
    if d >= cl["c"]: return cl["U"]
    cpat = cl.get("c_pat", cl["c"])
    if d >= cpat: return cl["U"]
    return cl["U"] * min(0.98, base_paid(cl, d, cpat) * cl["noise"][d])

def inc_paid_base(cl, d):
    return cum_paid_base(cl, d) - (cum_paid_base(cl, d - 1) if d > 0 else 0.0)

def ndev_avail(ay): return VAL - ay + 1

# --- seed driver events -------------------------------------------------
def add_event(cl, d, driver, dpaid, dcase, note):
    cl["events"].append(dict(dev=d, driver=driver, dpaid=round(dpaid), dcase=round(dcase)))
    cl["notes"].append(dict(dev=d, driver=driver, text=note))

def cum_paid_at(ay, d):
    return sum(cum_paid_base(cl, d) for cl in claims if cl["ay"] == ay)

def open_at(ay, d):
    return [cl for cl in claims if cl["ay"] == ay and cl["r"] <= d < cl["c"]]

def seed_inflation(ay, d, share, n_frac=0.45, note_pool=None):
    """raise incremental paid in dev d by share x cumulative paid at d-1, spread over a subset of open claims"""
    base = cum_paid_at(ay, d - 1)
    target = share * base
    cands = [cl for cl in open_at(ay, d - 1) if inc_paid_base(cl, d) > 0]
    random.shuffle(cands)
    k = max(3, int(len(cands) * n_frac))
    chosen = cands[:k]
    tot = sum(inc_paid_base(cl, d) for cl in chosen)
    for cl in chosen:
        dp = target * inc_paid_base(cl, d) / tot
        dc = min(dp * random.uniform(0.6, 1.1), 0.5 * max(0.0, cl["U"] - cum_paid_base(cl, d))) if cl["c"] > d else 0.0
        txt = random.choice(note_pool)(cl)
        add_event(cl, d, "inflation", dp, dc, txt)

INFL_NOTES = [
    lambda cl: f"Medical specials received for {cl['injury']}: billed charges running 16-22% above the 2021 fee schedule we priced at. Physical therapy extended from 12 to 20 visits. Reserve increased.",
    lambda cl: f"Repair estimate on third-party {cl['vehicle']} revised upward; parts and labor rates up ~18% year on year, shop quoting 6-week backlog. Rental days extended accordingly.",
    lambda cl: f"Plaintiff counsel demand letter references two recent {cl['state']} verdicts on comparable {cl['injury']} claims, both roughly double our historical settlement range. Adjusted evaluation upward.",
    lambda cl: f"Surgical recommendation for {cl['injury']}; hospital facility fee quoted 25% above what we saw on similar claims in 2022. Case reserve revised.",
    lambda cl: f"Settlement authority increased after mediation. Mediator noted {cl['state']} juries trending higher on pain-and-suffering awards; our offer at prior benchmarks was rejected twice.",
    lambda cl: f"Wage-loss component recalculated at current wage levels; claimant's employer confirms 9% raise since DOL. Future medical priced at 2025 CPT rates rather than policy-year rates.",
]
LARGE_NOTES = [
    lambda cl: f"Jury verdict returned in {cl['state']} against insured on {cl['injury']}, well in excess of policy limits with a punitive component. Limits paid plus defense costs. Single-claim event, no indication other open files share this fact pattern.",
    lambda cl: f"Catastrophic loss: {cl['vehicle']} crossed median, multi-vehicle, two fatalities. Full policy limits tendered to avoid bad-faith exposure. Flagged as large loss for reinsurance notification.",
]
RECOV_NOTES = [
    lambda cl: f"Subrogation recovery received from at-fault carrier following arbitration award; one-time credit applied against paid loss. File closing. Recovery is not expected to repeat on other files in this accident year.",
]
SPEED_NOTES = [
    lambda cl: f"File moved to the new fast-track settlement program (launched Q1 2025). Settled {cl['injury']} within 45 days of demand at evaluated value; no change to estimated ultimate, payment simply made earlier than the historical pattern.",
    lambda cl: f"Fast-track: pre-suit resolution with plaintiff firm under the 2025 early-settlement protocol. Paid at reserve. Closing file.",
    lambda cl: f"Settled under the early-resolution initiative. Claim paid roughly one year ahead of where our historical payment pattern would have placed it; indemnity amount consistent with original case reserve.",
    lambda cl: f"Early-settlement protocol applied: adjuster authority raised, claim closed without litigation. Severity unchanged versus case reserve; timing accelerated.",
]

# Trap 1: False stability -- AY2021, dev 3->4 (48->60m), CY2025 diagonal
seed_inflation(2021, 4, 0.15, note_pool=INFL_NOTES)
# recovery on one large early-reported claim in AY2021
big = sorted([cl for cl in claims if cl["ay"] == 2021 and cl["r"] == 0 and cl["c"] >= 5], key=lambda c: -c["U"])[0]
base21 = cum_paid_at(2021, 3)
big["U"] = 0.19 * base21 / 0.836 * 1.0  # large enough that paid-to-date at dev3 ~ 0.19 x cum
big["c"] = 4; big["noise"] = [1.0] * NDEV
rec = -0.15 * base21
add_event(big, 4, "recovery", rec, 0.0, RECOV_NOTES[0](big))
big["injury"] = "multiple fractures"; big["litigated"] = True

# Trap 2: Masked inflation -- AY2022, dev 2->3 (36->48m)
seed_inflation(2022, 3, 0.16, n_frac=0.5, note_pool=INFL_NOTES)
ll = sorted([cl for cl in claims if cl["ay"] == 2022 and cl["r"] <= 1 and cl["c"] >= 3], key=lambda c: -c["U"])[1]
base22 = cum_paid_at(2022, 2)
ll["c"] = 3; ll["noise"] = [1.0] * NDEV; ll["litigated"] = True; ll["injury"] = "multiple fractures"
dp = 0.04 * base22
ll["U"] = ll["U"] + dp
add_event(ll, 3, "large_loss", dp, 0.0, LARGE_NOTES[0](ll))

# Trap 3: Process speed-up -- AY2023, dev 1->2 (24->36m)
base23 = cum_paid_at(2023, 1)
cands = [cl for cl in claims if cl["ay"] == 2023 and cl["r"] <= 1 and cl["c"] >= 3]
cands.sort(key=lambda cl: (cl["U"] - cum_paid_base(cl, 2)))
cands = [cl for cl in cands if cl["U"] - cum_paid_base(cl, 2) > 0][:26]
tot = 0.0; chosen = []
for cl in cands:
    # pull paid forward: claim closes at dev 2 instead of later, paid jumps to U
    ahead = cl["U"] - cum_paid_base(cl, 2)
    if ahead <= 0: continue
    chosen.append((cl, ahead)); tot += ahead
    if tot >= 0.10 * base23: break
for cl, ahead in chosen:
    cl["c_pat"] = cl["c"]; cl["c"] = 2
    add_event(cl, 2, "speedup", 0.0, 0.0, random.choice(SPEED_NOTES)(cl))
    cl["speedup_excess"] = ahead
# small ambient inflation elsewhere on the CY2025 diagonal
seed_inflation(2023, 2, 0.03, n_frac=0.25, note_pool=INFL_NOTES)
STRENGTH_NOTES = [
    lambda cl: f"Case reserve reviewed under the 2025 reserve adequacy initiative. Increased to full expected value including future medical on {cl['injury']}. No new information received on the claim itself; this is a change in reserving basis.",
    lambda cl: f"Reserve adequacy review (claims leadership directive, 2025): case reserve raised to the upper end of the evaluation range. Claim facts unchanged.",
    lambda cl: f"Supervisor audit under the new adequacy guidelines: case reserve increased to include defence costs and a litigation contingency. No change in expected settlement value from the adjuster's view.",
]
def seed_strengthening(ay, d, share, n_frac=0.6):
    """raise case reserves at dev d by share x reported at d-1 on a subset of claims still open at d"""
    i = AYS.index(ay)
    base_rep = sum(cum_paid_base(cl, d - 1) + max(0.0, (cl["U"] - cum_paid_base(cl, d - 1)) * (1 + cl["adeq"])) * (1 if cl["r"] <= d - 1 < cl["c"] else 0) for cl in by_ay_(ay))
    target = share * base_rep
    cands = [cl for cl in claims if cl["ay"] == ay and cl["r"] <= d < cl["c"]]
    random.shuffle(cands)
    chosen = cands[:max(3, int(len(cands) * n_frac))]
    tot = sum(cl["U"] - cum_paid_base(cl, d) for cl in chosen) or 1.0
    for cl in chosen:
        dc = target * (cl["U"] - cum_paid_base(cl, d)) / tot
        add_event(cl, d, "strengthening", 0.0, dc, random.choice(STRENGTH_NOTES)(cl))
def by_ay_(ay): return [cl for cl in claims if cl["ay"] == ay]
seed_strengthening(2020, 5, 0.10)
seed_strengthening(2024, 1, 0.08)
# Older one-off: AY2018 dev 2->3 catastrophic large loss (explained, non-recurring)
cat = sorted([cl for cl in claims if cl["ay"] == 2018 and cl["r"] == 0 and cl["c"] >= 3], key=lambda c: -c["U"])[0]
base18 = cum_paid_at(2018, 2)
dp = 0.12 * base18
cat["U"] += dp; cat["c"] = 3; cat["litigated"] = True; cat["injury"] = "multiple fractures"
add_event(cat, 3, "large_loss", dp, 0.0, LARGE_NOTES[1](cat))

# --- routine notes -------------------------------------------------------
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
LIT_NOTES = [
    lambda cl: f"Suit filed in {cl['state']} state court. Defense counsel assigned. Reserve reviewed for litigation expense.",
]
for cl in claims:
    nd = ndev_avail(cl["ay"])
    cl["notes"].append(dict(dev=cl["r"], driver=None, text=random.choice(OPEN_NOTES)(cl)))
    for d in range(cl["r"] + 1, min(cl["c"], nd)):
        if random.random() < 0.55 and not any(n["dev"] == d for n in cl["notes"]):
            cl["notes"].append(dict(dev=d, driver=None, text=random.choice(MID_NOTES)(cl)))
    if cl["litigated"] and cl["c"] > cl["r"] + 1 and cl["r"] + 1 < nd:
        cl["notes"].append(dict(dev=cl["r"] + 1, driver=None, text=LIT_NOTES[0](cl)))
    if cl["c"] < nd and not any(n["dev"] == cl["c"] and n["driver"] for n in cl["notes"]):
        cl["notes"].append(dict(dev=cl["c"], driver=None, text=random.choice(CLOSE_NOTES)(cl)))
    cl["notes"].sort(key=lambda n: n["dev"])

# --- claim-level development with events ---------------------------------
def dev_series(cl):
    nd = ndev_avail(cl["ay"])
    paid, case, status = [], [], []
    for d in range(nd):
        p = cum_paid_base(cl, d)
        p += sum(e["dpaid"] for e in cl["events"] if e["dev"] <= d)
        if d < cl["r"]:
            cs = 0.0; st = "unreported"
        elif d >= cl["c"]:
            cs = 0.0; st = "closed"
        else:
            cs = max(0.0, (cl["U"] - cum_paid_base(cl, d)) * (1 + cl["adeq"]))
            cs += sum(e["dcase"] for e in cl["events"] if e["dev"] <= d)
            st = "open"
        paid.append(round(p)); case.append(round(cs)); status.append(st)
    return paid, case, status

for cl in claims:
    cl["paid"], cl["case"], cl["status"] = dev_series(cl)
    cl["incurred"] = [p + c for p, c in zip(cl["paid"], cl["case"])]

# --- triangles -------------------------------------------------------------
def tri(fn):
    out = []
    for ay in AYS:
        nd = ndev_avail(ay)
        row = [fn(ay, d) for d in range(nd)] + [None] * (NDEV - nd)
        out.append(row)
    return out

def by_ay(ay): return [cl for cl in claims if cl["ay"] == ay]
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
    F = []
    for row in M:
        fr = []
        for d in range(NDEV - 1):
            a, b = row[d], row[d + 1]
            fr.append(round(b / a, 4) if (a and b is not None and a > 0) else None)
        F.append(fr)
    return F

def vw_baseline(M, i, d):
    """volume-weighted average factor for column d excluding AY i"""
    num = den = 0.0
    for j, row in enumerate(M):
        if j == i or row[d + 1] is None or not row[d]: continue
        num += row[d + 1]; den += row[d]
    return (num / den) if den else None

# --- cell decomposition (paid & incurred) --------------------------------
def decompose(kind):
    M = T[kind]; cells = {}
    for i, ay in enumerate(AYS):
        for d in range(NDEV - 1):
            if M[i][d + 1] is None or not M[i][d]: continue
            obs = M[i][d + 1] / M[i][d]
            base = vw_baseline(M, i, d)
            if base is None: base = obs
            contrib = {}
            cls = []
            for cl in by_ay(ay):
                for e in cl["events"]:
                    if e["dev"] != d + 1: continue
                    if kind == "paid":
                        amt = e["dpaid"] if e["driver"] != "speedup" else cl.get("speedup_excess", 0)
                    else:  # incurred
                        amt = e["dpaid"] + e["dcase"] if e["driver"] != "speedup" else 0.0
                    if e["driver"] == "speedup" and kind == "incurred":
                        amt = 0.0
                    contrib[e["driver"]] = contrib.get(e["driver"], 0) + amt
                    cls.append(cl["id"])
            key = "paid" if kind == "paid" else "incurred"
            movers = sorted(((cl[key][d + 1] - cl[key][d], cl["id"]) for cl in by_ay(ay)), key=lambda t: -abs(t[0]))[:5]
            movers = [dict(id=m[1], amt=round(m[0])) for m in movers]
            parts = {k: round(v / M[i][d], 4) for k, v in contrib.items()}
            explained = sum(parts.values())
            resid = round(obs - base - explained, 4)
            # suggested LDF: baseline + recurring drivers
            sugg = base + sum(v for k, v in parts.items() if DRIVERS[k]["recurring"])
            gross = sum(abs(v) for v in parts.values())
            dev_pct = (obs - base) / base
            others = [row[d + 1] / row[d] for j, row in enumerate(M) if j != i and row[d + 1] is not None and row[d]]
            sd = (sum((x - base) ** 2 for x in others) / max(1, len(others) - 1)) ** 0.5 if len(others) > 1 else 0
            z = (obs - base) / sd if sd > 0 else 0
            flag = None
            if abs(dev_pct) > 0.05 and (abs(z) > 1.8 or abs(dev_pct) > 0.07): flag = "spike" if dev_pct > 0 else "drop"
            elif gross > 0.08 and abs(obs - base) < 0.05: flag = "hidden"
            cells[f"{ay}-{d}"] = dict(ay=ay, dev=d, observed=round(obs, 4), baseline=round(base, 4),
                                      parts=parts, residual=resid, suggested=round(sugg, 4),
                                      gross=round(gross, 4), flag=flag, z=round(z, 2), claims=sorted(set(cls)), movers=movers, incr=M[i][d + 1] - M[i][d])
    return cells

CELLS = {"paid": decompose("paid"), "incurred": decompose("incurred")}

out = dict(
    meta=dict(line="Commercial Auto Liability", valuation="31 Dec 2025", ays=AYS, ndev=NDEV,
              devLabels=[f"{12*(d+1)}" for d in range(NDEV)], drivers=DRIVERS,
              generated="synthetic; seeded for demonstration"),
    triangles=T,
    factors={k: factors(T[k]) for k in ["reported", "closed", "paid", "incurred", "severity", "avgcase"]},
    cells=CELLS,
    claims=[dict(id=cl["id"], ay=cl["ay"], r=cl["r"], c=cl["c"], state=cl["state"], vehicle=cl["vehicle"],
                 injury=cl["injury"], adjuster=cl["adjuster"], litigated=cl["litigated"],
                 paid=cl["paid"], case=cl["case"], status=cl["status"],
                 events=cl["events"], notes=cl["notes"]) for cl in claims],
)
json.dump(out, open("data/book.json", "w"))
print("claims", len(claims), "size KB", round(len(json.dumps(out)) / 1024))
for k in ["paid"]:
    print(k, "factors (latest diag):")
    for i, ay in enumerate(AYS):
        nd = ndev_avail(ay)
        if nd >= 2:
            c = CELLS["paid"][f"{ay}-{nd-2}"]
            print(ay, f"dev{nd-2}->{nd-1}", "obs", c["observed"], "base", c["baseline"], c["parts"], "resid", c["residual"], "flag", c["flag"], "sugg", c["suggested"])
print("flagged:", [(k, v["flag"]) for k, v in CELLS["paid"].items() if v["flag"]])
print("incurred flagged:", [(k, v["flag"], v["parts"]) for k, v in CELLS["incurred"].items() if v["flag"]])
