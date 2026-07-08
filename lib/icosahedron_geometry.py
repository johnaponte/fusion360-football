"""Pure-math model of a truncated icosahedron (football / soccer ball shape).

No dependency on the Fusion API (or any third-party library) so this module
can be exercised with a plain ``python3`` interpreter outside of Fusion 360 --
see ``tests/test_icosahedron_geometry.py``.

All coordinates are plain ``(x, y, z)`` tuples of floats. Callers decide the
unit (the Fusion add-in works in centimeters, the native Fusion API unit).
"""

import math

PHI = (1.0 + math.sqrt(5.0)) / 2.0

_EPS = 1e-6


# ---------------------------------------------------------------------------
# Small vector helpers (kept local so this module has zero dependencies)
# ---------------------------------------------------------------------------

def vec_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a):
    return math.sqrt(dot(a, a))


def normalize(a):
    n = norm(a)
    return (a[0] / n, a[1] / n, a[2] / n)


# ---------------------------------------------------------------------------
# Vertex generation
# ---------------------------------------------------------------------------

def _cyclic_perms(t):
    x, y, z = t
    return [(x, y, z), (z, x, y), (y, z, x)]


def _signed_variants(t):
    xs = (t[0],) if t[0] == 0 else (t[0], -t[0])
    ys = (t[1],) if t[1] == 0 else (t[1], -t[1])
    zs = (t[2],) if t[2] == 0 else (t[2], -t[2])
    return [(x, y, z) for x in xs for y in ys for z in zs]


def _point_family(base_triple):
    """All points reachable from base_triple via cyclic permutation + signs."""
    points = set()
    for perm in _cyclic_perms(base_triple):
        for v in _signed_variants(perm):
            points.add(v)
    return points


def _round_key(v, ndigits=9):
    return (round(v[0], ndigits), round(v[1], ndigits), round(v[2], ndigits))


def unit_truncated_icosahedron_vertices():
    """The 60 vertices of a truncated icosahedron with edge length 2.

    Coordinates per the standard construction: all even (cyclic) permutations
    and sign choices of (0, 1, 3*PHI), (1, 2+PHI, 2*PHI) and (PHI, 2, 2*PHI+1).
    """
    base_triples = [
        (0.0, 1.0, 3.0 * PHI),
        (1.0, 2.0 + PHI, 2.0 * PHI),
        (PHI, 2.0, 2.0 * PHI + 1.0),
    ]
    points = set()
    for triple in base_triples:
        points |= _point_family(triple)
    return [tuple(p) for p in points]


def unit_icosahedron_vertices():
    """12 unit vectors toward the vertices of a regular icosahedron.

    These are the pentagon-face directions of the truncated icosahedron.
    """
    points = _point_family((0.0, 1.0, PHI))
    return [normalize(p) for p in points]


def unit_hexagon_face_normals():
    """20 unit vectors toward the face centroids of a regular icosahedron.

    These are the hexagon-face directions of the truncated icosahedron. They
    are derived directly from unit_icosahedron_vertices() (rather than from
    an independently-parameterized dodecahedron) so both normal families are
    guaranteed to share the same coordinate frame as the truncated
    icosahedron vertices.
    """
    import itertools

    icosa_vertices = unit_icosahedron_vertices()
    edge = min(
        norm(vec_sub(icosa_vertices[i], icosa_vertices[j]))
        for i in range(len(icosa_vertices))
        for j in range(i + 1, len(icosa_vertices))
    )
    normals = []
    for i, j, k in itertools.combinations(range(len(icosa_vertices)), 3):
        a, b, c = icosa_vertices[i], icosa_vertices[j], icosa_vertices[k]
        if (
            abs(norm(vec_sub(a, b)) - edge) < 1e-6
            and abs(norm(vec_sub(a, c)) - edge) < 1e-6
            and abs(norm(vec_sub(b, c)) - edge) < 1e-6
        ):
            centroid = vec_scale(vec_add(vec_add(a, b), c), 1.0 / 3.0)
            normals.append(normalize(centroid))
    return normals


# ---------------------------------------------------------------------------
# Face construction
# ---------------------------------------------------------------------------

class Face(object):
    """A single pentagon or hexagon face of the ball.

    Attributes:
        kind: 'pentagon' or 'hexagon'.
        normal: outward unit normal of the face.
        vertices: ordered list of (x, y, z) vertex coordinates (CCW seen from
            outside), scaled to whatever edge length the caller requested.
        centroid: average of the vertices.
    """

    __slots__ = ("kind", "normal", "vertices", "centroid")

    def __init__(self, kind, normal, vertices):
        self.kind = kind
        self.normal = normal
        self.vertices = vertices
        cx = sum(v[0] for v in vertices) / len(vertices)
        cy = sum(v[1] for v in vertices) / len(vertices)
        cz = sum(v[2] for v in vertices) / len(vertices)
        self.centroid = (cx, cy, cz)

    @property
    def edge_count(self):
        return len(self.vertices)

    def edge(self, i):
        """Returns the (start, end) vertices of edge i (edge i follows vertex i)."""
        n = len(self.vertices)
        return self.vertices[i], self.vertices[(i + 1) % n]


