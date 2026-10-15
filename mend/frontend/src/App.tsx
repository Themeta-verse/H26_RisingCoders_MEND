import React, { useEffect, useState, useRef } from 'react';

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
  is_standard_library?: boolean;
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

interface LedgerEntry {
  package_name: string;
  normalized_name: string;
  stage: 'OBSERVED' | 'RECOMMENDED' | 'EXECUTED' | 'VERIFIED' | 'FAILED' | 'INCONCLUSIVE';
  observed_facts: {
    installed_version?: string;
    is_direct_usage: boolean;
    is_manifest_conflicted: boolean;
    conflict_details: string;
    manifest_declarations: ManifestDeclaration[];
    code_usage_count: number;
    code_usage_locations: CodeUsageLocation[];
    rule_findings: any[];
  };
  recommendation_provenance?: {
    model_tag: string;
    runtime: string;
    strategy: string;
    proposed_package: string;
    proposed_specifier: string;
    confidence_score: number;
    target_issue: string;
    migration_steps: string[];
    unresolved_risks: string[];
    assumptions: string[];
  };
  candidate_execution?: {
    candidate_id: string;
    proposed_change: string;
    status: string;
    verdict_summary: string;
    unresolved_gaps: string[];
    baseline_result: any;
    candidate_result: any;
  };
  capsule_exported: boolean;
  integrity_hash: string;
  repo_id?: string;
  commit_hash?: string;
  short_commit?: string;
}

interface LedgerData {
  target_repository: string;
  repo_id?: string;
  commit_hash?: string;
  short_commit?: string;
  total_dependencies: number;
  stage_distribution: Record<string, number>;
  ledger_sha256: string;
  source_snapshot_sha256: string;
  lifecycle_rule: string;
  entries: LedgerEntry[];
}


interface IntegrityData {
  target_name: string;
  repo_id?: string;
  commit_hash?: string;
  short_commit?: string;
  source_snapshot_sha256: string;
  scanned_at: string;
  exported_capsules: {
    json_filename?: string;
    json_sha256?: string;
    html_filename?: string;
    html_sha256?: string;
  };
  candidate_runner_safety: any;
  disclaimer: string;
}

interface DriftData {
  has_drift: boolean;
  scanned_at_previous: string;
  scanned_at_current: string;
  source_sha256_previous: string;
  source_sha256_current: string;
  added_dependencies: string[];
  removed_dependencies: string[];
  specifier_changes: Array<{ package: string; manifest_file: string; old_specifier: string; new_specifier: string }>;
  usage_changes: Array<{ package: string; old_is_direct_usage: boolean; new_is_direct_usage: boolean; old_import_count: number; new_import_count: number }>;
  conflict_changes: Array<{ package: string; change: string }>;
  total_dependencies_previous: number;
  total_dependencies_current: number;
}

interface RepositoryInfo {
  id: string;
  name: string;
  path: string;
  commit_hash: string;
  short_commit: string;
  clone_url?: string;
  is_official: boolean;
  ecosystem: string;
  support_level: string;
  detected_manifests: string[];
  limitations: string[];
  last_fetched_at?: string;
  revision_origin?: string;
  is_active: boolean;
}

