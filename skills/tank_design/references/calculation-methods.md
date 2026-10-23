# Calculation methods (as implemented)

Units inside the engine: mm, MPa (gauge), °C, kg, N. Symbols: P pressure at the
component (design + static head), S allowable stress, E joint efficiency,
R/D/L/r corroded inside radius / diameter / crown / knuckle radius, t thickness
less corrosion allowance. Register ids in brackets; all ship UNVERIFIED.

## Shells [ASME8-1:UG-27(c)(1), (c)(2)]
- t_circ = PR/(SE_long − 0.6P), valid P ≤ 0.385SE, t ≤ R/2
- t_long = PR/(2SE_circ + 0.4P), valid P ≤ 1.25SE
- t_min = max(t_req, 1.5 mm) [UG-16(b)]; t_design = t_min + CA
- available t = t_nom − u − CA, u deducted only if > min(0.25 mm, 6 %) [UG-16(c)]
- MAWP: P = SEt/(R + 0.6t) and 2SEt/(R − 0.4t), minus static head

## Heads
- Ellipsoidal [App1-4(c); UG-32 form for 2:1]: t = PDK/(2SE − 0.2P), K = (2 + (D/2h)²)/6
- Torispherical [App1-4(d)]: t = PLM/(2SE − 0.2P), M = (3 + √(L/r))/4, L/r ≤ 16⅔;
  geometry: L ≤ skirt OD, r ≥ 6 % skirt OD, r ≥ 3t
- Hemispherical [UG-32]: t = PL/(2SE − 0.2P), P ≤ 0.665SE, t ≤ 0.356L
- ts/L ≥ 0.002 on the specified minimum thickness after forming (crown radius
  D·(D/2h)/2 for ellipsoidal — conservative), else OUT_OF_SCOPE [App1-4(f)]
- E for seamless heads: 1.0 when UW-11(a)(5)(b) spot RT is met and the
  head-to-shell joint is Type 1/2, else 0.85 [UW-12(d)]

## Nozzles
- UG-45: ta = PRn/(Sn·E − 0.6P) + CA; tb1 = max(t_parent(E=1) + CA, 1.5 + CA);
  tb3 = 0.875·STD wall + CA (derived Table UG-45); t = max(ta, min(tb3, tb1));
  access openings: ta only. Neck available = t_nom(1 − pipe undertolerance) or
  plate t − u. External parts (tb2) not evaluated → review flag.
- UG-37 area replacement (Fig. UG-37.1), all corroded, tn = nominal − CA
  (no undertolerance, UG-16(d)):
  A = d·tr·F + 2tn·tr·F(1 − fr1)
  A1 = max[d(E1t − Ftr) − 2tn(E1t − Ftr)(1 − fr1), 2(t + tn)(E1t − Ftr) − 2tn(E1t − Ftr)(1 − fr1)]
  A2 = min[5(tn − trn)fr2·t, 5(tn − trn)fr2·tn] (no pad) or min[…, 2(tn − trn)(2.5tn + te)fr2] (pad)
  A3 inward projection, A41/A42/A43 weld areas (0 when weld sizes are not given),
  A5 = (Dp − d − 2tn)·te·fr4 with te, Dp limited by UG-40
  tr: shell PR/(S − 0.6P); 2:1 head center PK1D/(2S − 0.2P), K1 = 0.90; hemi PL/(2S − 0.2P)
- Opening MAWP: largest P with A_avail(P) ≥ A(P), bisection (monotonic)
- UG-36(b)(1): shells ID ≤ 1520: d ≤ min(ID/2, 508); ID > 1520: d ≤ min(ID/3, 1000)
- UW-14: an opening crossing a seam takes E1 = seam efficiency and is flagged

## External pressure
- Shell [UG-28(c)(1)]: L = T/T + h_top/3 + h_bot/3; Pa = 4B/(3·Do/t), or
  2AE/(3·Do/t) left of the material line. A, B, E only from the user (II-D).
- Heads [UG-33]: (a)(1) UG-32 thickness at 1.67·Pe, E = 1; (a)(2) Ro = K0·Do
  (2:1: K0 = 0.90) / crown radius / sphere radius; A = 0.125/(Ro/t); Pa = B/(Ro/t)
  or 0.0625E/(Ro/t)².

## MAWP and test
- MAWP = min over parts (shell courses, heads, openings, necks, flange ratings)
  of the part's MAWP minus the static head between the part and the top [UG-98]
- Hydrotest 1.3·MAWP·LSR [UG-99(b)]; pneumatic 1.1·MAWP·LSR [UG-100];
  design-pressure basis allowed only by the UG-99(b) footnote (warning printed)
- Test stress screening: σ = P(R + 0.6t)/(Et) at the bottom course vs 0.9·Sy
  — informational, never PASS

## API 650 (SI)
- td = 4.9D(H − 0.3)G/Sd + CA; tt = 4.9D(H − 0.3)/St (D m, H m, S MPa, t mm)
- cross-check Sd ≤ min(2/3 Fy, 2/5 Fu), St ≤ min(3/4 Fy, 3/7 Fu)

## Weights and geometry
Exact profiles (ellipse with normal offset, torispherical arcs, sphere) and
quadrature; nozzle necks, holes and pads by area integrals over the
cylinder/head intersection. These are compared with the OpenCASCADE volumes
of the FreeCAD solids (tolerance 2·10⁻³).

## Verification (independent of the engine's formula functions)
- Shells: bisection on the stress equation; Appendix 1-1 outside-radius forms
- Heads: outside-dimension forms (App. 1-1 / 1-4) by fixed-point iteration
- Nozzles: reinforcement-zone derivation of A, A1, A2, A5
- MAWP: minimum of parts; test pressure by hand formula
- Geometry: closed-form ring, ellipsoid, sphere, torisphere (Pappus + cap)
- Benchmarks: `pv_design/data/benchmarks/hand_calcs_si.json` (hand arithmetic),
  `laela_zorana_us_units.json` (cross-implementation, with the documented
  undertolerance-convention difference reported, not adjusted)
- PV Elite: CSV `calc_id,symbol,value,unit,rel_tolerance` (engine units) via
  `--pv-elite`; deviations are reported as discrepancies. Without a file the
  status is NOT_AVAILABLE.
