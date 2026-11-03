import { useState, useEffect } from 'react'
import './App.css'

function App() {
  // Backend health state
  const [healthData, setHealthData] = useState(null)
  const [rootData, setRootData] = useState(null)
  const [latency, setLatency] = useState(null)
  const [backendStatus, setBackendStatus] = useState('connecting') // 'connected' | 'connecting' | 'error'
  const [lastChecked, setLastChecked] = useState(null)
  const [loadingHealth, setLoadingHealth] = useState(false)

  // Diff Studio state
  const [specV1, setSpecV1] = useState('')
  const [specV2, setSpecV2] = useState('')
  const [isDiffLoading, setIsDiffLoading] = useState(false)
  const [diffResult, setDiffResult] = useState(null)
  const [diffError, setDiffError] = useState(null)
  const [changeFilter, setChangeFilter] = useState('all') // 'all' | 'breaking' | 'non_breaking'

  // AI Compatibility & Fixes state
  const [isFixLoading, setIsFixLoading] = useState(false)
  const [fixResult, setFixResult] = useState(null)
  const [fixError, setFixError] = useState(null)
  const [activeStudioTab, setActiveStudioTab] = useState('fixes') // 'fixes' | 'diff'
  const [samplePayloadText, setSamplePayloadText] = useState(
    JSON.stringify(
      {
        full_name: 'Jane Doe',
        email: 'jane.doe@example.com',
        age: 28,
      },
      null,
      2
    )
  )

  const checkBackend = async () => {
    setLoadingHealth(true)
    const startTime = performance.now()
    try {
      let res
      try {
        res = await fetch('/api/health')
      } catch {
        res = await fetch('http://127.0.0.1:8000/health')
      }

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const healthJson = await res.json()
      const endTime = performance.now()

      let rootJson = null
      try {
        const rootRes = await fetch('/api/')
        if (rootRes.ok) rootJson = await rootRes.json()
      } catch {
        const rootRes = await fetch('http://127.0.0.1:8000/')
        if (rootRes.ok) rootJson = await rootRes.json()
      }

      setHealthData(healthJson)
      setRootData(rootJson)
      setLatency(Math.round(endTime - startTime))
      setBackendStatus('connected')
      setLastChecked(new Date().toLocaleTimeString())
    } catch (err) {
      console.error('Backend health check error:', err)
      setBackendStatus('error')
      setHealthData(null)
      setRootData(null)
      setLatency(null)
      setLastChecked(new Date().toLocaleTimeString())
    } finally {
      setLoadingHealth(false)
    }
  }

  useEffect(() => {
    checkBackend()
    const interval = setInterval(checkBackend, 15000)
    return () => clearInterval(interval)
  }, [])

  // Load sample OpenAPI v1 & v2 from backend
  const loadSampleSpecs = async () => {
    try {
      setDiffError(null)
      setFixError(null)
      let res
      try {
        res = await fetch('/api/samples')
      } catch {
        res = await fetch('http://127.0.0.1:8000/api/samples')
      }

      if (!res.ok) {
        throw new Error(`Failed to load samples: HTTP ${res.status}`)
      }
      const data = await res.json()
      setSpecV1(data.v1)
      setSpecV2(data.v2)
      setSamplePayloadText(
        JSON.stringify(
          {
            full_name: 'Jane Doe',
            email: 'jane.doe@example.com',
            age: 28,
          },
          null,
          2
        )
      )
    } catch (err) {
      console.error('Failed to load sample specifications:', err)
      setDiffError(err.message)
    }
  }

  // Handle file uploads
  const handleFileUpload = (e, target) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      const content = event.target?.result
      if (typeof content === 'string') {
        if (target === 'v1') setSpecV1(content)
        if (target === 'v2') setSpecV2(content)
      }
    }
    reader.readAsText(file)
  }

  // Submit Diff Analysis to backend
  const handleRunDiff = async () => {
    if (!specV1.trim() || !specV2.trim()) {
      setDiffError('Please provide both Specification v1 and Specification v2.')
      return
    }

    setIsDiffLoading(true)
    setDiffError(null)
    setDiffResult(null)

    try {
      let res
      const body = JSON.stringify({ spec_v1: specV1, spec_v2: specV2 })
      const headers = { 'Content-Type': 'application/json' }

      try {
        res = await fetch('/api/diff', { method: 'POST', headers, body })
      } catch {
        res = await fetch('http://127.0.0.1:8000/api/diff', { method: 'POST', headers, body })
      }

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.detail || `Server error: HTTP ${res.status}`)
      }

      setDiffResult(data)
    } catch (err) {
      console.error('Diff computation error:', err)
      setDiffError(err.message || 'Failed to compare specifications.')
    } finally {
      setIsDiffLoading(false)
    }
  }

  // Run End-to-End AI Compatibility & Fix Generation
  const handleRunCompatibilityAndFixes = async () => {
    if (!specV1.trim() || !specV2.trim()) {
      setDiffError('Please provide both Specification v1 and Specification v2.')
      return
    }

    setIsFixLoading(true)
    setFixError(null)
    setDiffError(null)

    let parsedSample = null
    try {
      if (samplePayloadText.trim()) {
        parsedSample = JSON.parse(samplePayloadText)
      }
    } catch {
      setFixError('Sample Request Payload is not valid JSON. Please verify syntax.')
      setIsFixLoading(false)
      return
    }

    try {
      let res
      const body = JSON.stringify({
        spec_v1: specV1,
        spec_v2: specV2,
        sample_request: parsedSample,
        target_path: '/users',
        target_method: 'POST',
      })
      const headers = { 'Content-Type': 'application/json' }

      try {
        res = await fetch('/api/analyze-fixes', { method: 'POST', headers, body })
      } catch {
        res = await fetch('http://127.0.0.1:8000/api/analyze-fixes', { method: 'POST', headers, body })
      }

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || `Server error: HTTP ${res.status}`)
      }

      setFixResult(data)
      setActiveStudioTab('fixes')

      // Also generate structural diff if not already present
      if (!diffResult) {
        handleRunDiff()
      }
    } catch (err) {
      console.error('Compatibility & Fix error:', err)
      setFixError(err.message || 'Failed to analyze compatibility and fixes.')
    } finally {
      setIsFixLoading(false)
    }
  }

  const filteredChanges = diffResult?.changes?.filter((c) => {
    if (changeFilter === 'breaking') return c.category === 'BREAKING'
    if (changeFilter === 'non_breaking') return c.category === 'NON_BREAKING'
    return true
  }) || []

  return (
    <div className="app-container">
      {/* Brand Header */}
      <header className="app-header">
        <div className="brand-badge">
          <span className="dot"></span>
          <span>B.Tech CSE Capstone Project • Milestone 2 Active</span>
        </div>
        <h1 className="app-title">APIBridge AI</h1>
        <p className="app-subtitle">
          Autonomous API Breaking-Change Detection, Intelligent Schema Reasoning, and Dynamic WebAssembly Adapter Generation.
        </p>
      </header>

      {/* Backend Live Status Banner */}
      <section className={`status-card ${backendStatus}`}>
        <div className="status-card-header">
          <div className="status-indicator">
            <span className={`pulse-pill ${backendStatus}`}></span>
            <div>
              <h2 className="status-title">
                {backendStatus === 'connected' && 'FastAPI Backend Operational'}
                {backendStatus === 'connecting' && 'Connecting to Backend...'}
                {backendStatus === 'error' && 'Backend Disconnected (Port 8000)'}
              </h2>
              <p className="status-desc">
                {backendStatus === 'connected'
                  ? `Live link verified at ${lastChecked}`
                  : 'Probing http://127.0.0.1:8000/health'}
              </p>
            </div>
          </div>
          <button
            id="ping-backend-btn"
            className="ping-button"
            onClick={checkBackend}
            disabled={loadingHealth}
          >
            {loadingHealth ? 'Pinging...' : '⚡ Refresh Health Check'}
          </button>
        </div>

        <div className="metrics-grid">
          <div className="metric-item">
            <span className="metric-label">Service</span>
            <span className="metric-value">
              {healthData?.service || 'apibridge-backend'}
            </span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Health Status</span>
            <span className={`metric-value ${backendStatus === 'connected' ? 'highlight' : ''}`}>
              {backendStatus === 'connected' ? healthData?.status?.toUpperCase() : 'OFFLINE'}
            </span>
          </div>

          <div className="metric-item">
            <span className="metric-label">API Version</span>
            <span className="metric-value">
              {rootData?.version || '0.1.0'}
            </span>
          </div>

          <div className="metric-item">
            <span className="metric-label">Round-Trip Latency</span>
            <span className="metric-value">
              {latency !== null ? `${latency} ms` : '—'}
            </span>
          </div>
        </div>
      </section>

      {/* Milestone 2: OpenAPI Diff Studio */}
      <section className="diff-studio-card">
        <div className="studio-header">
          <div className="studio-title-wrap">
            <span className="studio-badge">Milestone 2 • Core Engine</span>
            <h2 className="studio-title">OpenAPI Structural Diff Engine</h2>
            <p className="studio-subtitle">
              Upload or paste OpenAPI v1 & v2 specifications (JSON/YAML) for deterministic breaking-change detection.
            </p>
          </div>
          <div className="studio-actions">
            <button
              id="load-samples-btn"
              type="button"
              className="btn-secondary"
              onClick={loadSampleSpecs}
            >
              📂 Load Sample v1 & v2 Specs
            </button>
            <button
              id="clear-specs-btn"
              type="button"
              className="btn-secondary"
              onClick={() => {
                setSpecV1('')
                setSpecV2('')
                setDiffResult(null)
                setFixResult(null)
                setDiffError(null)
                setFixError(null)
              }}
            >
              ✕ Clear
            </button>
            <button
              id="run-diff-btn"
              type="button"
              className="btn-secondary"
              onClick={handleRunDiff}
              disabled={isDiffLoading || isFixLoading || !specV1 || !specV2}
            >
              {isDiffLoading ? 'Comparing Specs...' : '⚡ Run Structural Diff'}
            </button>
            <button
              id="run-fixes-btn"
              type="button"
              className="btn-primary"
              onClick={handleRunCompatibilityAndFixes}
              disabled={isFixLoading || isDiffLoading || !specV1 || !specV2}
            >
              {isFixLoading ? 'Analyzing with Gemini...' : '🤖 Analyze Compatibility & Generate Fixes (Gemini)'}
            </button>
          </div>
        </div>

        {/* Error Notifications */}
        {(diffError || fixError) && (
          <div className="diff-error-banner" id="diff-error-message">
            <span style={{ fontSize: '18px' }}>⚠️</span>
            <div>
              <div className="error-title">Analysis / Validation Error</div>
              <div>{diffError || fixError}</div>
            </div>
          </div>
        )}

        {/* Specification Editors */}
        <div className="diff-editors-grid">
          {/* Spec v1 Panel */}
          <div className="spec-editor-box">
            <div className="editor-header">
              <span className="editor-title">
                <span className="spec-tag spec-tag-v1">BASELINE</span>
                Specification v1 (Legacy)
              </span>
              <div className="editor-tools">
                <label className="upload-btn-label">
                  📁 Upload v1
                  <input
                    type="file"
                    accept=".json,.yaml,.yml"
                    style={{ display: 'none' }}
                    onChange={(e) => handleFileUpload(e, 'v1')}
                  />
                </label>
              </div>
            </div>
            <textarea
              id="spec-v1-textarea"
              className="spec-textarea"
              placeholder="Paste OpenAPI v1 JSON or YAML here, or click 'Upload v1' / 'Load Sample v1 & v2 Specs'..."
              value={specV1}
              onChange={(e) => setSpecV1(e.target.value)}
            />
          </div>

          {/* Spec v2 Panel */}
          <div className="spec-editor-box">
            <div className="editor-header">
              <span className="editor-title">
                <span className="spec-tag spec-tag-v2">TARGET</span>
                Specification v2 (Updated)
              </span>
              <div className="editor-tools">
                <label className="upload-btn-label">
                  📁 Upload v2
                  <input
                    type="file"
                    accept=".json,.yaml,.yml"
                    style={{ display: 'none' }}
                    onChange={(e) => handleFileUpload(e, 'v2')}
                  />
                </label>
              </div>
            </div>
            <textarea
              id="spec-v2-textarea"
              className="spec-textarea"
              placeholder="Paste OpenAPI v2 JSON or YAML here, or click 'Upload v2' / 'Load Sample v1 & v2 Specs'..."
              value={specV2}
              onChange={(e) => setSpecV2(e.target.value)}
            />
          </div>
        </div>

        {/* Optional Sample Request Payload Inspector */}
        <div className="sample-payload-box">
          <div className="sample-payload-header">
            <div>
              <span className="sample-payload-title">🧪 Sample Request Payload (v1 Baseline)</span>
              <span className="sample-payload-desc">
                Payload fed to the Transformation Engine to evaluate backward compatibility against v2.
              </span>
            </div>
          </div>
          <textarea
            id="sample-payload-textarea"
            className="sample-payload-textarea"
            rows="3"
            value={samplePayloadText}
            onChange={(e) => setSamplePayloadText(e.target.value)}
            placeholder='{"full_name": "Jane Doe", "email": "jane@example.com", "age": 28}'
          />
        </div>
      </section>

      {/* Results View Tabs (if either Fixes or Diff results exist) */}
      {(fixResult || diffResult) && (
        <div className="studio-tabs-row">
          <button
            className={`studio-tab-btn ${activeStudioTab === 'fixes' ? 'active' : ''}`}
            onClick={() => setActiveStudioTab('fixes')}
          >
            🤖 AI Compatibility & Fix Suggestions {fixResult ? `(${fixResult.total_changes})` : ''}
          </button>
          <button
            className={`studio-tab-btn ${activeStudioTab === 'diff' ? 'active' : ''}`}
            onClick={() => setActiveStudioTab('diff')}
          >
            📊 Structural Diff Details {diffResult ? `(${diffResult.total_changes})` : ''}
          </button>
        </div>
      )}

      {/* TAB 1: AI Compatibility & Fix Suggestions */}
      {activeStudioTab === 'fixes' && fixResult && (
        <section className="diff-results-card" id="compatibility-results-card">
          {/* Verdict Banner */}
          <div className={`verdict-banner ${fixResult.overall_compatibility.toLowerCase()}`}>
            <div className="verdict-info">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className={`verdict-badge ${fixResult.overall_compatibility.toLowerCase()}`}>
                  {fixResult.overall_compatibility.replace('_', ' ')}
                </span>
                <span className="ai-source-tag">
                  ⚡ {fixResult.ai_provider}
                </span>
              </div>
              <div className="verdict-message">{fixResult.summary_message}</div>
            </div>

            <div className="results-stats-row">
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#34d399' }}>{fixResult.compatible_count}</span>
                <span className="stat-label">Compatible</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#f59e0b' }}>{fixResult.potentially_breaking_count}</span>
                <span className="stat-label">Potentially Breaking</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#f87171' }}>{fixResult.incompatible_count}</span>
                <span className="stat-label">Incompatible</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#38bdf8' }}>{fixResult.fixes_validated_count + fixResult.fixes_generated_count}</span>
                <span className="stat-label">Fixes Generated</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#e11d48' }}>{fixResult.manual_intervention_count}</span>
                <span className="stat-label">Manual Action</span>
              </div>
            </div>
          </div>

          {/* Side-by-Side Payload Transformation View */}
          {fixResult.sample_request_original && fixResult.sample_request_transformed && (
            <div className="payload-comparison-container">
              <div className="payload-comparison-header">
                <div>
                  <h3 className="payload-section-title">🔄 Sample Payload Transformation & Schema Validation</h3>
                  <p className="payload-section-subtitle">
                    Transformation engine applied generated fixes to the sample request and verified compliance with v2.
                  </p>
                </div>
                {fixResult.payload_validation && (
                  <span className={`validation-badge ${fixResult.payload_validation.is_valid ? 'valid' : 'invalid'}`}>
                    {fixResult.payload_validation.is_valid ? '✓ v2 Schema Validated' : '✕ Validation Errors'}
                  </span>
                )}
              </div>

              <div className="payload-grid">
                <div className="payload-col">
                  <div className="payload-col-header">
                    <span className="payload-tag v1">Original Client Request (v1)</span>
                  </div>
                  <pre className="payload-pre">
                    {JSON.stringify(fixResult.sample_request_original, null, 2)}
                  </pre>
                </div>

                <div className="payload-arrow-col">
                  <span className="payload-arrow">➔</span>
                  <span className="payload-arrow-label">Transformation Engine</span>
                </div>

                <div className="payload-col">
                  <div className="payload-col-header">
                    <span className="payload-tag v2">Transformed Request (v2)</span>
                  </div>
                  <pre className="payload-pre">
                    {JSON.stringify(fixResult.sample_request_transformed, null, 2)}
                  </pre>
                </div>
              </div>

              {fixResult.payload_validation && (
                <div className={`validation-summary-box ${fixResult.payload_validation.is_valid ? 'valid' : 'invalid'}`}>
                  <div className="validation-note">
                    <strong>Note: </strong>
                    {fixResult.payload_validation.notes}
                  </div>
                  {fixResult.payload_validation.validation_errors.length > 0 && (
                    <ul className="validation-error-list">
                      {fixResult.payload_validation.validation_errors.map((err, idx) => (
                        <li key={idx}>⚠️ {err}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Detailed Compatibility & Fix Cards */}
          <div className="changes-stack">
            <h3 className="section-title" style={{ fontSize: '18px' }}>
              Detailed Compatibility Analysis & Gemini Suggestions
            </h3>

            {fixResult.items.map((item) => {
              const statusClass = item.compatibility_status.toLowerCase()
              const fixClass = item.fix_status.toLowerCase()
              return (
                <div key={item.change_id} className={`change-card ${statusClass}`}>
                  <div className="change-card-header">
                    <div className="change-card-badges">
                      <span className={`status-badge status-${statusClass}`}>
                        {item.compatibility_status.replace('_', ' ')}
                      </span>
                      {item.fix_status !== 'NONE' && (
                        <span className={`fix-badge fix-${fixClass}`}>
                          {item.fix_status.replace(/_/g, ' ')}
                        </span>
                      )}
                      <span className="type-tag">{item.change_type}</span>
                      {item.method && <span className="method-tag">{item.method}</span>}
                      <span className="change-location">{item.location}</span>
                    </div>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {item.change_id}
                    </span>
                  </div>

                  {/* Compatibility Reason */}
                  <div className="change-description">
                    <strong>Contract Impact: </strong>
                    {item.compatibility_reason}
                  </div>

                  {/* Suspected Rename Banner */}
                  {item.suspected_rename && (
                    <div className="suspected-rename-box">
                      <span className="rename-icon">🔍</span>
                      <div>
                        <strong>Rename Discovery: </strong>
                        {item.suspected_rename}
                      </div>
                    </div>
                  )}

                  {/* Gemini Explanation & Suggested Fix */}
                  {item.gemini_explanation && (
                    <div className="ai-fix-box">
                      <div className="ai-fix-header">
                        <span className="ai-fix-icon">🤖</span>
                        <span className="ai-fix-title">Gemini Root-Cause & Fix Suggestion</span>
                      </div>
                      <div className="ai-fix-body">
                        <div><strong>Explanation: </strong>{item.gemini_explanation}</div>
                        {item.suggested_fix && (
                          <div style={{ marginTop: '6px' }}>
                            <strong>Suggested Fix: </strong>{item.suggested_fix}
                          </div>
                        )}
                        {item.missing_information && (
                          <div className="missing-info-alert">
                            <strong>Missing Information: </strong>{item.missing_information}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Generated Transformations */}
                  {item.suggested_transformations.length > 0 && (
                    <div className="transformations-tag-list">
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>
                        Applied Action:
                      </span>
                      {item.suggested_transformations.map((t, idx) => (
                        <span key={idx} className="transformation-action-pill">
                          ⚡ {t.action}
                          {t.from_field && t.to_field && `: ${t.from_field} → ${t.to_field}`}
                          {t.from_field && t.to_fields && `: ${t.from_field} → [${t.to_fields.join(', ')}]`}
                          {t.target_type && `: ${t.target_type}`}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* TAB 2: Diff Results Display (Structural Diff) */}
      {activeStudioTab === 'diff' && diffResult && (
        <section className="diff-results-card" id="diff-results-card">
          {/* Verdict Banner */}
          <div className={`verdict-banner ${diffResult.is_compatible ? 'compatible' : 'breaking'}`}>
            <div className="verdict-info">
              <span className={`verdict-badge ${diffResult.is_compatible ? 'compatible' : 'breaking'}`}>
                {diffResult.is_compatible ? '100% Backward Compatible' : 'Breaking Changes Detected'}
              </span>
              <div className="verdict-message">{diffResult.summary_message}</div>
              {(diffResult.v1_title || diffResult.v2_title) && (
                <div className="verdict-spec-names">
                  Comparing: {diffResult.v1_title || 'v1'} ({diffResult.v1_version || '1.0'}) &rarr;{' '}
                  {diffResult.v2_title || 'v2'} ({diffResult.v2_version || '2.0'})
                </div>
              )}
            </div>

            <div className="results-stats-row">
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#38bdf8' }}>{diffResult.total_changes}</span>
                <span className="stat-label">Total Changes</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#f87171' }}>{diffResult.breaking_count}</span>
                <span className="stat-label">Breaking</span>
              </div>
              <div className="stat-pill">
                <span className="stat-num" style={{ color: '#34d399' }}>{diffResult.non_breaking_count}</span>
                <span className="stat-label">Non-Breaking</span>
              </div>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="filter-bar">
            <button
              className={`filter-tab ${changeFilter === 'all' ? 'active' : ''}`}
              onClick={() => setChangeFilter('all')}
            >
              All Changes ({diffResult.total_changes})
            </button>
            <button
              className={`filter-tab ${changeFilter === 'breaking' ? 'active' : ''}`}
              onClick={() => setChangeFilter('breaking')}
            >
              Breaking Only ({diffResult.breaking_count})
            </button>
            <button
              className={`filter-tab ${changeFilter === 'non_breaking' ? 'active' : ''}`}
              onClick={() => setChangeFilter('non_breaking')}
            >
              Non-Breaking Only ({diffResult.non_breaking_count})
            </button>
          </div>

          {/* Categorized Changes List */}
          <div className="changes-stack">
            {filteredChanges.length === 0 ? (
              <div className="no-changes-msg">
                No changes matching current filter.
              </div>
            ) : (
              filteredChanges.map((change) => {
                const isBreaking = change.category === 'BREAKING'
                return (
                  <div
                    key={change.id}
                    className={`change-card ${isBreaking ? 'breaking' : 'non_breaking'}`}
                  >
                    <div className="change-card-header">
                      <div className="change-card-badges">
                        <span className={`cat-badge ${isBreaking ? 'breaking' : 'non_breaking'}`}>
                          {isBreaking ? 'BREAKING' : 'COMPATIBLE'}
                        </span>
                        <span className="type-tag">{change.change_type}</span>
                        {change.method && (
                          <span className="method-tag">{change.method}</span>
                        )}
                        <span className="change-location">{change.location}</span>
                      </div>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                        {change.id}
                      </span>
                    </div>

                    <div className="change-description">{change.description}</div>

                    {isBreaking && change.breaking_reason && (
                      <div className="breaking-reason-box">
                        <span className="breaking-reason-icon">⚠️</span>
                        <div>
                          <strong>Impact: </strong>
                          {change.breaking_reason}
                        </div>
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </section>
      )}

      {/* Architectural Pipeline Milestones */}
      <section className="section-title-wrap">
        <h2 className="section-title">System Pipeline & Architecture</h2>
        <p className="section-subtitle">
          Logical execution workflow for autonomous API breaking change reconciliation
        </p>

        <div className="pipeline-grid">
          <div className="pipeline-card">
            <span className="pipeline-step-badge step-active">Milestone 1 • Complete</span>
            <h3>Core Baseline & Health</h3>
            <p>
              FastAPI backend running on port 8000 with Pydantic validation, CORS middleware, and React Vite frontend.
            </p>
          </div>

          <div className="pipeline-card">
            <span className="pipeline-step-badge step-active">Milestone 2 • Complete</span>
            <h3>OpenAPI Diff Engine</h3>
            <p>
              Deterministic structural comparison of OpenAPI JSON/YAML specs detecting breaking vs compatible contract shifts.
            </p>
          </div>

          <div className="pipeline-card">
            <span className="pipeline-step-badge step-active">Milestone 3 • Active</span>
            <h3>Gemini Compatibility & Fix Reasoner</h3>
            <p>
              AI-driven reasoning to infer suspected renames, evaluate backward compatibility, generate safe transformations, and validate payloads.
            </p>
          </div>

          <div className="pipeline-card">
            <span className="pipeline-step-badge step-upcoming">Milestone 4 & 5 • Planned</span>
            <h3>Wasm Adapter & Runtime Proxy</h3>
            <p>
              Compiling synthesized Rust adapters into portable WebAssembly modules for high-performance traffic mediation.
            </p>
          </div>
        </div>
      </section>

      {/* Live Endpoints & Quick Links */}
      <section className="endpoints-card">
        <h3 className="section-title" style={{ fontSize: '20px' }}>Backend API Quick Links</h3>
        <div className="endpoint-list">
          <div className="endpoint-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="endpoint-badge" style={{ background: 'rgba(99, 102, 241, 0.2)', color: '#a5b4fc' }}>POST</span>
              <span className="endpoint-path">/api/analyze-fixes</span>
            </div>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Gemini compatibility reasoning, payload transformations & schema validation
            </span>
          </div>

          <div className="endpoint-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="endpoint-badge">POST</span>
              <span className="endpoint-path">/api/diff</span>
            </div>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
              Deterministic structural OpenAPI comparator
            </span>
          </div>

          <div className="endpoint-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="endpoint-badge">GET</span>
              <span className="endpoint-path">/api/samples</span>
            </div>
            <a
              href="http://127.0.0.1:8000/api/samples"
              target="_blank"
              rel="noreferrer"
              className="endpoint-action"
            >
              Open Samples JSON &rarr;
            </a>
          </div>

          <div className="endpoint-row">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span className="endpoint-badge">DOCS</span>
              <span className="endpoint-path">/docs</span>
            </div>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="endpoint-action"
            >
              Interactive Swagger UI &rarr;
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="app-footer">
        <p>APIBridge AI • B.Tech CSE AI/ML Project</p>
        <div className="tech-tags">
          <span className="tech-tag">Python 3.10</span>
          <span className="tech-tag">FastAPI</span>
          <span className="tech-tag">Pydantic v2</span>
          <span className="tech-tag">OpenAPI 3.x Diff</span>
          <span className="tech-tag">React 19</span>
          <span className="tech-tag">Vite</span>
        </div>
      </footer>
    </div>
  )
}

export default App
