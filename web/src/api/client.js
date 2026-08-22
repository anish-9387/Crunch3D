import axios from "axios";

const rawApiBase = (import.meta.env.VITE_API_BASE_URL || "").trim();
const normalizedApiBase = rawApiBase.replace(/\/+$/, "");
const API_BASE = normalizedApiBase
  ? (normalizedApiBase.endsWith("/api") ? normalizedApiBase : `${normalizedApiBase}/api`)
  : "/api";

const api = axios.create({ baseURL: API_BASE });

// ── Anonymous device id: powers the daily download quota server-side ──────
const CLIENT_ID_KEY = "crunch3d-client-id";

export function getClientId() {
  let id = localStorage.getItem(CLIENT_ID_KEY);
  if (!id) {
    id =
      (typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `anon-${Date.now()}-${Math.random().toString(36).slice(2)}`);
    localStorage.setItem(CLIENT_ID_KEY, id);
  }
  return id;
}

api.interceptors.request.use((config) => {
  config.headers["X-Client-Id"] = getClientId();
  return config;
});

export async function uploadMesh(file, onProgress) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    },
  });
  return response.data;
}

export async function optimizeMesh({
  jobId,
  targetFaces,
  preset,
  generateLods,
  preserveNormals,
  preserveBoundaries,
  reoptimizeFromLatest,
  strictQuality,
  maxDeviationPercent,
  desiredOutput,
}) {
  const response = await api.post("/optimize", {
    job_id: jobId,
    target_faces: targetFaces,
    preset: preset || null,
    generate_lods: generateLods || false,
    preserve_normals: preserveNormals !== false,
    preserve_boundaries: preserveBoundaries !== false,
    reoptimize_from_latest: reoptimizeFromLatest !== false,
    strict_quality: strictQuality !== false,
    max_deviation_percent: maxDeviationPercent || 2.0,
    desired_output: desiredOutput || null,
  });
  return response.data;
}

export async function getJobStatus(jobId) {
  const response = await api.get(`/status/${jobId}`);
  return response.data;
}

export function getDownloadUrl(jobId) {
  const t = Date.now();
  return `${API_BASE}/download/${jobId}?t=${t}`;
}

export async function downloadResult(jobId) {
  const response = await api.get(`/download/${jobId}`, {
    responseType: "blob",
  });
  return response;
}

export async function getDownloadQuota() {
  const response = await api.get("/download/quota");
  return response.data;
}

export function getPreviewUrl(jobId) {
  const t = Date.now();
  return `${API_BASE}/preview/${jobId}?t=${t}`;
}

export async function getOptimizationRecommendation(jobId, fromLatest = false) {
  const response = await api.get(`/recommend/${jobId}`, {
    params: { from_latest: fromLatest },
  });
  return response.data;
}

export async function getImportanceMap(jobId) {
  const response = await api.get(`/importance/${jobId}`);
  return response.data;
}

/**
 * Optimize only the region painted with the refactor brush.
 *
 * `stamps` are in bbox-normalised model space (see lib/brushSelection.js);
 * `clientExtents` is the viewer's bbox extents over its bbox diagonal, which
 * the backend uses to confirm both sides agree on the model's axes before it
 * edits anything.
 */
export async function brushRefine({
  jobId,
  stamps,
  reductionPercent,
  falloff,
  preserveNormals,
  preserveBoundaries,
  fromLatest,
  clientExtents,
}) {
  const response = await api.post("/brush/refine", {
    job_id: jobId,
    stamps: stamps.map((s) => ({
      center: s.center,
      radius: s.radius,
      erase: !!s.erase,
      strength: s.strength ?? 1,
    })),
    reduction_percent: reductionPercent ?? 40,
    falloff: falloff || "smooth",
    preserve_normals: preserveNormals !== false,
    preserve_boundaries: preserveBoundaries !== false,
    from_latest: fromLatest !== false,
    client_extents: clientExtents ?? null,
  });
  return response.data;
}

export async function getLearningStatus() {
  const response = await api.get("/learning/status");
  return response.data;
}