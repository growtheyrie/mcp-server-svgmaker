"""
SVGMaker MCP Server

Generate, edit, vectorize, and optimize SVGs via the SVGMaker REST API.
Deployed on Prefect Horizon.

Base URL: https://api.svgmaker.io/v1
Auth header: x-api-key: svgmaker-io{SVGMAKER_API_KEY}
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# --- Setup ---

load_dotenv()

log_level = logging.DEBUG if os.environ.get("SVGMAKER_DEBUG", "").lower() == "true" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("svgmaker_mcp_server")

SVGMAKER_API_KEY = os.environ["SVGMAKER_API_KEY"]
BASE_URL = os.environ.get("SVGMAKER_BASE_URL", "https://api.svgmaker.io/v1")

mcp = FastMCP(
    name="SVGMaker",
    instructions="Generate, edit, vectorize, and optimize SVGs via the SVGMaker API.",
)


# --- HTTP helpers ---

def _headers() -> Dict[str, str]:
    return {"x-api-key": f"svgmaker-io{SVGMAKER_API_KEY}"}


# --- Error handler ---

def _handle_error(e: Exception, tool_name: str) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 401:
            return json.dumps({"error": f"{tool_name}: Authentication failed. Check SVGMAKER_API_KEY."})
        if code == 402:
            return json.dumps({"error": f"{tool_name}: Insufficient credits."})
        if code == 422:
            return json.dumps({"error": f"{tool_name}: Content policy violation."})
        if code == 429:
            return json.dumps({"error": f"{tool_name}: Rate limit exceeded. Wait before retrying."})
        return json.dumps({"error": f"{tool_name}: API error {code}: {e.response.text}"})
    if isinstance(e, httpx.TimeoutException):
        return json.dumps({"error": f"{tool_name}: Request timed out. Try again."})
    if isinstance(e, ValueError):
        return json.dumps({"error": f"{tool_name}: {str(e)}"})
    return json.dumps({"error": f"{tool_name}: Unexpected error: {type(e).__name__}: {str(e)}"})


# --- Input models ---

class StyleParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: Optional[str] = Field(
        default=None,
        description=(
            "Visual art style. One of: flat, line_art, engraving, linocut, "
            "silhouette, isometric, cartoon, ghibli."
        ),
    )
    color_mode: Optional[str] = Field(
        default=None,
        description="Colour palette mode. One of: full_color, monochrome, few_colors.",
    )
    image_complexity: Optional[str] = Field(
        default=None,
        description="Detail level. One of: icon, illustration, scene.",
    )
    composition: Optional[str] = Field(
        default=None,
        description=(
            "Layout composition. One of: centered_object, repeating_pattern, "
            "full_scene, objects_in_grid."
        ),
    )
    text_style: Optional[str] = Field(
        default=None,
        description=(
            "Text handling in the SVG. One of: only_title (heading text only), "
            "embedded_text (text integrated into the design). Only specify when "
            "the design should include text."
        ),
    )


class GenerateSVGInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    prompt: str = Field(min_length=1, description="Text description of the SVG to generate.")
    quality: Optional[str] = Field(
        default="medium",
        pattern="^(low|medium|high)$",
        description="Render quality. Mutually exclusive with model.",
    )
    model: Optional[str] = Field(
        default=None,
        description=(
            "Specific AI model ID. Mutually exclusive with quality. "
            "Options: gpt-image-1, gpt-image-1-mini, flux-1-dev, flux-2-dev, "
            "z-image-turbo, qwen-image, nano-banana, nano-banana-pro, "
            "imagen-4, imagen-4-ultra, seedream-4.5."
        ),
    )
    aspect_ratio: Optional[str] = Field(
        default="auto",
        pattern="^(auto|portrait|landscape|square)$",
    )
    background: Optional[str] = Field(
        default="auto",
        pattern="^(auto|transparent|opaque)$",
    )
    style_params: Optional[StyleParams] = Field(
        default=None,
        description="Optional style customisation. See StyleParams fields.",
    )


class EditSVGInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    prompt: str = Field(min_length=1, description="Edit instructions.")
    image_url: str = Field(min_length=1, description="URL of the image or SVG to edit.")
    quality: Optional[str] = Field(
        default="medium",
        pattern="^(low|medium|high)$",
        description="Render quality. Mutually exclusive with model.",
    )
    model: Optional[str] = Field(
        default=None,
        description=(
            "Specific AI model ID. Mutually exclusive with quality. "
            "Options: flux-2-dev, qwen-image-edit-plus, flux-kontext-dev, "
            "gpt-image-1, gpt-image-1.5, nano-banana, nano-banana-pro, seedream-4.5."
        ),
    )
    aspect_ratio: Optional[str] = Field(
        default="auto",
        pattern="^(auto|portrait|landscape|square)$",
    )
    background: Optional[str] = Field(
        default="auto",
        pattern="^(auto|transparent|opaque)$",
    )
    style_params: Optional[StyleParams] = Field(
        default=None,
        description="Optional style customisation. See StyleParams fields.",
    )


class ConvertToSVGInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    image_url: str = Field(min_length=1, description="URL of the raster image to vectorize.")


class TraceToSVGInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    image_url: str = Field(min_length=1, description="URL of the raster image to trace.")
    preset: Optional[str] = Field(
        default="poster",
        pattern="^(bw|poster|photo)$",
        description="Tracing preset. 'bw' for black-and-white, 'poster' for flat colour, 'photo' for photographic.",
    )
    mode: Optional[str] = Field(
        default="spline",
        pattern="^(pixel|polygon|spline)$",
        description="Path generation mode.",
    )
    hierarchical: Optional[str] = Field(
        default="stacked",
        pattern="^(stacked|cutout)$",
        description="Layer ordering. 'stacked' overlaps layers; 'cutout' cuts holes.",
    )
    detail: Optional[int] = Field(default=50, ge=0, le=100, description="Detail level 0-100.")
    smoothness: Optional[int] = Field(default=50, ge=0, le=100, description="Path smoothness 0-100.")
    corners: Optional[int] = Field(default=50, ge=0, le=100, description="Corner sensitivity 0-100.")
    reduce_noise: Optional[int] = Field(default=4, ge=0, description="Noise reduction level.")


class OptimizeSVGInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    svg_url: str = Field(min_length=1, description="URL of the SVG to optimize.")
    compress: Optional[bool] = Field(
        default=False,
        description="If true, compresses output to SVGZ format and returns svgzUrl.",
    )


# --- styleParams builder ---

def _build_style_params(sp: Optional[StyleParams]) -> Optional[Dict[str, Any]]:
    """Convert StyleParams model to the API's styleParams dict.

    Note: text_style maps to the 'text' key in the API body, not 'text_style'.
    This matches the official @genwave/svgmaker-mcp implementation.
    """
    if sp is None:
        return None
    raw = sp.model_dump()
    result: Dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        api_key = "text" if key == "text_style" else key
        result[api_key] = value
    return result or None


# --- Tools ---

@mcp.tool(
    name="svgmaker_generate",
    annotations={
        "title": "Generate SVG from text",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def svgmaker_generate(params: GenerateSVGInput) -> str:
    """
    Generate an SVG from a text description using AI.

    Costs 1-3 credits depending on quality, or model-specific credits when
    using the model parameter. quality and model are mutually exclusive.

    Args:
        - prompt (str, required): Text description of the SVG to generate.
        - quality (str, optional): Render quality. Default: medium.
              One of: low (1 credit), medium (2 credits), high (3 credits).
              Mutually exclusive with model.
        - model (str, optional): Specific AI model ID. Mutually exclusive with quality.
              Options: gpt-image-1, gpt-image-1-mini, flux-1-dev, flux-2-dev,
              z-image-turbo, qwen-image, nano-banana, nano-banana-pro,
              imagen-4, imagen-4-ultra, seedream-4.5.
        - aspect_ratio (str, optional): One of: auto, portrait, landscape, square. Default: auto.
        - background (str, optional): One of: auto, transparent, opaque. Default: auto.
        - style_params (object, optional): Style customisation.
              - style (str): One of: flat, line_art, engraving, linocut, silhouette,
                    isometric, cartoon, ghibli.
              - color_mode (str): One of: full_color, monochrome, few_colors.
              - image_complexity (str): One of: icon, illustration, scene.
              - composition (str): One of: centered_object, repeating_pattern,
                    full_scene, objects_in_grid.
              - text_style (str): One of: only_title, embedded_text.
                    Only specify when the design should include text.

    Returns:
        - svgUrl (str): CDN URL of the generated SVG. Expires after 24 hours.
        - svgText (str): Raw SVG source code.
    """
    logger.info("Tool called: svgmaker_generate")
    if params.quality and params.model:
        return json.dumps({"error": "svgmaker_generate: quality and model are mutually exclusive."})
    try:
        body: Dict[str, Any] = {
            "prompt": params.prompt,
            "aspectRatio": params.aspect_ratio,
            "background": params.background,
            "svgText": True,
        }
        if params.model:
            body["model"] = params.model
        else:
            body["quality"] = params.quality or "medium"
        sp = _build_style_params(params.style_params)
        if sp:
            body["styleParams"] = sp

        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{BASE_URL}/generate",
                headers={**_headers(), "Content-Type": "application/json"},
                json=body,
                timeout=60,
            )
            res.raise_for_status()
            try:
                data = res.json()
            except ValueError:
                raise ValueError(f"Non-JSON response (status {res.status_code}): {res.text[:500]}")
            return json.dumps({
                "svgUrl": data["data"]["svgUrl"],
                "svgText": data["data"]["svgText"],
            })
    except Exception as e:
        return _handle_error(e, "svgmaker_generate")


@mcp.tool(
    name="svgmaker_edit",
    annotations={
        "title": "Edit an existing image or SVG with AI",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def svgmaker_edit(params: EditSVGInput) -> str:
    """
    Edit an existing image or SVG with AI-powered modifications.

    Accepts PNG, JPEG, WebP, or SVG via URL. Costs 2-5 credits depending
    on quality, or model-specific credits when using the model parameter.
    quality and model are mutually exclusive.

    Args:
        - prompt (str, required): Edit instructions.
              Example: 'change the background to transparent', 'convert to line_art style'.
        - image_url (str, required): URL of the image or SVG to edit.
              Supported formats: PNG, JPEG, WebP, SVG.
        - quality (str, optional): Render quality. Default: medium.
              One of: low (2 credits), medium (3 credits), high (5 credits).
              Mutually exclusive with model.
        - model (str, optional): Specific AI model ID. Mutually exclusive with quality.
              Options: flux-2-dev, qwen-image-edit-plus, flux-kontext-dev,
              gpt-image-1, gpt-image-1.5, nano-banana, nano-banana-pro, seedream-4.5.
        - aspect_ratio (str, optional): One of: auto, portrait, landscape, square. Default: auto.
        - background (str, optional): One of: auto, transparent, opaque. Default: auto.
        - style_params (object, optional): Style customisation.
              - style (str): One of: flat, line_art, engraving, linocut, silhouette,
                    isometric, cartoon, ghibli.
              - color_mode (str): One of: full_color, monochrome, few_colors.
              - image_complexity (str): One of: icon, illustration, scene.
              - composition (str): One of: centered_object, repeating_pattern,
                    full_scene, objects_in_grid.
              - text_style (str): One of: only_title, embedded_text.
                    Only specify when the design should include text.

    Returns:
        - svgUrl (str): CDN URL of the edited SVG. Expires after 24 hours.
        - svgText (str): Raw SVG source code.
    """
    logger.info("Tool called: svgmaker_edit")
    if params.quality and params.model:
        return json.dumps({"error": "svgmaker_edit: quality and model are mutually exclusive."})
    try:
        async with httpx.AsyncClient() as client:
            img_res = await client.get(params.image_url, timeout=30)
            if not img_res.is_success:
                return json.dumps({"error": f"svgmaker_edit: Could not fetch image ({img_res.status_code})"})

            content_type = img_res.headers.get("content-type", "image/svg+xml")
            ext = params.image_url.split(".")[-1].split("?")[0] or "svg"

            form_data: Dict[str, Any] = {
                "prompt": params.prompt,
                "aspectRatio": params.aspect_ratio or "auto",
                "background": params.background or "auto",
                "svgText": "true",
            }
            if params.model:
                form_data["model"] = params.model
            else:
                form_data["quality"] = params.quality or "medium"
            sp = _build_style_params(params.style_params)
            if sp:
                form_data["styleParams"] = json.dumps(sp)

            res = await client.post(
                f"{BASE_URL}/edit",
                headers=_headers(),
                data=form_data,
                files={"image": (f"image.{ext}", img_res.content, content_type)},
                timeout=60,
            )
            res.raise_for_status()
            try:
                data = res.json()
            except ValueError:
                raise ValueError(f"Non-JSON response (status {res.status_code}): {res.text[:500]}")
            return json.dumps({
                "svgUrl": data["data"]["svgUrl"],
                "svgText": data["data"]["svgText"],
            })
    except Exception as e:
        return _handle_error(e, "svgmaker_edit")


@mcp.tool(
    name="svgmaker_convert_ai",
    annotations={
        "title": "AI-vectorize a raster image to SVG",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def svgmaker_convert_ai(params: ConvertToSVGInput) -> str:
    """
    Convert a raster image to SVG using AI-powered vectorization (1 credit).

    Produces clean, optimized vector paths from PNG, JPEG, or WebP images.
    Use this for photographic or complex images. For flat/simple artwork,
    svgmaker_trace (0.5 credits) may produce better results at lower cost.

    Note: SVG files are not accepted as input -- use svgmaker_edit for SVG modifications.

    Args:
        - image_url (str, required): URL of the raster image to vectorize.
              Supported formats: PNG, JPEG, WebP, TIFF. SVGs are not accepted.

    Returns:
        - svgUrl (str): CDN URL of the vectorized SVG. Expires after 24 hours.
        - svgText (str): Raw SVG source code.
    """
    logger.info("Tool called: svgmaker_convert_ai")
    try:
        async with httpx.AsyncClient() as client:
            img_res = await client.get(params.image_url, timeout=30)
            if not img_res.is_success:
                return json.dumps({"error": f"svgmaker_convert_ai: Could not fetch image ({img_res.status_code})"})

            content_type = img_res.headers.get("content-type", "image/png")
            ext = params.image_url.split(".")[-1].split("?")[0] or "png"

            res = await client.post(
                f"{BASE_URL}/convert/ai-vectorize",
                headers=_headers(),
                data={"svgText": "true"},
                files={"file": (f"image.{ext}", img_res.content, content_type)},
                timeout=60,
            )
            res.raise_for_status()
            try:
                data = res.json()
            except ValueError:
                raise ValueError(f"Non-JSON response (status {res.status_code}): {res.text[:500]}")
            return json.dumps({
                "svgUrl": data["data"]["svgUrl"],
                "svgText": data["data"]["svgText"],
            })
    except Exception as e:
        return _handle_error(e, "svgmaker_convert_ai")


@mcp.tool(
    name="svgmaker_trace",
    annotations={
        "title": "Trace a raster image to SVG using VTracer",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def svgmaker_trace(params: TraceToSVGInput) -> str:
    """
    Convert a raster image to SVG using VTracer path tracing (0.5 credits).

    Cheaper than AI vectorization. Best for logos, icons, and flat artwork
    with clear edges. For photographic or complex images, use svgmaker_convert_ai.

    Args:
        - image_url (str, required): URL of the raster image to trace.
              Supported formats: PNG, JPEG, WebP, TIFF.
        - preset (str, optional): Tracing preset. Default: poster.
              One of:
              - bw: Black-and-white output, high contrast.
              - poster: Flat colour regions. Best for logos and icons.
              - photo: Photographic tracing with more colour detail.
        - mode (str, optional): Path generation mode. Default: spline.
              One of: pixel (pixel-aligned), polygon (straight edges), spline (smooth curves).
        - hierarchical (str, optional): Layer ordering. Default: stacked.
              One of: stacked (layers overlap), cutout (layers cut holes in each other).
        - detail (int, optional): Level of path detail. Range 0-100. Default: 50.
        - smoothness (int, optional): Path smoothness. Range 0-100. Default: 50.
        - corners (int, optional): Corner sensitivity. Range 0-100. Default: 50.
        - reduce_noise (int, optional): Noise reduction level. Default: 4.

    Returns:
        - svgUrl (str): CDN URL of the traced SVG. Expires after 24 hours.
              Note: trace endpoint does not return svgText.
    """
    logger.info("Tool called: svgmaker_trace")
    try:
        async with httpx.AsyncClient() as client:
            img_res = await client.get(params.image_url, timeout=30)
            if not img_res.is_success:
                return json.dumps({"error": f"svgmaker_trace: Could not fetch image ({img_res.status_code})"})

            content_type = img_res.headers.get("content-type", "image/png")
            ext = params.image_url.split(".")[-1].split("?")[0] or "png"

            form_data: Dict[str, Any] = {
                "algorithm": "vtracer",
                "preset": params.preset or "poster",
                "mode": params.mode or "spline",
                "hierarchical": params.hierarchical or "stacked",
                "detail": str(params.detail if params.detail is not None else 50),
                "smoothness": str(params.smoothness if params.smoothness is not None else 50),
                "corners": str(params.corners if params.corners is not None else 50),
                "reduceNoise": str(params.reduce_noise if params.reduce_noise is not None else 4),
            }

            res = await client.post(
                f"{BASE_URL}/convert/trace",
                headers=_headers(),
                data=form_data,
                files={"file": (f"image.{ext}", img_res.content, content_type)},
                timeout=60,
            )
            res.raise_for_status()
            try:
                data = res.json()
            except ValueError:
                raise ValueError(f"Non-JSON response (status {res.status_code}): {res.text[:500]}")
            return json.dumps({"svgUrl": data["data"]["svgUrl"]})
    except Exception as e:
        return _handle_error(e, "svgmaker_trace")


@mcp.tool(
    name="svgmaker_optimize",
    annotations={
        "title": "Optimize SVG file size using SVGO",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def svgmaker_optimize(params: OptimizeSVGInput) -> str:
    """
    Optimize an SVG file to reduce size by 10-30% using SVGO (0.5 credits).

    Removes redundant metadata, normalizes paths, and collapses unnecessary
    attributes. Optionally compresses to SVGZ (gzip) format.

    Args:
        - svg_url (str, required): URL of the SVG file to optimize.
        - compress (bool, optional): If true, compresses output to SVGZ format. Default: false.
              When true, returns svgzUrl instead of svgUrl.

    Returns:
        - svgUrl (str): CDN URL of the optimized SVG. Present when compress=false.
        - svgzUrl (str): CDN URL of the compressed SVGZ file. Present when compress=true.
              Both URLs expire after 24 hours.
    """
    logger.info("Tool called: svgmaker_optimize")
    try:
        async with httpx.AsyncClient() as client:
            svg_res = await client.get(params.svg_url, timeout=30)
            if not svg_res.is_success:
                return json.dumps({"error": f"svgmaker_optimize: Could not fetch SVG ({svg_res.status_code})"})

            form_data: Dict[str, Any] = {}
            if params.compress:
                form_data["compress"] = "true"

            res = await client.post(
                f"{BASE_URL}/svg/optimize",
                headers=_headers(),
                data=form_data,
                files={"file": ("image.svg", svg_res.content, "image/svg+xml")},
                timeout=30,
            )
            res.raise_for_status()
            try:
                data = res.json()
            except ValueError:
                raise ValueError(f"Non-JSON response (status {res.status_code}): {res.text[:500]}")
            if params.compress:
                return json.dumps({"svgzUrl": data["data"]["svgzUrl"]})
            return json.dumps({"svgUrl": data["data"]["svgUrl"]})
    except Exception as e:
        return _handle_error(e, "svgmaker_optimize")
