# mcp-server-svgmaker

FastMCP server providing SVG generation, editing, vectorization, and optimization tools via the SVGMaker API.
Deployed on Prefect Horizon.

## Tools

| Tool | Endpoint | Credits | Description |
|---|---|---|---|
| `svgmaker_generate` | `POST /v1/generate` | 1–3 | Generate SVG from a text description |
| `svgmaker_edit` | `POST /v1/edit` | 2–5 | Edit an existing image or SVG with AI |
| `svgmaker_convert_ai` | `POST /v1/convert/ai-vectorize` | 1 | AI-vectorize a raster image to SVG |
| `svgmaker_trace` | `POST /v1/convert/trace` | 0.5 | Trace a raster image to SVG using VTracer |
| `svgmaker_optimize` | `POST /v1/svg/optimize` | 0.5 | Optimize SVG file size using SVGO |

## Choosing between `svgmaker_convert_ai` and `svgmaker_trace`

Both tools convert raster images to SVG, but via different mechanisms:

- **`svgmaker_convert_ai`** (1 credit): Uses AI to interpret and redraw the image as vector art. Better for complex or photographic images. Output may stylize or simplify the original.
- **`svgmaker_trace`** (0.5 credits): Uses VTracer to algorithmically trace colour regions into paths. Better for logos, icons, and flat artwork with clear edges. Output is a faithful geometric trace.

## Deployment (Prefect Horizon)

- Entrypoint: `svgmaker_server.py:mcp`
- Environment secrets: `SVGMAKER_API_KEY`

## Local setup

```bash
pip install -r requirements.txt
cp .env.template .env
# Fill in your SVGMAKER_API_KEY in .env
fastmcp inspect svgmaker_server.py:mcp
```
