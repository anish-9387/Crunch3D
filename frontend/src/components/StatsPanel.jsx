export default function StatsPanel({
  original,
  optimized,
  lods,
  processingTime,
  qualityMeta,
  downloadUrl,
  feedbackState,
  trainingSummary,
  onFeedbackStateChange,
  onSubmitFeedback,
  submittingFeedback,
  feedbackResult,
  bootstrappingModel,
  bootstrapResult,
  onBootstrapModel,
}) {
  if (!original) return null

  const reductionPercent =
    optimized && original.face_count > 0
      ? Math.round((1 - optimized.face_count / original.face_count) * 100)
      : null

  const sizeReductionPercent =
    optimized && original.file_size_mb > 0
      ? Math.round((1 - optimized.file_size_mb / original.file_size_mb) * 100)
      : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="stats-grid">
        <div className="stat-item">
          <div className="label">Original Faces</div>
          <div className="value">{original.face_count.toLocaleString()}</div>
          <div className="sub">{original.vertex_count.toLocaleString()} vertices</div>
        </div>

        {optimized && (
          <>
            <div className="stat-item">
              <div className="label">Optimized Faces</div>
              <div className="value accent">{optimized.face_count.toLocaleString()}</div>
              <div className="sub">{optimized.vertex_count.toLocaleString()} vertices</div>
            </div>

            <div className="stat-item">
              <div className="label">Reduction</div>
              <div className="value success">{reductionPercent !== null ? `${reductionPercent}%` : '-'}</div>
              <div className="sub">polygons removed</div>
            </div>

            <div className="stat-item">
              <div className="label">File Size</div>
              <div className="value">
                {original.file_size_mb}MB {'->'} {optimized.file_size_mb}MB
              </div>
              <div className="sub">
                {sizeReductionPercent !== null ? `${sizeReductionPercent}% smaller` : '-'}
              </div>
            </div>

            {processingTime && (
              <div className="stat-item">
                <div className="label">Processing Time</div>
                <div className="value">{processingTime}s</div>
              </div>
            )}
          </>
        )}

        {!optimized && (
          <>
            <div className="stat-item">
              <div className="label">File Size</div>
              <div className="value">{original.file_size_mb} MB</div>
            </div>
            <div className="stat-item">
              <div className="label">UVs</div>
              <div className="value">{original.has_uvs ? 'Yes' : 'No'}</div>
            </div>
            <div className="stat-item">
              <div className="label">Normals</div>
              <div className="value">{original.has_normals ? 'Yes' : 'No'}</div>
            </div>
          </>
        )}
      </div>

      {lods && lods.length > 0 && (
        <div className="card">
          <h3>LOD Levels</h3>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ color: 'var(--text-secondary)', textAlign: 'left' }}>
                <th style={{ padding: '6px 0' }}>Level</th>
                <th>Faces</th>
                <th>Size</th>
                <th>Reduction</th>
              </tr>
            </thead>
            <tbody>
              {lods.map((lod) => (
                <tr key={lod.level} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: '8px 0', fontWeight: 600 }}>{lod.level}</td>
                  <td>{lod.face_count.toLocaleString()}</td>
                  <td>{lod.file_size_mb} MB</td>
                  <td style={{ color: 'var(--success)' }}>{lod.reduction_percent}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {optimized && qualityMeta?.strictQuality && (
        <div className="card">
          <h3>Quality Lock Report</h3>
          <div style={{ display: 'grid', gap: 8, fontSize: 13 }}>
            <div>
              Target Faces: {qualityMeta.targetRequested?.toLocaleString?.() || '-'}
            </div>
            <div>
              Used Faces: {qualityMeta.targetUsed?.toLocaleString?.() || '-'}
            </div>
            <div>
              Surface Deviation: {qualityMeta.deviationPercent != null ? `${qualityMeta.deviationPercent}%` : 'Not available for this file'}
            </div>
            <div style={{ color: qualityMeta.guardSatisfied ? 'var(--success)' : 'var(--danger)' }}>
              {qualityMeta.guardSatisfied
                ? 'Structure protection: Passed'
                : 'Structure protection: Requested reduction was too aggressive'}
            </div>
            {qualityMeta.guardRelaxed && (
              <div style={{ color: 'var(--text-secondary)' }}>
                Quality lock increased face count above requested target to preserve model structure.
              </div>
            )}
          </div>
        </div>
      )}

      {optimized && (
        <div className="card">
          <h3>User Feedback Loop</h3>
          <div style={{ display: 'grid', gap: 10, fontSize: 13 }}>
            <div style={{ color: 'var(--text-secondary)' }}>
              Did this output match your expected result?
            </div>

            <div className="feedback-btn-row">
              <button
                className={`feedback-btn ${feedbackState.satisfied === true ? 'active' : ''}`}
                onClick={() => onFeedbackStateChange({ ...feedbackState, satisfied: true })}
                type="button"
              >
                Desired Output Achieved
              </button>
              <button
                className={`feedback-btn ${feedbackState.satisfied === false ? 'active' : ''}`}
                onClick={() => onFeedbackStateChange({ ...feedbackState, satisfied: false })}
                type="button"
              >
                Needs Improvement
              </button>
            </div>

            <div className="feedback-grid-3">
              <label className="feedback-check">
                <input
                  type="checkbox"
                  checked={feedbackState.preserveShape}
                  onChange={(e) => onFeedbackStateChange({ ...feedbackState, preserveShape: e.target.checked })}
                />
                Shape Preserved
              </label>
              <label className="feedback-check">
                <input
                  type="checkbox"
                  checked={feedbackState.preserveVertices}
                  onChange={(e) => onFeedbackStateChange({ ...feedbackState, preserveVertices: e.target.checked })}
                />
                Vertices Preserved
              </label>
              <label className="feedback-check">
                <input
                  type="checkbox"
                  checked={feedbackState.preserveFaces}
                  onChange={(e) => onFeedbackStateChange({ ...feedbackState, preserveFaces: e.target.checked })}
                />
                Faces Preserved
              </label>
            </div>

            <div className="feedback-grid-2">
              <label>
                Rating (1-5)
                <input
                  className="config-input"
                  type="number"
                  min={1}
                  max={5}
                  value={feedbackState.rating}
                  onChange={(e) => onFeedbackStateChange({ ...feedbackState, rating: e.target.value })}
                />
              </label>
              <label>
                Issues (comma separated)
                <input
                  className="config-input"
                  type="text"
                  value={feedbackState.issuesText}
                  onChange={(e) => onFeedbackStateChange({ ...feedbackState, issuesText: e.target.value })}
                  placeholder="shape drift, UV stretch, shading"
                />
              </label>
            </div>

            <label>
              Feedback Notes
              <textarea
                className="config-textarea"
                rows={3}
                value={feedbackState.notes}
                onChange={(e) => onFeedbackStateChange({ ...feedbackState, notes: e.target.value })}
                placeholder="What should the optimizer improve next?"
              />
            </label>

            <button
              className="optimize-btn"
              type="button"
              onClick={onSubmitFeedback}
              disabled={submittingFeedback || feedbackState.satisfied === null}
            >
              {submittingFeedback ? 'Saving Feedback...' : 'Save Feedback For Training'}
            </button>

            {feedbackResult?.recommendations?.length > 0 && (
              <div style={{ display: 'grid', gap: 6 }}>
                <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Suggested AI Improvements</div>
                {feedbackResult.recommendations.map((item) => (
                  <div key={item} className="graph-item">
                    {item}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {trainingSummary && (
        <div className="card">
          <h3>Training Readiness</h3>
          <div className="kv-grid" style={{ rowGap: 8 }}>
            <div className="kv-key">Optimization Events</div>
            <div className="kv-val">{trainingSummary.total_optimization_events}</div>
            <div className="kv-key">Feedback Events</div>
            <div className="kv-val">{trainingSummary.total_feedback_events}</div>
            <div className="kv-key">Positive / Negative</div>
            <div className="kv-val">
              {trainingSummary.positive_feedback} / {trainingSummary.negative_feedback}
            </div>
          </div>

          <button
            className="optimize-btn"
            type="button"
            onClick={onBootstrapModel}
            disabled={bootstrappingModel}
            style={{ marginTop: 12 }}
          >
            {bootstrappingModel ? 'Building Model...' : 'Start / Refresh Preference Model'}
          </button>

          {bootstrapResult && (
            <div className="graph-item" style={{ marginTop: 8 }}>
              Model updated with {bootstrapResult.training_samples_used} positive samples.
            </div>
          )}
        </div>
      )}

      {downloadUrl && (
        <div className="download-bar">
          <span>Optimization complete - ready to download</span>
          <a href={downloadUrl} className="download-btn" download>
            Download Result
          </a>
        </div>
      )}
    </div>
  )
}
