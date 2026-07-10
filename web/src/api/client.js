import axios from "axios";

const rawApiBase = (import.meta.env.VITE_API_BASE_URL || "").trim();
const normalizedApiBase = rawApiBase.replace(/\/+$/, "");
const API_BASE = normalizedApiBase
  ? (normalizedApiBase.endsWith("/api") ? normalizedApiBase : `${normalizedApiBase}/api`)
  : "/api";

const api = axios.create({ baseURL: API_BASE });

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

export function getPreviewUrl(jobId) {
  const t = Date.now();
  return `${API_BASE}/preview/${jobId}?t=${t}`;
}

export async function submitFeedback({
  jobId,
  satisfied,
  preserveShape,
  preserveVertices,
  preserveFaces,
  rating,
  issues,
  notes,
}) {
  const response = await api.post("/feedback", {
    job_id: jobId,
    satisfied,
    preserve_shape: preserveShape,
    preserve_vertices: preserveVertices,
    preserve_faces: preserveFaces,
    rating: rating ?? null,
    issues: issues || [],
    notes: notes || null,
  });
  return response.data;
}

export async function getTrainingSummary() {
  const response = await api.get("/training/summary");
  return response.data;
}

export async function bootstrapTrainingModel() {
  const response = await api.post("/training/bootstrap");
  return response.data;
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
