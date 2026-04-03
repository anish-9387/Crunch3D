# 🧊 OptiMesh — 3D Mesh Optimizer

> Upload a heavy AI-generated mesh. Get a real-time-ready optimized asset in under 2 minutes. No 3D software experience required.

OptiMesh is a full-stack web application that solves a critical bottleneck in the 3D asset pipeline: AI-generated models from tools like Tripo3D, Meshy, and Shap-E produce meshes with 700,000–800,000+ polygons that are completely unusable in real-time environments (games, WebGL, VR/AR). Professional retopology takes hours and requires expensive software ($300–500/mo). OptiMesh eliminates this with an automated optimization pipeline powered by Quadric Error Metrics decimation with a built-in quality guard system.

---

## ✨ What It Does

- **Mesh Upload & Analysis** — Upload OBJ, STL, PLY, GLB, GLTF, FBX, OFF files up to 50MB. Instantly analyzes face count, vertex count, file size, UV presence, normals, and bounding box.
- **Mesh Decimation** — Quadric Error Metrics (QEM) via PyMeshLab. Preserves topology, normals, and boundary edges.
- **Quality Guard** — Unique surface deviation checker using nearest-neighbor vertex sampling. Automatically relaxes the target face count if decimation would break the mesh shape beyond your threshold.
- **Platform Presets** — One-click targets: Web/WebGL (15K faces), Mobile (8K), PC/Console (40K), VR/AR (5K).
- **Custom Target** — Slider for any custom face count target.
- **LOD Generation** — Generates LOD0 (100%), LOD1 (50%), LOD2 (25%), LOD3 (10%) levels in one click.
- **3D Viewer** — Real-time Three.js viewer with orbit/zoom/pan controls, wireframe toggle, split view (original vs optimized), and a full model inspector panel (scene graph, transform, bounds, camera info).
- **Before/After Stats** — Face count, vertex count, file size, reduction percentage, processing time.
- **Download** — Single optimized file or ZIP with all LOD levels.
- **Dark / Light Mode** — Auto-detects system preference, persisted in localStorage.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Three.js, @react-three/fiber, @react-three/drei |
| Backend | FastAPI (Python 3.11), Uvicorn |
| Mesh Processing | PyMeshLab 2023.12, Trimesh 4.5, NumPy 1.26 |
| Styling | Plain CSS with CSS custom properties (no Tailwind, no UI lib) |
| HTTP | Axios |

---

## 📁 Project Structure

```
optimesh/
├── backend/
│   ├── main.py                  # FastAPI app entry point, CORS config
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── routers/
│   │   └── mesh.py              # Upload, optimize, status, preview, download endpoints
│   ├── services/
│   │   ├── file_handler.py      # Job ID generation, upload/processed dirs, cleanup
│   │   ├── mesh_analyzer.py     # PyMeshLab stats extraction (faces, verts, UVs, bbox)
│   │   └── mesh_optimizer.py    # Decimation engine, quality guard, LOD generator
│   └── models/
│       └── schemas.py           # Pydantic schemas for all requests and responses
├── frontend/
│   ├── index.html
│   ├── vite.config.js           # Dev server + /api proxy to port 8000
│   ├── package.json
│   └── src/
│       ├── main.jsx
│       ├── App.jsx              # Root state management, theme toggle, layout
│       ├── index.css            # Full design system, dark/light CSS variables
│       ├── api/
│       │   └── client.js        # uploadMesh, optimizeMesh, getDownloadUrl, getPreviewUrl
│       └── components/
│           ├── FileUpload.jsx       # Drag & drop zone with upload progress
│           ├── ModelViewer.jsx      # Three.js canvas, OBJ/STL/PLY/GLB loaders, split view
│           ├── ModelInspector.jsx   # Right panel: mesh stats, scene graph, camera info
│           ├── PresetSelector.jsx   # Platform presets, face slider, options toggles
│           └── StatsPanel.jsx       # Before/after stats, LOD table, quality report, download
├── .env.example
├── .gitignore
└── README.md
```

---

## ✅ Prerequisites

| Tool | Version Required | Check |
|---|---|---|
| Python | 3.11 (not 3.12+) | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 8+ | `npm --version` |

> **Important:** PyMeshLab only supports Python 3.11 and below. Python 3.12 will fail at install.

On Linux you also need OpenGL system libs:
```bash
sudo apt-get install libgl1-mesa-glx libglib2.0-0
```

---

## 🚀 Setup & Installation

### 1. Clone the repo

```bash
git clone https://github.com/your-username/optimesh.git
cd optimesh
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate — macOS/Linux:
source venv/bin/activate
# Activate — Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

`requirements.txt` installs:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.20
pymeshlab==2023.12.post2
trimesh==4.5.3
numpy==1.26.4
pydantic==2.10.4
aiofiles==24.1.0
```

### 3. Frontend

```bash
cd ../frontend
npm install
```

### 4. Environment

```bash
cp .env.example .env
```

Default values in `.env.example` work for local development with no changes:

```env
BACKEND_PORT=8000
MAX_FILE_SIZE_MB=50
VITE_API_URL=http://localhost:8000
```

No API keys required.

---

## ▶️ Running the Project

Open **two terminals**.

### Terminal 1 — Backend

```bash
cd backend
source venv/bin/activate      # Windows: venv\Scripts\activate
uvicorn backend.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started reloader process
```

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Expected output:
```
  VITE ready in Xms
  ➜  Local:   http://localhost:5173/
```

