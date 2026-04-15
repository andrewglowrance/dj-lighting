"""
lighting/dmx_formatter.py

Generates a QLC+ 4.x / 5.x compatible export package:
  - cueforge_show.qxw   workspace file  (scenes + chaser + virtual console)
  - CueForge--GenericRGB.qxf  fixture definition (3-ch RGB generic fixture)

Why a .qxf is required:
  QLC+ resolves every fixture in a .qxw by looking up Manufacturer + Model
  in its local fixture library at startup. If the fixture isn't found, the
  scene channel values are discarded and the chaser has nothing to execute —
  the Virtual Console button stays grey even in Operate mode.

  We ship our own .qxf under the manufacturer name "CueForge" so it can
  never collide with QLC+'s built-in fixtures.

Fixture layout — "CueForge" / "Generic RGB" / mode "RGB" (3 channels):
  Ch 0 → Red    (0-255)
  Ch 1 → Green  (0-255)
  Ch 2 → Blue   (0-255)

Five fixtures are declared, one per abstract group, at consecutive addresses:
  wash_all     → DMX  1-3   (address 0)
  back_wash    → DMX  4-6   (address 3)
  spots        → DMX  7-9   (address 6)
  strobe       → DMX 10-12  (address 9)
  moving_heads → DMX 13-15  (address 12)

QLC+ one-time setup (per machine):
  1. Copy CueForge--GenericRGB.qxf to QLC+'s fixture folder:
       macOS   → ~/Library/Application Support/QLC+/fixtures/
       Windows → C:\\Users\\<you>\\AppData\\Roaming\\QLC+\\fixtures\\
       Linux   → ~/.qlcplus/fixtures/
  2. Restart QLC+
  3. Open cueforge_show.qxw — fixtures will resolve and scenes will load

QLC+ show workflow:
  1. Open cueforge_show.qxw
  2. Click the Virtual Console tab
  3. Press F5 (or green Operate button in toolbar) to enter Operate mode
  4. Click "Run Full Show"
  5. Press F5 to stop
"""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

from backend.schemas.cues import CueOutputSchema


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MANUFACTURER = "CueForge"
_MODEL        = "Generic RGB"
_MODE         = "RGB"
_CHANNELS_PER_FIXTURE = 3   # R, G, B
_FADE_MS      = 500

_GROUPS = ["wash_all", "back_wash", "spots", "strobe", "moving_heads"]

# Per-section, per-group RGB values (intensity already baked in)
_SECTION_RGB: dict[str, dict[str, tuple[int, int, int]]] = {
    "intro": {
        "wash_all":     (0,   20,  77),
        "back_wash":    (0,   12,  46),
        "spots":        (0,   16,  60),
        "strobe":       (0,   0,   0),
        "moving_heads": (0,   16,  60),
    },
    "build": {
        "wash_all":     (255, 120, 0),
        "back_wash":    (153, 72,  0),
        "spots":        (230, 108, 0),
        "strobe":       (0,   0,   0),
        "moving_heads": (200, 95,  0),
    },
    "drop": {
        "wash_all":     (255, 0,   40),
        "back_wash":    (255, 200, 0),
        "spots":        (255, 0,   40),
        "strobe":       (255, 255, 255),
        "moving_heads": (255, 0,   40),
    },
    "breakdown": {
        "wash_all":     (0,   32,  28),
        "back_wash":    (0,   19,  17),
        "spots":        (0,   26,  22),
        "strobe":       (0,   0,   0),
        "moving_heads": (0,   26,  22),
    },
    "outro": {
        "wash_all":     (0,   10,  25),
        "back_wash":    (0,   6,   15),
        "spots":        (0,   8,   20),
        "strobe":       (0,   0,   0),
        "moving_heads": (0,   8,   20),
    },
}
_DEFAULT_RGB: dict[str, tuple[int, int, int]] = {
    "wash_all": (100, 100, 100), "back_wash": (60, 60, 60),
    "spots": (80, 80, 80), "strobe": (0, 0, 0), "moving_heads": (60, 60, 60),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cues_to_qlcplus_zip(cue_output: CueOutputSchema) -> bytes:
    """
    Build a ZIP archive containing the .qxw workspace and the .qxf fixture
    definition. Returns raw bytes suitable for a streaming HTTP response.
    """
    qxw = cues_to_qlcplus_xml(cue_output).encode("utf-8")
    qxf = fixture_definition_qxf().encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("cueforge_show.qxw", qxw)
        zf.writestr("CueForge--GenericRGB.qxf", qxf)
    return buf.getvalue()


def cues_to_qlcplus_xml(cue_output: CueOutputSchema) -> str:
    """
    Generate the QLC+ workspace XML string (.qxw).
    References the CueForge/Generic RGB fixture by name — the .qxf must be
    installed in QLC+'s fixture library for scenes to load correctly.
    """
    sections_ordered, section_cues = _collate_sections(cue_output)

    workspace = ET.Element("Workspace")
    workspace.set("xmlns", "http://www.qlcplus.org/Workspace")
    workspace.set("CurrentWindow", "VirtualConsole")

    _creator(workspace)

    engine = ET.SubElement(workspace, "Engine")
    _input_output_map(engine)
    fixture_id_map = _fixtures(engine)

    functions_el = ET.SubElement(engine, "Functions")

    scene_ids: dict[str, int] = {}
    for fid, label in enumerate(sections_ordered):
        _scene(functions_el, fid, label, fixture_id_map)
        scene_ids[label] = fid

    chaser_id = len(sections_ordered)
    _chaser(functions_el, chaser_id, sections_ordered, scene_ids, section_cues)

    ET.SubElement(engine, "ChannelsGroups")
    _virtual_console(workspace, chaser_id)

    _indent(workspace)
    body = ET.tostring(workspace, encoding="unicode", xml_declaration=False)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE Workspace>\n'
        + body
    )


