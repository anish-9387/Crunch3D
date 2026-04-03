import { useEffect, useState } from 'react'
import FileUpload from './components/FileUpload'
import ModelViewer from './components/ModelViewer'
import PresetSelector from './components/PresetSelector'
import StatsPanel from './components/StatsPanel'
import { optimizeMesh, getDownloadUrl, getPreviewUrl } from './api/client'

export default function App() {
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('optimesh-theme')
    if (saved === 'dark') return true
    if (saved === 'light') return false
    return prefersDark
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light')
    localStorage.setItem('optimesh-theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  // Upload state
  const [jobId, setJobId] = useState(null)
  const [filename, setFilename] = useState(null)
  const [originalStats, setOriginalStats] = useState(null)
  const [originalUrl, setOriginalUrl] = useState(null)

  // Optimization config
  const [selectedPreset, setSelectedPreset] = useState('web')
  const [targetFaces, setTargetFaces] = useState(15000)
  const [generateLods, setGenerateLods] = useState(false)
  const [preserveNormals, setPreserveNormals] = useState(true)
  const [preserveBoundaries, setPreserveBoundaries] = useState(true)
  const [strictQuality, setStrictQuality] = useState(true)
  const [maxDeviationPercent, setMaxDeviationPercent] = useState(2.0)

  // Result state
  const [processing, setProcessing] = useState(false)
  const [stage, setStage] = useState('')
  const [optimizedStats, setOptimizedStats] = useState(null)
  const [optimizedUrl, setOptimizedUrl] = useState(null)
  const [optimizedFilename, setOptimizedFilename] = useState(null)
  const [lods, setLods] = useState(null)
  const [processingTime, setProcessingTime] = useState(null)
  const [qualityMeta, setQualityMeta] = useState(null)
  const [error, setError] = useState(null)

  function handleUploadComplete(result, file) {
    setJobId(result.job_id)
    setFilename(result.filename)
    setOriginalStats(result.original_stats)
    setOriginalUrl(URL.createObjectURL(file))
    // Reset results
    setOptimizedStats(null)
    setOptimizedUrl(null)
    setLods(null)
    setQualityMeta(null)
    setError(null)

    // Set slider max to original face count
    if (targetFaces > result.original_stats.face_count) {
      setTargetFaces(Math.floor(result.original_stats.face_count * 0.5))
    }
  }

  async function handleOptimize() {
    if (!jobId) return
    setProcessing(true)
    setStage('Starting optimization...')
    setError(null)

    try {
      const result = await optimizeMesh({
        jobId,
        targetFaces,
        preset: selectedPreset,
        generateLods,
        preserveNormals,
        preserveBoundaries,
        strictQuality,
        maxDeviationPercent,
      })

      setOptimizedStats(result.optimized_stats)
      setLods(result.lods)
      setProcessingTime(result.processing_time_seconds)
      setOptimizedFilename(result.optimized_filename)
      setQualityMeta({
        strictQuality,
        targetRequested: targetFaces,
        targetUsed: result.target_faces_used ?? result.optimized_stats?.face_count,
        deviationPercent: result.quality_deviation_percent,
        guardRelaxed: result.quality_guard_relaxed,
        guardSatisfied: result.quality_guard_satisfied,
      })

      // Use dedicated preview endpoint so renderer always gets a direct mesh file.
      setOptimizedUrl(getPreviewUrl(jobId))
      setStage('Complete')
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Optimization failed'
      setError(msg)
    } finally {
      setProcessing(false)
    }
  }

  function handleReset() {
    setJobId(null)
    setFilename(null)
    setOriginalStats(null)
    setOriginalUrl(null)
    setOptimizedStats(null)
    setOptimizedUrl(null)
    setOptimizedFilename(null)
    setLods(null)
    setProcessingTime(null)
    setQualityMeta(null)
    setError(null)
  }

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>OptiMesh</h1>
          <p>3D Mesh Optimization & LOD Generation</p>
        </div>
        <div className="header-actions">
          <button
            className={`viewer-btn ${darkMode ? 'active' : ''}`}
            onClick={() => setDarkMode((v) => !v)}
            aria-label="Toggle theme"
          >
            {darkMode ? 'Light Mode' : 'Dark Mode'}
          </button>
          {jobId && (
            <button className="viewer-btn" onClick={handleReset}>
              New Upload
            </button>
          )}
        </div>
      </header>

      {!jobId ? (
        <FileUpload onUploadComplete={handleUploadComplete} disabled={processing} />
      ) : (
        <>
          <div className="main-layout">
            <PresetSelector
              selectedPreset={selectedPreset}
              onPresetChange={setSelectedPreset}
              targetFaces={targetFaces}
              onTargetChange={setTargetFaces}
              generateLods={generateLods}
              onLodsChange={setGenerateLods}
              preserveNormals={preserveNormals}
              onNormalsChange={setPreserveNormals}
              preserveBoundaries={preserveBoundaries}
              onBoundariesChange={setPreserveBoundaries}
              strictQuality={strictQuality}
              onStrictQualityChange={setStrictQuality}
              maxDeviationPercent={maxDeviationPercent}
              onMaxDeviationChange={setMaxDeviationPercent}
              maxFaces={originalStats?.face_count || 500000}
              onOptimize={handleOptimize}
              canOptimize={!!jobId && !processing}
              processing={processing}
            />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <ModelViewer
                originalUrl={originalUrl}
                optimizedUrl={optimizedUrl}
                filename={filename}
                optimizedFilename={optimizedFilename}
                originalStats={originalStats}
                optimizedStats={optimizedStats}
                darkMode={darkMode}
                processing={processing}
                stage={stage}
              />

              {error && <div className="error-msg">{error}</div>}

              <StatsPanel
                original={originalStats}
                optimized={optimizedStats}
                lods={lods}
                processingTime={processingTime}
                qualityMeta={qualityMeta}
                downloadUrl={optimizedStats ? getDownloadUrl(jobId) : null}
              />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
