const PRESETS = [
  { id: 'web', label: 'Web / WebGL', faces: 15000 },
  { id: 'mobile', label: 'Mobile', faces: 8000 },
  { id: 'pc', label: 'PC / Console', faces: 40000 },
  { id: 'vr', label: 'VR / AR', faces: 5000 },
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
  strictQuality,
  onStrictQualityChange,
  maxDeviationPercent,
  onMaxDeviationChange,
  maxFaces,
  onOptimize,
  canOptimize,
  processing,
}) {
  return (
    <div className="sidebar">
      <div className="card">
        <h3>Target Platform</h3>
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
            </button>
          ))}
        </div>

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
