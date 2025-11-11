import time
import sys
import random
import json
import argparse

from pynput.keyboard import Controller

from tools import *

def fill(spec: FillSpec, origin: List[int] = [0, -60, 0]) -> List[str]:
    """
    Wrapper for FillSpec.
    Converts origin + translated coordinates + block states into a proper MC /fill command
    """

    # offset coordinates to MC coordinate system
    x1 = spec.start_coordinates[0] + origin[0]
    y1 = spec.start_coordinates[1] + origin[1]
    z1 = spec.start_coordinates[2] + origin[2]
    x2 = spec.end_coordinates[0] + origin[0]
    y2 = spec.end_coordinates[1] + origin[1]
    z2 = spec.end_coordinates[2] + origin[2]

    block_str = spec.block

    # in case of wrong block_states format
    if spec.block_states:
        bs = spec.block_states
        if isinstance(bs, str):
            bs = bs.strip().strip("[]")
            parts = [p.strip() for p in bs.split(",") if p.strip()]
            bs_dict = {}
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    bs_dict[k.strip()] = v.strip()
            bs = bs_dict

        if isinstance(bs, dict) and bs:
            block_str += "[" + ",".join(f"{k}={v}" for k, v in bs.items()) + "]"

    # --- HANDLE /fill OVERFLOW (BETA; COMPLETELY VIBE CODED) ---
    dx = abs(x2 - x1) + 1
    dy = abs(y2 - y1) + 1
    dz = abs(z2 - z1) + 1
    volume = dx * dy * dz

    if volume > 32768:
        cmds = []
        # Split along the longest axis into sub-regions under 32768 blocks
        max_blocks = 32768
        # determine step size along longest dimension
        if dx >= dy and dx >= dz:
            step = max(1, max_blocks // (dy * dz))
            for xs in range(min(x1, x2), max(x1, x2) + 1, step):
                xe = min(xs + step - 1, max(x1, x2))
                cmds.append(f"fill {xs} {y1} {z1} {xe} {y2} {z2} {block_str} {spec.mode}")
        elif dy >= dx and dy >= dz:
            step = max(1, max_blocks // (dx * dz))
            for ys in range(min(y1, y2), max(y1, y2) + 1, step):
                ye = min(ys + step - 1, max(y1, y2))
                cmds.append(f"fill {x1} {ys} {z1} {x2} {ye} {z2} {block_str} {spec.mode}")
        else:
            step = max(1, max_blocks // (dx * dy))
            for zs in range(min(z1, z2), max(z1, z2) + 1, step):
                ze = min(zs + step - 1, max(z1, z2))
                cmds.append(f"fill {x1} {y1} {zs} {x2} {y2} {ze} {block_str} {spec.mode}")
        return cmds
    # --- END HANDLE /fill OVERFLOW ---

    cmd = f"fill {x1} {y1} {z1} {x2} {y2} {z2} {block_str} {spec.mode}"
    return [cmd]

def beam(spec: BeamSpec, origin: List[int] = [0, -60, 0]) -> List[str]:
    """
    Builds a beam (square or circular cross-section) between two 3D points.
    Optimized for axis-aligned beams using bulk /fill operations.
    """

    cmds = []

    x1, y1, z1 = spec.start_coordinates
    x2, y2, z2 = spec.end_coordinates
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1

    abs_diffs = [abs(dx), abs(dy), abs(dz)]

    best_axis = 1

    if hasattr(spec, "direction"):
        if spec.direction == "XY" or spec.direction == "Z":
            best_axis = 2
        elif spec.direction == "YZ" or spec.direction == "X":
            best_axis = 0
        else:  # "XZ"
            best_axis = 1
    else:
        best_axis = abs_diffs.index(max(abs_diffs))
        if dx == 0 and dy == 0 and dz == 0: # special case: 1-block-thick with no direction specified should default to horizontal where it is most commonly used
            best_axis = 1

    def fill_cmd(xa, ya, za, xb, yb, zb, block, mode, reason, explanation):
        return fill(
            FillSpec(
                reason=reason,
                start_coordinates=[xa, ya, za],
                end_coordinates=[xb, yb, zb],
                block=block,
                block_states=spec.block_states,
                mode=mode,
                explanation=explanation,
            ),
            origin=origin,
        )

    # ---- OPTIMIZATION: Axis-aligned beam ----
    if (
        (x1 == x2 and y1 == y2) or
        (x1 == x2 and z1 == z2) or
        (y1 == y2 and z1 == z2)
    ):
        # Determine the constant axes and the axis of alignment
        if best_axis==0:
            axis = "x"
        elif best_axis==1:
            axis = "y"
        else:
            axis = "z"

        # Define the full bounding cuboid
        if axis == "x":
            xa, xb = sorted([x1, x2])
            cmds += fill_cmd(
                xa - 0, y1 - spec.thickness, z1 - spec.thickness,
                xb + 0, y1 + spec.thickness, z1 + spec.thickness,
                spec.block, spec.mode, spec.reason, spec.explanation
            )
            # Clear corners outside the circle, if circular
            if spec.shape == "circular":
                r = spec.thickness
                for y in range(-r, r + 1):
                    for z in range(-r, r + 1):
                        if y * y + z * z > r * r:
                            cmds += fill_cmd(
                                xa, y1 + y, z1 + z,
                                xb, y1 + y, z1 + z,
                                "minecraft:air", "replace",
                                "clearing circular corners",
                                spec.explanation+": "+"trim outside incircle",
                            )
                        if spec.fill=="hollow" and y * y + z * z < (r-1) * (r-1):
                            cmds += fill_cmd(
                                xa, y1 + y, z1 + z,
                                xb, y1 + y, z1 + z,
                                "minecraft:air", "replace",
                                "hollowing circle",
                                spec.explanation+": "+"trim inside incircle",
                            )
        elif axis == "y":
            ya, yb = sorted([y1, y2])
            cmds += fill_cmd(
                x1 - spec.thickness, ya - 0, z1 - spec.thickness,
                x1 + spec.thickness, yb + 0, z1 + spec.thickness,
                spec.block, spec.mode, spec.reason, spec.explanation
            )
            if spec.shape == "circular":
                r = spec.thickness
                for x in range(-r, r + 1):
                    for z in range(-r, r + 1):
                        if x * x + z * z > r * r:
                            cmds += fill_cmd(
                                x1 + x, ya, z1 + z,
                                x1 + x, yb, z1 + z,
                                "minecraft:air", "replace",
                                "clearing circular corners",
                                spec.explanation+": "+"trim outside incircle",
                            )
                        if spec.fill=="hollow" and x * x + z * z < (r-1) * (r-1):
                            cmds += fill_cmd(
                                x1 + x, ya, z1 + z,
                                x1 + x, yb, z1 + z,
                                "minecraft:air", "replace",
                                "hollowing circle",
                                spec.explanation+": "+"trim inside incircle",
                            )
        else:  # z-axis alignment
            za, zb = sorted([z1, z2])
            cmds += fill_cmd(
                x1 - spec.thickness, y1 - spec.thickness, za - 0,
                x1 + spec.thickness, y1 + spec.thickness, zb + 0,
                spec.block, spec.mode, spec.reason, spec.explanation
            )
            if spec.shape == "circular":
                r = spec.thickness
                for x in range(-r, r + 1):
                    for y in range(-r, r + 1):
                        if x * x + y * y > r * r:
                            cmds += fill_cmd(
                                x1 + x, y1 + y, za,
                                x1 + x, y1 + y, zb,
                                "minecraft:air", "replace",
                                "clearing circular corners",
                                spec.explanation+": "+"trim outside incircle",
                            )
                        if spec.fill=="hollow" and x * x + y * y < (r-1) * (r-1):
                            cmds += fill_cmd(
                                x1 + x, y1 + y, za,
                                x1 + x, y1 + y, zb,
                                "minecraft:air", "replace",
                                "hollowing circle",
                                spec.explanation+": "+"trim inside incircle",
                            )
        return cmds

    # ---- GENERAL CASE: Arbitrary orientation ----
    # fallback to layer-by-layer construction along best axis
    length = abs_diffs[best_axis]
    for i in range(length + 1):
        t = i / max(length, 1)
        cx = round(x1 + t * dx)
        cy = round(y1 + t * dy)
        cz = round(z1 + t * dz)

        # Build full filled square cross-section first
        cmds += fill_cmd(
            cx - spec.thickness,
            cy - spec.thickness,
            cz - spec.thickness,
            cx + spec.thickness,
            cy + spec.thickness,
            cz + spec.thickness,
            spec.block,
            spec.mode,
            spec.reason,
            spec.explanation,
        )

        # Trim to circle, if necessary
        if spec.shape == "circular":
            r = spec.thickness
            if best_axis == 0:  # x-axis
                for y in range(-r, r + 1):
                    for z in range(-r, r + 1):
                        if y * y + z * z > r * r:
                            cmds += fill_cmd(
                                cx, cy + y, cz + z,
                                cx, cy + y, cz + z,
                                "minecraft:air", "replace",
                                "clearing circular edges",
                                spec.explanation+": "+"trim outside incircle",
                            )
            elif best_axis == 1:  # y-axis
                for x in range(-r, r + 1):
                    for z in range(-r, r + 1):
                        if x * x + z * z > r * r:
                            cmds += fill_cmd(
                                cx + x, cy, cz + z,
                                cx + x, cy, cz + z,
                                "minecraft:air", "replace",
                                "clearing circular edges",
                                spec.explanation+": "+"trim outside incircle",
                            )
            else:  # z-axis
                for x in range(-r, r + 1):
                    for y in range(-r, r + 1):
                        if x * x + y * y > r * r:
                            cmds += fill_cmd(
                                cx + x, cy + y, cz,
                                cx + x, cy + y, cz,
                                "minecraft:air", "replace",
                                "clearing circular edges",
                                spec.explanation+": "+"trim outside incircle",
                            )

    return cmds

def plane(spec: PlaneSpec, origin: List[int] = [0, -60, 0]) -> List[str]:
    """
    Builds a 1-block-thick inclined plane between two 3D points.
    The plane is perpendicular to one of XY, YZ, or XZ coordinate planes.
    Returns a list of /fill commands using the safer fill() wrapper.
    """

    cmds = []

    x1, y1, z1 = spec.start_coordinates
    x2, y2, z2 = spec.end_coordinates
    perp = spec.perpendicular_to.upper()

    def fill_cmd(a, b, c, d, e, f, block, mode, reason, explanation):
        return fill(
            FillSpec(
                reason=reason,
                start_coordinates=[a, b, c],
                end_coordinates=[d, e, f],
                block=block,
                block_states=spec.block_states,
                mode=mode,
                explanation=explanation,
            ),
            origin=origin,
        )

    # === Case 1: Plane perpendicular to XY (vertical sheet along Z) ===
    if perp == "XY":
        zmin, zmax = sorted([z1, z2])
        # The plane’s shape in XY-space:
        dx, dy = x2 - x1, y2 - y1
        abs_dx, abs_dy = abs(dx), abs(dy)
        best_axis = "x" if abs_dx >= abs_dy else "y"

        # Iterate along best axis, fill lines along the other
        steps = abs_dx if best_axis == "x" else abs_dy
        for i in range(steps + 1):
            t = i / max(steps, 1)
            xi = round(x1 + t * dx)
            yi = round(y1 + t * dy)
            # Fill line along the other axis
            if best_axis == "x":
                # interpolate y and fill a line parallel to y at current x
                cmds += fill_cmd(
                    xi, yi, zmin,
                    xi, yi, zmax,
                    spec.block, spec.mode, spec.reason, spec.explanation
                )
            else:
                # interpolate x and fill a line parallel to x at current y
                cmds += fill_cmd(
                    xi, yi, zmin,
                    xi, yi, zmax,
                    spec.block, spec.mode, spec.reason, spec.explanation
                )

    # === Case 2: Plane perpendicular to YZ (vertical sheet along X) ===
    elif perp == "YZ":
        xmin, xmax = sorted([x1, x2])
        dy, dz = y2 - y1, z2 - z1
        abs_dy, abs_dz = abs(dy), abs(dz)
        best_axis = "y" if abs_dy >= abs_dz else "z"
        steps = abs_dy if best_axis == "y" else abs_dz
        for i in range(steps + 1):
            t = i / max(steps, 1)
            yi = round(y1 + t * dy)
            zi = round(z1 + t * dz)
            if best_axis == "y":
                cmds += fill_cmd(
                    xmin, yi, zi,
                    xmax, yi, zi,
                    spec.block, spec.mode, spec.reason, spec.explanation
                )
            else:
                cmds += fill_cmd(
                    xmin, yi, zi,
                    xmax, yi, zi,
                    spec.block, spec.mode, spec.reason, spec.explanation
                )

    # === Case 3: Plane perpendicular to XZ (horizontal or sloped sheet along Y) ===
    elif perp == "XZ":
        ymin, ymax = sorted([y1, y2])
        dx, dz = x2 - x1, z2 - z1
        abs_dx, abs_dz = abs(dx), abs(dz)
        best_axis = "x" if abs_dx >= abs_dz else "z"
        steps = abs_dx if best_axis == "x" else abs_dz
        for i in range(steps + 1):
            t = i / max(steps, 1)
            xi = round(x1 + t * dx)
            zi = round(z1 + t * dz)
            if best_axis == "x":
                cmds += fill_cmd(
                    xi, ymin, min(z1, z2),
                    xi, ymax, max(z1, z2),
                    spec.block, spec.mode, spec.reason, spec.explanation
                )
            else:
                cmds += fill_cmd(
                    min(x1, x2), ymin, zi,
                    max(x1, x2), ymax, zi,
                    spec.block, spec.mode, spec.reason, spec.explanation
                )
    else:
        raise ValueError(f"Invalid 'perpendicular_to' value: {perp}")

    return cmds




map_tools_to_wrappers = {
    "FillSpec": fill,
    "BeamSpec": beam,
    "PlaneSpec": plane
}

def enter_commands(filename, min_typing_speed=0.001, delay=0.2, counter_max=10, origin=[0, -60, 0], start_index=0):
    '''
    To enter commands into the Minecraft console
    '''
    
    print("Please make Minecraft the active window, with the console active and blank.")
    for i in range(counter_max):
        print(f"Countdown: {counter_max-i} s", end=" \r")
        time.sleep(1)

    keyboard = Controller()

    # read commands from JSON
    with open(filename, "r") as file:
        data = json.load(file)
        tool_calls = data.get("tool_calls", [])

        i = 0
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            spec = eval(tool_name)(**tool_args)
            cmds = map_tools_to_wrappers[tool_name](spec, origin=origin)
            
            for cmd in cmds:
                i += 1
                if i<start_index:
                    print()
                    continue
                print(f"[{i}] {spec.explanation} ({tool_name}): ", end="", flush=True)

                keyboard.press('/')
                time.sleep(min_typing_speed*(1+random.random()))
                keyboard.release('/')

                # type command
                for char in cmd:
                    keyboard.type(char)
                    print(char, end="", flush=True)
                    time.sleep(min_typing_speed*(1+random.random())) # just in case there is some kind of captcha
                
                # enter
                print()
                keyboard.type('\n')
                time.sleep(min_typing_speed*(1+random.random()))

                time.sleep(delay*(1+random.random()))

                # open chat
                keyboard.press('t')
                time.sleep(min_typing_speed*(1+random.random()))
                keyboard.release('t')

                time.sleep(delay*(1+random.random()))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load JSON blueprint and create+enter commands into Minecraft console.")
    parser.add_argument("--blueprint_path", required=True, help="Path to the JSON blueprint.")
    parser.add_argument("--origin", nargs=3, type=int, required=True, metavar=("X", "Y", "Z"),
                        help="Origin coordinates (3 space-separated integers) where the construction should start.")
    parser.add_argument("--min_typing_speed", type=float, default=0.0005,
                        help="Minimum typing speed (seconds per character).")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay between commands (seconds).")
    parser.add_argument("--counter_max", type=int, default=20,
                        help="Number of seconds to count down before starting, to allow for switching to Minecraft window.")
    parser.add_argument("--start_index", type=int, default=0,
                        help="Specify command index to resume a cancelled run. Command index is not necessarily the index of the tool call in the JSON.")

    args = parser.parse_args()

    enter_commands(filename=args.blueprint_path, min_typing_speed=args.min_typing_speed, delay=args.delay, counter_max=args.counter_max, origin=args.origin, start_index=args.start_index)