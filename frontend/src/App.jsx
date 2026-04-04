import { useEffect, useState } from 'react'
import FileUpload from './components/FileUpload'
import ModelViewer from './components/ModelViewer'
import PresetSelector from './components/PresetSelector'
import StatsPanel from './components/StatsPanel'
import {
  optimizeMesh,
  getDownloadUrl,
  getPreviewUrl,
  submitFeedback,
  getTrainingSummary,
  bootstrapTrainingModel,
  getOptimizationRecommendation,
} from './api/client'

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
  const [selectedPreset, setSelectedPreset] = useState('hero_standard')
  const [targetFaces, setTargetFaces] = useState(70000)
  const [generateLods, setGenerateLods] = useState(false)
  const [preserveNormals, setPreserveNormals] = useState(true)
  const [preserveBoundaries, setPreserveBoundaries] = useState(true)
  const [reoptimizeFromLatest, setReoptimizeFromLatest] = useState(true)
  const [performanceMode, setPerformanceMode] = useState(true)
  const [strictQuality, setStrictQuality] = useState(true)
  const [maxDeviationPercent, setMaxDeviationPercent] = useState(2.0)
  const [desiredUseCase, setDesiredUseCase] = useState('general')
  const [desiredQualityPriority, setDesiredQualityPriority] = useState('balanced')
  const [desiredPreserveShape, setDesiredPreserveShape] = useState(true)
  const [desiredPreserveVertices, setDesiredPreserveVertices] = useState(true)
  const [desiredPreserveFaces, setDesiredPreserveFaces] = useState(true)
  const [desiredNotes, setDesiredNotes] = useState('')

  // Result state
  const [processing, setProcessing] = useState(false)
  const [stage, setStage] = useState('')
  const [optimizedStats, setOptimizedStats] = useState(null)
  const [optimizedUrl, setOptimizedUrl] = useState(null)
  const [optimizedFilename, setOptimizedFilename] = useState(null)
  const [lods, setLods] = useState(null)
  const [processingTime, setProcessingTime] = useState(null)
  const [qualityMeta, setQualityMeta] = useState(null)
  const [trainingSummary, setTrainingSummary] = useState(null)
  const [feedbackState, setFeedbackState] = useState({
    satisfied: null,
    preserveShape: true,
    preserveVertices: true,
    preserveFaces: true,
    rating: '',
    issuesText: '',
    notes: '',
  })
  const [submittingFeedback, setSubmittingFeedback] = useState(false)
  const [feedbackResult, setFeedbackResult] = useState(null)
  const [bootstrappingModel, setBootstrappingModel] = useState(false)
  const [bootstrapResult, setBootstrapResult] = useState(null)
  const [recommendation, setRecommendation] = useState(null)
  const [error, setError] = useState(null)

  async function applyRecommendation(jobIdValue, fromLatest = false) {
    try {
      const rec = await getOptimizationRecommendation(jobIdValue, fromLatest)
      setRecommendation(rec)
      setSelectedPreset(rec.recommended_preset)
      setTargetFaces(rec.recommended_target_faces)
      setPerformanceMode(rec.enable_performance_mode)

      if (rec.recommended_preset === 'mobile_hero') {
        setDesiredUseCase('mobile_game')
      } else if (rec.recommended_preset === 'interactive_model') {
        setDesiredUseCase('web_realtime')
      } else {
        setDesiredUseCase('general')
      }
    } catch {
      // Keep manual controls available if recommendation endpoint fails.
    }
  }

  useEffect(() => {
    async function loadTrainingSummary() {
      try {
        const summary = await getTrainingSummary()
        setTrainingSummary(summary)
      } catch {
        // Keep UI usable even if training summary endpoint is unavailable.
      }
    }
    loadTrainingSummary()
  }, [])

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
    setFeedbackResult(null)
    setFeedbackState({
      satisfied: null,
      preserveShape: true,
      preserveVertices: true,
      preserveFaces: true,
      rating: '',
      issuesText: '',
      notes: '',
    })
    setError(null)

    // Set slider max to original face count
    if (targetFaces > result.original_stats.face_count) {
      setTargetFaces(Math.floor(result.original_stats.face_count * 0.5))
    }

    applyRecommendation(result.job_id, false)
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
        reoptimizeFromLatest,
        strictQuality,
        maxDeviationPercent,
        desiredOutput: {
          use_case: desiredUseCase,
          quality_priority: desiredQualityPriority,
          preserve_shape: desiredPreserveShape,
          preserve_vertices: desiredPreserveVertices,
          preserve_faces: desiredPreserveFaces,
          notes: desiredNotes || null,
        },
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

      if (reoptimizeFromLatest) {
        applyRecommendation(jobId, true)
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Optimization failed'
      setError(msg)
    } finally {
      setProcessing(false)
    }
  }

  async function handleSubmitFeedback() {
    if (!jobId || feedbackState.satisfied === null) return

    setSubmittingFeedback(true)
    setError(null)

    try {
      const issues = feedbackState.issuesText
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean)

      const rating = feedbackState.rating === '' ? null : Number(feedbackState.rating)

      const result = await submitFeedback({
        jobId,
        satisfied: feedbackState.satisfied,
        preserveShape: feedbackState.preserveShape,
        preserveVertices: feedbackState.preserveVertices,
        preserveFaces: feedbackState.preserveFaces,
        rating,
        issues,
        notes: feedbackState.notes,
      })

      setFeedbackResult(result)

      if (feedbackState.satisfied) {
        const boot = await bootstrapTrainingModel()
        setBootstrapResult(boot)
        await applyRecommendation(jobId, true)
      }

      const summary = await getTrainingSummary()
      setTrainingSummary(summary)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Could not save feedback'
      setError(msg)
    } finally {
      setSubmittingFeedback(false)
    }
  }

  async function handleBootstrapModel() {
    setBootstrappingModel(true)
    setError(null)

    try {
      const result = await bootstrapTrainingModel()
      setBootstrapResult(result)
      const summary = await getTrainingSummary()
      setTrainingSummary(summary)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Could not bootstrap training model'
      setError(msg)
    } finally {
      setBootstrappingModel(false)
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
    setFeedbackResult(null)
    setRecommendation(null)
    setFeedbackState({
      satisfied: null,
      preserveShape: true,
      preserveVertices: true,
      preserveFaces: true,
      rating: '',
      issuesText: '',
      notes: '',
    })
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
              reoptimizeFromLatest={reoptimizeFromLatest}
              onReoptimizeFromLatestChange={setReoptimizeFromLatest}
              performanceMode={performanceMode}
              onPerformanceModeChange={setPerformanceMode}
              strictQuality={strictQuality}
              onStrictQualityChange={setStrictQuality}
              maxDeviationPercent={maxDeviationPercent}
              onMaxDeviationChange={setMaxDeviationPercent}
              desiredUseCase={desiredUseCase}
              onDesiredUseCaseChange={setDesiredUseCase}
              desiredQualityPriority={desiredQualityPriority}
              onDesiredQualityPriorityChange={setDesiredQualityPriority}
              desiredPreserveShape={desiredPreserveShape}
              onDesiredPreserveShapeChange={setDesiredPreserveShape}
              desiredPreserveVertices={desiredPreserveVertices}
              onDesiredPreserveVerticesChange={setDesiredPreserveVertices}
              desiredPreserveFaces={desiredPreserveFaces}
              onDesiredPreserveFacesChange={setDesiredPreserveFaces}
              desiredNotes={desiredNotes}
              onDesiredNotesChange={setDesiredNotes}
              recommendation={recommendation}
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
                performanceMode={performanceMode}
              />

              {error && <div className="error-msg">{error}</div>}

              <StatsPanel
                original={originalStats}
                optimized={optimizedStats}
                lods={lods}
                processingTime={processingTime}
                qualityMeta={qualityMeta}
                downloadUrl={optimizedStats ? getDownloadUrl(jobId) : null}
                feedbackState={feedbackState}
                trainingSummary={trainingSummary}
                onFeedbackStateChange={setFeedbackState}
                onSubmitFeedback={handleSubmitFeedback}
                submittingFeedback={submittingFeedback}
                feedbackResult={feedbackResult}
                bootstrappingModel={bootstrappingModel}
                bootstrapResult={bootstrapResult}
                onBootstrapModel={handleBootstrapModel}
              />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
