"""Builds a football (truncated icosahedron) as 32 independent printable
BRep bodies -- 12 pentagons and 20 hexagons -- inside a Fusion design.

Each panel is a frustum-like solid: the outer face is either the flat
pentagon/hexagon plane ("flat" exterior) or that same plane further carved
by the ball's circumsphere ("rounded" exterior, so the panel center bulges
out into a dome while the true polygon corners -- which already lie on the
circumsphere -- are untouched). The inner face is a flat plane at the
requested depth. The sides are cut with the exact miter (angle-bisector)
plane shared with each neighboring panel, so assembled panels meet flush
at the true dihedral angle regardless of panel depth.

This module talks directly to the Fusion API (adsk.core / adsk.fusion) and
can only be exercised inside Fusion 360. The underlying geometry math lives
in icosahedron_geometry.py, which has no Fusion dependency and is covered by
tests/test_icosahedron_geometry.py.
"""

import adsk.core
import adsk.fusion

from . import icosahedron_geometry as geo
from . import appearance_utils

# Oversize margin (cm) added around/above/below the true panel before it is
# trimmed back down to shape by the miter and depth cuts.
_MARGIN_CM = 2.0

# Size (cm) of the throwaway cutting boxes used to carve each half-space.
# Just needs to comfortably exceed any panel's footprint and depth.
_HALFSPACE_SIZE_CM = 100.0

PENTAGON_APPEARANCE_NAME = "Football Pentagon"
HEXAGON_APPEARANCE_NAME = "Football Hexagon"


def build_football(design, hexagon_side_cm, face_deep_cm, rounded,
                   pentagon_rgb, hexagon_rgb, tolerance_cm=0.0,
                   progress_callback=None):
    """Creates the 32 panel bodies in the design's root component.

    hexagon_side_cm : edge length of the truncated icosahedron, in cm.
    face_deep_cm : depth of each panel measured at its edges, in cm.
    rounded : if True, the outer face is carved by the ball's circumsphere
        (domed panels); if False, the outer face stays flat.
    pentagon_rgb / hexagon_rgb : (r, g, b) tuples, each channel 0-255.
    tolerance_cm : print clearance -- the total gap left between two adjacent
        panels, in cm. 0 means the panels touch exactly; a positive value
        insets each mating (mitered side) face inward by half the tolerance so
        the printed pieces assemble without interference.
    progress_callback : optional callable(done_count, total_count).

    Returns the list of created BRepBody objects.
    """
    root_comp = design.rootComponent

    unit_vertices = geo.unit_truncated_icosahedron_vertices()
    vertices, _scale = geo.scale_vertices(unit_vertices, hexagon_side_cm)
    faces = geo.build_faces(vertices, hexagon_side_cm)
    adjacency = geo.build_adjacency(faces)
    ball_radius_cm = geo.circumradius(vertices)

    # Each run gets its own component so multiple balls can coexist in one
    # assembly, cleanly organized in the browser and timeline. "Part" design
    # documents only allow a single component; there addNewComponent raises,
    # so we fall back to building directly in the root component.
    ball_comp = root_comp
    try:
        occurrence = root_comp.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        ball_comp = occurrence.component
        ball_comp.name = _unique_component_name(root_comp, "Football")
    except RuntimeError:
        ball_comp = root_comp

    base_feature = None
    if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
        base_feature = ball_comp.features.baseFeatures.add()
        base_feature.startEdit()

    try:
        pentagon_appearance = appearance_utils.get_or_create_color_appearance(
            design, PENTAGON_APPEARANCE_NAME, pentagon_rgb)
        hexagon_appearance = appearance_utils.get_or_create_color_appearance(
            design, HEXAGON_APPEARANCE_NAME, hexagon_rgb)

        created_bodies = []
        pentagon_count = 0
        hexagon_count = 0
        total = len(faces)

        for index, face in enumerate(faces):
            temp_body = _build_panel_body(
                face, adjacency[index], face_deep_cm, rounded, ball_radius_cm,
                tolerance_cm)

            if base_feature is not None:
                body = ball_comp.bRepBodies.add(temp_body, base_feature)
            else:
                body = ball_comp.bRepBodies.add(temp_body)

            if face.kind == "pentagon":
                pentagon_count += 1
                body.name = "Pentagon_%02d" % pentagon_count
                if pentagon_appearance:
                    body.appearance = pentagon_appearance
            else:
                hexagon_count += 1
                body.name = "Hexagon_%02d" % hexagon_count
                if hexagon_appearance:
                    body.appearance = hexagon_appearance

            created_bodies.append(body)

            if progress_callback:
                progress_callback(index + 1, total)
    finally:
        if base_feature is not None:
            base_feature.finishEdit()

    return created_bodies