def fixture_definition_qxf() -> str:
    """
    Generate the QLC+ fixture definition XML string (.qxf).

    Defines "CueForge" / "Generic RGB" — a 3-channel RGB fixture.
    Install this file in QLC+'s fixture library folder before opening
    any .qxw exported by CueForge.
    """
    root = ET.Element("FixtureDefinition")
    root.set("xmlns", "http://www.qlcplus.org/FixtureDefinition")

    creator = ET.SubElement(root, "Creator")
    ET.SubElement(creator, "Name").text = "Q Light Controller Plus"
    ET.SubElement(creator, "Version").text = "4.12.8"
    ET.SubElement(creator, "Author").text = "CueForge DJ Lighting"

    ET.SubElement(root, "Manufacturer").text = _MANUFACTURER
    ET.SubElement(root, "Model").text = _MODEL
    ET.SubElement(root, "Type").text = "Color Changer"

    # Channel definitions
    for name, colour in [("Red", "Red"), ("Green", "Green"), ("Blue", "Blue")]:
        ch = ET.SubElement(root, "Channel")
        ch.set("Name", name)
        group = ET.SubElement(ch, "Group")
        group.set("Byte", "0")
        group.text = "Intensity"
        col = ET.SubElement(ch, "Colour")
        col.text = colour

    # Mode definition
    mode = ET.SubElement(root, "Mode")
    mode.set("Name", _MODE)

    physical = ET.SubElement(mode, "Physical")
    bulb = ET.SubElement(physical, "Bulb")
    bulb.set("Type", "LED")
    bulb.set("Lumens", "0")
    bulb.set("ColourTemperature", "0")
    dims = ET.SubElement(physical, "Dimensions")
    dims.set("Weight", "0")
    dims.set("Width", "0")
    dims.set("Height", "0")
    dims.set("Depth", "0")
    lens = ET.SubElement(physical, "Lens")
    lens.set("Name", "Other")
    lens.set("DegreesMin", "0")
    lens.set("DegreesMax", "0")
    focus = ET.SubElement(physical, "Focus")
    focus.set("Type", "Fixed")
    focus.set("PanMax", "0")
    focus.set("TiltMax", "0")
    tech = ET.SubElement(physical, "Technical")
    tech.set("PowerConsumption", "0")
    tech.set("DmxConnector", "3-pin")

    for i, ch_name in enumerate(["Red", "Green", "Blue"]):
        ch_el = ET.SubElement(mode, "Channel")
        ch_el.set("Number", str(i))
        ch_el.text = ch_name

    _indent(root)
    body = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE FixtureDefinition>\n'
        + body
    )


# ---------------------------------------------------------------------------
# XML element builders
# ---------------------------------------------------------------------------

def _collate_sections(
    cue_output: CueOutputSchema,
) -> tuple[list[str], dict[str, list]]:
    ordered: list[str] = []
    groups: dict[str, list] = {}
    for cue in cue_output.cues:
        if cue.section not in groups:
            groups[cue.section] = []
            ordered.append(cue.section)
        groups[cue.section].append(cue)
    return ordered, groups


def _creator(parent: ET.Element) -> None:
    el = ET.SubElement(parent, "Creator")
    ET.SubElement(el, "Name").text = "Q Light Controller Plus"
    ET.SubElement(el, "Version").text = "4.12.8"
    ET.SubElement(el, "Author").text = "CueForge DJ Lighting"


def _input_output_map(engine: ET.Element) -> None:
    iom = ET.SubElement(engine, "InputOutputMap")
    u = ET.SubElement(iom, "Universe")
    u.set("Name", "Universe 1")
    u.set("ID", "0")
    out = ET.SubElement(u, "Output")
    out.set("Plugin", "")
    out.set("UID", "")
    out.set("Line", "0")


