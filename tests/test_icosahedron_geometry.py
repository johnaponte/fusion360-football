"""Standalone sanity checks for lib/icosahedron_geometry.py.

Runs with plain python3 -- no Fusion, no third-party deps -- since the real
Fusion API can only be exercised inside the Fusion 360 application.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import icosahedron_geometry as geo  # noqa: E402


def check(label, condition):
    status = "OK" if condition else "FAIL"
    print("[%s] %s" % (status, label))
    if not condition:
        raise SystemExit(1)


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def main():
    edge_length = 4.4  # cm, i.e. 44 mm hexagon side

    unit_vertices = geo.unit_truncated_icosahedron_vertices()
    check("60 unique vertices generated", len(unit_vertices) == 60)

    vertices, scale = geo.scale_vertices(unit_vertices, edge_length)
    check("scale factor is positive", scale > 0)

    faces = geo.build_faces(vertices, edge_length)
    check("32 faces total", len(faces) == 32)
    pentagons = [f for f in faces if f.kind == "pentagon"]
    hexagons = [f for f in faces if f.kind == "hexagon"]
    check("12 pentagons", len(pentagons) == 12)
    check("20 hexagons", len(hexagons) == 20)

    # Every face edge should measure exactly edge_length.
    max_edge_error = 0.0
    for f in faces:
        for i in range(f.edge_count):
            a, b = f.edge(i)
            length = geo.norm(geo.vec_sub(a, b))
            max_edge_error = max(max_edge_error, abs(length - edge_length))
    check("all edges == hexagon side (max err %.2e cm)" % max_edge_error, max_edge_error < 1e-6)

    # Planarity: every vertex of a face must lie on the face's plane.
    max_planarity_error = 0.0
    for f in faces:
        for v in f.vertices:
            d = geo.dot(geo.vec_sub(v, f.centroid), f.normal)
            max_planarity_error = max(max_planarity_error, abs(d))
    check("faces are planar (max err %.2e cm)" % max_planarity_error, max_planarity_error < 1e-6)

    # Circumradius: every vertex should be equidistant from the origin.
    radii = [geo.norm(v) for v in vertices]
    r_min, r_max = min(radii), max(radii)
    check("uniform circumradius (spread %.2e cm)" % (r_max - r_min), (r_max - r_min) < 1e-6)
    r = geo.circumradius(vertices)
    print("    circumradius R = %.4f cm (%.2f mm) for edge length %.1f mm" % (r, r * 10, edge_length * 10))

    # Adjacency: pentagons only ever touch hexagons; hexagons touch 3+3.
    adjacency = geo.build_adjacency(faces)
    ok_adjacency = True
    for fi, face in enumerate(faces):
        neighbor_kinds = [faces[a.neighbor_face].kind for a in adjacency[fi]]
        if face.kind == "pentagon":
            if not all(k == "hexagon" for k in neighbor_kinds):
                ok_adjacency = False
        else:
            if neighbor_kinds.count("pentagon") != 3 or neighbor_kinds.count("hexagon") != 3:
                ok_adjacency = False
    check("pentagon-hexagon adjacency matches truncated icosahedron", ok_adjacency)

    # Dihedral angles derived from the miter-plane construction should match
    # the two known constants for a truncated icosahedron (142.62 / 138.19 deg).
    seen_angles = set()
    for fi, face in enumerate(faces):
        for ei in range(face.edge_count):
            adj = adjacency[fi][ei]
            cos_angle = geo.dot(face.normal, adj.neighbor_normal)
            angle_between_normals = math.degrees(math.acos(max(-1.0, min(1.0, cos_angle))))
            dihedral = 180.0 - angle_between_normals
            seen_angles.add(round(dihedral, 1))
    check(
        "dihedral angles are {138.2, 142.6} degrees, got %s" % sorted(seen_angles),
        seen_angles == {138.2, 142.6} or seen_angles == {138.2, 142.6, 142.6},
    )

    # Miter plane sanity: point should lie on the true edge midpoint, and the
    # plane normal should be a unit vector roughly bisecting the two faces.
    fi = 0
    face = faces[fi]
    ei = 0
    adj = adjacency[fi][ei]
    point, plane_normal = geo.miter_plane(face, ei, adj.neighbor_normal)
    check("miter plane normal is unit length", approx(geo.norm(plane_normal), 1.0, 1e-9))
    a, b = face.edge(ei)
    expected_midpoint = geo.vec_scale(geo.vec_add(a, b), 0.5)
    check(
        "miter plane point is the edge midpoint",
        geo.norm(geo.vec_sub(point, expected_midpoint)) < 1e-9,
    )

    # The real non-overlap condition: each miter plane must SEPARATE the two
    # panels it sits between -- the face's own centroid on the kept (negative)
    # side, and the neighbor face's centroid on the removed (positive) side.
    # This is what distinguishes the correct dihedral bisector (normal along
    # n1 - n2) from the wrong one (n1 + n2), which leaves panels overlapping.
    all_separated = True
    worst_own = -1e9
    worst_neighbor = 1e9
    for fi2, face2 in enumerate(faces):
        for ei2 in range(face2.edge_count):
            adj2 = adjacency[fi2][ei2]
            neighbor = faces[adj2.neighbor_face]
            pt, pn = geo.miter_plane(face2, ei2, adj2.neighbor_normal)
            own_side = geo.dot(geo.vec_sub(face2.centroid, pt), pn)       # want < 0
            neighbor_side = geo.dot(geo.vec_sub(neighbor.centroid, pt), pn)  # want > 0
            worst_own = max(worst_own, own_side)
            worst_neighbor = min(worst_neighbor, neighbor_side)
            if own_side >= 0 or neighbor_side <= 0:
                all_separated = False
    check(
        "miter planes separate adjacent panels (own<=%.3f, neighbor>=%.3f)" % (worst_own, worst_neighbor),
        all_separated,
    )

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
