"""Design geometry: the single dimensional source for weights, CAD, drawings
and BOM.

Built from the validated input plus the nominal thicknesses selected by the
calculations. Conventions (repeated in every output file):
* origin on the vessel axis at grade (underside of the leg base plates), +Z up;
* plan angle theta measured clockwise from 0 deg = +Y (plant north) seen from
  above, so the radial direction is (sin theta, cos theta, 0);
* nozzle elevations are measured from the bottom tangent line (BTL);
* projection = vessel outside surface at the nozzle centreline to flange face.
"""

from __future__ import annotations

import math

from .. import units
from ..inputs.models import VesselInput
from . import profiles as pf


def _dir(theta_deg):
    th = math.radians(theta_deg)
    return (math.sin(th), math.cos(th), 0.0)


def _flange_dict(fl):
    if fl is None or fl.dims is None:
        return None
    d = fl.dims
    return {"od": d.od, "thickness": d.thickness, "hub_od": d.hub_od,
            "length_through_hub": d.length_through_hub, "bolt_circle": d.bolt_circle,
            "bolt_holes": d.bolt_holes, "bolt_hole_diameter": d.bolt_hole_diameter,
            "bolt_size": d.bolt_size, "raised_face_od": d.raised_face_od,
            "raised_face_height": d.raised_face_height, "source": d.source, "status": d.status}


