// En local (servi par Flask sur 127.0.0.1), front et API sont sur le même host.
// En prod (Vercel), le front appelle l'API Render en cross-origin.
const API = ['localhost', '127.0.0.1'].includes(window.location.hostname)
  ? ''
  : 'https://musester.onrender.com'

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')
}

// ── Toasts ───────────────────────────────────────────────────────────────
function toast(msg, type = 'ok') {
  const stack = document.getElementById('toast-stack')
  const el = document.createElement('div')
  el.className = `toast ${type}`
  el.innerHTML = `<span class="t-dot"></span><span>${esc(msg)}</span>`
  stack.appendChild(el)
  setTimeout(() => el.remove(), 4200)
}

// ── Validation ───────────────────────────────────────────────────────────
function validateFields(fields) {
  let valid = true
  for (const { fieldId, value } of fields) {
    if (!value) { document.getElementById(fieldId).classList.add('error'); valid = false }
  }
  return valid
}
function clearError(fieldId) { document.getElementById(fieldId).classList.remove('error') }

// ── Auth ─────────────────────────────────────────────────────────────────
async function checkAuth() {
  const slowTimer = setTimeout(() => {
    const el = document.getElementById('loading-text')
    if (el) el.textContent = 'Le serveur se réveille, ça peut prendre jusqu\'à 50s…'
  }, 4000)
  try {
    const res  = await fetch(`${API}/auth/me`, { credentials: 'include' })
    const data = await res.json()
    if (res.ok && data.data?.user_id) setConnected(data.data.user_id)
    else setDisconnected()
  } catch { setDisconnected() }
  finally {
    clearTimeout(slowTimer)
    document.getElementById('view-loading').classList.add('hidden')
  }
}

function setConnected(userId) {
  document.getElementById('view-login').classList.add('hidden')
  document.getElementById('app').classList.remove('hidden')
  document.getElementById('account-label').textContent = userId
  renderTabs()
  renderActivePanel()
  updateGenHint()
  loadPlaylists()
  loadHistory()
}

function setDisconnected() {
  document.getElementById('app').classList.add('hidden')
  document.getElementById('view-login').classList.remove('hidden')
}

function login() { window.location.href = `${API}/auth/login` }

async function handleAccountTap() {
  if (!confirm('Se déconnecter de Musester ?')) return
  await fetch(`${API}/auth/logout`, { credentials: 'include' })
  setDisconnected()
}

// ── Screens (bottom nav) ────────────────────────────────────────────────
function switchScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.toggle('hidden', s.id !== `screen-${name}`))
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.screen === name))
  document.querySelector('.screens').scrollTo?.(0, 0)
  window.scrollTo(0, 0)
}

// ── SSE helper ───────────────────────────────────────────────────────────
function runSSE({ url, body, onStatus, onProgress, onPlaylistDone, onDone, onError }) {
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  }).then(async res => {
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      onError(data.error || `Erreur ${res.status}`)
      return
    }
    const reader  = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer    = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6))
          if (event.kind === 'status'        && onStatus)       onStatus(event.message)
          if (event.kind === 'progress'      && onProgress)     onProgress(event.done, event.total, event.phase)
          if (event.kind === 'playlist_done' && onPlaylistDone) onPlaylistDone(event)
          if (event.kind === 'done'          && onDone)         onDone(event)
        } catch {}
      }
    }
  }).catch(e => onError(e.message))
}

// ── Playlist tabs (Générer) ─────────────────────────────────────────────
let _playlistSlots   = [{ id: 0, name: '', prompt: '', anchors: new Map() }]
let _nextSlotId      = 1
let _activeTab       = 0
let _anchorTracks    = []
let _anchorLoadedFor = ''

function _activeSlot() { return _playlistSlots[_activeTab] }

function updateGenHint() {
  const hint   = document.getElementById('gen-hint')
  const source = document.getElementById('source-id').value.trim()
  const slot   = _activeSlot()
  const started = source || (slot && (slot.name.trim() || slot.prompt.trim())) || _playlistSlots.length > 1
  hint.classList.toggle('hidden', !!started)
}

