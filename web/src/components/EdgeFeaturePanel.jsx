const GROUP_ORDER = ['Geometry', 'Topology', 'Appearance', 'View', 'Deformation']

/**
 * Readout of the 19 per-edge cues the importance model consumed for this mesh.
 *
 * Cues the mesh had no data for (no UVs, no vertex colours, no rig) arrive with
 * `present: false`. Those are rendered dimmed rather than hidden, so it is
 * obvious that a cue exists but did not apply — hiding them would make an
 * unskinned mesh look like the optimizer has fewer capabilities than it does.
 *
 * Bars show each cue's mean relative to its own observed max, so a cue whose
 * raw values are tiny is still legible. `weight` is the cue's fixed
 * contribution to the fused importance score.
 */
export default function EdgeFeaturePanel({ summary }) {
  if (!summary || !summary.enabled || !summary.features?.length) return null

  const grouped = new Map()
  for (const feature of summary.features) {
    const group = feature.group || 'Other'
    if (!grouped.has(group)) grouped.set(group, [])
    grouped.get(group).push(feature)
  }

  const groups = [...grouped.keys()].sort((a, b) => {
    const ai = GROUP_ORDER.indexOf(a)
    const bi = GROUP_ORDER.indexOf(b)
    return (ai === -1 ? GROUP_ORDER.length : ai) - (bi === -1 ? GROUP_ORDER.length : bi)
  })

  const activeCount = summary.features.filter((f) => f.present).length

  return (
    <div className="card">
      <h3>Edge Feature Analysis</h3>

      <div className="edge-summary-row">
        <span>
          <strong>{activeCount}</strong> of {summary.features.length} cues active
        </span>
        <span>
          <strong>{summary.edge_count.toLocaleString()}</strong> edges analyzed
        </span>
      </div>

      <div className="edge-groups">
        {groups.map((group) => (
          <div key={group}>
            <div className="edge-group-label">{group}</div>
            {grouped.get(group).map((feature) => {
              // Normalize against the cue's own max so small-magnitude cues
              // remain readable; guard the divide for all-zero cues.
              const ratio =
                feature.present && feature.max > 0
                  ? Math.min(Math.max(feature.mean / feature.max, 0), 1)
                  : 0

              return (
                <div
                  key={feature.key}
                  className={`edge-feature ${feature.present ? '' : 'absent'}`}
                  title={
                    feature.present
                      ? `${feature.description}\nWeight ${feature.weight} · range ${feature.min} – ${feature.max}`
                      : `${feature.description}\nNot available for this mesh.`
                  }
                >
                  <span className="edge-feature-name">{feature.label}</span>
                  <span className="edge-feature-value">
                    {feature.present ? feature.mean.toFixed(3) : 'n/a'}
                  </span>
                  <span className="edge-feature-track">
                    <span
                      className="edge-feature-fill"
                      style={{ width: `${ratio * 100}%` }}
                    />
                  </span>
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
