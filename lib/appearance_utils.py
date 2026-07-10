"""Helpers for applying flat RGB colors to bodies.

Fusion's command dialogs have no native color-swatch input, and appearances
are normally picked from a library rather than built from raw RGB. To turn an
(r, g, b) triple into something that can be assigned to a BRepBody, we copy a
plain solid appearance into the design as a template and override its base
color.

The template must be a solid, texture-free appearance or the requested RGB
will not show through -- e.g. copying a wood appearance leaves the wood texture
driving the look and the color barely changes. So we deliberately start from a
known matte plastic ("ABS", id ``Prism-374``) in the Fusion Appearance Library
rather than from whatever appearance happens to be first in the design or a
library, which is locale-independent (the id is stable even though the display
name is localized).
"""

import adsk.core

# Fusion Appearance Library and a plain, matte, texture-free plastic within it.
# Ids are stable across languages; the display names are localized.
_APPEARANCE_LIBRARY_ID = "BA5EE55E-9982-449B-9D66-9F036540E140"
_SOLID_BASE_APPEARANCE_ID = "Prism-374"  # "ABS (white)"

# Prism "opaque" appearances expose their base surface color under this
# property id; preferring it (over the first color property found) makes the
# recolor land on the visible albedo rather than a secondary modifier.
_PREFERRED_COLOR_PROPERTY_IDS = ("opaque_albedo", "surface_albedo")


def get_or_create_color_appearance(design, name, rgb):
    """Returns a Design-local Appearance named `name` showing color `rgb`.

    rgb is an (r, g, b) tuple of ints in [0, 255]. If an appearance with this
    name already exists in the design it is recolored and reused so repeated
    runs of the add-in don't pile up duplicate appearances.
    """
    existing = design.appearances.itemByName(name)
    if existing:
        _set_appearance_color(existing, rgb)
        return existing

    template = _find_solid_template_appearance(design)
    if template is None:
        return None

    appearance = design.appearances.addByCopy(template, name)
    _set_appearance_color(appearance, rgb)
    return appearance


def _find_solid_template_appearance(design):
    app = adsk.core.Application.get()

    # Preferred: the known matte plastic from the Fusion Appearance Library.
    library = app.materialLibraries.itemById(_APPEARANCE_LIBRARY_ID)
    if library:
        base = library.appearances.itemById(_SOLID_BASE_APPEARANCE_ID)
        if base:
            return base
        solid = _first_texture_free_appearance(library)
        if solid:
            return solid

    # Fallbacks: any texture-free appearance from any library, then anything.
    for lib_index in range(app.materialLibraries.count):
        solid = _first_texture_free_appearance(app.materialLibraries.item(lib_index))
        if solid:
            return solid
    for lib_index in range(app.materialLibraries.count):
        lib = app.materialLibraries.item(lib_index)
        if lib.appearances.count > 0:
            return lib.appearances.item(0)
    return None


def _first_texture_free_appearance(library):
    for i in range(library.appearances.count):
        appearance = library.appearances.item(i)
        if _color_property(appearance) is not None and not _has_texture(appearance):
            return appearance
    return None


def _has_texture(appearance):
    props = appearance.appearanceProperties
    for i in range(props.count):
        color_prop = adsk.core.ColorProperty.cast(props.item(i))
        if color_prop:
            try:
                if color_prop.hasConnectedTexture:
                    return True
            except Exception:
                pass
    return False


def _color_property(appearance):
    """The color property to drive: the preferred base-color id if present,
    otherwise the first plain (texture-free) color property."""
    props = appearance.appearanceProperties
    by_id = {}
    first = None
    for i in range(props.count):
        color_prop = adsk.core.ColorProperty.cast(props.item(i))
        if not color_prop:
            continue
        try:
            if color_prop.hasConnectedTexture:
                continue
        except Exception:
            pass
        if first is None:
            first = color_prop
        by_id[color_prop.id] = color_prop
    for pref in _PREFERRED_COLOR_PROPERTY_IDS:
        if pref in by_id:
            return by_id[pref]
    return first


def _set_appearance_color(appearance, rgb):
    color_prop = _color_property(appearance)
    if color_prop is None:
        return False
    r, g, b = rgb
    color_prop.value = adsk.core.Color.create(r, g, b, 255)
    return True
