## Here's how Agent 2.1 would look as a self-contained Modal app.

# Container

import modal

agent_2_1_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install(
        "curl",
        "libgl1",          # OpenGL runtime for headless-gl
        "libxi6",          # X Input extension (linked but no display needed)
        "libxext6",        # X Extension library
        "libglu1-mesa",    # GLU
        "build-essential", # for any native node module rebuilds
    )
    .run_commands(
        # Node 20 LTS
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        # Mol* CLI tools — molstar package ships both mvs-render and molrender
        "npm install -g molstar@latest",
    )
    .pip_install(
        "molviewspec",  # Python builder for MVS scenes
        "gemmi",        # mmCIF parsing (faster than biotite for this)
        "numpy",
    )
)

# App structure

import modal, json, subprocess, tempfile, pathlib
import numpy as np
import molviewspec as mvs

app = modal.App("agent-2-1-render")

@app.function(
    image=agent_2_1_image,
    cpu=2,
    memory=2048,
    timeout=120,
    volumes={"/data": modal.Volume.from_name("pipeline-data")},
)
def render_structure(structure_id: str, cif_path: str, agent2_json_path: str) -> dict:
    """Render N panels for one structure. Returns dict of view_name -> png_path."""
    
    # Load Agent 2's measurements
    with open(agent2_json_path) as f:
        agent2 = json.load(f)
    
    # Compute camera vectors per view (your gyration tensor math)
    views = compute_views(agent2)  # returns list of (view_name, position, target, up)
    
    output_paths = {}
    for view_name, position, target, up in views:
        # Build MVS scene in Python
        scene_json = build_scene(cif_path, position, target, up)
        
        # Render via subprocess
        png_path = f"/data/renders/{structure_id}_{view_name}.png"
        try:
            run_mvs_render(scene_json, png_path)
            output_paths[view_name] = png_path
        except RenderError as e:
            log_render_failure(structure_id, view_name, scene_json, e)
            # Continue to next view; don't fail the whole structure
    
    return output_paths

# Scene builder
# This is the part you don't want in SKILL.md and that lives cleanly inside the container:

def build_scene(cif_path: str, position, target, up) -> dict:
    builder = mvs.create_builder()
    
    structure = (
        builder
        .download(url=f"file://{cif_path}")
        .parse(format="mmcif")
        .model_structure()
    )
    
    # Cartoon representation, polymer only
    polymer = structure.component(selector="polymer")
    polymer.representation(type="cartoon").color_from_source(
        schema="all_atomic",
        category_name="atom_site",
        field_name="B_iso_or_equiv",  # Boltz-2 pLDDT lives here
    )
    
    # Camera from your eigenvector math
    builder.camera(
        position=list(position),
        target=list(target),
        up=list(up),
    )
    
    return builder.get_state()


def compute_views(agent2: dict):
    """Map Agent 2 outputs to camera vectors. Drops near-degenerate views."""
    com = np.array(agent2["center_of_mass"])
    eigvals = np.array(agent2["principal_axes"]["eigenvalues"])
    eigvecs = np.array(agent2["principal_axes"]["eigenvectors"])  # rows = vectors
    extents = agent2["principal_axes"]["extents"]
    
    views = []
    for i in range(3):
        # Skip near-degenerate views: if λ_i ≈ λ_j for any j>i, only render one
        if i > 0 and any(abs(eigvals[i] - eigvals[j]) / eigvals[0] < 0.05 for j in range(i)):
            continue
        
        view_dir = eigvecs[i]
        # Camera distance from perpendicular extents
        perp_indices = [j for j in range(3) if j != i]
        max_perp = max(
            max(abs(extents[j][0]), abs(extents[j][1])) for j in perp_indices
        )
        distance = max_perp / np.tan(np.radians(15))  # 30° fov
        
        position = com + distance * view_dir
        up = eigvecs[perp_indices[0]]  # arbitrary perpendicular for up
        
        views.append((f"axis{i+1}", position, com, up))
    
    return views

# Render primitive
class RenderError(Exception): pass

def run_mvs_render(scene: dict, output_path: str, size=(1024, 1024)):
    """Single render call, isolated subprocess, fail loud."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mvsj', delete=False) as f:
        json.dump(scene, f)
        scene_path = f.name
    
    try:
        result = subprocess.run(
            [
                "mvs-render",
                "-i", scene_path,
                "-o", output_path,
                "--size", f"{size[0]}x{size[1]}",
                "--molj",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise RenderError(f"mvs-render failed: {result.stderr.decode()}")
        if not pathlib.Path(output_path).exists():
            raise RenderError("mvs-render produced no output")
    except subprocess.TimeoutExpired:
        raise RenderError("mvs-render timed out after 60s")
    finally:
        pathlib.Path(scene_path).unlink(missing_ok=True)


def log_render_failure(structure_id, view_name, scene_json, error):
    """Persist enough info to reproduce the failure locally."""
    failure_dir = pathlib.Path(f"/data/render_failures/{structure_id}")
    failure_dir.mkdir(parents=True, exist_ok=True)
    
    (failure_dir / f"{view_name}.mvsj").write_text(json.dumps(scene_json, indent=2))
    (failure_dir / f"{view_name}.error").write_text(str(error))

# Batch entry point

@app.function(image=agent_2_1_image, volumes={"/data": ...})
def render_batch(batch: list[dict]) -> list[dict]:
    """Fan out across the batch. Each call is independent."""
    results = list(
        render_structure.map(
            *zip(*[(b["structure_id"], b["cif_path"], b["json_path"]) for b in batch])
        )
    )
    return results

## What the orchestrator (SKILL.md) needs to know
# 1. After Agent 2 finishes, call render_batch with [{structure_id, cif_path, json_path}, ...].
# 2. It returns [{view_name: png_path, ...}, ...] in the same order, possibly with missing keys for failed renders.
# 3. Pass those paths to whatever downstream report assembler exists.