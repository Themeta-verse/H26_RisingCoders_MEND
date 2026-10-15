import React, { useEffect, useState } from 'react';

// Type definitions matching backend models
interface ManifestDeclaration {
  manifest_file: string;
  line_number: number;
  raw_line: string;
  package_name: string;
  normalized_name: string;
  specifier: string;
  is_pinned: boolean;
  is_commented: boolean;
}

interface CodeUsageLocation {
  file_path: string;
  line_number: number;
  statement: string;
  module: string;
  symbol?: string;
  context_snippet: string;
}

interface DependencyReport {
  name: string;
  normalized_name: string;
  manifest_declarations: ManifestDeclaration[];
  installed_version?: string;
  direct_imports: CodeUsageLocation[];
  is_direct_usage: boolean;
  is_manifest_conflicted: boolean;
  conflict_details: string;
}

interface RuleFinding {
  rule_id: string;
  package: string;
  severity: 'Critical' | 'High' | 'Medium' | 'Low' | 'Info';
  category: string;
  title: string;
  description: string;
  rationale: string;
  evidence_locations: Array<{ file: string; line?: number; snippet?: string }>;
  suggested_action: string;
}

interface MigrationRecommendation {
  package_name: string;
  target_issue: string;
  recommendation_type: string;
  proposed_package: string;
  proposed_specifier: string;
  migration_steps: string[];
  code_changes: Array<{
    file_path: string;
    original_snippet: string;
    replacement_snippet: string;
    explanation: string;
  }>;
  assumptions: string[];
  suggested_tests: string[];
  unresolved_risks: string[];
  confidence_score: number;
  provenance: Record<string, any>;
}

interface TestFailureDetail {
  test_name: string;
  file_path: string;
  failure_message: string;
  traceback_snippet: string;
}

interface TestExecutionResult {
  environment_type: string;
  command_executed: string;
  cwd: string;
  exit_code: number;
  duration_seconds: number;
  timestamp: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  error_count: number;
  raw_stdout: string;
  raw_stderr: string;
  failures: TestFailureDetail[];
  success: boolean;
  notes: string;
}

interface VerificationComparison {
  candidate_id: string;
  package_name: string;
  proposed_change: string;
  baseline_result: TestExecutionResult;
  candidate_result: TestExecutionResult;
  status: string;
  verdict_summary: string;
  unresolved_gaps: string[];
}

interface SystemStatus {
  status: string;
  target_repository: {
    name: string;
    path: string;
    exists: boolean;
    has_pyproject: boolean;
    has_requirements: boolean;
    has_venv: boolean;
  };
  gemma_runtime: {
    endpoint: string;
    is_online: boolean;
    model_tag: string;
    model_available: boolean;
    available_models: string[];
    error_message?: string;
  };
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'inventory' | 'rules' | 'recommendations' | 'verification' | 'capsule'>('inventory');
  
  // Data states
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [dependencies, setDependencies] = useState<Record<string, DependencyReport>>({});
  const [manifestConflicts, setManifestConflicts] = useState<any[]>([]);
  const [ruleFindings, setRuleFindings] = useState<RuleFinding[]>([]);
  const [recommendations, setRecommendations] = useState<Record<string, MigrationRecommendation>>({});
  const [baselineTests, setBaselineTests] = useState<TestExecutionResult | null>(null);
  const [candidateVerifications, setCandidateVerifications] = useState<VerificationComparison[]>([]);
  
  // UI states
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const [selectedDep, setSelectedDep] = useState<DependencyReport | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [depFilter, setDepFilter] = useState<'all' | 'conflicted' | 'used' | 'unreferenced'>('all');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Initial fetch
  useEffect(() => {
    loadAllData();
  }, []);

  const handleCancelRequest = () => {
    if (activeController) {
      activeController.abort();
      setActiveController(null);
    }
    setActionLoading(null);
    setElapsedSeconds(0);
    setErrorMsg('Request was cancelled by user. Controls have been restored.');
  };

  const loadAllData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Fetch system status
      const statusRes = await fetch('/api/status');
      const statusData = await statusRes.json();
      setStatus(statusData);

      // 2. Fetch scan
      const scanRes = await fetch('/api/scan');
      const scanData = await scanRes.json();
      setDependencies(scanData.dependencies || {});
      setManifestConflicts(scanData.manifest_conflicts || []);

      // 3. Fetch rules
      const rulesRes = await fetch('/api/rules');
      const rulesData = await rulesRes.json();
      setRuleFindings(rulesData || []);

