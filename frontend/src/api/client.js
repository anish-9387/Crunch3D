import axios from 'axios'

const API_BASE = '/api'

const api = axios.create({ baseURL: API_BASE })

export async function uploadMesh(file, onProgress) {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    },
  })
  return response.data
}

export async function optimizeMesh({
  jobId,
  targetFaces,
  preset,
  generateLods,
  preserveNormals,
  preserveBoundaries,
  strictQuality,
  maxDeviationPercent,
}) {
  const response = await api.post('/optimize', {
    job_id: jobId,
    target_faces: targetFaces,
    preset: preset || null,
    generate_lods: generateLods || false,
    preserve_normals: preserveNormals !== false,
    preserve_boundaries: preserveBoundaries !== false,
    strict_quality: strictQuality !== false,
    max_deviation_percent: maxDeviationPercent || 2.0,
  })
  return response.data
}

export async function getJobStatus(jobId) {
  const response = await api.get(`/status/${jobId}`)
  return response.data
}

export function getDownloadUrl(jobId) {
  return `${API_BASE}/download/${jobId}`
}

export function getPreviewUrl(jobId) {
  return `${API_BASE}/preview/${jobId}`
}
