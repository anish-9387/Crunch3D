const PRESETS = [
  { id: 'tiny_ui', label: 'Tiny UI Element', faces: 8000, range: '1K - 10K', notes: 'icons / floating shapes' },
  { id: 'decorative_bg', label: 'Decorative Background', faces: 25000, range: '10K - 30K', notes: 'repeatable background models' },
  { id: 'hero_standard', label: 'Hero Section', faces: 70000, range: '20K - 100K', notes: 'single focus object' },
  { id: 'interactive_model', label: 'Interactive Model', faces: 100000, range: '40K - 140K', notes: 'rotation / hover interactions' },
  { id: 'multi_scene', label: 'Multiple Models Scene', faces: 220000, range: '100K - 300K', notes: 'total scene budget' },
  { id: 'mobile_hero', label: 'Mobile Hero', faces: 45000, range: '20K - 60K', notes: 'performance priority' },
]

export default function PresetSelector({
  selectedPreset,
  onPresetChange,
  targetFaces,
  onTargetChange,
  generateLods,
  onLodsChange,
  preserveNormals,
  onNormalsChange,
  preserveBoundaries,
  onBoundariesChange,
  reoptimizeFromLatest,
  onReoptimizeFromLatestChange,
  performanceMode,
  onPerformanceModeChange,
  strictQuality,
  onStrictQualityChange,
  maxDeviationPercent,
  onMaxDeviationChange,
  desiredUseCase,
  onDesiredUseCaseChange,
  desiredQualityPriority,
  onDesiredQualityPriorityChange,
  desiredPreserveShape,
  onDesiredPreserveShapeChange,
  desiredPreserveVertices,
  onDesiredPreserveVerticesChange,
  desiredPreserveFaces,
  onDesiredPreserveFacesChange,
  desiredNotes,
  onDesiredNotesChange,
  recommendation,
  maxFaces,
  onOptimize,
  canOptimize,
  processing,
}) {
  return (
    <div className="sidebar">
      <div className="card">
        <h3>Target Platform</h3>

        {recommendation && (
          <div className="graph-item" style={{ marginBottom: 10 }}>
            Recommended by backend: {recommendation.recommended_preset} ({recommendation.recommended_target_faces.toLocaleString()} faces, {recommendation.risk_level} risk)
          </div>
        )}

        <div className="preset-grid">
          {PRESETS.map((p) => (
            <button
              key={p.id}
              className={`preset-btn ${selectedPreset === p.id ? 'active' : ''}`}
              onClick={() => {
                onPresetChange(p.id)
                onTargetChange(p.faces)
              }}
            >
              <span className="label">{p.label}</span>
              <span className="count">{p.faces.toLocaleString()} faces</span>
              <span className="count">Guide: {p.range}</span>
              <span className="count">{p.notes}</span>
            </button>
          ))}
        </div>

        {recommendation?.reasons?.length > 0 && (
          <div style={{ marginTop: 10, display: 'grid', gap: 6 }}>
            {recommendation.reasons.slice(0, 2).map((reason) => (
              <div key={reason} className="graph-item">{reason}</div>
            ))}
          </div>
        )}

        <div className="slider-group">
          <label>
            Custom Target
            <span>{targetFaces.toLocaleString()} faces</span>
          </label>
          <input
            type="range"
            min={100}
            max={maxFaces || 500000}
            step={100}
            value={targetFaces}
            onChange={(e) => {
              onTargetChange(Number(e.target.value))
              onPresetChange(null)
            }}
          />
        </div>
      </div>

      <div className="card">
        <h3>Options</h3>
        <div className="toggle-row">
          <span>Generate LODs</span>
          <label className="toggle">
            <input type="checkbox" checked={generateLods} onChange={(e) => onLodsChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>
        <div className="toggle-row">
          <span>Preserve Normals</span>
          <label className="toggle">
            <input type="checkbox" checked={preserveNormals} onChange={(e) => onNormalsChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>
        <div className="toggle-row">
          <span>Preserve Boundaries</span>
          <label className="toggle">
            <input type="checkbox" checked={preserveBoundaries} onChange={(e) => onBoundariesChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        <div className="toggle-row">
          <span>Re-modify From Last Output</span>
          <label className="toggle">
            <input type="checkbox" checked={reoptimizeFromLatest} onChange={(e) => onReoptimizeFromLatestChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        <div className="toggle-row">
          <span>FPS Performance Mode</span>
          <label className="toggle">
            <input type="checkbox" checked={performanceMode} onChange={(e) => onPerformanceModeChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        <div className="toggle-row">
          <span>Strict Quality Lock</span>
          <label className="toggle">
            <input type="checkbox" checked={strictQuality} onChange={(e) => onStrictQualityChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        {strictQuality && (
          <div className="slider-group">
            <label>
              Max Shape Deviation (diag %)
              <span>{maxDeviationPercent.toFixed(2)}%</span>
            </label>
            <input
              type="range"
              min={0.5}
              max={8.0}
              step={0.05}
              value={maxDeviationPercent}
              onChange={(e) => onMaxDeviationChange(Number(e.target.value))}
            />
          </div>
        )}

        <div style={{ marginTop: 12, color: 'var(--text-muted)', fontSize: 12, lineHeight: 1.4 }}>
          Performance limits: Safe {'<'} 50K faces, Moderate 50K-150K, Heavy 150K-500K, Avoid {'>'} 500K for landing pages.
        </div>
      </div>

      <div className="card">
        <h3>Desired Output</h3>

        <div className="slider-group" style={{ marginTop: 0 }}>
          <label>
            Use Case
            <span>{desiredUseCase || 'general'}</span>
          </label>
          <select
            value={desiredUseCase}
            onChange={(e) => onDesiredUseCaseChange(e.target.value)}
            className="config-select"
          >
            <option value="general">General</option>
            <option value="web_realtime">Web Realtime</option>
            <option value="mobile_game">Mobile Game</option>
            <option value="pc_console">PC / Console</option>
            <option value="vr_ar">VR / AR</option>
            <option value="3d_print">3D Print</option>
          </select>
        </div>

        <div className="slider-group">
          <label>
            Quality Priority
            <span>{desiredQualityPriority}</span>
          </label>
          <select
            value={desiredQualityPriority}
            onChange={(e) => onDesiredQualityPriorityChange(e.target.value)}
            className="config-select"
          >
            <option value="balanced">Balanced</option>
            <option value="quality">Preserve Quality</option>
            <option value="aggressive_reduction">Aggressive Reduction</option>
          </select>
        </div>

        <div className="toggle-row">
          <span>Preserve Shape</span>
          <label className="toggle">
            <input type="checkbox" checked={desiredPreserveShape} onChange={(e) => onDesiredPreserveShapeChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>
        <div className="toggle-row">
          <span>Preserve Vertex Pattern</span>
          <label className="toggle">
            <input type="checkbox" checked={desiredPreserveVertices} onChange={(e) => onDesiredPreserveVerticesChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>
        <div className="toggle-row">
          <span>Preserve Face Distribution</span>
          <label className="toggle">
            <input type="checkbox" checked={desiredPreserveFaces} onChange={(e) => onDesiredPreserveFacesChange(e.target.checked)} />
            <span className="toggle-slider" />
          </label>
        </div>

        <div className="slider-group">
          <label>
            Notes
            <span>optional</span>
          </label>
          <textarea
            value={desiredNotes}
            onChange={(e) => onDesiredNotesChange(e.target.value)}
            className="config-textarea"
            rows={3}
            placeholder="Describe expected visual quality and acceptable tradeoffs"
          />
        </div>
      </div>

      <button
        className="optimize-btn"
        onClick={onOptimize}
        disabled={!canOptimize || processing}
      >
        {processing ? 'Processing...' : 'Optimize Mesh'}
      </button>
    </div>
  )
}