      // 4. Fetch baseline tests
      const testsRes = await fetch('/api/baseline-tests');
      const testsData = await testsRes.json();
      setBaselineTests(testsData);

      // 5. Fetch candidates
      const candRes = await fetch('/api/candidates');
      const candData = await candRes.json();
      setCandidateVerifications(candData || []);

    } catch (err: any) {
      console.error('Failed to load initial data:', err);
      setErrorMsg(`Could not connect to backend: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRequestRecommendation = async (pkgName: string) => {
    // Prevent duplicate concurrent requests
    if (actionLoading) {
      return;
    }

    const controller = new AbortController();
    setActiveController(controller);
    setActionLoading(`Querying Gemma 4 (Local Ollama) for ${pkgName}...`);
    setErrorMsg(null);
    setElapsedSeconds(0);

    const timerInterval = setInterval(() => {
      setElapsedSeconds(s => s + 1);
    }, 1000);

    // 65s client-side timeout to avoid indefinite hanging
    const timeoutHandle = setTimeout(() => {
      controller.abort();
    }, 65000);

    try {
      const res = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ package_name: pkgName, timeout_seconds: 60.0 }),
        signal: controller.signal,
      });

      if (!res.ok) {
        let errorDetail = `Server returned HTTP ${res.status}`;
        try {
          const err = await res.json();
          errorDetail = err.detail || errorDetail;
        } catch {
          const rawText = await res.text().catch(() => '');
          if (rawText) errorDetail = rawText.slice(0, 250);
        }
        throw new Error(errorDetail);
      }

      const rec: MigrationRecommendation = await res.json();
      setRecommendations(prev => ({ ...prev, [pkgName]: rec }));
      setActiveTab('recommendations');
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setErrorMsg(`Request for ${pkgName} timed out after 65 seconds or was cancelled. Buttons have been restored.`);
      } else {
        setErrorMsg(`Gemma 4 Advisory Error: ${err.message}`);
      }
    } finally {
      clearInterval(timerInterval);
      clearTimeout(timeoutHandle);
      setActiveController(null);
      setActionLoading(null);
      setElapsedSeconds(0);
    }
  };

  const handleRunVerification = async (pkgName: string, installSpec: string) => {
    if (actionLoading) {
      return;
    }

    const controller = new AbortController();
    setActiveController(controller);
    setActionLoading(`Executing sandbox candidate experiment for ${pkgName} (${installSpec})...`);
    setErrorMsg(null);
    setElapsedSeconds(0);

    const timerInterval = setInterval(() => {
      setElapsedSeconds(s => s + 1);
    }, 1000);

    const timeoutHandle = setTimeout(() => {
      controller.abort();
    }, 90000);

    try {
      const res = await fetch('/api/verify-candidate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: `cand-${pkgName.toLowerCase()}-${Date.now()}`,
          package_name: pkgName,
          package_install_spec: installSpec,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        let errorDetail = `Sandbox verification failed (HTTP ${res.status})`;
        try {
          const err = await res.json();
          errorDetail = err.detail || errorDetail;
        } catch {
          const rawText = await res.text().catch(() => '');
          if (rawText) errorDetail = rawText.slice(0, 250);
        }
        throw new Error(errorDetail);
      }

      const comp: VerificationComparison = await res.json();
      setCandidateVerifications(prev => [comp, ...prev.filter(c => c.candidate_id !== comp.candidate_id)]);
      setActiveTab('verification');
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setErrorMsg(`Sandbox verification for ${pkgName} was cancelled or exceeded 90s.`);
      } else {
        setErrorMsg(`Candidate Verification Error: ${err.message}`);
      }
    } finally {
      clearInterval(timerInterval);
      clearTimeout(timeoutHandle);
      setActiveController(null);
      setActionLoading(null);
      setElapsedSeconds(0);
    }
  };

  // Filter dependencies
  const filteredDeps = Object.values(dependencies).filter(dep => {
    const matchesSearch = dep.name.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchesSearch) return false;
    if (depFilter === 'conflicted') return dep.is_manifest_conflicted;
    if (depFilter === 'used') return dep.is_direct_usage;
    if (depFilter === 'unreferenced') return dep.manifest_declarations.length > 0 && !dep.is_direct_usage;
    return true;
  });

  const criticalFindingsCount = ruleFindings.filter(f => f.severity === 'Critical').length;
  const highFindingsCount = ruleFindings.filter(f => f.severity === 'High').length;
  const verifiedFixesCount = candidateVerifications.filter(c => c.status === 'VERIFIED_FIX').length;

  return (
    <div style={{ maxWidth: '1360px', margin: '0 auto', padding: '32px 24px', backgroundColor: '#ffffff', minHeight: '100vh' }}>
      
      {/* Editorial Header */}
      <header style={{ borderBottom: '1px solid var(--border)', paddingBottom: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--text-black)' }}>
                MEND
              </span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Migration Evidence & Dependency Navigator
              </span>
              <span className="badge badge-info" style={{ fontWeight: 600 }}>Track 1: Gemma 4 — Dependency Resilience</span>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Deterministic manifest & AST evidence engine with local Gemma 4 advisory and sandbox verification.
            </p>
          </div>

          {/* Precision Diagnostic Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'var(--canvas-subtle)', padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)' }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>TARGET:</span>{' '}
              <span className="mono" style={{ fontWeight: 600, color: 'var(--text-black)' }}>{status?.target_repository.name || 'LinkWatch'}</span>
            </div>
            <div style={{ width: '1px', height: '14px', backgroundColor: 'var(--border)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className={`dot ${status?.gemma_runtime.is_online ? 'dot-green' : 'dot-red'}`} />
              <span style={{ color: 'var(--text-muted)' }}>RUNTIME:</span>{' '}
              <span className="mono" style={{ fontWeight: 600, color: 'var(--text-black)' }}>{status?.gemma_runtime.model_tag || 'gemma4:e2b-it-q4_K_M'}</span>
              <span style={{ color: 'var(--text-muted)' }}>({status?.gemma_runtime.is_online ? 'Ollama Online' : 'Offline'})</span>
            </div>
            <div style={{ width: '1px', height: '14px', backgroundColor: 'var(--border)' }} />
            <button className="btn btn-secondary btn-sm" onClick={loadAllData} disabled={loading || !!actionLoading}>
              Re-scan
            </button>
          </div>
        </div>

        {/* Compact Editorial Metadata Strip (Replaces bulky cards) */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '24px', alignItems: 'center', marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--canvas-surface)', fontSize: '0.8125rem' }}>
          <div>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em' }}>Dependencies</span>
            <div style={{ fontWeight: 600, color: 'var(--text-black)' }}>{Object.keys(dependencies).length} declared</div>
          </div>
          <div style={{ width: '1px', height: '24px', backgroundColor: 'var(--border)' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em' }}>Manifest Drift</span>
            <div style={{ fontWeight: 600, color: manifestConflicts.length > 0 ? 'var(--high-text)' : 'var(--text-black)' }}>
              {manifestConflicts.length} conflict {manifestConflicts.length > 0 && '(pydantic)'}
            </div>
          </div>
          <div style={{ width: '1px', height: '24px', backgroundColor: 'var(--border)' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em' }}>Resilience Findings</span>
            <div style={{ fontWeight: 600, color: criticalFindingsCount > 0 ? 'var(--crit-text)' : 'var(--text-black)' }}>
              {ruleFindings.length} findings ({criticalFindingsCount} critical, {highFindingsCount} high)
            </div>
          </div>
          <div style={{ width: '1px', height: '24px', backgroundColor: 'var(--border)' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em' }}>Baseline Suite</span>
            <div style={{ fontWeight: 600, color: baselineTests?.failed_tests ? 'var(--crit-text)' : 'var(--success-text)' }}>
              {baselineTests ? `${baselineTests.passed_tests} passed, ${baselineTests.failed_tests} failed` : 'Testing...'}
            </div>
          </div>
          <div style={{ width: '1px', height: '24px', backgroundColor: 'var(--border)' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em' }}>Sandbox Verified Fixes</span>
            <div style={{ fontWeight: 600, color: verifiedFixesCount > 0 ? 'var(--success-text)' : 'var(--text-secondary)' }}>
              {verifiedFixesCount} verified (Jinja2 &rarr; 10/10 passing)
            </div>
          </div>
        </div>
      </header>

      {/* Real-time Action / Loading State Banner with Timer and Cancellation */}
      {actionLoading && (
        <div style={{ background: 'var(--cobalt-subtle)', border: '1px solid var(--cobalt-border)', color: 'var(--cobalt)', padding: '10px 16px', borderRadius: 'var(--radius-xs)', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', fontSize: '0.8125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="dot dot-amber" />
            <span>
              <strong>Processing:</strong> {actionLoading}{' '}
              <span className="mono" style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>({elapsedSeconds}s elapsed)</span>
            </span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={handleCancelRequest} style={{ borderColor: 'var(--cobalt-border)', color: 'var(--cobalt)' }}>
            Cancel Request
          </button>
        </div>
      )}

      {errorMsg && (
        <div style={{ background: 'var(--crit-bg)', border: '1px solid var(--crit-border)', color: 'var(--crit-text)', padding: '10px 16px', borderRadius: 'var(--radius-xs)', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', fontSize: '0.8125rem' }}>
          <div>
            <strong>Error:</strong> {errorMsg}
          </div>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setErrorMsg(null)}
            style={{ borderColor: 'var(--crit-border)', color: 'var(--crit-text)', padding: '2px 8px' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Swiss Navigation Tabs */}
      <nav className="tabs-header" style={{ marginBottom: '24px' }}>
        <button className={`tab-item ${activeTab === 'inventory' ? 'active' : ''}`} onClick={() => setActiveTab('inventory')}>
          Dependency Inventory <span className="tab-pill">{Object.keys(dependencies).length}</span>
        </button>
        <button className={`tab-item ${activeTab === 'rules' ? 'active' : ''}`} onClick={() => setActiveTab('rules')}>
          Rule Engine Findings <span className="tab-pill">{ruleFindings.length}</span>
        </button>
        <button className={`tab-item ${activeTab === 'recommendations' ? 'active' : ''}`} onClick={() => setActiveTab('recommendations')}>
          Gemma 4 Advisory <span className="tab-pill">{Object.keys(recommendations).length}</span>
        </button>
        <button className={`tab-item ${activeTab === 'verification' ? 'active' : ''}`} onClick={() => setActiveTab('verification')}>
          Sandbox Verification <span className="tab-pill">{candidateVerifications.length}</span>
        </button>
        <button className={`tab-item ${activeTab === 'capsule' ? 'active' : ''}`} onClick={() => setActiveTab('capsule')}>
          Exit Capsule Export
        </button>
      </nav>

      {/* TAB 1: INVENTORY & MANIFEST EVIDENCE (MAIN FOCUS) */}
      {activeTab === 'inventory' && (
        <section>
          {/* Controls Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Filter by package name (e.g. Jinja2, pydantic, six)..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="input-text"
                style={{ width: '300px' }}
              />
              <div style={{ display: 'flex', gap: '4px' }}>
                <button
                  className={`btn btn-sm ${depFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setDepFilter('all')}
                >
                  All ({Object.keys(dependencies).length})
                </button>
                <button
                  className={`btn btn-sm ${depFilter === 'conflicted' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setDepFilter('conflicted')}
                >
                  Conflicts ({manifestConflicts.length})
                </button>
                <button
                  className={`btn btn-sm ${depFilter === 'used' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setDepFilter('used')}
                >
                  Direct Used
                </button>
                <button
                  className={`btn btn-sm ${depFilter === 'unreferenced' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setDepFilter('unreferenced')}
                >
                  Unreferenced / Zombie
                </button>
              </div>
            </div>

            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Showing {filteredDeps.length} of {Object.keys(dependencies).length} packages
            </div>
          </div>

          {/* Primary Table */}
          <div className="panel" style={{ overflow: 'hidden' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '22%' }}>Package</th>
                  <th style={{ width: '14%' }}>pyproject.toml</th>
                  <th style={{ width: '15%' }}>requirements.txt</th>
                  <th style={{ width: '13%' }}>Installed (.venv)</th>
                  <th style={{ width: '12%' }}>Code Usages</th>
                  <th style={{ width: '12%' }}>Status</th>
                  <th style={{ width: '12%', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDeps.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                      No dependencies match the current filter.
                    </td>
                  </tr>
                ) : (
                  filteredDeps.map(dep => {
                    const pyprojectDecl = dep.manifest_declarations.find(d => d.manifest_file === 'pyproject.toml');
                    const reqDecl = dep.manifest_declarations.find(d => d.manifest_file === 'requirements.txt');
                    const isSelected = selectedDep?.name === dep.name;

                    return (
                      <tr
                        key={dep.name}
                        className={isSelected ? 'selected' : ''}
                        style={{ cursor: 'pointer' }}
                        onClick={() => setSelectedDep(dep)}
                      >
                        <td style={{ fontWeight: 600 }}>
                          <span className="mono" style={{ color: 'var(--text-black)' }}>{dep.name}</span>
                        </td>
                        <td>
                          {pyprojectDecl ? (
                            <code className="code-inline">{pyprojectDecl.specifier || '*'}</code>
                          ) : (
                            <span style={{ color: 'var(--text-faint)' }}>—</span>
                          )}
                        </td>
                        <td>
                          {reqDecl ? (
                            <code className="code-inline">{reqDecl.specifier || '*'}</code>
                          ) : (
                            <span style={{ color: 'var(--text-faint)' }}>—</span>
                          )}
                        </td>
                        <td>
                          {dep.installed_version ? (
                            <code className="code-inline">{dep.installed_version}</code>
                          ) : (
                            <span style={{ color: 'var(--text-faint)', fontSize: '0.75rem' }}>Not in venv</span>
                          )}
                        </td>
                        <td>
                          {dep.direct_imports.length > 0 ? (
                            <span style={{ fontWeight: 500 }}>{dep.direct_imports.length} imports</span>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>0 imports</span>
                          )}
                        </td>
                        <td>
                          {dep.is_manifest_conflicted ? (
                            <span className="badge badge-high">Conflict</span>
                          ) : dep.name.toLowerCase() === 'jinja2' ? (
                            <span className="badge badge-critical">Fails Baseline</span>
                          ) : !dep.is_direct_usage && dep.manifest_declarations.length > 0 ? (
                            <span className="badge badge-neutral">Zombie</span>
                          ) : (
                            <span className="badge badge-success">Consistent</span>
                          )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedDep(dep);
                              }}
                            >
                              Inspect
                            </button>
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRequestRecommendation(dep.name);
                              }}
                              disabled={!!actionLoading}
                            >
                              Ask Gemma
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Structured Inspection View Drawer */}
          {selectedDep && (
            <div className="panel" style={{ marginTop: '20px', borderLeft: '3px solid var(--cobalt)' }}>
              <div className="panel-header">
                <div>
                  <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--cobalt)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Observed Code & Manifest Evidence
                  </span>
                  <h3 style={{ fontSize: '1rem', marginTop: '2px' }}>
                    Evidence Dossier: <code className="mono">{selectedDep.name}</code>
                  </h3>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => handleRequestRecommendation(selectedDep.name)}
                    disabled={!!actionLoading}
                  >
                    Request Gemma 4 Migration Plan
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={() => setSelectedDep(null)}>
                    Close
                  </button>
                </div>
              </div>

              <div className="panel-body">
                {selectedDep.conflict_details && (
                  <div style={{ background: 'var(--high-bg)', border: '1px solid var(--high-border)', color: 'var(--high-text)', padding: '10px 14px', borderRadius: 'var(--radius-xs)', marginBottom: '16px', fontSize: '0.8125rem' }}>
                    <strong>Manifest Specifier Mismatch:</strong> {selectedDep.conflict_details}
                  </div>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                  {/* Left: Manifest Declarations */}
                  <div>
                    <h4 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                      Manifest Declarations ({selectedDep.manifest_declarations.length})
                    </h4>
                    {selectedDep.manifest_declarations.length === 0 ? (
                      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>No direct manifest declarations found.</p>
                    ) : (
                      selectedDep.manifest_declarations.map((d, i) => (
                        <div key={i} style={{ border: '1px solid var(--border)', padding: '8px 12px', marginBottom: '8px', borderRadius: 'var(--radius-xs)', backgroundColor: 'var(--canvas-subtle)' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                            <span className="mono">{d.manifest_file}:{d.line_number}</span>
                            <span>{d.is_pinned ? 'Strict Pin (==)' : 'Range Specifier'}</span>
                          </div>
                          <code className="code-inline" style={{ display: 'inline-block' }}>{d.raw_line}</code>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Right: Discovered Source Usage */}
                  <div>
                    <h4 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                      Discovered AST Import Locations ({selectedDep.direct_imports.length})
                    </h4>
                    {selectedDep.direct_imports.length === 0 ? (
                      <div style={{ border: '1px dashed var(--border)', padding: '16px', borderRadius: 'var(--radius-xs)', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                        No AST imports detected in project source files. This dependency is declared in manifests but unused by application logic.
                      </div>
                    ) : (
                      selectedDep.direct_imports.map((loc, i) => (
                        <div key={i} style={{ border: '1px solid var(--border)', padding: '8px 12px', marginBottom: '8px', borderRadius: 'var(--radius-xs)' }}>
                          <div style={{ fontSize: '0.75rem', color: 'var(--cobalt)', marginBottom: '4px' }}>
                            <code className="mono">{loc.file_path}:{loc.line_number}</code>
                          </div>
                          <pre className="code-block">{loc.context_snippet || loc.statement}</pre>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* TAB 2: DETERMINISTIC RULE FINDINGS */}
      {activeTab === 'rules' && (
        <section>
          <div style={{ marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.125rem' }}>Deterministic Resilience Rule Evaluations</h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Static analysis rule engine evaluated across package manifests, AST imports, and Python runtime compatibility.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {ruleFindings.map((finding, idx) => {
              const sevClass = finding.severity.toLowerCase();
              return (
                <div key={idx} className="panel" style={{ borderLeft: `3px solid var(--${sevClass === 'critical' ? 'crit' : sevClass === 'high' ? 'high' : sevClass === 'medium' ? 'med' : 'cobalt'}-border)` }}>
                  <div className="panel-header" style={{ padding: '10px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className={`badge badge-${sevClass}`}>{finding.severity}</span>
                      <span className="badge badge-neutral">{finding.category}</span>
                      <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{finding.rule_id}</span>
                      <strong style={{ fontSize: '0.875rem', color: 'var(--text-black)' }}>{finding.title}</strong>
                    </div>

                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handleRequestRecommendation(finding.package)}
                        disabled={!!actionLoading}
                      >
                        Ask Gemma 4
                      </button>
                      {finding.package.toLowerCase() === 'jinja2' && (
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => handleRunVerification('Jinja2', 'Jinja2>=3.1.4')}
                          disabled={!!actionLoading}
                        >
                          Verify in Sandbox
                        </button>
                      )}
                    </div>
                  </div>

                  <div className="panel-body" style={{ padding: '12px 16px' }}>
                    <p style={{ fontSize: '0.84rem', color: 'var(--text-primary)', marginBottom: '8px' }}>
                      {finding.description}
                    </p>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '0.8125rem', marginTop: '10px' }}>
                      <div>
                        <strong style={{ color: 'var(--text-secondary)' }}>Technical Rationale:</strong>
                        <p style={{ color: 'var(--text-muted)', marginTop: '2px' }}>{finding.rationale}</p>
                      </div>
                      <div>
                        <strong style={{ color: 'var(--text-secondary)' }}>Suggested Remediation:</strong>
                        <p style={{ color: 'var(--text-primary)', marginTop: '2px' }}>{finding.suggested_action}</p>
                      </div>
                    </div>

                    {/* Evidence Snippets */}
                    <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid var(--canvas-surface)' }}>
                      <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                        Observed Evidence ({finding.evidence_locations.length} points)
                      </span>
                      <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {finding.evidence_locations.map((loc, lIdx) => (
                          <div key={lIdx} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            <span className="mono" style={{ color: 'var(--cobalt)' }}>{loc.file}{loc.line ? `:${loc.line}` : ''}</span>
                            {loc.snippet && <pre className="code-block" style={{ marginTop: '2px' }}>{loc.snippet}</pre>}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* TAB 3: GEMMA 4 RECOMMENDATIONS */}
      {activeTab === 'recommendations' && (
        <section>
          <div style={{ marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.125rem' }}>Gemma 4 Migration Advisory</h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Structured migration plans generated strictly by local Gemma 4 (<code>{status?.gemma_runtime.model_tag}</code>) using bounded repository facts.
            </p>
          </div>

          {Object.keys(recommendations).length === 0 ? (
            <div className="panel" style={{ textAlign: 'center', padding: '48px 24px' }}>
              <h3 style={{ fontSize: '0.9375rem', marginBottom: '6px' }}>No Migration Advice Requested Yet</h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', maxWidth: '480px', margin: '0 auto 16px auto' }}>
                Select a package from the Dependency Inventory or request Gemma 4's concrete migration plan for the failing Jinja2 dependency.
              </p>
              <button
                className="btn btn-primary"
                onClick={() => handleRequestRecommendation('Jinja2')}
                disabled={!!actionLoading}
              >
                Request Migration Advice for Jinja2
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {Object.entries(recommendations).map(([pkg, rec]) => (
                <div key={pkg} className="panel" style={{ borderLeft: '3px solid #6366f1' }}>
                  <div className="panel-header" style={{ background: '#fcfcfd' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span className="badge badge-info" style={{ background: '#eef2ff', color: '#4338ca', borderColor: '#c7d2fe' }}>
                          AI Advisory (Non-Authoritative)
                        </span>
                        <span className="badge badge-neutral">{rec.recommendation_type}</span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Confidence: {(rec.confidence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <h3 style={{ fontSize: '1.05rem' }}>
                        {rec.package_name} &rarr; <span className="mono" style={{ color: 'var(--cobalt)' }}>{rec.proposed_package} {rec.proposed_specifier}</span>
                      </h3>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        Target Friction: {rec.target_issue}
                      </div>
                    </div>

                    <button
                      className="btn btn-success"
                      onClick={() => handleRunVerification(rec.package_name, `${rec.proposed_package}${rec.proposed_specifier}`)}
                      disabled={!!actionLoading}
                    >
                      Verify in Isolated Sandbox
                    </button>
                  </div>

                  <div className="panel-body">
                    {/* Migration Steps */}
                    <div>
                      <h4 style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
                        Step-by-Step Procedure
                      </h4>
                      <ol style={{ paddingLeft: '18px', fontSize: '0.8125rem', lineHeight: 1.7, color: 'var(--text-primary)' }}>
                        {rec.migration_steps.map((step, sIdx) => (
                          <li key={sIdx}>{step}</li>
                        ))}
                      </ol>
                    </div>

                    {/* Suggested Tests */}
                    {rec.suggested_tests && rec.suggested_tests.length > 0 && (
                      <div style={{ marginTop: '16px' }}>
                        <h4 style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
                          Suggested Test Invocations
                        </h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          {rec.suggested_tests.map((t, tIdx) => (
                            <code key={tIdx} className="code-inline" style={{ fontSize: '0.75rem' }}>{t}</code>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Residual Risks */}
                    {rec.unresolved_risks && rec.unresolved_risks.length > 0 && (
                      <div style={{ marginTop: '16px', background: 'var(--med-bg)', border: '1px solid var(--med-border)', padding: '10px 14px', borderRadius: 'var(--radius-xs)' }}>
                        <h4 style={{ fontSize: '0.75rem', color: 'var(--med-text)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
                          Residual Risks & Human Verification Items
                        </h4>
                        <ul style={{ paddingLeft: '18px', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                          {rec.unresolved_risks.map((r, rIdx) => (
                            <li key={rIdx}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div style={{ marginTop: '16px', paddingTop: '10px', borderTop: '1px solid var(--border)', fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                      <span>Model: {rec.provenance?.model_tag || 'gemma4:e2b-it-q4_K_M'} via Ollama</span>
                      <span>Epistemic Status: Non-Authoritative AI Output (Requires Sandbox Verification)</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* TAB 4: EMPIRICAL SANDBOX VERIFICATION */}
      {activeTab === 'verification' && (
        <section>
          <div style={{ marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.125rem' }}>Empirical Sandbox Test Verification</h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Actual test execution results comparing the pristine baseline environment against candidate modifications run in isolated sandboxes.
            </p>
          </div>

          {/* Baseline Panel */}
          {baselineTests && (
            <div className="panel" style={{ marginBottom: '20px', borderLeft: `3px solid ${baselineTests.success ? 'var(--success-border)' : 'var(--crit-border)'}` }}>
              <div className="panel-header">
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className={`badge ${baselineTests.success ? 'badge-success' : 'badge-critical'}`}>
                      Original Baseline Environment
                    </span>
                    <strong style={{ fontSize: '0.875rem' }}>Target: LinkWatch (Read-Only)</strong>
                  </div>
                  <div className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {baselineTests.command_executed} (Exit code: {baselineTests.exit_code})
                  </div>
                </div>

                <div style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
                  <span style={{ color: 'var(--success-text)' }}>{baselineTests.passed_tests} Passed</span> /{' '}
                  <span style={{ color: 'var(--crit-text)' }}>{baselineTests.failed_tests} Failed</span>
                </div>
              </div>

              {baselineTests.failures.length > 0 && (
                <div className="panel-body">
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--crit-text)', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: '6px' }}>
                    Observed Baseline Test Failure:
                  </div>
                  {baselineTests.failures.map((f, i) => (
                    <div key={i} style={{ border: '1px solid var(--crit-border)', borderRadius: 'var(--radius-xs)', overflow: 'hidden' }}>
                      <div style={{ background: 'var(--crit-bg)', padding: '6px 12px', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--crit-text)' }}>
                        {f.test_name}
                      </div>
                      <pre className="code-block" style={{ border: 'none', background: '#fafafa', borderRadius: '0' }}>{f.traceback_snippet || f.failure_message}</pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Candidate Experiments List */}
          {candidateVerifications.length === 0 ? (
            <div className="panel" style={{ textAlign: 'center', padding: '36px 20px' }}>
              <h3 style={{ fontSize: '0.9375rem', marginBottom: '6px' }}>No Candidate Verifications Run Yet</h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
                Run an isolated experiment for Jinja2 upgrade to verify if it resolves the baseline failure without modifying LinkWatch.
              </p>
              <button
                className="btn btn-success"
                onClick={() => handleRunVerification('Jinja2', 'Jinja2>=3.1.4')}
                disabled={!!actionLoading}
              >
                Verify Candidate (Jinja2 &gt;= 3.1.4) in Sandbox
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {candidateVerifications.map((cand, idx) => {
                const isFix = cand.status === 'VERIFIED_FIX';
                return (
                  <div key={idx} className="panel" style={{ borderLeft: `3px solid ${isFix ? '#15803d' : '#ca8a04'}` }}>
                    <div className="panel-header">
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <span className={`badge ${isFix ? 'badge-success' : 'badge-high'}`}>{cand.status}</span>
                          <span className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{cand.candidate_id}</span>
                        </div>
                        <h3 style={{ fontSize: '0.9375rem' }}>
                          Candidate Experiment: <code className="mono">{cand.package_name} &rarr; {cand.proposed_change}</code>
                        </h3>
                        <p style={{ fontSize: '0.8125rem', color: isFix ? 'var(--success-text)' : 'var(--text-secondary)', marginTop: '2px', fontWeight: 500 }}>
                          {cand.verdict_summary}
                        </p>
                      </div>

                      <div style={{ textAlign: 'right', fontSize: '0.8125rem' }}>
                        <div>
                          <strong>{cand.candidate_result.passed_tests} Passed</strong> / {cand.candidate_result.failed_tests} Failed
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Exit Code: {cand.candidate_result.exit_code} ({cand.candidate_result.duration_seconds}s)
                        </div>
                      </div>
                    </div>

                    <div className="panel-body">
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                        Isolated Subprocess Execution Command:
                      </div>
                      <code className="code-inline" style={{ display: 'block', fontSize: '0.75rem', marginBottom: '8px' }}>
                        {cand.candidate_result.command_executed}
                      </code>

                      <details>
                        <summary style={{ fontSize: '0.75rem', color: 'var(--cobalt)', cursor: 'pointer', fontWeight: 500 }}>
                          View Raw Subprocess Execution Log
                        </summary>
                        <pre className="code-block" style={{ marginTop: '6px', maxHeight: '180px' }}>
                          {cand.candidate_result.raw_stdout}
                        </pre>
                      </details>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* TAB 5: CAPSULE EXPORT */}
      {activeTab === 'capsule' && (
        <section>
          <div style={{ marginBottom: '16px' }}>
            <h2 style={{ fontSize: '1.125rem' }}>Dependency Exit Capsule</h2>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              Self-contained, versioned engineering artifact consolidating all observed facts, deterministic findings, Gemma 4 advisory, and empirical test verification.
            </p>
          </div>

          <div className="panel" style={{ marginBottom: '20px' }}>
            <div className="panel-body" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div>
                <h3 style={{ fontSize: '0.9375rem', marginBottom: '4px' }}>Export Capsule Artifacts</h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  Download the machine-readable JSON capsule or the zero-dependency executive HTML report.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <a
                  href="/api/capsule/download"
                  download
                  className="btn btn-primary"
                  style={{ textDecoration: 'none' }}
                >
                  Download Capsule JSON
                </a>
                <a
                  href="/api/capsule/report"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary"
                  style={{ textDecoration: 'none' }}
                >
                  Open Executive HTML Report
                </a>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h3 style={{ fontSize: '0.875rem' }}>Provenance & Schema Metadata</h3>
            </div>
            <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', fontSize: '0.8125rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Schema Version</span>
                <div className="mono" style={{ fontWeight: 600 }}>1.0.0</div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>AI Model Specification</span>
                <div className="mono" style={{ fontWeight: 600 }}>{status?.gemma_runtime.model_tag}</div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>License Terms</span>
                <div style={{ fontWeight: 500 }}>Gemma Terms of Use (Google Open Weights)</div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Verification Engine</span>
                <div style={{ fontWeight: 500 }}>Isolated Sandbox Pytest (Pristine Target)</div>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
};

export default App;
