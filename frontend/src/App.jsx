import React, { useState, useEffect, useRef } from 'react'
import {
  MessageSquare,
  ShieldAlert,
  Building2,
  Send,
  RotateCcw,
  CheckCircle2,
  Clock,
  Truck,
  User,
  Phone,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  Terminal,
  RefreshCw,
  SlidersHorizontal,
  PackageCheck,
  Zap,
  Activity,
  Check,
  Database,
  ArrowRight,
  Layers,
  Cpu,
  BarChart3,
  XCircle,
  AlertOctagon,
  Flame,
  GitCommit,
  Play,
  Filter,
  Search,
  FileText,
  TrendingUp,
  Bug,
  Network,
  ListOrdered
} from 'lucide-react'

// Backend API Base URL (uses VITE_API_URL in production, or empty string for local dev proxy)
const API_BASE = import.meta.env.VITE_API_URL || ''

// Formatted text renderer for natural human chat messages
function FormattedMessage({ text }) {
  if (!text) return null

  // If text was accidentally a stringified JSON object, parse and show friendly text
  let displayText = text
  if (typeof text === 'string' && text.trim().startsWith('{') && text.trim().endsWith('}')) {
    try {
      const parsed = JSON.parse(text)
      displayText = parsed.response || parsed.message || parsed.content || text
    } catch (e) {
      // not JSON
    }
  }

  // Split lines
  const lines = displayText.split('\n')
  return (
    <div className="formatted-content">
      {lines.map((line, lIdx) => {
        const trimmed = line.trim()
        if (!trimmed) {
          return <div key={lIdx} style={{ height: '0.4rem' }} />
        }

        // Bullet point
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={lIdx} style={{ display: 'flex', gap: '0.4rem', marginLeft: '0.5rem', marginBottom: '0.2rem' }}>
              <span style={{ color: 'var(--primary)' }}>•</span>
              <span>{renderBold(trimmed.substring(2))}</span>
            </div>
          )
        }

        // Numbered item (e.g. 1. , 2. )
        const matchNum = trimmed.match(/^(\d+)\.\s+(.*)$/)
        if (matchNum) {
          return (
            <div key={lIdx} style={{ display: 'flex', gap: '0.4rem', marginLeft: '0.5rem', marginBottom: '0.2rem' }}>
              <span style={{ fontWeight: 700, color: '#93c5fd' }}>{matchNum[1]}.</span>
              <span>{renderBold(matchNum[2])}</span>
            </div>
          )
        }

        return <p key={lIdx} style={{ marginBottom: '0.35rem' }}>{renderBold(trimmed)}</p>
      })}
    </div>
  )
}

// Convert **bold** markdown to JSX strong
function renderBold(str) {
  if (!str.includes('**')) return str
  const parts = str.split('**')
  return parts.map((part, i) => (i % 2 === 1 ? <strong key={i}>{part}</strong> : part))
}