function onSourceInput() {
  clearError('field-source')
  resetAnchors()
  updateGenHint()
}

function renderTabs() {
  const tabsEl = document.getElementById('playlist-tabs')
  tabsEl.innerHTML = ''
  _playlistSlots.forEach((slot, i) => {
    const label  = slot.name.trim() || `Playlist ${i + 1}`
    const active = i === _activeTab ? ' active' : ''
    const btn    = document.createElement('button')
    btn.className = `pl-tab${active}`
    btn.innerHTML = `<span>${esc(label)}</span>`
    if (_playlistSlots.length > 1) {
      const x = document.createElement('span')
      x.className = 'tab-close'
      x.textContent = '×'
      x.title = 'Supprimer'
      x.addEventListener('click', e => { e.stopPropagation(); removePlaylist(slot.id) })
      btn.appendChild(x)
    }
    btn.addEventListener('click', () => switchTab(i))
    tabsEl.appendChild(btn)
  })
  document.getElementById('btn-add-playlist').disabled = _playlistSlots.length >= 3
}

function renderActivePanel() {
  const slot  = _activeSlot()
  const panel = document.getElementById('playlist-panel')

  const anchorBody = _anchorTracks.length === 0
    ? `<span class="muted-note">Entre d'abord une playlist source pour charger les morceaux.</span>`
    : ''

  panel.innerHTML = `
    <div class="field" id="field-pl-name-${slot.id}">
      <label>Nom</label>
      <input type="text" id="pl-name-${slot.id}" placeholder="Chill Soir" oninput="onNameInput(${slot.id})" />
      <span class="field-error">Ce champ est requis</span>
    </div>
    <div class="field" id="field-pl-prompt-${slot.id}">
      <label>Prompt</label>
      <textarea id="pl-prompt-${slot.id}" rows="3"
        placeholder="Musiques calmes et introspectives pour la fin de soirée"
        oninput="onPromptInput(${slot.id})"></textarea>
      <span class="field-error">Ce champ est requis</span>
    </div>
    <div class="anchor-section field">
      <div class="anchor-head">
        <label>Ancres — morceaux de référence</label>
        <span class="anchor-count"><span class="n" id="anchor-count-num">0</span> sélectionné(s)</span>
      </div>
      <p class="helper-text">Choisis des morceaux qui correspondent <strong>exactement</strong> à ce que tu veux : GPT s'en sert d'étalon pour les cas limites. Recommandé : au moins 5.</p>
      <div id="anchor-recap" class="anchor-recap hidden"></div>
      <input type="text" id="anchor-search" placeholder="Rechercher un titre ou un artiste…" oninput="filterAnchorGrid(this.value)" />
      <div id="anchor-grid" class="anchor-grid">${anchorBody}</div>
    </div>`

  document.getElementById(`pl-name-${slot.id}`).value   = slot.name
  document.getElementById(`pl-prompt-${slot.id}`).value = slot.prompt

  if (_anchorTracks.length) {
    renderAnchorGrid(_anchorTracks)
    _renderRecap()
    _updateAnchorMeta()
  }
}

function onNameInput(slotId) {
  const slot = _playlistSlots.find(s => s.id === slotId)
  if (!slot) return
  slot.name = document.getElementById(`pl-name-${slotId}`).value
  clearError(`field-pl-name-${slotId}`)
  renderTabs()
  updateGenHint()
}

function onPromptInput(slotId) {
  const slot = _playlistSlots.find(s => s.id === slotId)
  if (!slot) return
  slot.prompt = document.getElementById(`pl-prompt-${slotId}`).value
  clearError(`field-pl-prompt-${slotId}`)
  updateGenHint()
}

function switchTab(tabIdx) {
  _activeTab = tabIdx
  renderTabs()
  renderActivePanel()
}

function addPlaylist() {
  if (_playlistSlots.length >= 3) return
  const id = _nextSlotId++
  _playlistSlots.push({ id, name: '', prompt: '', anchors: new Map() })
  _activeTab = _playlistSlots.length - 1
  renderTabs()
  renderActivePanel()
  updateGenHint()
}