def _unique_component_name(root_comp, base):
    """A component name like 'Football', 'Football (2)', ... that isn't already
    used by another occurrence in the root component."""
    existing = set()
    for i in range(root_comp.occurrences.count):
        existing.add(root_comp.occurrences.item(i).component.name)
    if base not in existing:
        return base
    n = 2
    while "%s (%d)" % (base, n) in existing:
        n += 1
    return "%s (%d)" % (base, n)


def _build_panel_body(face, edge_adjacency, face_deep_cm, rounded, ball_radius_cm,
                      tolerance_cm=0.0):
    mgr = adsk.fusion.TemporaryBRepManager.get()
    normal = face.normal

    # Half the clearance is removed from each of the two panels meeting at a
    # seam, so the total gap between them equals tolerance_cm.
    side_inset_cm = tolerance_cm / 2.0

    top_margin_cm = _MARGIN_CM
    if rounded:
        bulge_cm = ball_radius_cm - geo.dot(face.vertices[0], normal)
        top_margin_cm = bulge_cm + _MARGIN_CM

    bottom_extent_cm = face_deep_cm + _MARGIN_CM
    blank_height_cm = top_margin_cm + bottom_extent_cm
    blank_center = geo.vec_add(
        face.centroid,
        geo.vec_scale(normal, (top_margin_cm - bottom_extent_cm) / 2.0),
    )
    footprint_cm = _footprint_size(face)

    length_dir, width_dir = geo.perpendicular_basis(normal)
    obb = adsk.core.OrientedBoundingBox3D.create(
        _point3d(blank_center),
        _vector3d(length_dir),
        _vector3d(width_dir),
        footprint_cm,
        footprint_cm,
        blank_height_cm,
    )
    body = mgr.createBox(obb)

    # Trim every side down to the true edge along the dihedral miter plane
    # shared with the neighboring panel across that edge. When a print
    # tolerance is requested, move each miter plane inward (toward the panel
    # centroid) by half the tolerance so the seam ends up with that clearance.
    for edge_index in range(face.edge_count):
        neighbor_normal = edge_adjacency[edge_index].neighbor_normal
        point, outward_normal = geo.miter_plane(face, edge_index, neighbor_normal)
        if side_inset_cm:
            point = geo.vec_sub(point, geo.vec_scale(outward_normal, side_inset_cm))
        cutter = _half_space_box(point, outward_normal)
        mgr.booleanOperation(body, cutter, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    # Trim the inner face flat at the requested depth.
    bottom_point = geo.vec_sub(face.centroid, geo.vec_scale(normal, face_deep_cm))
    bottom_cutter = _half_space_box(bottom_point, geo.vec_scale(normal, -1.0))
    mgr.booleanOperation(body, bottom_cutter, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    # Shape the outer face. The face centroid lies on the true polygon plane,
    # so cutting there (removing the outward side) gives the flat exterior.
    # In rounded mode the circumsphere becomes the outer boundary instead --
    # it bulges past the flat plane at the panel center yet still passes
    # through the polygon corners, so the flat top cut would remove nothing
    # useful and is skipped.
    if rounded:
        sphere = mgr.createSphere(_point3d((0.0, 0.0, 0.0)), ball_radius_cm)
        mgr.booleanOperation(body, sphere, adsk.fusion.BooleanTypes.IntersectionBooleanType)
    else:
        top_cutter = _half_space_box(face.centroid, normal)
        mgr.booleanOperation(body, top_cutter, adsk.fusion.BooleanTypes.DifferenceBooleanType)

    return body


def _footprint_size(face):
    max_radius = max(geo.norm(geo.vec_sub(v, face.centroid)) for v in face.vertices)
    return 2.0 * (max_radius + _MARGIN_CM)


def _half_space_box(point, outward_dir):
    """A large box whose near face sits at `point`, extending along
    `outward_dir`. Subtracting it removes everything on that side of the
    plane through `point` perpendicular to `outward_dir`."""
    outward_dir = geo.normalize(outward_dir)
    length_dir, width_dir = geo.perpendicular_basis(outward_dir)
    center = geo.vec_add(point, geo.vec_scale(outward_dir, _HALFSPACE_SIZE_CM / 2.0))
    obb = adsk.core.OrientedBoundingBox3D.create(
        _point3d(center),
        _vector3d(length_dir),
        _vector3d(width_dir),
        _HALFSPACE_SIZE_CM,
        _HALFSPACE_SIZE_CM,
        _HALFSPACE_SIZE_CM,
    )
    mgr = adsk.fusion.TemporaryBRepManager.get()
    return mgr.createBox(obb)


def _point3d(p):
    return adsk.core.Point3D.create(p[0], p[1], p[2])


def _vector3d(v):
    return adsk.core.Vector3D.create(v[0], v[1], v[2])