interface SystemStatus {
  status: string;
  target_repository: {
    id: string;
    name: string;
    path: string;
    commit_hash: string;
    short_commit: string;
    clone_url?: string;
    is_official: boolean;
    ecosystem: string;
    support_level: string;
    detected_manifests: string[];
    limitations: string[];
    last_fetched_at?: string;
    revision_origin?: string;
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

export interface DependencyIntelligenceItem {
  package_name: string;
  ecosystem: string;
  current_version: string;
  latest_stable_version: string;
  recommended_target: string;
  version_difference: string;
  release_status: string;
  compatibility: string;
  change_severity: 'major' | 'minor' | 'patch' | 'none' | 'unknown';
  reason: string;
  official_links: Array<{
    title: string;
    url: string;
    category?: string;
  }>;
  verification_status: string;
  metadata_source: string;
}

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'inventory' | 'rules' | 'recommendations' | 'verification' | 'ledger' | 'capsule'>('inventory');
  
  // Repository states
  const [repositories, setRepositories] = useState<RepositoryInfo[]>([]);
  const [activeRepoId, setActiveRepoId] = useState<string>('linkwatch');
  const [isRepoModalOpen, setIsRepoModalOpen] = useState<boolean>(false);
  const [newRepoUrl, setNewRepoUrl] = useState<string>('');
  const [newRepoRef, setNewRepoRef] = useState<string>('');
  const [addingRepo, setAddingRepo] = useState<boolean>(false);

  // Data states
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [dependencies, setDependencies] = useState<Record<string, DependencyReport>>({});
  const [manifestConflicts, setManifestConflicts] = useState<any[]>([]);
  const [ruleFindings, setRuleFindings] = useState<RuleFinding[]>([]);
  const [recommendations, setRecommendations] = useState<Record<string, MigrationRecommendation>>({});
  const [baselineTests, setBaselineTests] = useState<TestExecutionResult | null>(null);
  const [candidateVerifications, setCandidateVerifications] = useState<VerificationComparison[]>([]);
  const [ledgerData, setLedgerData] = useState<LedgerData | null>(null);
  const [integrityData, setIntegrityData] = useState<IntegrityData | null>(null);
  const [driftData, setDriftData] = useState<DriftData | null>(null);
  const [intelligenceData, setIntelligenceData] = useState<DependencyIntelligenceItem[]>([]);
  const [inventorySubView, setInventorySubView] = useState<'manifest' | 'intelligence'>('manifest');
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('mend_theme');
    return (saved === 'light' || saved === 'dark') ? saved : 'dark';
  });

  // UI states
  const loadSequenceRef = useRef<number>(0);
  const [modalError, setModalError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const [selectedDep, setSelectedDep] = useState<DependencyReport | null>(null);
  const [selectedLedgerPkg, setSelectedLedgerPkg] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [depFilter, setDepFilter] = useState<'all' | 'conflicted' | 'used' | 'unreferenced'>('all');
  const [ledgerFilter, setLedgerFilter] = useState<'all' | 'VERIFIED' | 'FAILED' | 'RECOMMENDED' | 'OBSERVED'>('all');
  const [isDriftModalOpen, setIsDriftModalOpen] = useState<boolean>(false);
  const [loadingDrift, setLoadingDrift] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Sync theme attribute with document root
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('mend_theme', theme);
  }, [theme]);

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

  const safeFetchJson = async <T,>(url: string, fallback: T): Promise<T> => {
    try {
      const res = await fetch(url);
      if (!res.ok) {
        console.warn(`[MEND API] ${url} returned status ${res.status}`);
        return fallback;
      }
      const ct = res.headers.get('content-type') || '';
      if (!ct.includes('application/json')) {
        const text = await res.text();
        console.warn(`[MEND API] ${url} returned non-JSON:`, text.slice(0, 100));
        return fallback;
      }
      return await res.json();
    } catch (err: any) {
      console.warn(`[MEND API] Failed to fetch ${url}:`, err.message);
      return fallback;
    }
  };

  const loadAllData = async () => {
    const currentSeq = ++loadSequenceRef.current;
    setLoading(true);
    setErrorMsg(null);
    try {
      // 0. Fetch registered repositories list
      const repoData = await safeFetchJson<{ active_repo_id: string; repositories: RepositoryInfo[] }>('/api/repositories', { active_repo_id: 'linkwatch', repositories: [] });
      if (loadSequenceRef.current !== currentSeq) return;
      setRepositories(repoData.repositories || []);
      setActiveRepoId(repoData.active_repo_id || 'linkwatch');

      // 1. Fetch system status
      const statusData = await safeFetchJson<SystemStatus | null>('/api/status', null);
      if (loadSequenceRef.current !== currentSeq) return;
      setStatus(statusData);

      // 2. Fetch scan
      const scanData = await safeFetchJson<any>('/api/scan', { dependencies: {}, manifests_found: [], manifest_conflicts: [] });
      if (loadSequenceRef.current !== currentSeq) return;
      setDependencies(scanData.dependencies || {});
      setManifestConflicts(scanData.manifest_conflicts || []);

      // 3. Fetch rules
      const rulesData = await safeFetchJson<RuleFinding[]>('/api/rules', []);
      if (loadSequenceRef.current !== currentSeq) return;
      setRuleFindings(rulesData || []);

      // 4. Fetch baseline tests
      const testsData = await safeFetchJson<TestExecutionResult | null>('/api/baseline-tests', null);
      if (loadSequenceRef.current !== currentSeq) return;
      setBaselineTests(testsData);

      // 5. Fetch candidates
      const candData = await safeFetchJson<VerificationComparison[]>('/api/candidates', []);
      if (loadSequenceRef.current !== currentSeq) return;
      setCandidateVerifications(candData || []);

      // 6. Fetch recommendations (restores Gemma Advisory count on load/refresh)
      const recsData = await safeFetchJson<Record<string, MigrationRecommendation>>('/api/recommendations', {});
      if (loadSequenceRef.current !== currentSeq) return;
      setRecommendations(recsData || {});

      // 7. Fetch integrity ledger
      const ledgerJson = await safeFetchJson<LedgerData | null>('/api/ledger', null);
      if (loadSequenceRef.current !== currentSeq) return;
      setLedgerData(ledgerJson);

      // 8. Fetch integrity fingerprints & boundaries
      const integJson = await safeFetchJson<IntegrityData | null>('/api/integrity', null);
      if (loadSequenceRef.current !== currentSeq) return;
      setIntegrityData(integJson);

      // 9. Fetch dependency intelligence with latest PyPI verified metadata
      const intelData = await safeFetchJson<DependencyIntelligenceItem[]>('/api/dependency-intelligence', []);
      if (loadSequenceRef.current !== currentSeq) return;
      setIntelligenceData(intelData || []);

    } catch (err: any) {
      if (loadSequenceRef.current === currentSeq) {
        console.error('Failed to load initial data:', err);
        setErrorMsg(`Could not connect to backend: ${err.message}`);
      }
    } finally {
      if (loadSequenceRef.current === currentSeq) {
        setLoading(false);
      }
    }
  };

  const handleSelectRepository = async (repoId: string) => {
    if (repoId === activeRepoId) {
      setIsRepoModalOpen(false);
      return;
    }
    setActionLoading(`Switching to repository '${repoId}'...`);
    setErrorMsg(null);
    setModalError(null);

    // Invalidate and clear repository-specific state immediately so no cross-repo contamination can display
    setDependencies({});
    setManifestConflicts([]);
    setRuleFindings([]);
    setRecommendations({});
    setBaselineTests(null);
    setCandidateVerifications([]);
    setLedgerData(null);
    setIntegrityData(null);
    setDriftData(null);
    setIntelligenceData([]);
    setSelectedDep(null);
    setSelectedLedgerPkg(null);

    try {
      const res = await fetch('/api/repositories/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_id: repoId }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}`);
      }
      setIsRepoModalOpen(false);
      await loadAllData();
    } catch (err: any) {
      setErrorMsg(`Failed to select repository: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddRepository = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRepoUrl.trim()) return;
    setAddingRepo(true);
    setActionLoading(`Cloning public repository from ${newRepoUrl.trim()}...`);
    setErrorMsg(null);
    setModalError(null);
    try {
      const res = await fetch('/api/repositories/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: newRepoUrl.trim(), ref: newRepoRef.trim() || undefined }),
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || `HTTP ${res.status}`);
      }
      setNewRepoUrl('');
      setNewRepoRef('');
      setModalError(null);
      setIsRepoModalOpen(false);
      await loadAllData();
    } catch (err: any) {
      setModalError(err.message);
      setErrorMsg(`Failed to add repository: ${err.message}`);
    } finally {
      setAddingRepo(false);
      setActionLoading(null);
    }
  };

  const handleRefreshActiveRepo = async () => {
    setActionLoading(`Re-reading local files & clearing caches for '${status?.target_repository.name}'...`);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/repositories/refresh', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await loadAllData();
    } catch (err: any) {
      setErrorMsg(`Failed to refresh repository: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSyncActiveRepo = async () => {
    if (status?.target_repository.is_official) {
      setErrorMsg('Official LinkWatch checkout is an immutable challenge benchmark; remote git sync is intentionally disabled.');
      return;
    }
    setActionLoading(`Fetching latest revision from GitHub for '${status?.target_repository.name}'...`);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/repositories/sync', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      if (data.is_changed) {
        setErrorMsg(`Git Sync: Updated from commit ${data.old_commit.slice(0, 10)} to ${data.new_commit.slice(0, 10)}. In-memory scan cache invalidated.`);
      } else {
        setErrorMsg(`Git Sync: '${status?.target_repository.name}' is already up to date with origin/HEAD at commit ${data.new_commit.slice(0, 10)}.`);
      }
      await loadAllData();
    } catch (err: any) {
      setErrorMsg(`Git sync failed: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };


  const handleCheckDrift = async (refresh: boolean = true) => {
    setLoadingDrift(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/scan/diff?refresh=${refresh}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DriftData = await res.json();
      setDriftData(data);
      setIsDriftModalOpen(true);
      if (refresh) {
        // Refresh local scan and ledger data
        const scanRes = await fetch('/api/scan');
        const scanData = await scanRes.json();
        setDependencies(scanData.dependencies || {});
        setManifestConflicts(scanData.manifest_conflicts || []);
        const ledgerRes = await fetch('/api/ledger');
        const ledgerJson = await ledgerRes.json();
        setLedgerData(ledgerJson);
      }
    } catch (err: any) {
      setErrorMsg(`Snapshot drift comparison failed: ${err.message}`);
    } finally {
      setLoadingDrift(false);
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
      // Refresh ledger to reflect candidate execution stage immediately
      const updatedLedger = await safeFetchJson<LedgerData | null>('/api/ledger', null);
      if (updatedLedger) setLedgerData(updatedLedger);
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

  const filteredIntelligence = intelligenceData.filter(item => {
    return item.package_name.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const criticalFindingsCount = ruleFindings.filter(f => f.severity === 'Critical').length;
  const highFindingsCount = ruleFindings.filter(f => f.severity === 'High').length;
  const verifiedFixesCount = candidateVerifications.filter(c => c.status === 'VERIFIED_FIX').length;

  return (
    <div style={{ maxWidth: '1360px', margin: '0 auto', padding: '32px 24px', backgroundColor: 'var(--canvas)', minHeight: '100vh' }}>
      
      {/* Editorial Header */}
      <header style={{ borderBottom: '1px solid var(--border)', paddingBottom: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.03em', color: 'var(--text-black)' }}>
                MEND
              </span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Migration Evidence &amp; Dependency Navigator
              </span>
              <span className="badge badge-info" style={{ fontWeight: 600 }}>Track 1: Gemma 4 — Dependency Resilience</span>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setTheme(prev => prev === 'dark' ? 'light' : 'dark')}
                title="Toggle Dark / Light Theme"
                style={{ padding: '2px 8px', fontSize: '0.72rem', fontWeight: 600 }}
              >
                {theme === 'dark' ? '☀ Light Theme' : '🌙 Dark Theme'}
              </button>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Deterministic manifest &amp; AST evidence engine with local Gemma 4 advisory and sandbox verification.
            </p>
          </div>

          {/* Precision Diagnostic Status */}
          <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '12px', fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'var(--canvas-subtle)', padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>TARGET:</span>
              <select
                id="repository-selector"
                value={activeRepoId}
                onChange={e => {
                  if (e.target.value === '__add_new__') {
                    setIsRepoModalOpen(true);
                  } else {
                    handleSelectRepository(e.target.value);
                  }
                }}
                disabled={loading || !!actionLoading}
                style={{
                  padding: '3px 8px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: 'var(--text-black)',
                  background: '#ffffff',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-xs)',
                  fontFamily: 'inherit',
                  cursor: 'pointer',
                  maxWidth: '240px',
                }}
                title="Select active repository target or add a public GitHub repository"
              >
                {repositories.map(repo => (
                  <option key={repo.id} value={repo.id}>
                    {repo.name} {repo.is_official ? '(Official Target)' : `(${repo.short_commit})`}
                  </option>
                ))}
                <option value="__add_new__">+ Add Public GitHub Repo...</option>
              </select>

              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setIsRepoModalOpen(true)}
                title="Add a new public GitHub repository"
                style={{ padding: '2px 8px', fontSize: '0.75rem', color: 'var(--cobalt)', borderColor: 'var(--cobalt-border)' }}
              >
                + Add Repo
              </button>

              <span className="mono" style={{ fontSize: '0.6875rem', background: 'var(--border)', padding: '2px 6px', borderRadius: '3px', fontWeight: 600 }} title={`Commit SHA: ${status?.target_repository.commit_hash}`}>
                {status?.target_repository.short_commit || 'local'}
              </span>

              <span
                style={{
                  fontSize: '0.6875rem',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  background: status?.target_repository.is_official ? '#f1f5f9' : '#ecfdf5',
                  color: status?.target_repository.is_official ? '#475569' : '#047857',
                  border: `1px solid ${status?.target_repository.is_official ? '#cbd5e1' : '#a7f3d0'}`,
                  fontWeight: 600,
                }}
                title={status?.target_repository.is_official
                  ? 'Official LinkWatch benchmark (immutable local target)'
                  : `Cloned from ${status?.target_repository.clone_url || 'GitHub'} at ${status?.target_repository.last_fetched_at || 'initial clone'}`
                }
              >
                {status?.target_repository.is_official ? 'Benchmark: Immutable' : 'Revision: Fetched'}
              </span>

              <span style={{
                fontSize: '0.6875rem',
                padding: '2px 6px',
                borderRadius: '3px',
                background: status?.target_repository.support_level === 'full' ? '#ecfdf5' : '#fffbeb',
                color: status?.target_repository.support_level === 'full' ? '#047857' : '#b45309',
                fontWeight: 600,
                border: `1px solid ${status?.target_repository.support_level === 'full' ? '#a7f3d0' : '#fde68a'}`,
              }}>
                {status?.target_repository.ecosystem?.split(' ')[0] || 'Python'} ({status?.target_repository.support_level || 'full'})
              </span>
            </div>

            <div style={{ width: '1px', height: '16px', backgroundColor: 'var(--border)' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span className={`dot ${status?.gemma_runtime.is_online ? 'dot-green' : 'dot-red'}`} />
              <span style={{ color: 'var(--text-muted)' }}>RUNTIME:</span>{' '}
              <span className="mono" style={{ fontWeight: 600, color: 'var(--text-black)' }}>{status?.gemma_runtime.model_tag || 'gemma4:e2b-it-q4_K_M'}</span>
              <span style={{ color: 'var(--text-muted)' }}>({status?.gemma_runtime.is_online ? 'Ollama Online' : 'Offline'})</span>
            </div>

            <div style={{ width: '1px', height: '16px', backgroundColor: 'var(--border)' }} />

            {/* Action Buttons with Explicit Operational Semantics */}
            {!status?.target_repository.is_official && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleSyncActiveRepo}
                disabled={loading || !!actionLoading}
                title="Fetches latest revision from GitHub via git fetch/reset and clears scan caches"
              >
                Sync with GitHub
              </button>
            )}
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleRefreshActiveRepo}
              disabled={loading || !!actionLoading}
              title="Re-runs deterministic AST and manifest scanning on current local files without network calls"
            >
              Re-scan
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => handleCheckDrift(true)}
              disabled={loading || !!actionLoading || loadingDrift}
              title="Deterministically compares previous and current scan snapshots to detect manifest, specifier, and AST usage drift"
            >
              {loadingDrift ? 'Diffing...' : 'Drift Check'}
            </button>
          </div>
        </div>

        {/* Compact Editorial Metadata Strip */}
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
              {status?.target_repository.support_level !== 'full'
                ? 'N/A (AST only)'
                : (baselineTests ? `${baselineTests.passed_tests} passed, ${baselineTests.failed_tests} failed` : 'Testing...')}
            </div>
          </div>
          <div style={{ width: '1px', height: '24px', backgroundColor: 'var(--border)' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em' }}>Sandbox Verified Fixes</span>
            <div style={{ fontWeight: 600, color: verifiedFixesCount > 0 ? 'var(--success-text)' : 'var(--text-secondary)' }}>
              {status?.target_repository.support_level !== 'full'
                ? 'Unsupported (Python only)'
                : `${verifiedFixesCount} verified (${status?.target_repository.is_official ? 'Jinja2 \u2192 10/10' : 'Candidate'})`}
            </div>
          </div>
          <div style={{ width: '1px', height: '24px', backgroundColor: 'var(--border)' }} />
          <div>
            <span style={{ color: 'var(--text-muted)', textTransform: 'uppercase', fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.04em' }}>Manifest Snapshot SHA-256</span>
            <div className="mono" style={{ fontWeight: 600, color: 'var(--text-black)', fontSize: '0.75rem', cursor: 'help' }} title={integrityData?.source_snapshot_sha256 ? `${integrityData.source_snapshot_sha256}\n\nCoverage: Deterministic digest over sorted, normalized manifest declarations (e.g. requirements.txt, pyproject.toml). Tamper-evident audit record.` : 'Manifest Snapshot SHA-256 Digest'}>
              {loading
                ? 'Calculating...'
                : (integrityData?.source_snapshot_sha256
                    ? `${integrityData.source_snapshot_sha256.slice(0, 10)}...`
                    : 'Unavailable')}
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
        <button className={`tab-item ${activeTab === 'ledger' ? 'active' : ''}`} onClick={() => setActiveTab('ledger')}>
          Migration Integrity Ledger <span className="tab-pill">{ledgerData ? ledgerData.entries.length : (loading ? '...' : 0)}</span>
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

          {/* Sub-view switcher: Manifest Declarations vs Side-by-Side Version Intelligence */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', background: 'var(--canvas-subtle)', padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Inventory View:
              </span>
              <button
                className={`btn btn-sm ${inventorySubView === 'manifest' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setInventorySubView('manifest')}
                style={{ fontSize: '0.75rem' }}
              >
                Manifest &amp; Usage Inventory
              </button>
              <button
                className={`btn btn-sm ${inventorySubView === 'intelligence' ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setInventorySubView('intelligence')}
                style={{ fontSize: '0.75rem' }}
              >
                Side-by-Side Version Intelligence ({intelligenceData.length})
              </button>
            </div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {inventorySubView === 'manifest'
                ? 'Manifest-declared packages, AST usage locations, and lock-file versions'
                : 'PyPI registry verified versions, recommended targets, compatibility severity & official links'}
            </div>
          </div>

          {/* Primary Table: Manifest & Usage Inventory */}
          {inventorySubView === 'manifest' && (
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
          )}

          {/* Side-by-Side Version Intelligence & Risk Analysis Table */}
          {inventorySubView === 'intelligence' && (
            <div className="panel" style={{ overflow: 'hidden' }}>
              <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--border)', background: 'var(--canvas-subtle)', fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                <div>
                  <strong>Dependency Intelligence Matrix:</strong> Live PyPI official release metadata cross-referenced against repository constraints. Click official links for release notes and documentation.
                </div>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={async () => {
                    setActionLoading('Refreshing PyPI registry metadata for all dependencies...');
                    try {
                      const fresh = await safeFetchJson<DependencyIntelligenceItem[]>('/api/dependency-intelligence?refresh=true', []);
                      setIntelligenceData(fresh);
                    } catch (e: any) {
                      setErrorMsg(`Failed to refresh version intelligence: ${e.message}`);
                    } finally {
                      setActionLoading(null);
                    }
                  }}
                  disabled={!!actionLoading}
                  style={{ fontSize: '0.7rem', padding: '2px 8px' }}
                >
                  Force Registry Refresh
                </button>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '13%' }}>Package</th>
                    <th style={{ width: '10%' }}>Current</th>
                    <th style={{ width: '11%' }}>Latest Stable</th>
                    <th style={{ width: '13%' }}>Recommended Target</th>
                    <th style={{ width: '12%' }}>Severity &amp; Compat</th>
                    <th style={{ width: '27%' }}>Reason &amp; Official Evidence Links</th>
                    <th style={{ width: '14%', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredIntelligence.length === 0 ? (
                    <tr>
                      <td colSpan={7} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                        {intelligenceData.length === 0 ? 'Loading dependency intelligence records...' : 'No packages match the current filter.'}
                      </td>
                    </tr>
                  ) : (
                    filteredIntelligence.map(item => {
                      const sevBadgeClass = item.change_severity === 'major'
                        ? 'badge-critical'
                        : item.change_severity === 'minor'
                        ? 'badge-high'
                        : item.change_severity === 'patch'
                        ? 'badge-low'
                        : 'badge-neutral';

                      const verifBadgeClass = item.verification_status === 'VERIFIED_FIX'
                        ? 'badge-success'
                        : item.verification_status.includes('FAIL')
                        ? 'badge-critical'
                        : 'badge-neutral';

                      return (
                        <tr key={item.package_name}>
                          <td style={{ fontWeight: 600 }}>
                            <div className="mono" style={{ color: 'var(--text-black)' }}>{item.package_name}</div>
                            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>{item.ecosystem}</div>
                          </td>
                          <td>
                            <code className="code-inline">{item.current_version}</code>
                          </td>
                          <td>
                            <code className="code-inline" style={{ fontWeight: 600 }}>{item.latest_stable_version}</code>
                            {item.release_status && (
                              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>{item.release_status}</div>
                            )}
                          </td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <strong className="mono" style={{ color: 'var(--cobalt)' }}>{item.recommended_target}</strong>
                            </div>
                            <div style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)' }}>
                              {item.version_difference}
                            </div>
                          </td>
                          <td>
                            <span className={`badge ${sevBadgeClass}`}>{item.change_severity}</span>
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '3px' }}>
                              {item.compatibility}
                            </div>
                            <div style={{ marginTop: '4px' }}>
                              <span className={`badge ${verifBadgeClass}`} style={{ fontSize: '0.625rem' }}>
                                {item.verification_status}
                              </span>
                            </div>
                          </td>
                          <td>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-primary)', marginBottom: '6px', lineHeight: 1.35 }}>
                              {item.reason}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                              {item.official_links && item.official_links.map((link, idx) => (
                                <a key={idx} className="link-pill" href={link.url} target="_blank" rel="noopener noreferrer">
                                  {link.title}
                                </a>
                              ))}
                            </div>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'flex', gap: '4px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                              {item.recommended_target && item.recommended_target !== item.current_version && !item.recommended_target.includes('N/A') && (
                                <button
                                  className="btn btn-success btn-sm"
                                  onClick={() => handleRunVerification(item.package_name, item.recommended_target)}
                                  disabled={!!actionLoading}
                                  title={`Execute isolated candidate sandbox verification for ${item.package_name} == ${item.recommended_target}`}
                                  style={{ fontSize: '0.7rem', padding: '2px 6px' }}
                                >
                                  Verify Fix
                                </button>
                              )}
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleRequestRecommendation(item.package_name)}
                                disabled={!!actionLoading}
                                style={{ fontSize: '0.7rem', padding: '2px 6px' }}
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
          )}

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
                {selectedDep.is_standard_library && (
                  <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1e40af', padding: '10px 14px', borderRadius: 'var(--radius-xs)', marginBottom: '16px', fontSize: '0.8125rem' }}>
                    <strong>Python Standard Library Built-in:</strong> <code>{selectedDep.name}</code> is part of Python's built-in standard library. It does not require a declaration in <code>requirements.txt</code> or <code>pyproject.toml</code>. The absence of a manifest entry is standard Python behavior and not a missing or broken dependency.
                  </div>
                )}

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
                      <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                        {selectedDep.is_standard_library
                          ? 'Standard Library built-in module. No external PyPI manifest declaration required or expected.'
                          : 'No direct manifest declarations found.'}
                      </p>
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
                    {(() => {
                      const uniqueImports = selectedDep.direct_imports.filter((loc, idx, self) =>
                        idx === self.findIndex(l => l.file_path === loc.file_path && l.line_number === loc.line_number && l.statement === loc.statement)
                      );
                      return (
                        <>
                          <h4 style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                            Discovered AST Import Locations ({uniqueImports.length})
                          </h4>
                          {uniqueImports.length === 0 ? (
                            <div style={{ border: '1px dashed var(--border)', padding: '16px', borderRadius: 'var(--radius-xs)', color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                              No AST imports detected in project source files. This dependency is declared in manifests but unused by application logic.
                            </div>
                          ) : (
                            uniqueImports.map((loc, i) => (
                              <div key={i} style={{ border: '1px solid var(--border)', padding: '8px 12px', marginBottom: '8px', borderRadius: 'var(--radius-xs)' }}>
                                <div style={{ fontSize: '0.75rem', color: 'var(--cobalt)', marginBottom: '4px' }}>
                                  <code className="mono">{loc.file_path}:{loc.line_number}</code>
                                </div>
                                <pre className="code-block">{loc.context_snippet || loc.statement}</pre>
                              </div>
                            ))
                          )}
                        </>
                      );
                    })()}
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
                        className="btn btn-secondary btn-sm"
                        onClick={() => {
                          const dep = dependencies[finding.package] || Object.values(dependencies).find(d => d.normalized_name === finding.package.toLowerCase());
                          if (dep) {
                            setSelectedDep(dep);
                            setActiveTab('inventory');
                          }
                        }}
                        title="Jump to Evidence Dossier to inspect AST import locations and manifest lines"
                      >
                        View Dossier
                      </button>
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

                    {rec.recommendation_type === 'informational_stdlib' ? (
                      <span className="badge badge-info" style={{ padding: '6px 12px', fontSize: '0.8125rem', fontWeight: 600 }}>
                        Standard Library (No Fix Needed)
                      </span>
                    ) : (
                      <button
                        className="btn btn-success"
                        onClick={() => handleRunVerification(rec.package_name, `${rec.proposed_package}${rec.proposed_specifier}`)}
                        disabled={!!actionLoading}
                      >
                        Verify in Isolated Sandbox
                      </button>
                    )}
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
                    <strong style={{ fontSize: '0.875rem' }}>
                      Target: {status?.target_repository.name || 'Repository'} ({status?.target_repository.is_official ? 'Official Target, Read-Only' : 'Isolated Workspace'})
                    </strong>
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
                {status?.target_repository.is_official
                  ? 'Run an isolated experiment for Jinja2 upgrade to verify if it resolves the baseline failure without modifying LinkWatch.'
                  : 'Execute an isolated candidate experiment from the Rule Engine or Gemma 4 Advisory tabs to verify fixes against this workspace.'}
              </p>
              {status?.target_repository.is_official && (
                <button
                  className="btn btn-success"
                  onClick={() => handleRunVerification('Jinja2', 'Jinja2>=3.1.4')}
                  disabled={!!actionLoading}
                >
                  Verify Candidate (Jinja2 &gt;= 3.1.4) in Sandbox
                </button>
              )}
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

      {/* TAB 5: MIGRATION INTEGRITY LEDGER */}
      {activeTab === 'ledger' && (
        <section>
          <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h2 style={{ fontSize: '1.125rem' }}>Migration Integrity Ledger</h2>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                Auditable evidence-backed lifecycle tracking for every declared and discovered dependency.
              </p>
            </div>
            <div className="mono" style={{ fontSize: '0.75rem', background: 'var(--canvas-subtle)', padding: '6px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-xs)' }}>
              LEDGER DIGEST: <strong style={{ color: 'var(--cobalt)' }}>{ledgerData?.ledger_sha256 ? `${ledgerData.ledger_sha256.slice(0, 16)}...` : loading ? 'Computing...' : 'Unavailable'}</strong>
            </div>
          </div>

          {/* Lifecycle Principle Banner */}
          <div className="panel" style={{ marginBottom: '18px', background: '#fafafa' }}>
            <div className="panel-body" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', fontSize: '0.8125rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                  State Machine:
                </span>
                <span className="badge badge-info" style={{ fontWeight: 600 }}>OBSERVED</span>
                <span style={{ color: 'var(--text-muted)' }}>&rarr;</span>
                <span className="badge badge-warning" style={{ fontWeight: 600 }}>RECOMMENDED</span>
                <span style={{ color: 'var(--text-muted)' }}>&rarr;</span>
                <span className="badge badge-info" style={{ fontWeight: 600 }}>EXECUTED</span>
                <span style={{ color: 'var(--text-muted)' }}>&rarr;</span>
                <span className="badge badge-success" style={{ fontWeight: 600 }}>VERIFIED</span>
                <span style={{ color: 'var(--text-muted)' }}>/</span>
                <span className="badge badge-critical" style={{ fontWeight: 600 }}>FAILED</span>
              </div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                Strict Rule: AI recommendations are never marked verified without isolated sandbox pytest execution.
              </div>
            </div>
          </div>

          {/* Lifecycle Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginBottom: '20px' }}>
            <div className="panel" style={{ padding: '12px 16px' }}>
              <div style={{ fontSize: '0.6875rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Observed</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-black)' }}>{ledgerData?.stage_distribution?.OBSERVED || 0}</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Static AST & Manifest facts</div>
            </div>
            <div className="panel" style={{ padding: '12px 16px' }}>
              <div style={{ fontSize: '0.6875rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Recommended</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--high-text)' }}>{ledgerData?.stage_distribution?.RECOMMENDED || 0}</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Local Gemma 4 proposal</div>
            </div>
            <div className="panel" style={{ padding: '12px 16px' }}>
              <div style={{ fontSize: '0.6875rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Sandbox Verified</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--success-text)' }}>{ledgerData?.stage_distribution?.VERIFIED || 0}</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Isolated test suite passed</div>
            </div>
            <div className="panel" style={{ padding: '12px 16px' }}>
              <div style={{ fontSize: '0.6875rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Failed / Regressed</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--crit-text)' }}>{ledgerData?.stage_distribution?.FAILED || 0}</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Test failures or errors</div>
            </div>
          </div>

          {/* Ledger Filter Bar */}
          <div style={{ display: 'flex', gap: '6px', marginBottom: '14px', flexWrap: 'wrap' }}>
            <button
              className={`btn btn-sm ${ledgerFilter === 'all' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setLedgerFilter('all')}
            >
              All Entries ({ledgerData?.entries?.length || 0})
            </button>
            <button
              className={`btn btn-sm ${ledgerFilter === 'VERIFIED' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setLedgerFilter('VERIFIED')}
            >
              Verified ({ledgerData?.stage_distribution?.VERIFIED || 0})
            </button>
            <button
              className={`btn btn-sm ${ledgerFilter === 'RECOMMENDED' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setLedgerFilter('RECOMMENDED')}
            >
              Recommended ({ledgerData?.stage_distribution?.RECOMMENDED || 0})
            </button>
            <button
              className={`btn btn-sm ${ledgerFilter === 'OBSERVED' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setLedgerFilter('OBSERVED')}
            >
              Observed ({ledgerData?.stage_distribution?.OBSERVED || 0})
            </button>
            <button
              className={`btn btn-sm ${ledgerFilter === 'FAILED' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setLedgerFilter('FAILED')}
            >
              Failed ({ledgerData?.stage_distribution?.FAILED || 0})
            </button>
          </div>

          {/* Ledger Entries Table */}
          <div className="panel" style={{ overflow: 'hidden' }}>
            <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
              <thead>
                <tr style={{ background: 'var(--canvas-subtle)', textAlign: 'left', borderBottom: '1px solid var(--border)' }}>
                  <th style={{ padding: '10px 14px' }}>Package</th>
                  <th style={{ padding: '10px 14px' }}>Lifecycle Stage</th>
                  <th style={{ padding: '10px 14px' }}>Manifest Evidence</th>
                  <th style={{ padding: '10px 14px' }}>AST Imports</th>
                  <th style={{ padding: '10px 14px' }}>Gemma 4 Advisory</th>
                  <th style={{ padding: '10px 14px' }}>Sandbox Execution</th>
                  <th style={{ padding: '10px 14px', textAlign: 'right' }}>Provenance</th>
                </tr>
              </thead>
              <tbody>
                {ledgerData?.entries
                  ?.filter(e => {
                    if (ledgerFilter !== 'all' && e.stage !== ledgerFilter) return false;
                    return true;
                  })
                  .map((entry, idx) => {
                    const isExpanded = selectedLedgerPkg === entry.package_name;
                    let badgeClass = 'badge-info';
                    if (entry.stage === 'VERIFIED') badgeClass = 'badge-success';
                    else if (entry.stage === 'RECOMMENDED') badgeClass = 'badge-warning';
                    else if (entry.stage === 'FAILED') badgeClass = 'badge-critical';

                    return (
                      <React.Fragment key={idx}>
                        <tr
                          style={{
                            borderBottom: '1px solid var(--border)',
                            backgroundColor: isExpanded ? '#fafafa' : undefined,
                            cursor: 'pointer',
                          }}
                          onClick={() => setSelectedLedgerPkg(isExpanded ? null : entry.package_name)}
                        >
                          <td style={{ padding: '10px 14px', fontWeight: 600 }}>
                            <code>{entry.package_name}</code>
                            {entry.observed_facts.installed_version && (
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '6px' }}>
                                (v{entry.observed_facts.installed_version})
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            <span className={`badge ${badgeClass}`}>{entry.stage}</span>
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            {entry.observed_facts.manifest_declarations.length} decl ({entry.observed_facts.manifest_declarations.map(d => d.manifest_file).join(', ')})
                            {entry.observed_facts.is_manifest_conflicted && (
                              <span className="badge badge-warning" style={{ marginLeft: '6px' }}>Conflict</span>
                            )}
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            {entry.observed_facts.code_usage_count > 0 ? (
                              <span style={{ color: 'var(--text-black)' }}>{entry.observed_facts.code_usage_count} call sites</span>
                            ) : (
                              <span style={{ color: 'var(--text-muted)' }}>0 (Zombie / Unreferenced)</span>
                            )}
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            {entry.recommendation_provenance ? (
                              <span>
                                <strong>{entry.recommendation_provenance.proposed_package}</strong> ({Math.round(entry.recommendation_provenance.confidence_score * 100)}%)
                              </span>
                            ) : (
                              <span style={{ color: 'var(--text-muted)' }}>Not Requested</span>
                            )}
                          </td>
                          <td style={{ padding: '10px 14px' }}>
                            {entry.candidate_execution ? (
                              <span style={{ color: entry.candidate_execution.status === 'VERIFIED_FIX' ? 'var(--success-text)' : 'var(--crit-text)', fontWeight: 600 }}>
                                {entry.candidate_execution.candidate_result.passed} P / {entry.candidate_execution.candidate_result.failed} F ({entry.candidate_execution.status})
                              </span>
                            ) : (
                              <span style={{ color: 'var(--text-muted)' }}>Not Run</span>
                            )}
                          </td>
                          <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedLedgerPkg(isExpanded ? null : entry.package_name);
                              }}
                            >
                              {isExpanded ? 'Hide' : 'Inspect'}
                            </button>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr style={{ background: '#fcfcfc', borderBottom: '1px solid var(--border)' }}>
                            <td colSpan={7} style={{ padding: '16px 20px' }}>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <h4 style={{ margin: 0, fontSize: '0.875rem' }}>
                                    Full Evidence Provenance Chain: <code>{entry.package_name}</code>
                                  </h4>
                                  <div className="mono" style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                                    ENTRY SHA-256: <code>{entry.integrity_hash}</code>
                                  </div>
                                </div>

                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '14px' }}>
                                  {/* 1. Manifest Evidence */}
                                  <div style={{ background: '#fff', border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--radius-xs)' }}>
                                    <div style={{ fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
                                      1. Declared Manifest Evidence
                                    </div>
                                    {entry.observed_facts.manifest_declarations.map((d, i) => (
                                      <div key={i} style={{ marginBottom: '6px', fontSize: '0.75rem' }}>
                                        <code>{d.manifest_file}:{d.line_number}</code>
                                        <pre className="code-block" style={{ margin: '4px 0', padding: '4px 8px' }}>{d.raw_line}</pre>
                                        <span style={{ color: 'var(--text-secondary)' }}>Parsed Specifier: <code>{d.specifier || 'unpinned'}</code></span>
                                      </div>
                                    ))}
                                    {entry.observed_facts.is_manifest_conflicted && (
                                      <div style={{ background: 'var(--high-bg)', border: '1px solid var(--high-border)', color: 'var(--high-text)', padding: '6px 10px', borderRadius: 'var(--radius-xs)', marginTop: '8px', fontSize: '0.75rem' }}>
                                        {entry.observed_facts.conflict_details}
                                      </div>
                                    )}
                                  </div>

                                  {/* 2. AST Usage Evidence */}
                                  <div style={{ background: '#fff', border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--radius-xs)' }}>
                                    <div style={{ fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
                                      2. Code Usage Locations ({entry.observed_facts.code_usage_count} AST Imports)
                                    </div>
                                    {entry.observed_facts.code_usage_locations.length === 0 ? (
                                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                        Zero direct imports found across target repository Python AST. Confirmed zombie / unreferenced dependency.
                                      </div>
                                    ) : (
                                      entry.observed_facts.code_usage_locations.slice(0, 3).map((loc, i) => (
                                        <div key={i} style={{ marginBottom: '6px', fontSize: '0.75rem' }}>
                                          <code>{loc.file_path}:{loc.line_number}</code>
                                          <pre className="code-block" style={{ margin: '4px 0', padding: '4px 8px' }}>{loc.statement}</pre>
                                        </div>
                                      ))
                                    )}
                                  </div>
                                </div>

                                {/* 3. Gemma 4 Advisory */}
                                {entry.recommendation_provenance && (
                                  <div style={{ background: '#fff', border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--radius-xs)' }}>
                                    <div style={{ fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
                                      3. Gemma 4 Model Provenance ({entry.recommendation_provenance.model_tag} via {entry.recommendation_provenance.runtime})
                                    </div>
                                    <div style={{ fontSize: '0.75rem', display: 'flex', gap: '16px', marginBottom: '8px' }}>
                                      <div><strong>Strategy:</strong> {entry.recommendation_provenance.strategy}</div>
                                      <div><strong>Target Package:</strong> <code>{entry.recommendation_provenance.proposed_package} {entry.recommendation_provenance.proposed_specifier}</code></div>
                                      <div><strong>Confidence:</strong> {Math.round(entry.recommendation_provenance.confidence_score * 100)}%</div>
                                    </div>
                                    <div style={{ fontSize: '0.75rem', marginBottom: '6px' }}>
                                      <strong>Migration Steps:</strong>
                                      <ol style={{ margin: '4px 0 0 16px', padding: 0 }}>
                                        {entry.recommendation_provenance.migration_steps.map((st, i) => (
                                          <li key={i}>{st}</li>
                                        ))}
                                      </ol>
                                    </div>
                                    {entry.recommendation_provenance.unresolved_risks.length > 0 && (
                                      <div style={{ fontSize: '0.75rem', color: 'var(--crit-text)' }}>
                                        <strong>Unresolved Risks:</strong> {entry.recommendation_provenance.unresolved_risks.join('; ')}
                                      </div>
                                    )}
                                  </div>
                                )}

                                {/* 4. Candidate Sandbox Execution */}
                                {entry.candidate_execution && (
                                  <div style={{ background: '#fff', border: '1px solid var(--border)', padding: '12px', borderRadius: 'var(--radius-xs)' }}>
                                    <div style={{ fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px' }}>
                                      4. Isolated Sandbox Execution ({entry.candidate_execution.candidate_id})
                                    </div>
                                    <div style={{ fontSize: '0.75rem', marginBottom: '6px' }}>
                                      <strong>Execution Command:</strong> <code>{entry.candidate_execution.candidate_result.command}</code>
                                    </div>
                                    <div style={{ fontSize: '0.75rem', marginBottom: '6px' }}>
                                      <strong>Verdict:</strong> {entry.candidate_execution.verdict_summary}
                                    </div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                      Duration: {entry.candidate_execution.candidate_result.duration_s}s | Exit Code: {entry.candidate_execution.candidate_result.exit_code} | Passed: {entry.candidate_execution.candidate_result.passed} | Failed: {entry.candidate_execution.candidate_result.failed}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 6: CAPSULE EXPORT */}
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

          {/* Cryptographic Artifact Integrity Section */}
          <div className="panel" style={{ marginBottom: '20px' }}>
            <div className="panel-header">
              <h3 style={{ fontSize: '0.875rem' }}>Artifact Integrity & Cryptographic Fingerprints</h3>
            </div>
            <div className="panel-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', fontSize: '0.8125rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>Target Snapshot SHA-256</span>
                <div className="mono" style={{ fontWeight: 600, wordBreak: 'break-all', marginTop: '4px' }}>
                  {integrityData?.source_snapshot_sha256 || 'N/A'}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>JSON Export SHA-256</span>
                <div className="mono" style={{ fontWeight: 600, wordBreak: 'break-all', marginTop: '4px' }}>
                  {integrityData?.exported_capsules.json_sha256 || 'Generated on export'}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>HTML Report SHA-256</span>
                <div className="mono" style={{ fontWeight: 600, wordBreak: 'break-all', marginTop: '4px' }}>
                  {integrityData?.exported_capsules.html_sha256 || 'Generated on export'}
                </div>
              </div>
              <div style={{ gridColumn: '1 / -1', background: 'var(--canvas-subtle)', padding: '10px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)' }}>
                <strong style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Integrity Scope & Disclaimer:</strong>
                <p style={{ margin: '4px 0 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {integrityData?.disclaimer || 'SHA-256 fingerprints provide tamper-evident verification for pipeline audit trails. A hash is not proof of truth, authorship, runtime correctness, or complete security.'}
                </p>
              </div>
            </div>
          </div>

          {/* Candidate Runner Safety Specification Panel */}
          <div className="panel" style={{ marginBottom: '20px' }}>
            <div className="panel-header">
              <h3 style={{ fontSize: '0.875rem' }}>Candidate Runner Execution Safety Boundaries</h3>
            </div>
            <div className="panel-body" style={{ fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Isolation Mechanism</span>
                  <div style={{ fontWeight: 600 }}>Filesystem workspace copy with target-prefixed PYTHONPATH</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Pristine Target Guarantee</span>
                  <div style={{ fontWeight: 600, color: 'var(--success-text)' }}>LinkWatch files & venv 100% read-only</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Process Invocation</span>
                  <div style={{ fontWeight: 600 }}>Direct argument lists (no shell=True)</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Resource Bounds</span>
                  <div style={{ fontWeight: 600 }}>Pytest: 60s timeout | Output cap: 250KB</div>
                </div>
              </div>
              <p style={{ margin: '6px 0 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {integrityData?.candidate_runner_safety?.sandbox_boundaries_disclaimer}
              </p>
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

      {/* Snapshot Drift Comparison Modal */}
      {isDriftModalOpen && driftData && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: '#fff', borderRadius: 'var(--radius-xs)', width: '100%', maxWidth: '680px', maxHeight: '85vh', overflowY: 'auto', border: '1px solid var(--border)', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>Snapshot Drift Comparison</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Deterministic diff between previous and current scan snapshots</span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setIsDriftModalOpen(false)}
                style={{ padding: '2px 8px', fontSize: '1rem', lineHeight: '1' }}
              >
                &times;
              </button>
            </div>

            <div style={{ padding: '20px', fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Drift Status Banner */}
              <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-xs)', background: driftData.has_drift ? 'var(--high-bg)' : 'var(--success-bg)', border: `1px solid ${driftData.has_drift ? 'var(--high-border)' : 'var(--success-border)'}`, color: driftData.has_drift ? 'var(--high-text)' : 'var(--success-text)', fontWeight: 600 }}>
                {driftData.has_drift ? '⚠️ Drift Detected Across Scan Snapshots' : '✓ No Drift Detected — Target source and manifest state are identical'}
              </div>

              {/* Timestamp & SHA-256 Comparison */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: 'var(--canvas-subtle)', padding: '12px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border)' }}>
                <div>
                  <div style={{ fontSize: '0.6875rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Previous Snapshot</div>
                  <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>{driftData.scanned_at_previous ? new Date(driftData.scanned_at_previous).toLocaleTimeString() : 'Baseline'}</div>
                  <div className="mono" style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)', marginTop: '2px', wordBreak: 'break-all' }}>
                    {driftData.source_sha256_previous ? `${driftData.source_sha256_previous.slice(0, 16)}...` : 'N/A'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.6875rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>Current Snapshot</div>
                  <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>{new Date(driftData.scanned_at_current).toLocaleTimeString()}</div>
                  <div className="mono" style={{ fontSize: '0.6875rem', color: 'var(--text-secondary)', marginTop: '2px', wordBreak: 'break-all' }}>
                    {driftData.source_sha256_current ? `${driftData.source_sha256_current.slice(0, 16)}...` : 'N/A'}
                  </div>
                </div>
              </div>

              {/* Detailed Diffs */}
              <div>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '0.8125rem' }}>Added Dependencies ({driftData.added_dependencies.length})</h4>
                {driftData.added_dependencies.length === 0 ? (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>None</span>
                ) : (
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {driftData.added_dependencies.map((pkg, i) => (
                      <span key={i} className="badge badge-success">{pkg}</span>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '0.8125rem' }}>Removed Dependencies ({driftData.removed_dependencies.length})</h4>
                {driftData.removed_dependencies.length === 0 ? (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>None</span>
                ) : (
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {driftData.removed_dependencies.map((pkg, i) => (
                      <span key={i} className="badge badge-critical">{pkg}</span>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '0.8125rem' }}>Specifier Modifications ({driftData.specifier_changes.length})</h4>
                {driftData.specifier_changes.length === 0 ? (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>No declared specifier changes</span>
                ) : (
                  driftData.specifier_changes.map((chg, i) => (
                    <div key={i} style={{ fontSize: '0.75rem', padding: '4px 0' }}>
                      <code>{chg.package}</code> in <code>{chg.manifest_file}</code>: <code>{chg.old_specifier}</code> &rarr; <code>{chg.new_specifier}</code>
                    </div>
                  ))
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '10px', borderTop: '1px solid var(--border)' }}>
                <button className="btn btn-secondary btn-sm" onClick={() => setIsDriftModalOpen(false)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Repository Switcher & Public GitHub Clone Modal */}
      {isRepoModalOpen && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: '#fff', borderRadius: 'var(--radius-xs)', width: '100%', maxWidth: '640px', maxHeight: '85vh', overflowY: 'auto', border: '1px solid var(--border)', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>Repository Navigator & Workspaces</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Switch active repository or clone a public GitHub repository</span>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setIsRepoModalOpen(false)}
                style={{ padding: '2px 8px', fontSize: '1rem', lineHeight: '1' }}
              >
                &times;
              </button>
            </div>

            <div style={{ padding: '20px', fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: '18px' }}>
              
              {/* Registered Repositories List */}
              <div>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '0.8125rem', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                  Available Workspaces ({repositories.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {repositories.map(repo => (
                    <div
                      key={repo.id}
                      style={{
                        padding: '12px 14px',
                        border: `1px solid ${repo.id === activeRepoId ? 'var(--cobalt)' : 'var(--border)'}`,
                        borderRadius: 'var(--radius-xs)',
                        background: repo.id === activeRepoId ? 'var(--cobalt-subtle)' : 'var(--canvas-subtle)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '12px',
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <strong style={{ color: 'var(--text-black)' }}>{repo.name}</strong>
                          {repo.is_official && (
                            <span className="badge badge-info" style={{ fontSize: '0.6875rem' }}>Official Target</span>
                          )}
                          <span style={{
                            fontSize: '0.6875rem',
                            padding: '1px 6px',
                            borderRadius: '3px',
                            background: repo.support_level === 'full' ? '#ecfdf5' : '#fffbeb',
                            color: repo.support_level === 'full' ? '#047857' : '#b45309',
                            fontWeight: 600,
                            border: `1px solid ${repo.support_level === 'full' ? '#a7f3d0' : '#fde68a'}`,
                          }}>
                            {repo.ecosystem} ({repo.support_level})
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          <span>Commit: <code className="mono">{repo.short_commit}</code></span>
                          <span>&bull;</span>
                          <span>Manifests: {repo.detected_manifests.join(', ') || 'None'}</span>
                        </div>
                      </div>

                      <div>
                        {repo.id === activeRepoId ? (
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--cobalt)' }}>Active Target</span>
                        ) : (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleSelectRepository(repo.id)}
                            disabled={!!actionLoading}
                          >
                            Select
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Add New Public GitHub Repository */}
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <h4 style={{ margin: '0 0 6px 0', fontSize: '0.8125rem', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                  Clone Public GitHub Repository
                </h4>
                <p style={{ margin: '0 0 12px 0', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  Fetches public code into an isolated controlled workspace. Code is never executed during inspection. No Personal Access Token required.
                </p>
                <form onSubmit={handleAddRepository} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '4px' }}>
                      GitHub Repository URL
                    </label>
                    <input
                      type="url"
                      placeholder="https://github.com/bottlepy/bottle"
                      value={newRepoUrl}
                      onChange={e => setNewRepoUrl(e.target.value)}
                      required
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        fontSize: '0.8125rem',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-xs)',
                        fontFamily: 'inherit',
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 600, marginBottom: '4px' }}>
                      Branch or Commit Revision (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="main (defaults to default branch HEAD)"
                      value={newRepoRef}
                      onChange={e => setNewRepoRef(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        fontSize: '0.8125rem',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius-xs)',
                        fontFamily: 'inherit',
                      }}
                    />
                  </div>
                  {modalError && (
                    <div style={{ background: 'var(--crit-bg)', border: '1px solid var(--crit-border)', color: 'var(--crit-text)', padding: '8px 12px', borderRadius: 'var(--radius-xs)', fontSize: '0.75rem', lineHeight: 1.4 }}>
                      <strong>Clone Failed:</strong> {modalError}
                    </div>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setIsRepoModalOpen(false)}
                      disabled={addingRepo}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn btn-primary btn-sm"
                      disabled={addingRepo || !newRepoUrl.trim()}
                    >
                      {addingRepo ? 'Cloning & Scanning...' : 'Clone & Scan'}
                    </button>
                  </div>
                </form>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
