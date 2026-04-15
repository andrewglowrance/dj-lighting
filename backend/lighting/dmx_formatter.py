"""
lighting/dmx_formatter.py

Generates a QLC+ workspace (.qxw) XML file from a CueOutputSchema.

QLC+ file structure produced:
  - One generic RGBD (4-channel) fixture per abstract group
  - One Scene function per unique section label (the dominant lighting state)
  - One Chaser function sequencing all scenes with hold times from section durations
  - One Virtual Console button wired to the Chaser

Channel layout per fixture (Generic RGB, 4 channels):
  0 → Dimmer   (0-255)
  1 → Red      (0-255)
  2 → Green    (0-255)
  3 → Blue     (0-255)

Abstract groups map to fixture IDs in declaration order. Rig-template mapping
(Phase 2) will replace these generic fixtures with real models and channel
assignments; for now this gives a working, importable demo file.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from backend.schemas.cues import CueOutputSchema


# ---------------------------------------------------------------------------
# Section colour and intensity lookup
# Matches the palette defined in lighting/rules.py
# ---------------------------------------------------------------------------

_SECTION_COLORS: dict[str, tuple[int, int, int]] = {
    "intro":     (0,   80,  255),   # cool blue
    "build":     (255, 120, 0),     # warm amber
    "drop":      (255, 0,   40),    # drop red
    "breakdown": (0,   160, 140),   # breakdown teal
    "outro":     (0,   40,  100),   # dark blue
}

_SECTION_INTENSITY: dict[str, float] = {
    "intro":     0.30,
    "build":     0.70,
    "drop":      1.00,
    "breakdown": 0.20,
    "outro":     0.25,
}

# Abstract fixture groups — order determines DMX start address
# (4 channels each, Universe 0, addresses 0, 4, 8, 12, 16)
_GROUPS = ["wash_all", "back_wash", "spots", "strobe", "moving_heads"]
_CHANNELS_PER_FIXTURE = 4
_FADE_OUT_MS = 500   # ms crossfade between scenes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cues_to_qlcplus_xml(cue_output: CueOutputSchema) -> str:
    """
    Convert a CueOutputSchema into a QLC+ workspace XML string.

    Returns a UTF-8 encoded XML string with DOCTYPE declaration, ready to
    save as a .qxw file and imported directly into QLC+ 4.x or 5.x.
    """
    # ---- collect ordered unique sections from cue list ----
    sections_ordered: list[str] = []
    section_cues: dict[str, list] = {}
    for cue in cue_output.cues:
        label = cue.section
        if label not in section_cues:
            section_cues[label] = []
            sections_ordered.append(label)
        section_cues[label].append(cue)

    # ---- build XML tree ----
    workspace = ET.Element("Workspace")
    workspace.set("xmlns", "http://www.qlcplus.org/Workspace")
    workspace.set("CurrentWindow", "VirtualConsole")

    _add_creator(workspace)

    engine = ET.SubElement(workspace, "Engine")
    _add_input_output_map(engine)
    fixture_id_map = _add_fixtures(engine)
    function_id_counter = [0]   # mutable int in list so nested funcs can mutate

    functions_el = ET.SubElement(engine, "Functions")

    # One Scene per section label
    section_function_ids: dict[str, int] = {}
    for label in sections_ordered:
        fid = function_id_counter[0]
        _add_scene(functions_el, fid, label, fixture_id_map)
        section_function_ids[label] = fid
        function_id_counter[0] += 1

    # One Chaser sequencing all scenes
    chaser_id = function_id_counter[0]
    _add_chaser(
        functions_el,
        chaser_id,
        sections_ordered,
        section_function_ids,
        section_cues,
    )

    ET.SubElement(engine, "ChannelsGroups")

    _add_virtual_console(workspace, chaser_id)

    # ---- serialise ----
    _indent(workspace)   # pretty-print without lxml dependency
    xml_bytes = ET.tostring(workspace, encoding="unicode", xml_declaration=False)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE Workspace>\n'
        + xml_bytes
    )


# ---------------------------------------------------------------------------
# XML builder helpers
# ---------------------------------------------------------------------------

def _add_creator(parent: ET.Element) -> None:
    creator = ET.SubElement(parent, "Creator")
    ET.SubElement(creator, "Name").text = "Q Light Controller Plus"
    ET.SubElement(creator, "Version").text = "4.12.8"
    ET.SubElement(creator, "Author").text = "CueForge DJ Lighting"


def _add_input_output_map(engine: ET.Element) -> None:
    iom = ET.SubElement(engine, "InputOutputMap")
    universe = ET.SubElement(iom, "Universe")
    universe.set("Name", "Universe 1")
    universe.set("ID", "0")
    # Output left unconfigured — user sets ArtNet / sACN in QLC+ after import
    ET.SubElement(universe, "Output").set("Plugin", "")


def _add_fixtures(engine: ET.Element) -> dict[str, int]:
    """
    Declare one Generic RGB fixture per abstract group.
    Returns mapping of group_name → fixture_id.
    """
    fixtures_el = ET.SubElement(engine, "Fixtures")
    fixture_id_map: dict[str, int] = {}

    for fid, group in enumerate(_GROUPS):
        fx = ET.SubElement(fixtures_el, "Fixture")
        ET.SubElement(fx, "Manufacturer").text = "Generic"
        ET.SubElement(fx, "Model").text = "Generic RGBD"
        ET.SubElement(fx, "Mode").text = "RGBD"
        ET.SubElement(fx, "ID").text = str(fid)
        ET.SubElement(fx, "Name").text = group
        ET.SubElement(fx, "Universe").text = "0"
        ET.SubElement(fx, "Address").text = str(fid * _CHANNELS_PER_FIXTURE)
        ET.SubElement(fx, "Channels").text = str(_CHANNELS_PER_FIXTURE)
        fixture_id_map[group] = fid

    return fixture_id_map


def _add_scene(
    functions_el: ET.Element,
    function_id: int,
    section_label: str,
    fixture_id_map: dict[str, int],
) -> None:
    """Create one QLC+ Scene representing the dominant state of a section."""
    color = _SECTION_COLORS.get(section_label, (255, 255, 255))
    intensity = _SECTION_INTENSITY.get(section_label, 0.5)

    scene = ET.SubElement(functions_el, "Function")
    scene.set("ID", str(function_id))
    scene.set("Type", "Scene")
    scene.set("Name", f"Section: {section_label}")

    speed = ET.SubElement(scene, "Speed")
    speed.set("FadeIn", "0")
    speed.set("FadeOut", str(_FADE_OUT_MS))
    speed.set("Duration", "0")

    ET.SubElement(scene, "ChannelGroups")

    r, g, b = color

    for group, fid in fixture_id_map.items():
        # Determine per-group intensity scaling
        if group == "strobe":
            # Strobe is only lit at full during drop
            dim = 255 if section_label == "drop" else 0
            fr, fg, fb = (255, 255, 255) if section_label == "drop" else (0, 0, 0)
        elif group == "moving_heads":
            dim = int(intensity * 0.8 * 255)
            fr, fg, fb = r, g, b
        elif group == "back_wash":
            # Back wash carries a dimmer version of the section colour
            dim = int(intensity * 0.6 * 255)
            fr, fg, fb = r, g, b
        elif group == "spots":
            dim = int(intensity * 0.9 * 255)
            fr, fg, fb = r, g, b
        else:  # wash_all — full intensity
            dim = int(intensity * 255)
            fr, fg, fb = r, g, b

        fx_el = ET.SubElement(scene, "Fixture")
        fx_el.set("Head", "0")
        fx_el.set("Fixture", str(fid))
        fx_el.set("Mode", "1")

        for ch_num, value in enumerate([dim, fr, fg, fb]):
            ch = ET.SubElement(fx_el, "Channel")
            ch.set("Number", str(ch_num))
            ch.text = str(value)


def _add_chaser(
    functions_el: ET.Element,
    chaser_id: int,
    sections_ordered: list[str],
    section_function_ids: dict[str, int],
    section_cues: dict[str, list],
) -> None:
    """Create a Chaser that sequences scenes in show order."""
    chaser = ET.SubElement(functions_el, "Function")
    chaser.set("ID", str(chaser_id))
    chaser.set("Type", "Chaser")
    chaser.set("Name", "Full Show — Auto Sequence")

    speed = ET.SubElement(chaser, "Speed")
    speed.set("FadeIn", "0")
    speed.set("FadeOut", str(_FADE_OUT_MS))
    speed.set("Duration", "0")

    ET.SubElement(chaser, "Direction").text = "Forward"
    ET.SubElement(chaser, "RunOrder").text = "SingleShot"

    steps_el = ET.SubElement(chaser, "Steps")
    for step_num, label in enumerate(sections_ordered):
        cues = section_cues.get(label, [])

        # Hold time = total span of cues in this section, in milliseconds
        if cues:
            t_start = min(c.time for c in cues)
            t_end   = max(c.time + c.duration for c in cues)
            hold_ms = max(int((t_end - t_start) * 1000), 500)
        else:
            hold_ms = 4000  # fallback 4 s

        step = ET.SubElement(steps_el, "Step")
        step.set("Number",  str(step_num))
        step.set("FadeIn",  "0")
        step.set("Hold",    str(hold_ms))
        step.set("FadeOut", str(_FADE_OUT_MS))
        step.text = str(section_function_ids[label])


def _add_virtual_console(workspace: ET.Element, chaser_id: int) -> None:
    """Add a minimal Virtual Console with a single Run Show button."""
    vc = ET.SubElement(workspace, "VirtualConsole")
    frame = ET.SubElement(vc, "Frame")

    button = ET.SubElement(frame, "Button")
    button.set("Caption", "▶ Run Full Show")
    button.set("Icon", "")

    ws = ET.SubElement(button, "WindowState")
    ws.set("Visible", "True")
    ws.set("X", "20")
    ws.set("Y", "20")
    ws.set("Width", "160")
    ws.set("Height", "60")

    appearance = ET.SubElement(button, "Appearance")
    ET.SubElement(appearance, "ForegroundColor").text = "Default"
    ET.SubElement(appearance, "BackgroundColor").text = "Default"
    ET.SubElement(appearance, "Font").text = "Default"

    func_ref = ET.SubElement(button, "Function")
    func_ref.set("ID", str(chaser_id))

    ET.SubElement(button, "Action").text = "Toggle"
    ET.SubElement(button, "Input")


# ---------------------------------------------------------------------------
# Pretty-print helper (stdlib only — no lxml needed)
# ---------------------------------------------------------------------------

def _indent(elem: ET.Element, level: int = 0) -> None:
    """Add whitespace to element tree for readable output (in-place)."""
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = pad
        for child in elem:
            _indent(child, level + 1)
        # last child's tail should close the parent's indent
        if not child.tail or not child.tail.strip():  # noqa: F821
            child.tail = pad
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = pad