Open **http://localhost:5173** in your browser.

The Vite dev server automatically proxies all `/api/*` calls to `http://localhost:8000` — no CORS configuration needed.

---

## 🧪 Testing the App

### Get a test mesh

Any of these work:
- Download a free GLB or OBJ from [Sketchfab](https://sketchfab.com/features/free-3d-models) (filter CC license)
- Export from any AI model generator (Tripo3D, Meshy, Shap-E)
- Any `.obj`, `.stl`, `.ply`, `.glb`, `.gltf`, or `.off` file under 50MB

### Full test flow

**1. Upload**

Drag and drop your mesh file onto the upload zone or click to browse. The app analyzes it and shows:
- Face count and vertex count
- File size in MB
- Whether the mesh has UVs and normals
- Bounding box dimensions

**2. Select a preset**

Click one of the four platform presets:
| Preset | Target Faces | Use Case |
|---|---|---|
| Web / WebGL | 15,000 | Three.js, Babylon.js, websites |
| Mobile | 8,000 | iOS/Android games |
| PC / Console | 40,000 | Unity, Unreal Engine desktop |
| VR / AR | 5,000 | Quest, HoloLens, ARKit |

Or drag the **Custom Target** slider to any face count.

**3. Configure options**

| Option | Default | What it does |
|---|---|---|
| Generate LODs | Off | Produces 4 LOD files (LOD0–LOD3) |
| Preserve Normals | On | Keeps smooth shading through decimation |
| Preserve Boundaries | On | Prevents edge collapse on mesh borders |
| Strict Quality Lock | On | Refuses over-aggressive decimation |
| Max Shape Deviation | 2.0% | How much surface change is acceptable |

**4. Optimize**

Click **Optimize Mesh**. The backend runs the decimation pipeline and the viewer switches to the optimized mesh automatically.

**5. Inspect results**

- Click **Split View** to see original and optimized side by side with synchronized orbit controls
- Click **Wireframe** to inspect the triangle topology
- The **Model Inspector** panel on the right shows live mesh stats, scene graph nodes, transform data, bounding box, and current camera position

**6. Read the stats panel**

After optimization the stats panel shows:
- Original vs optimized face and vertex counts
- Polygon reduction percentage
- File size before and after
- Processing time in seconds
- LOD table with per-level face count, file size, and reduction % (if LODs were generated)
- Quality Lock Report showing target requested vs target used, surface deviation %, and whether the quality guard was satisfied

**7. Download**

Click **Download Result**:
- Single optimized file if no LODs were generated
- `optimesh_[jobid].zip` containing all four LOD files if LODs were enabled

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/` | API info and all endpoint listing |
| `POST` | `/api/upload` | Upload mesh file, returns job ID + mesh stats |
| `POST` | `/api/optimize` | Run decimation on uploaded mesh |
| `GET` | `/api/status/{job_id}` | Job status: uploaded / processing / completed / failed |
| `GET` | `/api/preview/{job_id}` | Stream optimized mesh file for the Three.js viewer |
| `GET` | `/api/download/{job_id}` | Download optimized file or LOD ZIP |
| `DELETE` | `/api/job/{job_id}` | Delete job and clean up temp files |

Full interactive docs at **http://localhost:8000/docs** when the backend is running.

### Quick curl test

```bash
# Health check
curl http://localhost:8000/health

# Upload a mesh
curl -X POST http://localhost:8000/api/upload \
  -F "file=@/path/to/your/model.obj"

# Optimize (use job_id from upload response)
curl -X POST http://localhost:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "YOUR_JOB_ID",
    "target_faces": 15000,
    "preset": "web",
    "generate_lods": false,
    "preserve_normals": true,
    "preserve_boundaries": true,
    "strict_quality": true,
    "max_deviation_percent": 2.0
  }'

# Check status
curl http://localhost:8000/api/status/YOUR_JOB_ID

# Download result
curl -OJ http://localhost:8000/api/download/YOUR_JOB_ID
```

---

## ⚙️ How the Quality Guard Works

Standard decimation tools blindly hit a target face count, often destroying the mesh's visible shape. OptiMesh's quality guard works differently:

1. Before decimation, samples up to 700 vertices from the original mesh as a geometric reference
2. Tries the requested target face count
3. After decimation, measures **surface deviation** — the 95th percentile nearest-neighbor distance between original and decimated vertex clouds, as a percentage of the bounding box diagonal
4. If deviation exceeds `max_deviation_percent`, tries progressively less aggressive targets across 6 candidate levels between the request and the original
5. Reports back the exact target used, measured deviation, and whether the guard was triggered

This means setting `max_deviation_percent: 2.0` guarantees the output mesh never deviates more than 2% from the original shape — even if that means keeping more polygons than requested.

---

## ⚠️ Known Limitations

- **File size:** 50MB maximum upload
- **Output format:** Always OBJ, PLY, STL, or OFF. GLB/GLTF and FBX inputs are processed but saved as OBJ (PyMeshLab save constraint)
- **Rigged meshes:** Skinned/animated meshes with bone weights are not supported — static meshes only
- **Job persistence:** Jobs stored in memory only. Restarting the backend clears all job state
- **Concurrency:** No async job queue — large meshes block during decimation

---

## 👥 Team - 4Unknowns

Built at Ossome Hacks 3.0 · 3-April-2026