function removePlaylist(slotId) {
  const idx = _playlistSlots.findIndex(s => s.id === slotId)
  if (idx === -1) return
  _playlistSlots.splice(idx, 1)
  _activeTab = Math.min(_activeTab, _playlistSlots.length - 1)
  renderTabs()
  renderActivePanel()
}

// ── Anchors ──────────────────────────────────────────────────────────────
function resetAnchors() {
  _anchorLoadedFor = ''
  _anchorTracks    = []
  _playlistSlots.forEach(s => s.anchors.clear())
  renderActivePanel()
}

async function onSourceBlur() {
  const source = document.getElementById('source-id').value.trim()
  if (!source || source === _anchorLoadedFor) return
  _anchorLoadedFor = source
  _playlistSlots.forEach(s => s.anchors.clear())

  const grid = document.getElementById('anchor-grid')
  if (grid) grid.innerHTML = '<span class="muted-note">Chargement des morceaux…</span>'

  try {
    const res  = await fetch(`${API}/source-tracks?source_id=${encodeURIComponent(source)}`, { credentials: 'include' })
    const data = await res.json()
    if (!res.ok || !data.data?.length) {
      if (grid) grid.innerHTML = '<span class="muted-note">Aucun morceau trouvé</span>'
      return
    }
    _anchorTracks = data.data
    renderAnchorGrid(_anchorTracks)
    _renderRecap()
    _updateAnchorMeta()
  } catch {
    const g = document.getElementById('anchor-grid')
    if (g) g.innerHTML = '<span class="muted-note">Erreur de chargement</span>'
  }
}

function renderAnchorGrid(tracks) {
  const slot      = _activeSlot()
  const selectedM = slot ? slot.anchors : new Map()
  const grid      = document.getElementById('anchor-grid')
  if (!grid) return
  grid.innerHTML = ''
  if (!tracks.length) {
    grid.innerHTML = '<span class="muted-note">Aucun résultat</span>'
    return
  }
  tracks.forEach(t => {
    const card = document.createElement('div')
    card.className = 'anchor-card' + (selectedM.has(t.id) ? ' selected' : '')
    card.id        = `ac-${t.id}`
    card.innerHTML = t.cover_url
      ? `<img src="${t.cover_url}" alt="" loading="lazy" />`
      : `<div class="ph"></div>`
    card.innerHTML += `<span class="ac-title" title="${esc(t.title)}">${esc(t.title)}</span>`
    card.innerHTML += `<span class="ac-artist" title="${esc(t.artists)}">${esc(t.artists)}</span>`
    card.addEventListener('click', () => toggleAnchor(t))
    grid.appendChild(card)
  })
}

function filterAnchorGrid(query) {
  const q = query.trim().toLowerCase()
  renderAnchorGrid(q
    ? _anchorTracks.filter(t => t.title.toLowerCase().includes(q) || t.artists.toLowerCase().includes(q))
    : _anchorTracks
  )
}

function toggleAnchor(t) {
  const slot = _activeSlot()
  if (!slot) return
  if (slot.anchors.has(t.id)) slot.anchors.delete(t.id)
  else slot.anchors.set(t.id, { id: t.id, title: t.title, artists: t.artists })
  const card = document.getElementById(`ac-${t.id}`)
  if (card) card.classList.toggle('selected', slot.anchors.has(t.id))
  _updateAnchorMeta()
  _renderRecap()
}

function _updateAnchorMeta() {
  const slot = _activeSlot()
  const n    = slot ? slot.anchors.size : 0
  const cnt  = document.getElementById('anchor-count-num')
  if (!cnt) return
  cnt.textContent = n
  cnt.className   = 'n' + (n > 0 && n < 5 ? ' warn' : '')
}

function _renderRecap() {
  const slot  = _activeSlot()
  const recap = document.getElementById('anchor-recap')
  if (!recap) return
  if (!slot || slot.anchors.size === 0) {
    recap.classList.add('hidden')
    recap.innerHTML = ''
    return
  }
  recap.classList.remove('hidden')
  recap.innerHTML = ''
  for (const t of slot.anchors.values()) {
    const chip = document.createElement('div')
    chip.className = 'anchor-chip'
    chip.title     = `${t.title} — ${t.artists}`
    const raw  = _anchorTracks.find(a => a.id === t.id)
    chip.innerHTML = raw?.cover_url
      ? `<img src="${raw.cover_url}" alt="" />`
      : `<div class="chip-placeholder"></div>`
    chip.innerHTML += `<span class="chip-name">${esc(t.title)}</span><span class="chip-x">×</span>`
    chip.addEventListener('click', () => toggleAnchor(t))
    recap.appendChild(chip)
  }
}