def _fixtures(engine: ET.Element) -> dict[str, int]:
    container = ET.SubElement(engine, "Fixtures")
    id_map: dict[str, int] = {}
    for fid, group in enumerate(_GROUPS):
        fx = ET.SubElement(container, "Fixture")
        ET.SubElement(fx, "Manufacturer").text = _MANUFACTURER
        ET.SubElement(fx, "Model").text = _MODEL
        ET.SubElement(fx, "Mode").text = _MODE
        ET.SubElement(fx, "ID").text = str(fid)
        ET.SubElement(fx, "Name").text = group.replace("_", " ").title()
        ET.SubElement(fx, "Universe").text = "0"
        ET.SubElement(fx, "Address").text = str(fid * _CHANNELS_PER_FIXTURE)
        ET.SubElement(fx, "Channels").text = str(_CHANNELS_PER_FIXTURE)
        id_map[group] = fid
    return id_map


def _scene(
    functions_el: ET.Element,
    function_id: int,
    section_label: str,
    fixture_id_map: dict[str, int],
) -> None:
    scene = ET.SubElement(functions_el, "Function")
    scene.set("ID", str(function_id))
    scene.set("Type", "Scene")
    scene.set("Name", f"Section: {section_label.title()}")
    scene.set("Path", "")

    speed = ET.SubElement(scene, "Speed")
    speed.set("FadeIn", "0")
    speed.set("FadeOut", str(_FADE_MS))
    speed.set("Duration", "0")

    ET.SubElement(scene, "ChannelGroups")

    palette = _SECTION_RGB.get(section_label, {})

    for group, fid in fixture_id_map.items():
        r, g, b = palette.get(group, _DEFAULT_RGB.get(group, (100, 100, 100)))

        fx_el = ET.SubElement(scene, "Fixture")
        fx_el.set("Head", "0")
        fx_el.set("Fixture", str(fid))
        fx_el.set("Mode", "1")

        for ch_num, value in enumerate([r, g, b]):
            ch = ET.SubElement(fx_el, "Channel")
            ch.set("Number", str(ch_num))
            ch.text = str(value)


def _chaser(
    functions_el: ET.Element,
    chaser_id: int,
    sections_ordered: list[str],
    scene_ids: dict[str, int],
    section_cues: dict[str, list],
) -> None:
    chaser = ET.SubElement(functions_el, "Function")
    chaser.set("ID", str(chaser_id))
    chaser.set("Type", "Chaser")
    chaser.set("Name", "Full Show — Auto Sequence")
    chaser.set("Path", "")

    speed = ET.SubElement(chaser, "Speed")
    speed.set("FadeIn", "0")
    speed.set("FadeOut", str(_FADE_MS))
    speed.set("Duration", "0")

    ET.SubElement(chaser, "Direction").text = "Forward"
    ET.SubElement(chaser, "RunOrder").text = "SingleShot"

    steps_el = ET.SubElement(chaser, "Steps")
    for step_num, label in enumerate(sections_ordered):
        cues = section_cues.get(label, [])
        if cues:
            t_start = min(c.time for c in cues)
            t_end   = max(c.time + c.duration for c in cues)
            hold_ms = max(int((t_end - t_start) * 1000), 1000)
        else:
            hold_ms = 4000

        step = ET.SubElement(steps_el, "Step")
        step.set("Number",  str(step_num))
        step.set("FadeIn",  "0")
        step.set("Hold",    str(hold_ms))
        step.set("FadeOut", str(_FADE_MS))
        step.text = str(scene_ids[label])


def _virtual_console(workspace: ET.Element, chaser_id: int) -> None:
    vc = ET.SubElement(workspace, "VirtualConsole")

    frame = ET.SubElement(vc, "Frame")
    frame.set("Caption", "")

    frame_app = ET.SubElement(frame, "Appearance")
    ET.SubElement(frame_app, "FrameStyle").text = "None"
    ET.SubElement(frame_app, "ForegroundColor").text = "Default"
    ET.SubElement(frame_app, "BackgroundColor").text = "Default"
    ET.SubElement(frame_app, "BackgroundImage").text = "None"
    ET.SubElement(frame_app, "Font").text = "Default"

    button = ET.SubElement(frame, "Button")
    button.set("Caption", "Run Full Show")
    button.set("Icon", "")

    ws = ET.SubElement(button, "WindowState")
    ws.set("Visible", "True")
    ws.set("X", "20")
    ws.set("Y", "20")
    ws.set("Width", "160")
    ws.set("Height", "60")

    btn_app = ET.SubElement(button, "Appearance")
    ET.SubElement(btn_app, "FrameStyle").text = "None"
    ET.SubElement(btn_app, "ForegroundColor").text = "Default"
    ET.SubElement(btn_app, "BackgroundColor").text = "Default"
    ET.SubElement(btn_app, "BackgroundImage").text = "None"
    ET.SubElement(btn_app, "Font").text = "Default"

    func_ref = ET.SubElement(button, "Function")
    func_ref.set("ID", str(chaser_id))

    ET.SubElement(button, "Action").text = "Toggle"
    ET.SubElement(button, "Input")


# ---------------------------------------------------------------------------
# Pretty-print (stdlib only)
# ---------------------------------------------------------------------------

def _indent(elem: ET.Element, level: int = 0) -> None:
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():  # noqa: F821
            child.tail = pad
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = pad