def perpendicular_basis(n):
    """Returns unit vectors (u, w) forming a right-handed frame with n.

    That is, u is perpendicular to n, w = n x u, and u x w == n. Useful for
    building an OrientedBoundingBox3D whose height direction must match a
    specific outward direction (Fusion derives height as lengthDir x widthDir).
    """
    arbitrary = (1.0, 0.0, 0.0)
    if abs(dot(arbitrary, n)) > 0.9:
        arbitrary = (0.0, 1.0, 0.0)
    u = normalize(cross(n, arbitrary))
    w = cross(n, u)
    return u, w


def _order_face_vertices(vertices, normal):
    cx = sum(v[0] for v in vertices) / len(vertices)
    cy = sum(v[1] for v in vertices) / len(vertices)
    cz = sum(v[2] for v in vertices) / len(vertices)
    centroid = (cx, cy, cz)

    u, w = perpendicular_basis(normal)

    def angle_key(v):
        rel = vec_sub(v, centroid)
        return math.atan2(dot(rel, w), dot(rel, u))

    return sorted(vertices, key=angle_key)


def build_faces(vertices, edge_length):
    """Builds the 12 pentagon + 20 hexagon faces for the given vertex cloud.

    vertices: the 60 vertices from unit_truncated_icosahedron_vertices(),
        already scaled so its edges measure `edge_length`.
    """
    pentagon_normals = unit_icosahedron_vertices()
    hexagon_normals = unit_hexagon_face_normals()

    faces = []
    for kind, normals in (("pentagon", pentagon_normals), ("hexagon", hexagon_normals)):
        for n in normals:
            d_max = max(dot(v, n) for v in vertices)
            face_vertices = [v for v in vertices if dot(v, n) > d_max - 1e-4 * max(edge_length, 1.0)]
            expected = 5 if kind == "pentagon" else 6
            if len(face_vertices) != expected:
                raise ValueError(
                    "expected %d vertices for %s face, found %d" % (expected, kind, len(face_vertices))
                )
            ordered = _order_face_vertices(face_vertices, n)
            faces.append(Face(kind, n, ordered))
    return faces


def scale_vertices(vertices, edge_length):
    """Rescales the unit (edge=2) vertex cloud to the requested edge length."""
    # Nearest-neighbor distance in the unit cloud gives the reference edge length.
    sample = vertices[0]
    nearest = min(
        (norm(vec_sub(sample, v)) for v in vertices if v is not sample),
    )
    scale = edge_length / nearest
    return [vec_scale(v, scale) for v in vertices], scale


# ---------------------------------------------------------------------------
# Adjacency + miter (bisector) planes
# ---------------------------------------------------------------------------

class EdgeAdjacency(object):
    """For one face, the neighboring face index across each edge."""

    __slots__ = ("neighbor_face", "neighbor_normal")

    def __init__(self, neighbor_face, neighbor_normal):
        self.neighbor_face = neighbor_face
        self.neighbor_normal = neighbor_normal


def build_adjacency(faces):
    """Returns adjacency[face_index] = [EdgeAdjacency, ...] aligned to edges."""
    edge_map = {}
    for fi, face in enumerate(faces):
        n = face.edge_count
        for ei in range(n):
            a, b = face.edge(ei)
            key = frozenset((_round_key(a), _round_key(b)))
            edge_map.setdefault(key, []).append((fi, ei))

    adjacency = [[None] * face.edge_count for face in faces]
    for key, entries in edge_map.items():
        if len(entries) != 2:
            raise ValueError("edge shared by %d faces (expected 2): %r" % (len(entries), key))
        (fi_a, ei_a), (fi_b, ei_b) = entries
        adjacency[fi_a][ei_a] = EdgeAdjacency(fi_b, faces[fi_b].normal)
        adjacency[fi_b][ei_b] = EdgeAdjacency(fi_a, faces[fi_a].normal)

    for face_adj in adjacency:
        for entry in face_adj:
            if entry is None:
                raise ValueError("unresolved edge adjacency")
    return adjacency


def miter_plane(face, edge_index, neighbor_normal):
    """The mitered cutting plane for one edge of a face.

    Returns (point_on_plane, outward_plane_normal). `outward_plane_normal`
    points away from the face's own centroid, i.e. subtracting the half-space
    on the side the normal points to trims the panel back to the true edge.

    The cut is the radial bisecting plane of the dihedral: it contains the
    shared edge and the ball center, so two adjacent panels trimmed this way
    meet flush regardless of panel depth. Of the two angle-bisector planes of
    the face planes, the radial one has a normal along (n1 - n2) (which is
    perpendicular to the edge and passes through the center); the other, along
    (n1 + n2), is the non-radial bisector and would leave the panels
    overlapping.
    """
    a, b = face.edge(edge_index)
    midpoint = vec_scale(vec_add(a, b), 0.5)
    bisector = vec_sub(face.normal, neighbor_normal)
    bn = norm(bisector)
    if bn < _EPS:
        # Coplanar faces (180 degree dihedral); no real miter is needed. Fall
        # back to a plane perpendicular to the edge and to this face.
        edge_dir = normalize(vec_sub(b, a))
        plane_normal = normalize(cross(face.normal, edge_dir))
    else:
        plane_normal = vec_scale(bisector, 1.0 / bn)

    # Ensure the normal points away from the face centroid (outward cut side).
    to_centroid = vec_sub(face.centroid, midpoint)
    if dot(plane_normal, to_centroid) > 0:
        plane_normal = vec_scale(plane_normal, -1.0)

    return midpoint, plane_normal


def circumradius(vertices):
    radii = [norm(v) for v in vertices]
    return sum(radii) / len(radii)