// ── Generate ─────────────────────────────────────────────────────────────
function generate() {
  const sourceId  = document.getElementById('source-id').value.trim()
  const multiPass = document.getElementById('toggle-multipass').checked

  let valid         = validateFields([{ fieldId: 'field-source', value: sourceId }])
  let firstErrorTab = -1

  const playlists = _playlistSlots.map((slot, i) => {
    if (!slot.name.trim() || !slot.prompt.trim()) {
      if (firstErrorTab === -1) firstErrorTab = i
      valid = false
    }
    return { name: slot.name.trim(), prompt: slot.prompt.trim(), anchors: Array.from(slot.anchors.values()) }
  })

  if (!valid) {
    if (firstErrorTab !== -1) {
      switchTab(firstErrorTab)
      const slot = _playlistSlots[firstErrorTab]
      if (!slot.name.trim())   document.getElementById(`field-pl-name-${slot.id}`)?.classList.add('error')
      if (!slot.prompt.trim()) document.getElementById(`field-pl-prompt-${slot.id}`)?.classList.add('error')
    }
    return
  }

  const btn        = document.getElementById('btn-generate')
  const loader     = document.getElementById('gen-loader')
  const progressEl = document.getElementById('gen-progress-bar')
  const statusEl   = document.getElementById('gen-status-line')
  const phaseEl    = document.getElementById('gen-phase-label')
  const resultEl   = document.getElementById('gen-result')

  resultEl.classList.add('hidden')
  resultEl.innerHTML = ''
  btn.disabled          = true
  btn.textContent       = 'En cours…'
  loader.classList.remove('hidden')
  progressEl.className  = 'progress-bar indeterminate'
  statusEl.textContent  = 'Connexion…'
  phaseEl.textContent   = ''

  runSSE({
    url:  `${API}/generate`,
    body: { source_id: sourceId, playlists, multi_pass: multiPass },

    onStatus: msg => { statusEl.textContent = msg },

    onProgress: (done, total, phase) => {
      progressEl.className   = 'progress-bar'
      progressEl.style.width = total > 0 ? Math.round((done / total) * 100) + '%' : '0%'
      if (phase === 1) phaseEl.textContent = 'Passe 1 — filtrage large'
      else if (phase === 2) phaseEl.textContent = 'Passe 2 — sélection fine'
      else phaseEl.textContent = ''
    },

    onDone: data => {
      loader.classList.add('hidden')
      btn.disabled    = false
      btn.textContent = 'Générer'
      const results = data.results || []
      resultEl.innerHTML = results.map(r =>
        `<div class="result-row"><span class="rn">IA-${esc(r.playlist_name)}</span><span class="rc mono">${r.selected_songs}/${r.checked_songs}</span></div>`
      ).join('')
      resultEl.classList.remove('hidden')
      toast(`${results.length > 1 ? results.length + ' playlists créées' : 'Playlist créée'} ✓`, 'ok')
      loadPlaylists()
      loadHistory()
    },

    onError: err => {
      progressEl.className = 'progress-bar'
      loader.classList.add('hidden')
      btn.disabled          = false
      btn.textContent       = 'Générer'
      toast(err, 'err')
    },
  })
}

// ── Sync accordion & picker ─────────────────────────────────────────────
function toggleSyncAccordion() {
  const acc = document.getElementById('sync-accordion')
  acc.classList.toggle('open')
}

let _syncPlaylists   = []
let _syncSelectedIds = null
let _syncPickerOpen  = false

async function ensureSyncPlaylists() {
  if (_syncPlaylists.length) return
  try {
    const res  = await fetch(`${API}/playlists`, { credentials: 'include' })
    const data = await res.json()
    _syncPlaylists = (data.data || []).map(p => ({ id: p.id, name: p.name }))
  } catch { _syncPlaylists = [] }
}