def build_geometry(vi: VesselInput, selected: dict[str, float]) -> dict:
    g, mats = vi.geometry, vi.materials
    D = g.inside_diameter
    a = D / 2.0
    btl = g.bottom_tangent_elevation
    ttl = btl + g.tangent_to_tangent
    comps: list[dict] = []

    def add(tag, kind, desc, mat_key, V, centroid, params, *, pressure_part, calc_ref="", group="",
            bom=True):
        m = mats.get(mat_key)
        rho = m.rho if m else None
        mass = None if rho is None else V * rho * 1e-9
        comps.append({"tag": tag, "kind": kind, "description": desc, "material": mat_key,
                      "material_label": m.label if m else mat_key, "density_kg_m3": rho,
                      "material_status": m.data_status if m else "UNKNOWN",
                      "pressure_part": pressure_part, "calc_ref": calc_ref, "bom_group": group,
                      "in_bom": bom, "params": params, "volume_mm3": V, "mass_kg": mass,
                      "centroid": list(centroid)})
        return comps[-1]

    # --- heads (nominal thickness, exact profile + normal offset) -----------
    head_info = {}
    for pos, sign, z_tl in (("bottom", -1, btl), ("top", 1, ttl)):
        h = g.heads[pos]
        t = selected[pos]
        prof = pf.HeadProfile(h.type, a, h.aspect_ratio or 2.0, h.crown_radius or 0.0, h.knuckle_radius or 0.0)
        V, yc = pf.head_metal(prof, t, h.straight_flange)
        # straight flange lies on the shell side of the tangent line
        z_c = z_tl + sign * yc
        head_info[pos] = {"profile": prof, "t": t, "z_tangent": z_tl, "sign": sign,
                          "outer_extreme": z_tl + sign * (prof.depth + t), "sf": h.straight_flange}
        add(f"HD-{pos.upper()[:3]}", "head", f"{pos.capitalize()} head, {h.type}"
            + (f" {h.aspect_ratio:g}:1" if h.type == "ellipsoidal" else ""), h.material, V, (0, 0, z_c),
            {"type": h.type, "inside_diameter": D, "thickness": t, "aspect_ratio": h.aspect_ratio,
             "crown_radius": h.crown_radius, "knuckle_radius": h.knuckle_radius,
             "straight_flange": h.straight_flange, "inside_depth": prof.depth, "z_tangent": z_tl,
             "direction": sign, "min_thickness_after_forming": h.min_thickness_after_forming},
            pressure_part=True, calc_ref=f"HD-{pos.upper()[:3]}", group="heads")

    # --- shell courses (between the head straight flanges) -------------------
    z = btl + g.heads["bottom"].straight_flange
    course_z = {}
    for cc in g.shell_courses:
        t = selected[cc.id]
        V = math.pi * ((a + t) ** 2 - a ** 2) * cc.length
        course_z[cc.id] = (z, z + cc.length, t)
        add(cc.id, "shell_course", f"Shell course {cc.id}", cc.material, V, (0, 0, z + cc.length / 2),
            {"inside_diameter": D, "thickness": t, "z0": z, "z1": z + cc.length, "length": cc.length,
             "long_seam_orientation": cc.long_seam_orientation,
             "developed_length_mean": math.pi * (D + t)},
            pressure_part=True, calc_ref=f"SH-{cc.id}", group="shell")
        z += cc.length

    seams = [{"kind": "circumferential", "z": btl + g.heads["bottom"].straight_flange, "between": "HD-BOT/" + g.shell_courses[0].id}]
    for c0, c1 in zip(g.shell_courses, g.shell_courses[1:]):
        seams.append({"kind": "circumferential", "z": course_z[c0.id][1], "between": f"{c0.id}/{c1.id}"})
    seams.append({"kind": "circumferential", "z": course_z[g.shell_courses[-1].id][1],
                  "between": g.shell_courses[-1].id + "/HD-TOP"})
    for cc in g.shell_courses:
        if cc.long_seam_orientation is not None:
            seams.append({"kind": "longitudinal", "orientation": cc.long_seam_orientation,
                          "z0": course_z[cc.id][0], "z1": course_z[cc.id][1], "course": cc.id})

    # --- nozzles -------------------------------------------------------------
    nozzle_sched = []
    hole_corrections = {}
    for nz in g.nozzles:
        neck = nz.neck
        fl = _flange_dict(nz.flange)
        nid = neck.od - 2 * neck.wall
        hub_len = fl["length_through_hub"] if fl and fl.get("length_through_hub") else (fl["thickness"] if fl else 0.0)
        entry = {"tag": nz.tag, "service": nz.service, "location": nz.location,
                 "neck_od": neck.od, "neck_wall": neck.wall, "neck_id": nid, "nps": neck.nps,
                 "schedule": neck.schedule, "neck_type": neck.type, "attachment": nz.attachment,
                 "projection": nz.projection, "flange": fl,
                 "flange_class": nz.flange.pressure_class if nz.flange else None,
                 "flange_standard": nz.flange.standard if nz.flange else None,
                 "flange_type": nz.flange.flange_type if nz.flange else None,
                 "facing": nz.flange.facing if nz.flange else None,
                 "blind_cover": bool(nz.flange and nz.flange.blind_cover),
                 "pad": None if nz.pad is None else {"thickness": nz.pad.thickness, "od": nz.pad.od,
                                                       "material": nz.pad.material},
                 "inward_projection": nz.inward_projection}
        if nz.location == "shell":
            course = next((cid for cid, (z0, z1, t) in course_z.items() if z0 <= btl + nz.elevation <= z1), None)
            if course is None:
                raise ValueError(f"nozzle {nz.tag}: elevation {nz.elevation:g} mm is not on a shell course")
            t_par = course_z[course][2]
            Ri, Ro = a, a + t_par
            z_abs = btl + nz.elevation
            dvec = _dir(nz.orientation)
            face_s = Ro + nz.projection            # radial position of the flange face
            weld_s = face_s - hub_len if fl else face_s
            ig = pf.shell_nozzle_integrals(Ri, Ro, nid / 2, neck.od / 2, weld_s, nz.attachment,
                                           nz.inward_projection,
                                           r_hole=neck.od / 2 if nz.attachment == "set_in" else nid / 2,
                                           pad=(nz.pad.thickness, nz.pad.od) if nz.pad else None)
            entry.update({"parent": course, "parent_thickness": t_par, "elevation_from_btl": nz.elevation,
                          "z": z_abs, "orientation": nz.orientation, "axis_dir": list(dvec),
                          "axis_point": [0.0, 0.0, z_abs], "face_distance_from_axis": face_s,
                          "weld_distance_from_axis": weld_s,
                          "face_point": [dvec[0] * face_s, dvec[1] * face_s, z_abs]})
            hole_corrections.setdefault(course, []).append((ig["hole_V"], ig["hole_M"], dvec, z_abs))
            s_c = ig["neck_M"] / ig["neck_V"]
            add(f"{nz.tag}-NECK", "nozzle_neck", f"Nozzle {nz.tag} neck ({nz.service})", neck.material,
                ig["neck_V"], (dvec[0] * s_c, dvec[1] * s_c, z_abs),
                {"nozzle": nz.tag, "od": neck.od, "wall": neck.wall, "start": nz.attachment,
                 "length_at_axis": weld_s - (Ri - nz.inward_projection if nz.attachment == "set_in" else Ro)},
                pressure_part=True, calc_ref=f"NZ-{nz.tag}", group="nozzles")
            if nz.pad:
                s_p = ig["pad_M"] / ig["pad_V"]
                add(f"{nz.tag}-PAD", "pad", f"Reinforcing pad {nz.tag}", nz.pad.material, ig["pad_V"],
                    (dvec[0] * s_p, dvec[1] * s_p, z_abs),
                    {"nozzle": nz.tag, "thickness": nz.pad.thickness, "od": nz.pad.od, "id": neck.od,
                     "parent_outer_radius": Ro},
                    pressure_part=True, calc_ref=f"NZ-{nz.tag}-UG37", group="pads")
            fl_pos = lambda s: (dvec[0] * s, dvec[1] * s, z_abs)   # noqa: E731
        else:
            pos = "top" if nz.location == "top_head" else "bottom"
            hi = head_info[pos]
            prof, t_par, sign = hi["profile"], hi["t"], hi["sign"]
            y_face = prof.depth + t_par + nz.projection
            y_weld = y_face - hub_len if fl else y_face
            ig = pf.head_nozzle_integrals(prof, t_par, nid / 2, neck.od / 2, y_weld, nz.attachment,
                                          r_hole=neck.od / 2 if nz.attachment == "set_in" else nid / 2)
            z_face = hi["z_tangent"] + sign * y_face
            dvec = (0.0, 0.0, float(sign))
            entry.update({"parent": f"HD-{pos.upper()[:3]}", "parent_thickness": t_par,
                          "z": z_face, "orientation": None, "axis_dir": list(dvec),
                          "axis_point": [0.0, 0.0, hi["z_tangent"]], "face_point": [0.0, 0.0, z_face],
                          "face_y_from_tangent": y_face, "weld_y_from_tangent": y_weld})
            hole_corrections.setdefault(f"HD-{pos.upper()[:3]}", []).append(
                (ig["hole_V"], ig["hole_M"], dvec, hi["z_tangent"]))
            yc = ig["neck_M"] / ig["neck_V"]
            add(f"{nz.tag}-NECK", "nozzle_neck", f"Nozzle {nz.tag} neck ({nz.service})", neck.material,
                ig["neck_V"], (0, 0, hi["z_tangent"] + sign * yc),
                {"nozzle": nz.tag, "od": neck.od, "wall": neck.wall, "start": nz.attachment,
                 "length_at_axis": y_weld - prof.depth},
                pressure_part=True, calc_ref=f"NZ-{nz.tag}", group="nozzles")
            z_t = hi["z_tangent"]
            fl_pos = lambda s, z_t=z_t, sign=sign: (0.0, 0.0, z_t + sign * s)   # noqa: E731
            face_s = y_face
        if fl and nz.flange:
            Vf, cf = pf.flange_volume(fl, neck.od, nid)
            add(f"{nz.tag}-FLG", "flange", f"Flange {nz.tag}, {nz.flange.standard} Cl {nz.flange.pressure_class} "
                f"{nz.flange.flange_type} {nz.flange.facing}", nz.flange.material, Vf, fl_pos(face_s - cf),
                {"nozzle": nz.tag, **{k: v for k, v in fl.items() if k not in ("source", "status")},
                 "bore": nid, "neck_od": neck.od}, pressure_part=True, calc_ref=f"NZ-{nz.tag}-FLG",
                group="flanges")
            if nz.flange.blind_cover:
                Vb, cb = pf.flange_volume(fl, neck.od, nid, blind=True)
                add(f"{nz.tag}-BLD", "blind", f"Blind flange {nz.tag}", nz.flange.material, Vb,
                    fl_pos(face_s + cb), {"nozzle": nz.tag, **{k: v for k, v in fl.items()
                                                                if k not in ("source", "status")}},
                    pressure_part=True, calc_ref=f"NZ-{nz.tag}-FLG", group="flanges")
        nozzle_sched.append(entry)

    # subtract the nozzle holes from their parent components
    for c in comps:
        if c["tag"] in hole_corrections:
            V0 = c["volume_mm3"]
            cz0 = c["centroid"]
            Mx, My, Mz = (cz0[0] * V0, cz0[1] * V0, cz0[2] * V0)
            for hv, hm, dvec, zref in hole_corrections[c["tag"]]:
                V0 -= hv
                s = hm / hv if hv else 0.0
                if dvec[2] == 0:
                    Mx -= hv * dvec[0] * s
                    My -= hv * dvec[1] * s
                    Mz -= hv * zref
                else:
                    Mz -= hv * (zref + dvec[2] * s)
            c["volume_mm3"] = V0
            c["centroid"] = [Mx / V0, My / V0, Mz / V0]
            if c["density_kg_m3"]:
                c["mass_kg"] = V0 * c["density_kg_m3"] * 1e-9
            c["params"]["openings"] = [n["tag"] for n in nozzle_sched if n.get("parent") == c["tag"]]

    # --- legs and base plates -------------------------------------------------
    t_bot_course = course_z[g.shell_courses[0].id][2]
    Ro_shell = a + t_bot_course
    if g.legs:
        lg = g.legs
        bp = lg.base_plate
        r_leg = Ro_shell + lg.od / 2.0            # tangent to the shell outside surface
        z_top = btl + lg.top_elevation
        L_leg = z_top - bp["thickness"]
        for i in range(lg.count):
            th = lg.orientation_start + i * 360.0 / lg.count
            dv = _dir(th)
            cx, cy = dv[0] * r_leg, dv[1] * r_leg
            V = math.pi / 4 * (lg.od ** 2 - (lg.od - 2 * lg.wall) ** 2) * L_leg
            add(f"LEG-{i + 1}", "leg", f"Support leg {i + 1}, {lg.section}", lg.material, V,
                (cx, cy, bp["thickness"] + L_leg / 2),
                {"orientation": th, "center": [cx, cy], "od": lg.od, "wall": lg.wall,
                 "z0": bp["thickness"], "z1": z_top, "radius": r_leg, "section": lg.section},
                pressure_part=False, group="supports")
            Vb = bp["length"] * bp["width"] * bp["thickness"] - bp["anchor_holes"] * math.pi / 4 * \
                (bp["anchor_hole_diameter"] or 0) ** 2 * bp["thickness"]
            add(f"BP-{i + 1}", "base_plate", f"Base plate {i + 1}", bp["material"], Vb,
                (cx, cy, bp["thickness"] / 2),
                {"orientation": th, "center": [cx, cy], **bp}, pressure_part=False, group="supports")
    # --- lifting lugs -------------------------------------------------------------
    if g.lugs:
        lu = g.lugs
        z_c = btl + lu.elevation
        course = next(cid for cid, (z0, z1, t) in course_z.items() if z0 <= z_c <= z1)
        Ro = a + course_z[course][2]
        tl = lu.thickness

        def width(v):
            return Ro + lu.projection - math.sqrt(Ro * Ro - v * v)

        def mom(v):
            s0 = math.sqrt(Ro * Ro - v * v)
            return ((Ro + lu.projection) ** 2 - s0 ** 2) / 2.0
        V = lu.height * pf.simpson(width, -tl / 2, tl / 2, 100) - math.pi / 4 * lu.hole_diameter ** 2 * tl
        s_hole = Ro + lu.projection - lu.hole_edge_distance
        M = lu.height * pf.simpson(mom, -tl / 2, tl / 2, 100) - math.pi / 4 * lu.hole_diameter ** 2 * tl * s_hole
        for i in range(lu.count):
            th = lu.orientation_start + i * 360.0 / lu.count
            dv = _dir(th)
            sc = M / V
            add(f"LUG-{i + 1}", "lifting_lug", f"Lifting lug {i + 1}", lu.material, V,
                (dv[0] * sc, dv[1] * sc, z_c),
                {"orientation": th, "z_center": z_c, "thickness": tl, "height": lu.height,
                 "projection": lu.projection, "hole_diameter": lu.hole_diameter,
                 "hole_center_radius": s_hole, "parent": course, "parent_outer_radius": Ro},
                pressure_part=False, group="lugs")

    # --- envelope and key dimensions -----------------------------------------------
    top = max([head_info["top"]["outer_extreme"]] + [n["z"] for n in nozzle_sched])
    max_r = max([a + max(t for _, _, t in course_z.values())] +
                [n.get("face_distance_from_axis", 0.0) + (n["flange"]["thickness"] if n.get("blind_cover") and n.get("flange") else 0.0)
                 for n in nozzle_sched] +
                ([c["params"]["radius"] + c["params"]["od"] / 2 for c in comps if c["kind"] == "leg"]) +
                ([c["params"]["hole_center_radius"] + lu.hole_edge_distance for c in comps if c["kind"] == "lifting_lug"]
                 if g.lugs else []))
    capacity = (math.pi * a * a * sum(cc.length for cc in g.shell_courses) +
                sum(pf.head_capacity(head_info[p]["profile"], head_info[p]["sf"]) for p in ("top", "bottom")))
    inner_height = g.tangent_to_tangent + head_info["top"]["profile"].depth + head_info["bottom"]["profile"].depth
    key = [
        {"name": "inside_diameter", "value": D, "unit": "mm"},
        {"name": "tangent_to_tangent", "value": g.tangent_to_tangent, "unit": "mm"},
        {"name": "bottom_tangent_elevation", "value": btl, "unit": "mm"},
        {"name": "top_tangent_elevation", "value": ttl, "unit": "mm"},
        {"name": "overall_height", "value": top, "unit": "mm"},
        {"name": "max_radius", "value": max_r, "unit": "mm"},
        {"name": "internal_volume", "value": capacity, "unit": "mm3"},
        {"name": "inside_height_between_head_crowns", "value": inner_height, "unit": "mm"},
    ]
    return {
        "schema": "pv-design/geometry@1",
        "project_id": vi.project.project_id, "equipment_tag": vi.project.equipment_tag,
        "revision": vi.project.revision, "input_hash": vi.input_hash,
        "units": {"length": "mm", "mass": "kg", "volume": "mm3", "angle": "deg"},
        "conventions": {"origin": "vessel axis at grade (underside of base plates)", "z": "up",
                        "zero_angle": "+Y = plan 0 deg (plant north)",
                        "angle_sense": "clockwise seen from above",
                        "nozzle_elevation_datum": "bottom tangent line",
                        "projection": "outside surface at nozzle centreline to flange face"},
        "vessel": {"inside_diameter": D, "tangent_to_tangent": g.tangent_to_tangent,
                   "bottom_tangent_elevation": btl, "top_tangent_elevation": ttl,
                   "overall_height": top, "max_radius": max_r, "internal_volume_mm3": capacity,
                   "inside_height": inner_height, "orientation": g.orientation},
        "heads": {p: {k: v for k, v in hi.items() if k != "profile"} | {"inside_depth": hi["profile"].depth}
                  for p, hi in head_info.items()},
        "courses": {cid: {"z0": z0, "z1": z1, "thickness": t} for cid, (z0, z1, t) in course_z.items()},
        "seams": seams, "nozzles": nozzle_sched, "components": comps, "key_dimensions": key,
    }


def total_mass(geom: dict) -> tuple[float, list[str]]:
    missing = [c["tag"] for c in geom["components"] if c["mass_kg"] is None]
    return sum(c["mass_kg"] or 0.0 for c in geom["components"]), missing


def centre_of_gravity(geom: dict, extra: list[tuple[float, tuple]] = ()) -> tuple[float, tuple]:
    W = Mx = My = Mz = 0.0
    for c in geom["components"]:
        if c["mass_kg"]:
            m = c["mass_kg"]
            W += m
            Mx += m * c["centroid"][0]
            My += m * c["centroid"][1]
            Mz += m * c["centroid"][2]
    for m, (x, y, z) in extra:
        W += m
        Mx += m * x
        My += m * y
        Mz += m * z
    return W, (Mx / W, My / W, Mz / W)


def fmt_len(v):
    return units.fmt(v, 1)
