"""
lighting/stage_layout.py

Defines 3D stage layouts for each rig template.
Consumed by GET /api/visualizer/{rig_id} and used by the in-browser renderer.

Coordinate system (right-hand, Y-up):
  X  left (-) → right (+)
  Y  floor (0) → up (+)
  Z  front (+) → back (-)

Each fixture entry:
  id          str    matches the fixture id in the rig template JSON
  group       str    abstract group name (wash_all, moving_heads, etc.)
  type        str    rendering hint: par | moving_head | strobe | batten | derby | laser_rgb
  position    [x,y,z] 3D mount position in metres
  aim         [x,y,z] default aim direction vector (normalised in frontend)
  beam_angle  float  cone half-angle in degrees (lasers: razor-thin, 1-2°)
  scan_angle  float  (laser_rgb only) maximum sweep half-angle in degrees
  beam_length float  (laser_rgb only) how far in metres the beam travels before fading
  label       str    display label
"""

from __future__ import annotations

LAYOUTS: dict[str, dict] = {

    # -----------------------------------------------------------------------
    "small_club": {
        "stage": {
            "width": 8, "depth": 6, "height": 4,
            "truss": [
                {"x": 0, "y": 4.0, "z": -1.0, "length": 8, "axis": "x"}
            ],
        },
        "fixtures": [
            # Aim wash PARs toward audience (forward+slight down) — not at floor
            {"id": "par_wash_l",  "group": "wash_all",     "type": "par",          "position": [-2.5, 4.0, -1.0], "aim": [-0.25, -0.55, 0.8], "beam_angle": 28, "label": "Wash L"},
            {"id": "par_wash_r",  "group": "wash_all",     "type": "par",          "position": [ 2.5, 4.0, -1.0], "aim": [ 0.25, -0.55, 0.8], "beam_angle": 28, "label": "Wash R"},
            {"id": "par_back_l",  "group": "back_wash",    "type": "par",          "position": [-1.5, 4.0, -3.5], "aim": [ 0.0,  -0.45, 0.9], "beam_angle": 25, "label": "Back L"},
            {"id": "par_back_r",  "group": "back_wash",    "type": "par",          "position": [ 1.5, 4.0, -3.5], "aim": [ 0.0,  -0.45, 0.9], "beam_angle": 25, "label": "Back R"},
            {"id": "mh_wash_1",   "group": "moving_heads", "type": "moving_head",  "position": [ 0.0, 4.0, -1.0], "aim": [ 0.0,  -0.6,  0.8], "beam_angle": 14, "label": "MH Wash"},
            {"id": "strobe_1",    "group": "strobe",       "type": "strobe",       "position": [ 0.0, 4.0,  0.3], "aim": [ 0.0,  -0.7,  0.7], "beam_angle": 65, "label": "Strobe"},
            # Overhead truss laser — sweeps through haze toward audience (no floor units)
            {"id": "laser_oh_l",  "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [-1.5, 3.9, -0.8], "aim": [-0.15, -0.35, 1.0],
             "beam_angle": 1, "scan_angle": 45, "beam_length": 8.0,
             "label": "Laser L"},
            {"id": "laser_oh_c",  "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [ 0.0, 3.9, -0.8], "aim": [ 0.0,  -0.35, 1.0],
             "beam_angle": 1, "scan_angle": 45, "beam_length": 8.0,
             "label": "Laser C"},
            {"id": "laser_oh_r",  "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [ 1.5, 3.9, -0.8], "aim": [ 0.15, -0.35, 1.0],
             "beam_angle": 1, "scan_angle": 45, "beam_length": 8.0,
             "label": "Laser R"},
        ],
    },

    # -----------------------------------------------------------------------
    "festival_lite": {
        "stage": {
            "width": 16, "depth": 10, "height": 8,
            "truss": [
                {"x": 0, "y": 8.0, "z": -1.5, "length": 16, "axis": "x"},
                {"x": 0, "y": 8.0, "z": -5.0, "length": 16, "axis": "x"},
            ],
        },
        "fixtures": [
            # 8 PARs aimed toward audience (forward/horizontal) not at floor
            {"id": "par_1", "group": "wash_all", "type": "par", "position": [-6.5, 8.0, -1.5], "aim": [-0.8, -0.5, 0.8], "beam_angle": 28, "label": "PAR 1"},
            {"id": "par_2", "group": "wash_all", "type": "par", "position": [-4.5, 8.0, -1.5], "aim": [-0.4, -0.5, 0.8], "beam_angle": 28, "label": "PAR 2"},
            {"id": "par_3", "group": "wash_all", "type": "par", "position": [-2.0, 8.0, -1.5], "aim": [ 0.0, -0.5, 0.8], "beam_angle": 28, "label": "PAR 3"},
            {"id": "par_4", "group": "wash_all", "type": "par", "position": [-0.5, 8.0, -1.5], "aim": [ 0.0, -0.5, 0.8], "beam_angle": 28, "label": "PAR 4"},
            {"id": "par_5", "group": "wash_all", "type": "par", "position": [ 0.5, 8.0, -1.5], "aim": [ 0.0, -0.5, 0.8], "beam_angle": 28, "label": "PAR 5"},
            {"id": "par_6", "group": "wash_all", "type": "par", "position": [ 2.0, 8.0, -1.5], "aim": [ 0.0, -0.5, 0.8], "beam_angle": 28, "label": "PAR 6"},
            {"id": "par_7", "group": "wash_all", "type": "par", "position": [ 4.5, 8.0, -1.5], "aim": [ 0.4, -0.5, 0.8], "beam_angle": 28, "label": "PAR 7"},
            {"id": "par_8", "group": "wash_all", "type": "par", "position": [ 6.5, 8.0, -1.5], "aim": [ 0.8, -0.5, 0.8], "beam_angle": 28, "label": "PAR 8"},
            # 2 LED battens — rear truss, audience-facing
            {"id": "batten_l", "group": "back_wash", "type": "batten", "position": [-3.0, 8.0, -5.0], "aim": [ 0.0, -0.4, 0.9], "beam_angle": 75, "label": "Batten L"},
            {"id": "batten_r", "group": "back_wash", "type": "batten", "position": [ 3.0, 8.0, -5.0], "aim": [ 0.0, -0.4, 0.9], "beam_angle": 75, "label": "Batten R"},
            # 4 moving head spots — front truss
            {"id": "mh_spot_1", "group": "moving_heads", "type": "moving_head", "position": [-5.0, 8.0, -1.5], "aim": [-1.2, -0.6, 0.6], "beam_angle":  9, "label": "MH 1"},
            {"id": "mh_spot_2", "group": "moving_heads", "type": "moving_head", "position": [-1.5, 8.0, -1.5], "aim": [-0.4, -0.6, 0.6], "beam_angle":  9, "label": "MH 2"},
            {"id": "mh_spot_3", "group": "moving_heads", "type": "moving_head", "position": [ 1.5, 8.0, -1.5], "aim": [ 0.4, -0.6, 0.6], "beam_angle":  9, "label": "MH 3"},
            {"id": "mh_spot_4", "group": "moving_heads", "type": "moving_head", "position": [ 5.0, 8.0, -1.5], "aim": [ 1.2, -0.6, 0.6], "beam_angle":  9, "label": "MH 4"},
            # 2 spot positions
            {"id": "spot_l", "group": "spots", "type": "moving_head", "position": [-6.0, 8.0, -3.5], "aim": [-1.5, -0.6, 0.5], "beam_angle":  7, "label": "Spot L"},
            {"id": "spot_r", "group": "spots", "type": "moving_head", "position": [ 6.0, 8.0, -3.5], "aim": [ 1.5, -0.6, 0.5], "beam_angle":  7, "label": "Spot R"},
            # 2 strobes — front truss
            {"id": "strobe_1", "group": "strobe", "type": "strobe", "position": [-2.0, 8.0, -0.5], "aim": [ 0.0, -0.65, 0.75], "beam_angle": 68, "label": "Strobe L"},
            {"id": "strobe_2", "group": "strobe", "type": "strobe", "position": [ 2.0, 8.0, -0.5], "aim": [ 0.0, -0.65, 0.75], "beam_angle": 68, "label": "Strobe R"},
            # ── Festival laser array — overhead truss only (no floor units) ──
            # All three units sweep through haze in a coordinated fan toward audience.
            {"id": "laser_oh_l",  "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [-4.0, 8.0, -5.0], "aim": [ 0.20, -0.30, 1.0],
             "beam_angle": 1, "scan_angle": 65, "beam_length": 22.0, "label": "Laser L"},
            {"id": "laser_oh_r",  "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [ 4.0, 8.0, -5.0], "aim": [-0.20, -0.30, 1.0],
             "beam_angle": 1, "scan_angle": 65, "beam_length": 22.0, "label": "Laser R"},
            {"id": "laser_oh_c",  "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [ 0.0, 8.0, -1.5], "aim": [ 0.0,  -0.30, 1.0],
             "beam_angle": 1, "scan_angle": 55, "beam_length": 16.0, "label": "Laser C"},
        ],
    },

    # -----------------------------------------------------------------------
    "mobile_dj": {
        "stage": {
            "width": 4, "depth": 3, "height": 2.5,
            "truss": [
                {"x": 0, "y": 2.5, "z": 0.0, "length": 4, "axis": "x"}
            ],
        },
        "fixtures": [
            {"id": "wash_bar_l", "group": "wash_all",  "type": "batten",       "position": [-1.2, 2.5,  0.0], "aim": [ 0.0, -0.5,  0.9], "beam_angle": 55, "label": "Wash L"},
            {"id": "wash_bar_r", "group": "wash_all",  "type": "batten",       "position": [ 1.2, 2.5,  0.0], "aim": [ 0.0, -0.5,  0.9], "beam_angle": 55, "label": "Wash R"},
            {"id": "derby_1",    "group": "spots",     "type": "derby",        "position": [ 0.0, 2.5,  0.0], "aim": [ 0.0, -0.6,  0.8], "beam_angle": 18, "label": "Derby"},
            {"id": "strobe_1",   "group": "strobe",    "type": "strobe",       "position": [ 0.0, 2.5,  0.4], "aim": [ 0.0, -0.6,  0.8], "beam_angle": 62, "label": "Strobe"},
            # 2 overhead compact RGB lasers — truss mounted, sweep toward audience
            {"id": "laser_oh_l", "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [-0.8, 2.3,  0.3], "aim": [-0.1, -0.35, 1.0],
             "beam_angle": 1, "scan_angle": 30, "beam_length": 5.0, "label": "Laser L"},
            {"id": "laser_oh_r", "group": "lasers", "type": "laser_rgb",
             "emission_zone": "overhead",
             "position": [ 0.8, 2.3,  0.3], "aim": [ 0.1, -0.35, 1.0],
             "beam_angle": 1, "scan_angle": 30, "beam_length": 5.0, "label": "Laser R"},
        ],
    },
}


def get_layout(rig_id: str) -> dict:
    if rig_id not in LAYOUTS:
        available = list(LAYOUTS.keys())
        raise KeyError(f"No stage layout for rig '{rig_id}'. Available: {available}")
    return {"rig_id": rig_id, **LAYOUTS[rig_id]}