async function toggleSyncPicker() {
  _syncPickerOpen = !_syncPickerOpen
  const listEl = document.getElementById('sync-picker-list')
  const btnEl  = document.getElementById('btn-sync-picker')
  if (_syncPickerOpen) {
    listEl.classList.remove('hidden')
    btnEl.textContent = 'Masquer'
    await ensureSyncPlaylists()
    renderSyncPickerItems()
  } else {
    listEl.classList.add('hidden')
    btnEl.textContent = 'Choisir'
  }
}

function renderSyncPickerItems() {
  const container = document.getElementById('sync-playlist-items')
  if (!_syncPlaylists.length) {
    container.innerHTML = '<span class="muted-note">Aucune playlist IA- trouvée</span>'
    return
  }
  container.innerHTML = ''
  _syncPlaylists.forEach(p => {
    const checked = _syncSelectedIds === null || _syncSelectedIds.has(p.id)
    const item = document.createElement('div')
    item.className = 'sync-pl-item'
    const cb = document.createElement('input')
    cb.type    = 'checkbox'
    cb.id      = `sp-${p.id}`
    cb.checked = checked
    cb.addEventListener('change', () => toggleSyncPlaylist(p.id, cb.checked))
    const lbl = document.createElement('label')
    lbl.htmlFor     = `sp-${p.id}`
    lbl.textContent = p.name
    item.append(cb, lbl)
    item.addEventListener('click', e => { if (e.target !== cb) cb.click() })
    container.appendChild(item)
  })
  updateSyncTargetInfo()
}

function toggleSyncPlaylist(id, checked) {
  if (_syncSelectedIds === null) _syncSelectedIds = new Set(_syncPlaylists.map(p => p.id))
  if (checked) _syncSelectedIds.add(id)
  else _syncSelectedIds.delete(id)
  if (_syncSelectedIds.size === _syncPlaylists.length) _syncSelectedIds = null
  updateSyncTargetInfo()
}

function syncSelectAll(check) {
  _syncSelectedIds = check ? null : new Set()
  renderSyncPickerItems()
}

function updateSyncTargetInfo() {
  const el = document.getElementById('sync-target-info')
  if (!el) return
  if (_syncSelectedIds === null) {
    el.innerHTML = 'Cibles : <strong>toutes</strong>'
  } else {
    const n = _syncSelectedIds.size
    el.innerHTML = `Cibles : <strong>${n} sélectionnée${n > 1 ? 's' : ''}</strong>`
  }
}

// ── Sync ─────────────────────────────────────────────────────────────────
function sync() {
  const sourceId    = document.getElementById('sync-source-id').value.trim()
  const destructive = document.getElementById('toggle-destructive').checked
  if (!validateFields([{ fieldId: 'field-sync-source', value: sourceId }])) return

  if (_syncSelectedIds !== null && _syncSelectedIds.size === 0) {
    toast('Aucune playlist sélectionnée pour le sync', 'err')
    return
  }

  const btn        = document.getElementById('btn-sync')
  const loader     = document.getElementById('sync-loader')
  const progressEl = document.getElementById('sync-progress-bar')
  const statusEl   = document.getElementById('sync-status-line')

  btn.disabled          = true
  btn.textContent       = 'En cours…'
  loader.classList.remove('hidden')
  progressEl.className  = 'progress-bar indeterminate'
  statusEl.textContent  = 'Connexion…'

  runSSE({
    url:  `${API}/sync`,
    body: {
      source_id:           sourceId,
      destructive,
      target_playlist_ids: _syncSelectedIds !== null ? Array.from(_syncSelectedIds) : null,
    },
    onStatus: msg => { statusEl.textContent = msg },
    onProgress: (done, total) => {
      progressEl.className   = 'progress-bar'
      progressEl.style.width = total > 0 ? Math.round((done / total) * 100) + '%' : '0%'
    },
    onDone: data => {
      loader.classList.add('hidden')
      btn.disabled    = false
      btn.textContent = 'Synchroniser'
      const results = data.results || {}
      let added = 0, removed = 0
      for (const v of Object.values(results)) { added += v.added||0; removed += v.removed||0 }
      toast(`Sync terminée — +${added} / -${removed} morceaux`, 'ok')
      loadPlaylists()
      loadHistory()
    },
    onError: err => {
      progressEl.className = 'progress-bar'
      loader.classList.add('hidden')
      btn.disabled          = false
      btn.textContent       = 'Synchroniser'
      toast(err, 'err')
    },
  })
}

