from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Union

class FillSpec(BaseModel):
    """
    Fill region with block.
    """
    reason: str = Field(
        ...,
        description=(
            "Short reasoning (≤20 words) explaining what's already built, what's next, and why this fill region was selected and is safe."
        ),
    )
    start_coordinates: List[int] = Field(
        ...,
        description="List of the 3 coordinates of one corner of the cuboidal region being filled. Must be non-negative integers!",
    )
    end_coordinates: List[int] = Field(
        ...,
        description="List of the 3 coordinates of the opposite corner of the cuboidal region being filled. Must be non-negative integers!",
    )
    block: str = Field(
        ...,
        description='Block to use to fill the region, e.g. "minecraft:oak_log". Must be a valid Minecraft: Java Edition block.',
    )
    block_states: Optional[Union[Dict[str, str], str]] = Field(
        default=None,
        description="""
        Optional block state properties (orientation, facing, variant, etc.)
        as either a dict (recommended) or a Minecraft-style string (tolerated).
        Examples accepted:
        - {"facing": "north", "half": "lower"}
        - "facing=north,half=lower"
        - "[facing=north,half=lower]"
        """,
    )
    mode: Literal["replace", "keep", "outline"] = Field(
        ...,
        description="replace = replace all blocks, keep = replace non-air blocks only, outline = fill only outer shell, leaving inside untouched.",
    )
    explanation: str = Field(
        ..., description="Brief explanation of action (e.g. 'building wall', 'adding roof') to show in progress bar for the user."
    )




class BeamSpec(BaseModel):
    """
    Draw a line between two points with a given cross-section and thickness.
    """
    start_coordinates: List[int] = Field(
        ...,
        description="3D start point of the line. Must be non-negative integers."
    )
    end_coordinates: List[int] = Field(
        ...,
        description="3D end point of the line. Must be non-negative integers."
    )
    block: str = Field(
        ...,
        description='Block to use for the line, e.g. "minecraft:stone".'
    )
    block_states: Optional[Union[Dict[str, str], str]] = Field(
        default=None,
        description="Optional block state properties (dict or Minecraft-style string)"
    )
    mode: Literal["replace", "keep", "outline"] = Field(
        ...,
        description="Fill mode for the line."
    )
    shape: Literal["square", "circular"] = Field(
        ...,
        description="Cross-section shape of the line."
    )
    direction: Optional[Literal["XY", "YZ", "XZ", "X", "Y", "Z"]] = Field(
        ...,
        description="Which coordinate plane or axis should each stacked circle/square used be parallel to?"
    )
    thickness: int = Field(
        ...,
        description="Radius of the line's cross-section in blocks."
    )
    fill: Literal["filled", "hollow"] = Field(
        ...,
        description="Whether the cross-section is filled or hollow."
    )
    explanation: str = Field(
        ...,
        description="Brief explanation of this line segment."
    )
    reason: str = Field(
        ...,
        description="Short reasoning explaining what's already built and next step."
    )




class PlaneSpec(BaseModel):
    """
    Draws a 1-block-thick inclined plane between two 3D points.
    The plane is perpendicular to one of the coordinate planes (XY, YZ, XZ).
    """
    start_coordinates: List[int] = Field(
        ...,
        description="One corner of the plane (x1, y1, z1)."
    )
    end_coordinates: List[int] = Field(
        ...,
        description="Opposite corner of the plane (x2, y2, z2)."
    )
    perpendicular_to: Literal["XY", "YZ", "XZ"] = Field(
        ...,
        description="Which coordinate plane this plane is perpendicular to. E.g. a vertical wall is perpendicular to XZ."
    )
    block: str = Field(
        ...,
        description='Block to use for the plane, e.g. "minecraft:stone".'
    )
    block_states: Optional[Union[Dict[str, str], str]] = Field(
        default=None,
        description="Optional block state properties."
    )
    mode: Literal["replace", "keep", "outline"] = Field(
        ...,
        description="Fill mode for the plane."
    )
    explanation: str = Field(
        ...,
        description="Brief explanation of the operation."
    )
    reason: str = Field(
        ...,
        description="Short reasoning about why this plane is being placed."
    )