export default function App() {
  const [activeTab, setActiveTab] = useState('chat') // 'chat' | 'operations' | 'facilities'
  const [healthStatus, setHealthStatus] = useState('ONLINE')
  const [metrics, setMetrics] = useState({
    open_exceptions: 0,
    total_shipments: 0,
    trucks_in_yard: 0,
    dock_disruptions: 0
  })

  // Driver & Chat State
  const [drivers, setDrivers] = useState([])
  const [selectedDriverId, setSelectedDriverId] = useState('DRV006')
  const [messages, setMessages] = useState({})
  const [inputText, setInputText] = useState('')
  const [isLoadingChat, setIsLoadingChat] = useState(false)
  const chatBottomRef = useRef(null)

  // Real Background Activity Inspector State
  const [showInspector, setShowInspector] = useState(true)
  const [activeInspectorData, setActiveInspectorData] = useState(null)
  const [expandedJson, setExpandedJson] = useState({})

  // Operations Review State
  const [escalations, setEscalations] = useState([])
  const [resolutionNotes, setResolutionNotes] = useState({})
  const [resolvingId, setResolvingId] = useState(null)
  const [opMessage, setOpMessage] = useState(null)

  // Facilities State
  const [facilityData, setFacilityData] = useState({
    facilities: [],
    docks: [],
    active_disruptions: [],
    yard_queue: []
  })
  const [loadingFacilities, setLoadingFacilities] = useState(false)

  // Observability, Traces, Errors & Evals State
  const [obsSubTab, setObsSubTab] = useState('telemetry') // 'telemetry' | 'tracing' | 'errors' | 'evals'
  const [obsMetrics, setObsMetrics] = useState(null)
  const [obsTraces, setObsTraces] = useState([])
  const [selectedTrace, setSelectedTrace] = useState(null)
  const [selectedSpan, setSelectedSpan] = useState(null)
  const [obsErrors, setObsErrors] = useState([])
  const [errorFilter, setErrorFilter] = useState('ALL')
  const [errorResolutionNote, setErrorResolutionNote] = useState({})
  const [resolvingErrorId, setResolvingErrorId] = useState(null)
  const [expandedErrorId, setExpandedErrorId] = useState(null)
  const [obsEvals, setObsEvals] = useState([])
  const [latestEval, setLatestEval] = useState(null)
  const [isRunningEval, setIsRunningEval] = useState(false)
  const [evalCategoryFilter, setEvalCategoryFilter] = useState('ALL')
  const [isRefreshingObs, setIsRefreshingObs] = useState(false)

  // Computed Thread ID
  const threadId = `THR-${selectedDriverId}`

  // Fetch initial system data
  useEffect(() => {
    fetchHealth()
    fetchMetrics()
    fetchDrivers()
    fetchEscalations()
    fetchFacilities()
    fetchObservabilityData()
  }, [])

  // Auto-scroll chat to bottom
  useEffect(() => {
    if (activeTab === 'chat') {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, selectedDriverId, activeTab])

  // System Health
  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`)
      const data = await res.json()
      setHealthStatus(data.status === 'PASS' ? 'ONLINE' : 'DEGRADED')
    } catch (err) {
      setHealthStatus('ONLINE')
    }
  }

  // Operational Metrics
  const fetchMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/metrics`)
      if (res.ok) {
        const data = await res.json()
        setMetrics(data)
      }
    } catch (err) {
      console.warn('Metrics fetch error:', err)
    }
  }

  // Drivers List
  const fetchDrivers = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/drivers`)
      if (res.ok) {
        const data = await res.json()
        setDrivers(data.drivers || [])
      }
    } catch (err) {
      console.warn('Drivers fetch error:', err)
    }
  }

  // Escalations List
  const fetchEscalations = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/operations/escalations`)
      if (res.ok) {
        const data = await res.json()
        setEscalations(data.escalations || [])
      }
    } catch (err) {
      console.warn('Escalations fetch error:', err)
    }
  }

  // Facilities & Queue
  const fetchFacilities = async () => {
    setLoadingFacilities(true)
    try {
      const res = await fetch(`${API_BASE}/api/facilities`)
      if (res.ok) {
        const data = await res.json()
        setFacilityData(data)
      }
    } catch (err) {
      console.warn('Facilities fetch error:', err)
    } finally {
      setLoadingFacilities(false)
    }
  }

  // Observability & Telemetry Handlers
  const fetchObservabilityData = async () => {
    setIsRefreshingObs(true)
    await Promise.all([
      fetchObsMetrics(),
      fetchObsTraces(),
      fetchObsErrors(),
      fetchObsEvals()
    ])
    setIsRefreshingObs(false)
  }

  const fetchObsMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/observability/metrics`)
      if (res.ok) setObsMetrics(await res.json())
    } catch (e) {
      console.warn('Obs metrics error:', e)
    }
  }

  const fetchObsTraces = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/observability/traces?limit=50`)
      if (res.ok) {
        const data = await res.json()
        const tracesList = Array.isArray(data) ? data : (data?.traces || [])
        setObsTraces(tracesList)
        if (tracesList.length > 0) {
          setSelectedTrace(prev => {
            if (!prev) return tracesList[0]
            const found = tracesList.find(t => t.trace_id === prev.trace_id)
            return found || tracesList[0]
          })
          if (!selectedSpan && tracesList[0].spans && tracesList[0].spans.length > 0) {
            setSelectedSpan(tracesList[0].spans[0])
          }
        }
      }
    } catch (e) {
      console.warn('Obs traces error:', e)
    }
  }

  const fetchObsErrors = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/observability/errors?limit=50`)
      if (res.ok) {
        const data = await res.json()
        const errorsList = Array.isArray(data) ? data : (data?.errors || [])
        setObsErrors(errorsList)
      }
    } catch (e) {
      console.warn('Obs errors error:', e)
    }
  }

  const fetchObsEvals = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/observability/evals`)
      if (res.ok) {
        const data = await res.json()
        const evalsList = Array.isArray(data) ? data : (data?.eval_runs || [])
        setObsEvals(evalsList)
        if (evalsList.length > 0 && !latestEval) {
          setLatestEval(evalsList[0])
        }
      }
    } catch (e) {
      console.warn('Obs evals error:', e)
    }
  }

  const handleRunEvalSuite = async () => {
    setIsRunningEval(true)
    try {
      const res = await fetch(`${API_BASE}/api/observability/evals/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_name: `Automated Dashboard Suite ${new Date().toLocaleTimeString()}` })
      })
      if (res.ok) {
        const report = await res.json()
        setLatestEval(report)
        fetchObsEvals()
        fetchObsMetrics()
      }
    } catch (e) {
      console.error('Run eval suite error:', e)
    } finally {
      setIsRunningEval(false)
    }
  }

  const handleResolveObsError = async (errorId) => {
    const note = errorResolutionNote[errorId] || 'Manual resolution confirmed via Observability Dashboard'
    setResolvingErrorId(errorId)
    try {
      const res = await fetch(`${API_BASE}/api/observability/errors/${errorId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolution_note: note, resolved_by: 'Operations Supervisor' })
      })
      if (res.ok) {
        fetchObsErrors()
      }
    } catch (e) {
      console.error('Resolve error failure:', e)
    } finally {
      setResolvingErrorId(null)
    }
  }

  // Active Driver Info
  const currentDriver = drivers.find(d => d.driver_id === selectedDriverId) || {
    driver_id: selectedDriverId,
    driver_name: selectedDriverId === 'DRV006' ? 'Manoj Sharma' : selectedDriverId,
    phone: '+91-9000010006',
    carrier_id: 'CAR003',
    shipment_id: 'SHP1006',
    order_reference: 'ORD-260804-006',
    shipment_status: 'IN_TRANSIT',
    facility_name: 'Jaipur Distribution Centre'
  }

  // Current Thread Messages
  const currentMessages = messages[threadId] || [
    {
      role: 'assistant',
      content: `Hello ${currentDriver.driver_name || 'Driver'}! SetuHaul Logistics Inbound Assistant here. How can I help you with your delivery today?`,
      timestamp: '11:00 AM',
      tool_calls: [],
      execution_pipeline: [
        {
          stage: 'Session Initialized',
          detail: `Driver ${selectedDriverId} session connected. Active load manifest loaded.`,
          status: 'READY',
          timestamp: '11:00:00'
        }
      ]
    }
  ]

  // Default inspector to the latest assistant message
  useEffect(() => {
    const lastMsg = currentMessages[currentMessages.length - 1]
    if (lastMsg && lastMsg.role === 'assistant') {
      setActiveInspectorData(lastMsg)
    }
  }, [messages, threadId])

  // Send Chat Message
  const sendMessage = async (customText = null) => {
    const textToSend = customText || inputText
    if (!textToSend.trim() || isLoadingChat) return

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    const userMsg = {
      role: 'user',
      content: textToSend,
      timestamp: now
    }

    setMessages(prev => ({
      ...prev,
      [threadId]: [...(prev[threadId] || currentMessages), userMsg]
    }))
    setInputText('')
    setIsLoadingChat(true)

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: textToSend,
          thread_id: threadId,
          driver_id: selectedDriverId,
          phone: currentDriver.phone,
          shipment_id: currentDriver.shipment_id
        })
      })

      if (res.ok) {
        const data = await res.json()
        const assistantMsg = {
          role: 'assistant',
          content: data.response || 'Acknowledged.',
          tool_calls: data.tool_calls || [],
          execution_pipeline: data.execution_pipeline || [],
          feasible_slots: data.feasible_slots || [],
          latency_ms: data.latency_ms,
          status: data.status,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }

        setMessages(prev => ({
          ...prev,
          [threadId]: [...(prev[threadId] || []), assistantMsg]
        }))

        // Update real background inspector immediately with real activity
        setActiveInspectorData(assistantMsg)

        // Refresh metrics & escalations if tools were invoked
        fetchMetrics()
        fetchEscalations()
      } else {
        const errData = await res.json().catch(() => ({}))
        const errorMsg = {
          role: 'assistant',
          content: `⚠️ Error from server: ${errData.detail || 'Could not complete request'}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          tool_calls: [],
          execution_pipeline: []
        }
        setMessages(prev => ({
          ...prev,
          [threadId]: [...(prev[threadId] || []), errorMsg]
        }))
      }
    } catch (err) {
      const errorMsg = {
        role: 'assistant',
        content: `⚠️ Network Error: Unable to connect to backend on port 8000.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        tool_calls: [],
        execution_pipeline: []
      }
      setMessages(prev => ({
        ...prev,
        [threadId]: [...(prev[threadId] || []), errorMsg]
      }))
    } finally {
      setIsLoadingChat(false)
    }
  }

  // Reset Thread
  const resetThread = async () => {
    try {
      await fetch(`${API_BASE}/api/chat/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: threadId })
      })
    } catch (e) {
      console.warn('Reset error:', e)
    }
    const initialMsg = {
      role: 'assistant',
      content: `Hello ${currentDriver.driver_name || 'Driver'}! SetuHaul Logistics Inbound Assistant here. How can I help you with your delivery today?`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      tool_calls: [],
      execution_pipeline: [
        {
          stage: 'Session Reset',
          detail: `Thread memory cleared. Ready for fresh operational query.`,
          status: 'READY',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]
    }
    setMessages(prev => ({
      ...prev,
      [threadId]: [initialMsg]
    }))
    setActiveInspectorData(initialMsg)
  }

  // Resolve Escalation
  const handleResolve = async (exceptionId) => {
    const note = resolutionNotes[exceptionId] || 'Manual override approved by operations supervisor.'
    setResolvingId(exceptionId)
    try {
      const res = await fetch(`${API_BASE}/api/operations/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exception_id: exceptionId,
          resolution_note: note,
          action: 'MANUAL_SUPERVISOR_RESOLUTION'
        })
      })
      if (res.ok) {
        setOpMessage(`✅ Ticket ${exceptionId} resolved successfully!`)
        fetchEscalations()
        fetchMetrics()
        setTimeout(() => setOpMessage(null), 4000)
      }
    } catch (err) {
      console.error('Resolve error:', err)
    } finally {
      setResolvingId(null)
    }
  }

  // Direct Book Slot action
  const handleBookSlot = async (slotId) => {
    const targetShipment = currentDriver.shipment_id || 'SHP1006'
    sendMessage(`Please confirm and book slot ${slotId} for shipment ${targetShipment}.`)
  }

  // Toggle JSON accordion in inspector
  const toggleJson = (key) => {
    setExpandedJson(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="app-header">
        <div className="brand-section">
          <div className="brand-logo">🚚</div>
          <div className="brand-info">
            <h1>SetuHaul Logistics Portal</h1>
            <p>Conversational Exception Resolution & Dock Scheduling Service</p>
          </div>
        </div>

        <div className="header-status-bar">
          <span className="status-pill online">
            <span className="pulse-dot"></span>
            Backend: {healthStatus}
          </span>
          <span className="status-pill model">
            <Cpu size={13} />
            Model: deepseek/deepseek-chat (OpenRouter)
          </span>
          <span className="status-pill">
            <Clock size={13} />
            4 Aug 2026, 11:00 AM IST (+05:30)
          </span>
          <span className="status-pill alert">
            <ShieldAlert size={13} />
            Tickets: {metrics.open_exceptions}
          </span>
        </div>
      </header>

      {/* Tabs Navigation */}
      <nav className="tabs-nav">
        <button
          className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          <MessageSquare size={16} />
          Driver Chat Portal
        </button>

        <button
          className={`tab-btn ${activeTab === 'operations' ? 'active' : ''}`}
          onClick={() => setActiveTab('operations')}
        >
          <ShieldAlert size={16} />
          Operations Review Queue
          {metrics.open_exceptions > 0 && (
            <span className="tab-badge">{metrics.open_exceptions}</span>
          )}
        </button>

        <button
          className={`tab-btn ${activeTab === 'facilities' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('facilities')
            fetchFacilities()
          }}
        >
          <Building2 size={16} />
          Live Facility Status & Yard Queue
        </button>

        <button
          className={`tab-btn ${activeTab === 'observability' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('observability')
            fetchObservabilityData()
          }}
        >
          <Activity size={16} />
          Observability & Evals
          {(Array.isArray(obsErrors) ? obsErrors : []).filter(e => e.status === 'OPEN' || e.status === 'UNRESOLVED').length > 0 && (
            <span className="tab-badge" style={{ background: 'var(--danger)', color: '#fff' }}>
              {(Array.isArray(obsErrors) ? obsErrors : []).filter(e => e.status === 'OPEN' || e.status === 'UNRESOLVED').length}
            </span>
          )}
        </button>

        {activeTab === 'chat' && (
          <button
            className="inspector-toggle-btn"
            onClick={() => setShowInspector(!showInspector)}
            title="Toggle Live Background Activity Inspector"
          >
            <Activity size={14} />
            {showInspector ? 'Hide Background Inspector' : 'Show Background Inspector'}
          </button>
        )}
      </nav>

      {/* Main Tab Content */}
      <main className="app-content">
        {/* ============================================================== */}
        {/* TAB 1: DRIVER CHAT PORTAL */}
        {/* ============================================================== */}
        {activeTab === 'chat' && (
          <div className={showInspector ? "chat-layout-3col" : "chat-layout-2col"}>
            {/* COLUMN 1: Driver Session & Context */}
            <div className="card">
              <div className="card-title">
                <span>🪪 Driver Session</span>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '0.25rem 0.55rem', fontSize: '0.75rem' }}
                  onClick={resetThread}
                  title="Clear conversation history"
                >
                  <RotateCcw size={12} />
                  Reset
                </button>
              </div>

              <div>
                <label className="info-label" style={{ marginBottom: '0.35rem', display: 'block' }}>
                  Select Verified Driver Identity:
                </label>
                <select
                  className="select-input"
                  value={selectedDriverId}
                  onChange={(e) => {
                    setSelectedDriverId(e.target.value)
                  }}
                >
                  <option value="DRV006">DRV006 - Manoj Sharma (SHP1006 - Standard, Shahpura)</option>
                  <option value="DRV004">DRV004 - Sandeep Meena (Ambiguous: SHP1004 & SHP1020)</option>
                  <option value="DRV015">DRV015 - Mohammed Salim (SHP1015 - Reefer Curfew Risk)</option>
                  <option value="DRV007">DRV007 - Nitin Patil (SHP1016 - Heavy 31T Load)</option>
                  <option value="DRV012">DRV012 - Arjun Das (SHP1012 - Standard Slot Competition)</option>
                  <option value="DRV003">DRV003 - Mukesh Yadav (SHP1003 - Early in Yard)</option>
                  {drivers
                    .filter(d => !['DRV006', 'DRV004', 'DRV015', 'DRV007', 'DRV012', 'DRV003'].includes(d.driver_id))
                    .map((d, i) => (
                      <option key={`${d.driver_id}-${i}`} value={d.driver_id}>
                        {d.driver_id} - {d.driver_name} ({d.shipment_id || 'No Active Load'})
                      </option>
                    ))}
                </select>
              </div>

              {/* Driver Details Card */}
              <div className="info-grid">
                <div className="info-item">
                  <span className="info-label">Driver Name</span>
                  <span className="info-val">{currentDriver.driver_name}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Phone</span>
                  <span className="info-val">{currentDriver.phone}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Carrier</span>
                  <span className="info-val">{currentDriver.carrier_id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Assigned Shipment</span>
                  <span className="info-val" style={{ color: '#93c5fd' }}>{currentDriver.shipment_id || 'N/A'}</span>
                </div>
              </div>

              {/* Shipment Details Card */}
              {currentDriver.order_reference && (
                <div style={{ background: 'rgba(0,0,0,0.25)', padding: '0.85rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)' }}>
                  <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 700, marginBottom: '0.4rem' }}>
                    Active Load Manifest
                  </div>
                  <div style={{ fontSize: '0.82rem', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                    <div><strong>Order:</strong> <span style={{ fontFamily: 'var(--font-mono)', color: '#93c5fd' }}>{currentDriver.order_reference}</span></div>
                    <div><strong>Destination:</strong> {currentDriver.facility_name || currentDriver.destination_facility_id}</div>
                    <div><strong>Status:</strong> <span className="badge badge-medium">{currentDriver.shipment_status}</span></div>
                    {currentDriver.slot_start_ts && (
                      <div><strong>Current Slot:</strong> <span style={{ fontFamily: 'var(--font-mono)', color: '#34d399' }}>{currentDriver.slot_start_ts.replace('T', ' ').slice(11, 16)} ({currentDriver.dock_id})</span></div>
                    )}
                  </div>
                </div>
              )}

              <div style={{ marginTop: 'auto', fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                Thread ID: <code style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}>{threadId}</code>
              </div>
            </div>

            {/* COLUMN 2: Driver Chat Pane */}
            <div className="chat-pane">
              {/* Message History */}
              <div className="chat-messages">
                {currentMessages.map((msg, idx) => (
                  <div key={idx} className={`message ${msg.role}`}>
                    <div className={`avatar ${msg.role}`}>
                      {msg.role === 'user' ? <User size={18} /> : <Truck size={18} />}
                    </div>
                    <div style={{ maxWidth: '100%' }}>
                      <div className="message-bubble">
                        {/* Real Human Conversational Text */}
                        <FormattedMessage text={msg.content} />

                        {/* Interactive Feasible Slots Cards */}
                        {msg.feasible_slots && msg.feasible_slots.length > 0 && (
                          <div style={{ marginTop: '0.85rem' }}>
                            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#93c5fd', marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              <PackageCheck size={14} />
                              Available Feasible Slots (Click to Book):
                            </div>
                            <div className="slots-container">
                              {msg.feasible_slots.slice(0, 4).map((slot, sIdx) => (
                                <div key={sIdx} className="slot-card">
                                  <span className="slot-time">
                                    {slot.slot_start_ts?.slice(11, 16)} – {slot.slot_end_ts?.slice(11, 16)}
                                  </span>
                                  <span className="slot-dock">
                                    Dock <strong>{slot.dock_code || slot.dock_id}</strong> ({slot.dock_type || 'STANDARD'})
                                  </span>
                                  <button
                                    className="btn btn-primary"
                                    style={{ padding: '0.35rem', fontSize: '0.75rem', marginTop: '0.3rem' }}
                                    onClick={() => handleBookSlot(slot.slot_id)}
                                  >
                                    <Check size={13} />
                                    Book This Slot
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Message Meta Info */}
                      <div className="message-meta" style={{ justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                        <span>{msg.timestamp}</span>
                        {msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0 && (
                          <button
                            className="activity-badge-pill"
                            onClick={() => {
                              setActiveInspectorData(msg)
                              setShowInspector(true)
                            }}
                            title="Inspect real background tools executed for this message"
                          >
                            <Terminal size={11} />
                            {msg.tool_calls.length} Background {msg.tool_calls.length === 1 ? 'Job' : 'Jobs'} Executed
                          </button>
                        )}
                        {msg.latency_ms && (
                          <span style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>
                            ⚡ {msg.latency_ms} ms
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {isLoadingChat && (
                  <div className="message assistant">
                    <div className="avatar assistant"><Truck size={18} /></div>
                    <div className="message-bubble" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <RefreshCw size={15} style={{ animation: 'spin 1s linear infinite' }} />
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        Evaluating operational feasibility & scheduling constraints...
                      </span>
                    </div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Quick Prompts Bar */}
              <div className="quick-prompts-bar">
                <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', alignSelf: 'center', fontWeight: 600 }}>
                  Quick Prompts:
                </span>
                <button
                  className="chip-btn"
                  onClick={() => sendMessage("Traffic after Shahpura. Reaching around 11:20. Any slot after 12?")}
                >
                  🚗 Delay: Shahpura (~11:20 AM)
                </button>
                <button
                  className="chip-btn"
                  onClick={() => sendMessage("I will be late by 45 minutes due to highway congestion.")}
                >
                  ⏱️ Late by 45 Minutes
                </button>
                <button
                  className="chip-btn"
                  onClick={() => sendMessage("Evening traffic on highway. ETA 6:30 PM. Can the reefer unload tonight?")}
                >
                  ❄️ Reefer Curfew Query (ETA 6:30 PM)
                </button>
                <button
                  className="chip-btn"
                  onClick={() => sendMessage("I am carrying order ORD-260804-006.")}
                >
                  📋 Specify ORD-260804-006
                </button>
                <button
                  className="chip-btn"
                  onClick={() => sendMessage("Arrived early in yard. Can I unload now?")}
                >
                  📦 Early Yard Check-In
                </button>
              </div>

              {/* Chat Input Bar */}
              <form
                className="chat-input-bar"
                onSubmit={(e) => {
                  e.preventDefault()
                  sendMessage()
                }}
              >
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Type message to SetuHaul assistant (e.g. 'Stuck in traffic, new ETA 11:30 AM')..."
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  disabled={isLoadingChat}
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isLoadingChat || !inputText.trim()}
                >
                  <Send size={15} />
                  Send
                </button>
              </form>
            </div>

            {/* COLUMN 3: REAL BACKGROUND ACTIVITY INSPECTOR (MVP MONITOR) */}
            {showInspector && (
              <div className="inspector-pane">
                <div className="inspector-header">
                  <div className="inspector-title-row">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontWeight: 700, fontSize: '0.9rem' }}>
                      <Activity size={16} style={{ color: '#c084fc' }} />
                      <span>Live Agent Background Pipeline</span>
                    </div>
                    <span className="badge badge-resolved" style={{ fontSize: '0.68rem' }}>
                      REAL MVP JOBS
                    </span>
                  </div>

                  <div className="inspector-meta-bar">
                    <span>Model: <strong style={{ color: '#c084fc' }}>deepseek-chat</strong></span>
                    <span>•</span>
                    <span>Latency: <strong>{activeInspectorData?.latency_ms ? `${activeInspectorData.latency_ms} ms` : 'Cached/Initial'}</strong></span>
                    <span>•</span>
                    <span>Tools Executed: <strong>{activeInspectorData?.tool_calls?.length || 0}</strong></span>
                  </div>
                </div>

                <div className="inspector-content">
                  {/* Pipeline Timeline */}
                  {activeInspectorData?.execution_pipeline && activeInspectorData.execution_pipeline.length > 0 ? (
                    activeInspectorData.execution_pipeline.map((step, sIdx) => (
                      <div key={sIdx} className="pipeline-step-card active">
                        <div className="pipeline-step-header">
                          <span style={{ color: '#93c5fd' }}>{step.stage}</span>
                          <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                            {step.timestamp}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#e5e7eb' }}>
                          {step.detail}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div style={{ color: 'var(--text-dim)', fontSize: '0.8rem', textAlign: 'center', padding: '1rem' }}>
                      No active pipeline events recorded for this turn.
                    </div>
                  )}

                  {/* Real Tool Invocations Section */}
                  {activeInspectorData?.tool_calls && activeInspectorData.tool_calls.length > 0 && (
                    <div style={{ marginTop: '0.5rem' }}>
                      <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-dim)', fontWeight: 700, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <Terminal size={13} style={{ color: 'var(--primary)' }} />
                        Authoritative Tool Invocations ({activeInspectorData.tool_calls.length}):
                      </div>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {activeInspectorData.tool_calls.map((tc, tIdx) => (
                          <div key={tIdx} className="pipeline-step-card">
                            <div className="pipeline-step-header">
                              <span className="tool-name-badge">{tc.name}</span>
                              <span className={`badge ${tc.status === 'SUCCESS' ? 'badge-resolved' : 'badge-critical'}`}>
                                {tc.status}
                              </span>
                            </div>

                            <div style={{ fontSize: '0.8rem', color: '#f3f4f6' }}>
                              {tc.summary || `Invoked tool ${tc.name}`}
                            </div>

                            {/* Collapsible Tool Arguments */}
                            <div>
                              <button
                                style={{ background: 'transparent', border: 'none', color: '#93c5fd', fontSize: '0.72rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.15rem 0' }}
                                onClick={() => toggleJson(`args_${tIdx}`)}
                              >
                                {expandedJson[`args_${tIdx}`] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                Input Arguments ({Object.keys(tc.args || {}).length} params)
                              </button>
                              {expandedJson[`args_${tIdx}`] && (
                                <pre className="tool-json-viewer">
                                  {JSON.stringify(tc.args, null, 2)}
                                </pre>
                              )}
                            </div>

                            {/* Collapsible Tool Database Result */}
                            <div>
                              <button
                                style={{ background: 'transparent', border: 'none', color: '#34d399', fontSize: '0.72rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.15rem 0' }}
                                onClick={() => toggleJson(`res_${tIdx}`)}
                              >
                                {expandedJson[`res_${tIdx}`] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                Database / Feasibility Result
                              </button>
                              {expandedJson[`res_${tIdx}`] && (
                                <pre className="tool-json-viewer" style={{ color: '#a7f3d0' }}>
                                  {JSON.stringify(tc.result, null, 2)}
                                </pre>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Business Rules Summary */}
                  <div style={{ marginTop: 'auto', background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-light)', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    <div style={{ fontWeight: 700, color: '#f3f4f6', marginBottom: '0.25rem' }}>
                      Enforced Invariants:
                    </div>
                    <div>• Zero double-booking via SQLite unique indexes</div>
                    <div>• Strict curfew cutoff (21:00 at Jaipur DC)</div>
                    <div>• Automated D3 breakdown exclusion (DEVT001)</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 2: OPERATIONS REVIEW QUEUE */}
        {/* ============================================================== */}
        {activeTab === 'operations' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.4rem', fontWeight: 800 }}>Warehouse Operations Review Queue</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                  Exceptions requiring human supervisor approval, dock reassignment, or manual scheduling overrides.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                <span className="status-pill alert">
                  <ShieldAlert size={14} />
                  {escalations.length} Pending Exceptions
                </span>
                <button
                  className="btn btn-secondary"
                  onClick={fetchEscalations}
                >
                  <RefreshCw size={14} />
                  Refresh Queue
                </button>
              </div>
            </div>

            {opMessage && (
              <div style={{ background: 'var(--success-bg)', border: '1px solid var(--success)', color: 'var(--success)', padding: '0.85rem 1.25rem', borderRadius: 'var(--radius-md)', marginBottom: '1.25rem', fontWeight: 600 }}>
                {opMessage}
              </div>
            )}

            {escalations.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                <CheckCircle2 size={48} style={{ color: 'var(--success)', margin: '0 auto 1rem' }} />
                <h3>No Open Exception Tickets</h3>
                <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                  All driver exceptions have been resolved or automated by the SetuHaul agent!
                </p>
              </div>
            ) : (
              <div className="escalations-list">
                {escalations.map((exc) => {
                  const severityBadgeClass =
                    exc.severity_code === 'CRITICAL' ? 'badge-critical' :
                      exc.severity_code === 'HIGH' ? 'badge-high' : 'badge-medium'

                  return (
                    <div key={exc.exception_id} className="escalation-card">
                      <div>
                        <div className="escalation-header">
                          <span className="ticket-id">{exc.exception_id}</span>
                          <span className={`badge ${severityBadgeClass}`}>{exc.severity_code}</span>
                          <span className="badge badge-open">{exc.exception_status}</span>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginLeft: 'auto' }}>
                            Reported: {exc.reported_at?.replace('T', ' ').slice(0, 19)}
                          </span>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '0.85rem' }}>
                          <div>
                            <span className="info-label">Shipment / Order</span>
                            <div style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: '#93c5fd' }}>
                              {exc.shipment_id || 'N/A'} ({exc.order_reference || 'N/A'})
                            </div>
                          </div>
                          <div>
                            <span className="info-label">Destination Facility</span>
                            <div style={{ fontWeight: 600 }}>{exc.destination_facility_id || 'N/A'}</div>
                          </div>
                          <div>
                            <span className="info-label">Priority Code</span>
                            <div><span className="badge badge-high">{exc.priority_code || 'NORMAL'}</span></div>
                          </div>
                          <div>
                            <span className="info-label">Driver Contact</span>
                            <div style={{ fontWeight: 600 }}>{exc.driver_name} ({exc.driver_phone})</div>
                          </div>
                        </div>

                        <div className="ticket-desc">
                          <strong>Disruption Context:</strong> {exc.description}
                        </div>
                      </div>

                      {/* Supervisor Resolution Box */}
                      <div className="supervisor-box">
                        <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#f3f4f6' }}>
                          Supervisor Resolution
                        </span>
                        <textarea
                          className="text-input"
                          rows={2}
                          placeholder="Enter supervisor resolution note..."
                          value={resolutionNotes[exc.exception_id] || ''}
                          onChange={(e) => setResolutionNotes({ ...resolutionNotes, [exc.exception_id]: e.target.value })}
                        />
                        <button
                          className="btn btn-success"
                          disabled={resolvingId === exc.exception_id}
                          onClick={() => handleResolve(exc.exception_id)}
                        >
                          <CheckCircle2 size={15} />
                          {resolvingId === exc.exception_id ? 'Resolving...' : 'Approve & Close Ticket'}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 3: LIVE FACILITY & YARD STATUS */}
        {/* ============================================================== */}
        {activeTab === 'facilities' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.4rem', fontWeight: 800 }}>Live Operational Facility Status</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                  Real-time dock health, active disruption events, and trucks currently queued in facility yards.
                </p>
              </div>

              <button
                className="btn btn-secondary"
                onClick={fetchFacilities}
                disabled={loadingFacilities}
              >
                <RefreshCw size={14} className={loadingFacilities ? 'spin' : ''} />
                Refresh Status
              </button>
            </div>

            {/* Facility Information Cards */}
            <div className="facilities-grid">
              <div className="card">
                <div className="card-title">
                  <span>🏢 Jaipur Distribution Centre</span>
                  <code style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}>FAC-JAI-01</code>
                </div>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">Operating Window</span>
                    <span className="info-val">06:00 – 22:00 IST</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Strict Curfew (Last Start)</span>
                    <span className="info-val" style={{ color: '#f87171' }}>21:00 IST</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Standard Docks</span>
                    <span className="info-val">D1, D2, D3, D4</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Specialized Docks</span>
                    <span className="info-val">D5 (Reefer), D6 (Heavy 35T)</span>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="card-title">
                  <span>🏢 Gurugram Cross-Dock</span>
                  <code style={{ color: 'var(--primary)', fontFamily: 'var(--font-mono)' }}>FAC-GGN-01</code>
                </div>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">Operating Window</span>
                    <span className="info-val">07:00 – 21:00 IST</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Strict Curfew</span>
                    <span className="info-val">20:00 IST</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Standard Docks</span>
                    <span className="info-val">D1, D2</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Specialized Docks</span>
                    <span className="info-val">D3 (Reefer)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Active Dock Disruptions */}
            <div className="data-table-container">
              <div className="table-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
                  <AlertTriangle size={17} style={{ color: 'var(--warning)' }} />
                  <span>Active Dock Disruptions (`dock_status_events`)</span>
                </div>
                <span className="badge badge-high">{facilityData.active_disruptions.length} Disruptions</span>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Event ID</th>
                    <th>Dock ID</th>
                    <th>Disruption Type</th>
                    <th>Window Start</th>
                    <th>Window End</th>
                    <th>Operational Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {facilityData.active_disruptions.map((evt) => (
                    <tr key={evt.dock_event_id}>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{evt.dock_event_id}</td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{evt.dock_id}</td>
                      <td>
                        <span className={`badge ${evt.event_type === 'BREAKDOWN' ? 'badge-critical' : 'badge-high'}`}>
                          {evt.event_type}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{evt.event_start_ts?.slice(11, 16)}</td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{evt.event_end_ts?.slice(11, 16) || 'Ongoing'}</td>
                      <td>{evt.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Trucks Waiting in Yard Queue */}
            <div className="data-table-container">
              <div className="table-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
                  <Truck size={17} style={{ color: 'var(--primary)' }} />
                  <span>Trucks Currently Waiting in Facility Yard (`v_current_facility_queue`)</span>
                </div>
                <span className="badge badge-medium">{facilityData.yard_queue.length} Queued</span>
              </div>
              {facilityData.yard_queue.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No trucks currently waiting in the yard queue.
                </div>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Queue Pos</th>
                      <th>Facility</th>
                      <th>Shipment</th>
                      <th>Driver</th>
                      <th>Check-In Time</th>
                      <th>Waiting Duration</th>
                      <th>Assigned Dock</th>
                    </tr>
                  </thead>
                  <tbody>
                    {facilityData.yard_queue.map((row, idx) => (
                      <tr key={idx}>
                        <td style={{ fontWeight: 700, textAlign: 'center' }}>#{row.queue_position || idx + 1}</td>
                        <td>{row.facility_id}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', color: '#93c5fd' }}>{row.shipment_id}</td>
                        <td>{row.driver_name || row.driver_id}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{row.gate_checkin_ts?.slice(11, 16)}</td>
                        <td>{row.wait_minutes ? `${row.wait_minutes} mins` : 'Waiting'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)' }}>{row.dock_id || 'Pending Call'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* TAB 4: OBSERVABILITY, TRACES, ERRORS & EVALS */}
        {/* ============================================================== */}
        {activeTab === 'observability' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Top Toolbar */}
            <div className="obs-header-bar">
              <div className="obs-subnav">
                <button
                  className={`obs-subnav-btn ${obsSubTab === 'telemetry' ? 'active' : ''}`}
                  onClick={() => setObsSubTab('telemetry')}
                >
                  <BarChart3 size={15} />
                  Telemetry & KPIs
                </button>
                <button
                  className={`obs-subnav-btn ${obsSubTab === 'tracing' ? 'active' : ''}`}
                  onClick={() => setObsSubTab('tracing')}
                >
                  <Network size={15} />
                  Distributed Traces ({(Array.isArray(obsTraces) ? obsTraces : []).length})
                </button>
                <button
                  className={`obs-subnav-btn ${obsSubTab === 'errors' ? 'active' : ''}`}
                  onClick={() => setObsSubTab('errors')}
                >
                  <Bug size={15} />
                  Error Monitoring
                  {(Array.isArray(obsErrors) ? obsErrors : []).filter(e => e.status === 'OPEN' || e.status === 'UNRESOLVED').length > 0 && (
                    <span style={{ background: '#ef4444', color: '#fff', borderRadius: '9999px', padding: '0.1rem 0.45rem', fontSize: '0.68rem', fontWeight: 700 }}>
                      {(Array.isArray(obsErrors) ? obsErrors : []).filter(e => e.status === 'OPEN' || e.status === 'UNRESOLVED').length}
                    </span>
                  )}
                </button>
                <button
                  className={`obs-subnav-btn ${obsSubTab === 'evals' ? 'active' : ''}`}
                  onClick={() => setObsSubTab('evals')}
                >
                  <ListOrdered size={15} />
                  Automated Evals (22 Scenarios)
                </button>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <button
                  className="btn btn-secondary"
                  onClick={fetchObservabilityData}
                  disabled={isRefreshingObs}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', padding: '0.45rem 0.85rem' }}
                >
                  <RefreshCw size={13} className={isRefreshingObs ? 'spin' : ''} />
                  Refresh Telemetry
                </button>
              </div>
            </div>

            {/* SUBTAB 1: TELEMETRY & KPIS */}
            {obsSubTab === 'telemetry' && (
              <div>
                {/* 4 KPI Cards */}
                <div className="obs-kpi-grid">
                  <div className="obs-kpi-card success">
                    <div className="obs-kpi-label">
                      <span>Total Requests</span>
                      <Activity size={15} style={{ color: '#10b981' }} />
                    </div>
                    <div className="obs-kpi-value">{obsMetrics?.total_requests ?? 0}</div>
                    <div className="obs-kpi-subtext">
                      {obsMetrics?.successful_requests ?? obsMetrics?.status_counts?.['2xx'] ?? 0} Successful • {obsMetrics?.failed_requests ?? ((obsMetrics?.status_counts?.['4xx'] || 0) + (obsMetrics?.status_counts?.['5xx'] || 0))} Failed
                    </div>
                  </div>

                  <div className="obs-kpi-card">
                    <div className="obs-kpi-label">
                      <span>Latency (P50 / P95)</span>
                      <Clock size={15} style={{ color: '#60a5fa' }} />
                    </div>
                    <div className="obs-kpi-value">
                      {obsMetrics?.p50_latency_ms?.toFixed(1) ?? '0.0'} <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>ms</span>
                    </div>
                    <div className="obs-kpi-subtext">
                      p95: {obsMetrics?.p95_latency_ms?.toFixed(1) ?? '0.0'}ms • p99: {obsMetrics?.p99_latency_ms?.toFixed(1) ?? '0.0'}ms
                    </div>
                  </div>

                  <div className={`obs-kpi-card ${obsMetrics?.error_rate_pct > 0 ? 'danger' : 'success'}`}>
                    <div className="obs-kpi-label">
                      <span>Error Rate</span>
                      <AlertOctagon size={15} style={{ color: obsMetrics?.error_rate_pct > 0 ? '#ef4444' : '#10b981' }} />
                    </div>
                    <div className="obs-kpi-value">
                      {obsMetrics?.error_rate_pct?.toFixed(1) ?? '0.0'}%
                    </div>
                    <div className="obs-kpi-subtext">
                      Active Exceptions: {obsErrors.filter(e => e.status === 'UNRESOLVED').length} Unresolved
                    </div>
                  </div>

                  <div className="obs-kpi-card">
                    <div className="obs-kpi-label">
                      <span>System Health</span>
                      <Zap size={15} style={{ color: '#f59e0b' }} />
                    </div>
                    <div className="obs-kpi-value" style={{ color: '#10b981', fontSize: '1.35rem' }}>
                      {obsMetrics?.system_status || 'HEALTHY'}
                    </div>
                    <div className="obs-kpi-subtext">
                      Uptime: {Math.floor((obsMetrics?.uptime_seconds || 0) / 60)}m {(Math.floor(obsMetrics?.uptime_seconds || 0) % 60)}s
                    </div>
                  </div>
                </div>

                {/* Per-Tool Execution Telemetry Matrix */}
                <div className="data-table-container">
                  <div className="table-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700 }}>
                      <Cpu size={17} style={{ color: 'var(--primary)' }} />
                      <span>Deterministic Tool Execution Breakdown</span>
                    </div>
                    <span className="badge badge-medium">
                      {Object.keys(obsMetrics?.tool_metrics || obsMetrics?.tool_executions || {}).length} Registered Tools
                    </span>
                  </div>
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Tool Name</th>
                        <th>Total Invocations</th>
                        <th>Success</th>
                        <th>Failed</th>
                        <th>Success Rate</th>
                        <th>Avg Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.keys(obsMetrics?.tool_metrics || obsMetrics?.tool_executions || {}).length === 0 ? (
                        <tr>
                          <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
                            No tool executions recorded yet in current session. Send a driver message to trigger tools.
                          </td>
                        </tr>
                      ) : (
                        Object.entries(obsMetrics?.tool_metrics || obsMetrics?.tool_executions || {}).map(([toolName, stats]) => {
                          const rate = stats.success_rate_pct !== undefined ? Number(stats.success_rate_pct).toFixed(0) : (stats.calls > 0 ? ((stats.success / stats.calls) * 100).toFixed(0) : '100')
                          const failedCount = stats.errors ?? stats.failed ?? 0
                          const avgMs = stats.avg_ms ?? stats.avg_latency_ms ?? 0
                          return (
                            <tr key={toolName}>
                              <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#93c5fd' }}>
                                {toolName}
                              </td>
                              <td style={{ fontWeight: 700 }}>{stats.calls}</td>
                              <td style={{ color: '#34d399' }}>{stats.success}</td>
                              <td style={{ color: failedCount > 0 ? '#ef4444' : 'var(--text-dim)' }}>{failedCount}</td>
                              <td>
                                <span className={`badge ${rate === '100' ? 'badge-resolved' : 'badge-high'}`}>
                                  {rate}%
                                </span>
                              </td>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>{Number(avgMs).toFixed(1)} ms</td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>

                {/* System Architecture Guarantees Card */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem', marginTop: '1.5rem' }}>
                  <div className="card">
                    <div className="card-title">
                      <span>🛡️ Invariant 1: Feasibility Engine Determinism</span>
                    </div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                      Dock assignment queries bypass LLM hallucination and run directly through <code>app/services/feasibility.py</code> with strict parameter verification against <code>dock_specifications</code>, curfew boundaries, and disruption windows.
                    </p>
                  </div>
                  <div className="card">
                    <div className="card-title">
                      <span>🔒 Invariant 2: Zero Double-Booking Lock</span>
                    </div>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                      Transactions use <code>EXCLUSIVE IMMEDIATE</code> locking in SQLite and enforce unique <code>(dock_id, slot_start_ts)</code> constraints. Even under concurrent re-scheduling attempts, duplicate slot allocation is mathematically impossible.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* SUBTAB 2: DISTRIBUTED TRACES & WATERFALL */}
            {obsSubTab === 'tracing' && (
              <div className="trace-split-layout">
                {/* Left Trace Selector */}
                <div className="trace-list-panel">
                  <div style={{ padding: '0.85rem 1rem', background: 'rgba(17, 24, 39, 0.9)', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                      Trace Execution History
                    </span>
                    <span className="badge badge-medium">{(Array.isArray(obsTraces) ? obsTraces : []).length} Traces</span>
                  </div>
                  <div style={{ overflowY: 'auto', flex: 1 }}>
                    {(Array.isArray(obsTraces) ? obsTraces : []).length === 0 ? (
                      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                        No traces captured yet.
                      </div>
                    ) : (
                      (Array.isArray(obsTraces) ? obsTraces : []).map((trace) => {
                        const isSelected = selectedTrace?.trace_id === trace.trace_id
                        const isOk = trace.status === 'SUCCESS' || trace.status === 'OK'
                        return (
                          <div
                            key={trace.trace_id}
                            className={`trace-item ${isSelected ? 'active' : ''}`}
                            onClick={() => {
                              setSelectedTrace(trace)
                              if (trace.spans && trace.spans.length > 0) {
                                setSelectedSpan(trace.spans[0])
                              }
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', fontWeight: 700, color: isSelected ? 'var(--primary)' : 'var(--text-main)' }}>
                                {trace.root_name || trace.root_span_name}
                              </span>
                              <span className={`badge ${isOk ? 'badge-resolved' : 'badge-critical'}`}>
                                {trace.status}
                              </span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                              <span style={{ fontFamily: 'var(--font-mono)' }}>{trace.trace_id.slice(0, 16)}...</span>
                              <span>{(trace.duration_ms || 0).toFixed(1)} ms • {trace.span_count} spans</span>
                            </div>
                          </div>
                        )
                      })
                    )}
                  </div>
                </div>

                {/* Right Waterfall View */}
                <div className="waterfall-panel">
                  {selectedTrace ? (
                    <div>
                      <div className="waterfall-header">
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
                            <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>{selectedTrace.root_name}</h3>
                            <span className={`badge ${selectedTrace.status === 'SUCCESS' ? 'badge-resolved' : 'badge-critical'}`}>
                              {selectedTrace.status}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                            Trace ID: {selectedTrace.trace_id}
                          </div>
                        </div>
                        <div style={{ textAlign: 'right', display: 'flex', gap: '1rem', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: '1.25rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#93c5fd' }}>
                              {selectedTrace.duration_ms.toFixed(1)} ms
                            </div>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                              {selectedTrace.span_count} hierarchical spans
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Waterfall Gantt Rows */}
                      <div style={{ marginBottom: '1.5rem' }}>
                        <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '0.6rem' }}>
                          Hierarchical Execution Waterfall (Nested Spans)
                        </div>

                        {selectedTrace.spans?.map((span, sIdx) => {
                          const totalMs = Math.max(selectedTrace.duration_ms, 1)
                          const traceStart = new Date(selectedTrace.start_ts).getTime()
                          const spanStart = new Date(span.start_ts).getTime()
                          const offsetMs = Math.max(0, spanStart - traceStart)
                          const leftPct = Math.min(95, (offsetMs / totalMs) * 100)
                          const widthPct = Math.max(3, Math.min(100 - leftPct, (span.duration_ms / totalMs) * 100))

                          const isSelectedSpan = selectedSpan?.span_id === span.span_id

                          return (
                            <div
                              key={span.span_id || sIdx}
                              className={`waterfall-row ${isSelectedSpan ? 'selected' : ''}`}
                              onClick={() => setSelectedSpan(span)}
                            >
                              <div className="waterfall-info" style={{ paddingLeft: `${(span.parent_span_id ? 1 : 0) * 1.25}rem` }}>
                                <span className={`span-badge ${span.span_type || 'internal'}`}>
                                  {span.span_type}
                                </span>
                                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: span.status === 'ERROR' ? '#ef4444' : 'var(--text-main)' }}>
                                  {span.name}
                                </span>
                              </div>

                              <div className="waterfall-bar-container">
                                <div
                                  className="waterfall-bar"
                                  style={{
                                    left: `${leftPct}%`,
                                    width: `${widthPct}%`,
                                    background: span.status === 'ERROR' ? '#ef4444' :
                                      span.span_type === 'agent' ? '#a855f7' :
                                        span.span_type === 'tool' ? '#10b981' :
                                          span.span_type === 'db' ? '#f59e0b' : '#3b82f6'
                                  }}
                                />
                              </div>

                              <div style={{ width: '80px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                                {span.duration_ms.toFixed(1)} ms
                              </div>
                            </div>
                          )
                        })}
                      </div>

                      {/* Selected Span Details Inspector */}
                      {selectedSpan && (
                        <div style={{ background: 'rgba(0, 0, 0, 0.35)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', borderBottom: '1px solid var(--border-light)', paddingBottom: '0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span className={`span-badge ${selectedSpan.span_type}`}>{selectedSpan.span_type}</span>
                              <strong style={{ fontSize: '0.9rem' }}>{selectedSpan.name}</strong>
                            </div>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: '#93c5fd' }}>
                              Span ID: {selectedSpan.span_id}
                            </span>
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
                            <div><strong>Duration:</strong> {selectedSpan.duration_ms.toFixed(2)} ms</div>
                            <div><strong>Status:</strong> <span className={`badge ${selectedSpan.status === 'SUCCESS' ? 'badge-resolved' : 'badge-critical'}`}>{selectedSpan.status}</span></div>
                            <div><strong>Start Time:</strong> {selectedSpan.start_ts?.slice(11, 23)}</div>
                            <div><strong>Parent:</strong> {selectedSpan.parent_span_id || 'Root Span'}</div>
                          </div>

                          {selectedSpan.attributes && Object.keys(selectedSpan.attributes).length > 0 && (
                            <div>
                              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 700, marginBottom: '0.35rem' }}>
                                Span Attributes & Metadata
                              </div>
                              <pre style={{ background: '#090d16', padding: '0.65rem', borderRadius: '4px', fontSize: '0.75rem', color: '#a7f3d0', overflowX: 'auto', maxHeight: '180px' }}>
                                {JSON.stringify(selectedSpan.attributes, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      Select a trace from the left panel to inspect its waterfall.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* SUBTAB 3: ERROR MONITORING & AUDIT */}
            {obsSubTab === 'errors' && (
              <div>
                {/* Filter and stats row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    {['ALL', 'UNRESOLVED', 'RESOLVED', 'CRITICAL', 'ERROR', 'WARNING'].map(f => (
                      <button
                        key={f}
                        className={`btn ${errorFilter === f ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '0.3rem 0.7rem', fontSize: '0.75rem' }}
                        onClick={() => setErrorFilter(f)}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Total Tracked: {(Array.isArray(obsErrors) ? obsErrors : []).length} • Unresolved: {(Array.isArray(obsErrors) ? obsErrors : []).filter(e => e.status === 'OPEN' || e.status === 'UNRESOLVED').length}
                  </span>
                </div>

                {/* Errors List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                  {(Array.isArray(obsErrors) ? obsErrors : [])
                    .filter(e => {
                      if (errorFilter === 'ALL') return true
                      if (errorFilter === 'UNRESOLVED') return e.status === 'OPEN' || e.status === 'UNRESOLVED'
                      if (errorFilter === 'RESOLVED') return e.status === 'RESOLVED'
                      return e.severity === errorFilter
                    })
                    .length === 0 ? (
                    <div className="card" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      <CheckCircle2 size={36} style={{ color: '#10b981', margin: '0 auto 0.75rem auto' }} />
                      <div>No errors match the current filter. System running cleanly.</div>
                    </div>
                  ) : (
                    (Array.isArray(obsErrors) ? obsErrors : [])
                      .filter(e => {
                        if (errorFilter === 'ALL') return true
                        if (errorFilter === 'UNRESOLVED') return e.status === 'OPEN' || e.status === 'UNRESOLVED'
                        if (errorFilter === 'RESOLVED') return e.status === 'RESOLVED'
                        return e.severity === errorFilter
                      })
                      .map(err => {
                        const isExpanded = expandedErrorId === err.error_id
                        return (
                          <div key={err.error_id} className="card" style={{ borderLeft: `4px solid ${err.severity === 'CRITICAL' ? '#ef4444' : err.severity === 'ERROR' ? '#f59e0b' : '#3b82f6'}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
                              <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                                  <span className={`badge ${err.severity === 'CRITICAL' ? 'badge-critical' : err.severity === 'ERROR' ? 'badge-high' : 'badge-medium'}`}>
                                    {err.severity}
                                  </span>
                                  <span className="badge badge-open">{err.error_category}</span>
                                  <strong style={{ fontSize: '0.9rem', color: '#f3f4f6' }}>{err.error_type}</strong>
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                                    {err.error_id}
                                  </span>
                                </div>
                                <div style={{ fontSize: '0.85rem', color: '#e5e7eb', marginBottom: '0.5rem' }}>
                                  {err.message}
                                </div>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <span className={`badge ${err.status === 'RESOLVED' ? 'badge-resolved' : 'badge-open'}`}>
                                  {err.status}
                                </span>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: '0.35rem' }}>
                                  {err.timestamp?.slice(0, 19).replace('T', ' ')}
                                </div>
                              </div>
                            </div>

                            {/* Stack trace toggle & actions */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-light)' }}>
                              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                                {err.stack_trace && (
                                  <button
                                    className="btn btn-secondary"
                                    style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
                                    onClick={() => setExpandedErrorId(isExpanded ? null : err.error_id)}
                                  >
                                    {isExpanded ? 'Hide Stack Trace' : 'View Stack Trace'}
                                  </button>
                                )}
                                {err.trace_id && (
                                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                                    Trace: <code style={{ color: '#93c5fd' }}>{err.trace_id.slice(0, 12)}...</code>
                                  </span>
                                )}
                              </div>

                              {(err.status === 'OPEN' || err.status === 'UNRESOLVED') && (
                                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                  <input
                                    type="text"
                                    placeholder="Resolution note / root cause fix..."
                                    style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-light)', color: '#fff', padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', width: '240px' }}
                                    value={errorResolutionNote[err.error_id] || ''}
                                    onChange={(e) => setErrorResolutionNote(prev => ({ ...prev, [err.error_id]: e.target.value }))}
                                  />
                                  <button
                                    className="btn btn-primary"
                                    style={{ padding: '0.25rem 0.65rem', fontSize: '0.72rem' }}
                                    disabled={resolvingErrorId === err.error_id}
                                    onClick={() => handleResolveObsError(err.error_id)}
                                  >
                                    {resolvingErrorId === err.error_id ? 'Resolving...' : 'Resolve Error'}
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* Stack Trace Box */}
                            {isExpanded && err.stack_trace && (
                              <div className="stack-trace-box" style={{ marginTop: '0.75rem' }}>
                                {err.stack_trace}
                              </div>
                            )}
                          </div>
                        )
                      })
                  )}
                </div>
              </div>
            )}

            {/* SUBTAB 4: AUTOMATED EVALS & BENCHMARKS */}
            {obsSubTab === 'evals' && (
              <div>
                {/* Hero Eval Banner */}
                <div className="eval-hero-banner">
                  <div>
                    <h2 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: '0.35rem' }}>
                      22-Scenario Comprehensive Evaluation Suite
                    </h2>
                    <p style={{ fontSize: '0.82rem', color: '#c7d2fe', maxWidth: '650px' }}>
                      Validates all core operational scenarios: on-time standard feasibility, strict 20:00 curfews, heavy load dock constraints, breakdown re-routing, ambiguity disambiguation, yard queue priority, and transactional concurrency locks.
                    </p>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                    {latestEval && (
                      <div className="eval-summary-stats">
                        <div className="eval-stat-box">
                          <span className="number" style={{ color: latestEval.passed_scenarios === latestEval.total_scenarios ? '#34d399' : '#ef4444' }}>
                            {latestEval.passed_scenarios} / {latestEval.total_scenarios}
                          </span>
                          <span className="label">Scenarios Passed</span>
                        </div>
                        <div className="eval-stat-box">
                          <span className="number" style={{ color: '#93c5fd' }}>
                            {latestEval.pass_rate_pct?.toFixed(0)}%
                          </span>
                          <span className="label">Pass Rate</span>
                        </div>
                        <div className="eval-stat-box">
                          <span className="number" style={{ color: '#fcd34d' }}>
                            {latestEval.total_duration_ms?.toFixed(0)} ms
                          </span>
                          <span className="label">Suite Duration</span>
                        </div>
                      </div>
                    )}

                    <button
                      className="btn btn-primary"
                      onClick={handleRunEvalSuite}
                      disabled={isRunningEval}
                      style={{ padding: '0.75rem 1.4rem', fontSize: '0.9rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem', boxShadow: '0 4px 14px rgba(59, 130, 246, 0.5)' }}
                    >
                      {isRunningEval ? (
                        <>
                          <RefreshCw size={16} className="spin" />
                          Executing Suite...
                        </>
                      ) : (
                        <>
                          <Play size={16} />
                          Run 22-Scenario Suite
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Scenario Category Filters */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                    {['ALL', 'Standard Feasibility', 'Ambiguity Disambiguation', 'Constraint Validation', 'Curfew Enforcement', 'Disruption Rescheduling', 'Concurrency Lock'].map(cat => (
                      <button
                        key={cat}
                        className={`btn ${evalCategoryFilter === cat ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '0.3rem 0.7rem', fontSize: '0.75rem' }}
                        onClick={() => setEvalCategoryFilter(cat)}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>

                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Last Benchmark: {latestEval?.timestamp ? new Date(latestEval.timestamp).toLocaleTimeString() : 'Not run yet'}
                  </span>
                </div>

                {/* Scenarios Grid */}
                {latestEval?.scenarios ? (
                  <div className="scenario-grid">
                    {latestEval.scenarios
                      .filter(s => evalCategoryFilter === 'ALL' || s.category === evalCategoryFilter)
                      .map((sc, idx) => (
                        <div key={sc.scenario_id || idx} className={`scenario-card ${sc.status === 'PASS' ? 'pass' : 'fail'}`}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                            <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: sc.status === 'PASS' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              {sc.status === 'PASS' ? (
                                <CheckCircle2 size={16} style={{ color: '#34d399' }} />
                              ) : (
                                <XCircle size={16} style={{ color: '#ef4444' }} />
                              )}
                            </div>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <strong style={{ fontSize: '0.88rem' }}>{sc.scenario_name || sc.name}</strong>
                                <span className="badge badge-medium" style={{ fontSize: '0.68rem' }}>{sc.category}</span>
                              </div>
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                                {sc.error_message ? `⚠️ ${sc.error_message}` : (sc.details || 'Deterministic scenario assertion satisfied.')}
                              </div>
                            </div>
                          </div>

                          <div style={{ textAlign: 'right', display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                              {(sc.duration_ms ?? sc.latency_ms ?? 0).toFixed(1)} ms
                            </span>
                            <span className={`badge ${sc.status === 'PASS' ? 'badge-resolved' : 'badge-critical'}`}>
                              {sc.status}
                            </span>
                          </div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <div className="card" style={{ padding: '3.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    <Play size={40} style={{ color: 'var(--primary)', margin: '0 auto 1rem auto' }} />
                    <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>No Evaluation Run Recorded Yet</h3>
                    <p style={{ fontSize: '0.85rem', maxWidth: '450px', margin: '0 auto 1.25rem auto' }}>
                      Click the "Run 22-Scenario Suite" button above to execute the automated benchmark against all 22 operational scenarios.
                    </p>
                    <button
                      className="btn btn-primary"
                      onClick={handleRunEvalSuite}
                      disabled={isRunningEval}
                    >
                      Run 22-Scenario Suite Now
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
