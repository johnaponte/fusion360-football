"""Helpers for applying flat RGB colors to bodies.

Fusion's command dialogs have no native color-swatch input, and appearances
are normally picked from a library rather than built from raw RGB. To turn an
(r, g, b) triple into something that can be assigned to a BRepBody, we copy
any existing appearance into the design (as a template) and then override its
color property -- this works regardless of which appearance libraries happen
to be loaded or what language Fusion is running in, since it doesn't depend on
matching a specific appearance name.
"""

import adsk.core


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

    template = _find_template_appearance(design)
    if template is None:
        return None

    appearance = design.appearances.addByCopy(template, name)
    _set_appearance_color(appearance, rgb)
    return appearance


def _find_template_appearance(design):
    if design.appearances.count > 0:
        return design.appearances.item(0)

    app = adsk.core.Application.get()
    for lib_index in range(app.materialLibraries.count):
        library = app.materialLibraries.item(lib_index)
        if library.appearances.count > 0:
            return library.appearances.item(0)
    return None


def _set_appearance_color(appearance, rgb):
    r, g, b = rgb
    color = adsk.core.Color.create(r, g, b, 255)
    props = appearance.appearanceProperties
    for i in range(props.count):
        color_prop = adsk.core.ColorProperty.cast(props.item(i))
        if color_prop:
            color_prop.value = color
            return True
    return False