// ── Playlists (Accueil) ──────────────────────────────────────────────────
async function loadPlaylists() {
  const container = document.getElementById('playlist-list')
  try {
    const res  = await fetch(`${API}/playlists`, { credentials: 'include' })
    const data = await res.json()
    if (!res.ok || !data.data?.length) {
      container.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
          <span>Tu n'as pas encore de playlist.<br/>Va dans <strong style="color:var(--text)">Générer</strong> pour créer la première.</span>
        </div>`
      return
    }
    container.innerHTML = ''
    data.data.forEach(p => {
      const el = document.createElement('div')
      el.className = 'playlist-item clickable'
      el.innerHTML = `
        <div class="pi-row">
          <span class="pi-name">${esc(p.name)}</span>
          <button class="icon-btn" title="Modifier le prompt">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
          </button>
        </div>
        <p class="pi-prompt" id="pi-prompt-${p.id}">${esc(p.prompt) || '—'}</p>
        <div class="pi-meta">
          <span class="mono">${p.track_count} morceaux</span>
          <span>sync ${p.last_sync ? formatDate(p.last_sync) : 'jamais'}</span>
        </div>
        <div class="pi-edit" id="pi-edit-${p.id}">
          <div class="field" id="pi-field-${p.id}">
            <label>Nouveau prompt</label>
            <textarea rows="2" id="pi-input-${p.id}">${esc(p.prompt || '')}</textarea>
            <span class="field-error">Le prompt ne peut pas être vide</span>
          </div>
          <div class="btn-row">
            <button class="btn btn-primary btn-inline" data-action="save">Sauvegarder</button>
            <button class="btn btn-secondary btn-inline" data-action="cancel">Annuler</button>
          </div>
        </div>`
      el.querySelector('.icon-btn').addEventListener('click', e => { e.stopPropagation(); toggleEditPrompt(p.id) })
      el.querySelector('[data-action="save"]').addEventListener('click', e => { e.stopPropagation(); savePrompt(p.id) })
      el.querySelector('[data-action="cancel"]').addEventListener('click', e => { e.stopPropagation(); toggleEditPrompt(p.id) })
      el.querySelector('.pi-edit').addEventListener('click', e => e.stopPropagation())
      el.addEventListener('click', () => openAnchors(p.id, p.name, p.prompt))
      container.appendChild(el)
    })
  } catch {
    container.innerHTML = '<span class="muted-note">Erreur de chargement</span>'
  }
}

function toggleEditPrompt(id) {
  document.getElementById(`pi-edit-${id}`).classList.toggle('open')
  document.getElementById(`pi-field-${id}`).classList.remove('error')
}

async function savePrompt(id) {
  const prompt = document.getElementById(`pi-input-${id}`).value.trim()
  if (!prompt) { document.getElementById(`pi-field-${id}`).classList.add('error'); return }
  try {
    const res = await fetch(`${API}/playlists/${id}/prompt`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ prompt }),
    })
    if (res.ok) {
      document.getElementById(`pi-prompt-${id}`).textContent = prompt
      toggleEditPrompt(id)
      toast('Prompt mis à jour', 'ok')
    } else { toast('Erreur lors de la mise à jour du prompt', 'err') }
  } catch (e) { toast(e.message, 'err') }
}

// ── History ──────────────────────────────────────────────────────────────
let _allHistory      = []
let _historyLimit    = 10
const HISTORY_LIMITS = [10, 20, 40, null] // null = tout

async function loadHistory() {
  try {
    const res  = await fetch(`${API}/history`, { credentials: 'include' })
    const data = await res.json()
    _allHistory = (res.ok && data.data?.length) ? data.data : []
  } catch {
    _allHistory = []
  }
  renderHistory()
}

const ICON_GENERATE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v16M4 12h16"/></svg>'
const ICON_SYNC      = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 4v5h-5" /></svg>'

function renderHistory() {
  const container = document.getElementById('history-list')
  const bar       = document.getElementById('history-limit-bar')

  if (_allHistory.length > 10) {
    bar.innerHTML = HISTORY_LIMITS.map(n => {
      const label  = n === null ? 'Tout' : n
      const active = n === _historyLimit ? ' active' : ''
      return `<button class="limit-btn${active}" onclick="setHistoryLimit(${n})">${label}</button>`
    }).join('')
  } else {
    bar.innerHTML = ''
  }

  if (!_allHistory.length) {
    container.innerHTML = `
      <div class="empty-state">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
        <span>Aucune activité pour l'instant.<br/>Génère ta première playlist pour la voir ici.</span>
      </div>`
    return
  }

  const items = _historyLimit === null ? _allHistory : _allHistory.slice(0, _historyLimit)
  container.innerHTML = ''
  items.forEach(h => {
    const isGen  = h.action === 'generate'
    const name   = h.playlist_name || h.playlist_id || '—'
    const count  = isGen ? `${h.selected_songs}/${h.checked_songs}` : `+${h.selected_songs||0} / -${h.removed_songs||0}`
    const detail = isGen ? (h.prompt || '') : `sync — ${h.checked_songs||0} vérifiés`

    const el = document.createElement('div')
    el.className = 'history-item' + (isGen ? ' clickable' : '')
    el.innerHTML = `
      <span class="hi-badge ${h.action}">${isGen ? ICON_GENERATE : ICON_SYNC}</span>
      <div class="hi-body">
        <div class="hi-top">
          <span class="hi-name">${isGen ? 'IA-' : ''}${esc(name)}</span>
          <span class="hi-count mono">${count}</span>
        </div>
        <p class="hi-detail">${esc(detail)}</p>
        <p class="hi-date">${formatDate(h.created_at)}</p>
      </div>`
    if (isGen) el.addEventListener('click', () => openDecisions(h.id, `IA-${name}`, detail))
    container.appendChild(el)
  })
}

function setHistoryLimit(n) {
  _historyLimit = n
  renderHistory()
}

// ── Bottom sheet (decisions & anchors) ──────────────────────────────────
const ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
const ICON_X     = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>'

let _sheetMode  = 'decisions' // 'decisions' | 'anchors'
let _sheetItems = []
const _decisionsCache = new Map() // history_id -> decisions[]
const _anchorsCache   = new Map() // playlist_id -> { anchors, source_id }

function openSheet(title, subtitle) {
  document.getElementById('decisions-title').textContent = title
  document.getElementById('decisions-subtitle').textContent = subtitle || ''
  document.getElementById('decisions-search').value = ''
  document.getElementById('decisions-overlay').classList.add('open')
  document.querySelector('.screens')?.classList.add('locked')
}

function closeSheet() {
  document.getElementById('decisions-overlay').classList.remove('open')
  document.querySelector('.screens')?.classList.remove('locked')
}

async function openDecisions(historyId, title, subtitle) {
  _sheetMode = 'decisions'
  openSheet(title, subtitle)
  const body = document.getElementById('decisions-body')

  if (_decisionsCache.has(historyId)) {
    _sheetItems = _decisionsCache.get(historyId)
    renderSheetBody(_sheetItems)
    return
  }
  body.innerHTML = '<span class="muted-note">Chargement…</span>'
  try {
    const res  = await fetch(`${API}/history/${historyId}/decisions`, { credentials: 'include' })
    const data = await res.json()
    if (!res.ok || !data.data?.length) {
      _sheetItems = []
      body.innerHTML = '<div class="empty-state"><span>Aucun détail enregistré pour cette génération.</span></div>'
      return
    }
    _sheetItems = data.data
    _decisionsCache.set(historyId, _sheetItems)
    renderSheetBody(_sheetItems)
  } catch {
    body.innerHTML = '<div class="empty-state"><span>Erreur de chargement</span></div>'
  }
}

async function openAnchors(playlistId, name, prompt) {
  _sheetMode = 'anchors'
  openSheet(name, prompt || '')
  const body = document.getElementById('decisions-body')

  const fill = ({ anchors, source_id }) => {
    _sheetItems = anchors || []
    const label = source_id === 'liked' ? 'Titres likés' : (source_id ? 'Playlist source' : null)
    document.getElementById('decisions-subtitle').textContent = [prompt, label].filter(Boolean).join(' · ')
    renderSheetBody(_sheetItems)
  }

  if (_anchorsCache.has(playlistId)) { fill(_anchorsCache.get(playlistId)); return }
  body.innerHTML = '<span class="muted-note">Chargement…</span>'
  try {
    const res  = await fetch(`${API}/playlists/${playlistId}/anchors`, { credentials: 'include' })
    const data = await res.json()
    if (!res.ok) { body.innerHTML = '<div class="empty-state"><span>Erreur de chargement</span></div>'; return }
    _anchorsCache.set(playlistId, data.data)
    fill(data.data)
  } catch {
    body.innerHTML = '<div class="empty-state"><span>Erreur de chargement</span></div>'
  }
}

function renderSheetBody(list) {
  const body = document.getElementById('decisions-body')
  if (!list.length) {
    body.innerHTML = _sheetMode === 'anchors'
      ? '<div class="empty-state"><span>Aucune ancre n\'a été utilisée pour cette playlist.</span></div>'
      : '<div class="empty-state"><span>Aucun résultat</span></div>'
    return
  }
  body.innerHTML = _sheetMode === 'anchors'
    ? list.map(t => `
        <div class="decision-row">
          <div class="d-body">
            <div class="d-title">${esc(t.title)}</div>
            <div class="d-reason">${esc(t.artists || '')}</div>
          </div>
        </div>`).join('')
    : list.map(d => `
        <div class="decision-row ${d.include ? 'include' : 'exclude'}">
          <span class="d-mark">${d.include ? ICON_CHECK : ICON_X}</span>
          <div class="d-body">
            <div class="d-title">${esc(d.title)}</div>
            <div class="d-reason">${esc(d.reason || '')}</div>
          </div>
        </div>`).join('')
}

function filterSheet(query) {
  const q = query.trim().toLowerCase()
  renderSheetBody(q ? _sheetItems.filter(d => d.title.toLowerCase().includes(q)) : _sheetItems)
}

// Drag-to-dismiss (grab handle or header)
;(function setupSheetDrag() {
  const sheet = document.querySelector('.sheet')
  const grips = document.querySelectorAll('.sheet-handle, .sheet-head')
  if (!sheet || !grips.length) return
  let startY = 0, dy = 0, dragging = false

  grips.forEach(grip => {
    grip.addEventListener('touchstart', e => {
      dragging = true; startY = e.touches[0].clientY; dy = 0
      sheet.style.transition = 'none'
    }, { passive: true })

    grip.addEventListener('touchmove', e => {
      if (!dragging) return
      dy = Math.max(0, e.touches[0].clientY - startY)
      sheet.style.transform = `translate(-50%, ${dy}px)`
    }, { passive: true })

    grip.addEventListener('touchend', () => {
      dragging = false
      sheet.style.transition = ''
      sheet.style.transform = ''
      if (dy > 90) closeSheet()
    })
  })
})()

// ── Helpers ──────────────────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return '—'
  const d   = new Date(iso)
  const now = new Date()
  const time = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  const sameDay = d.toDateString() === now.toDateString()
  const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1)
  if (sameDay) return `Aujourd'hui ${time}`
  if (d.toDateString() === yesterday.toDateString()) return `Hier ${time}`
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' }) + ` ${time}`
}

const params = new URLSearchParams(window.location.search)
if (params.get('error')) {
  const err = params.get('error')
  toast(err === 'unauthorized'
    ? 'Accès refusé — ton compte Spotify n\'est pas autorisé à utiliser cette application.'
    : `Erreur Spotify : ${err}`, 'err')
  history.replaceState({}, '', '/')
}

checkAuth()
