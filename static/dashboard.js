// Dashboard Controller
document.addEventListener('DOMContentLoaded', () => {
    // Current state caching
    let state = {
        totalRecords: 0,
        activePlayers: 0,
        flaggedCount: 0,
        lobbyCount: 0,
        leaderboardType: 'global', // 'global' or 'regional'
        globalLeaderboard: [],
        regionalLeaderboard: [],
        flaggedPlayers: [],
        lobbies: []
    };

    // DOM Elements
    const tabBtns = document.querySelectorAll('.nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');
    
    // KPI elements
    const kpiRecords = document.getElementById('kpi-total-records');
    const kpiPlayers = document.getElementById('kpi-active-players');
    const kpiFlagged = document.getElementById('kpi-flagged-players');
    const kpiLobbies = document.getElementById('kpi-match-lobbies');
    
    // Sidebar Status
    const statusMatches = document.getElementById('status-matches');
    const statusPlayers = document.getElementById('status-players');

    // Tables & Lists
    const lbBody = document.getElementById('leaderboard-body');
    const lbSearch = document.getElementById('lb-search');
    const btnGlobalLb = document.getElementById('btn-global-lb');
    const btnRegionalLb = document.getElementById('btn-regional-lb');
    
    const suspiciousBody = document.getElementById('suspicious-body');
    const lobbyContainer = document.getElementById('lobby-cards-container');
    const mmRegionSelect = document.getElementById('mm-region-select');

    // Form elements
    const formSubmitScore = document.getElementById('form-submit-score');
    const resultCard = document.getElementById('submission-result-card');
    const feedbackIcon = document.getElementById('feedback-icon-wrapper');
    const feedbackTitle = document.getElementById('feedback-title');
    const feedbackText = document.getElementById('feedback-text');
    const feedbackDetails = document.getElementById('feedback-details');

    // Reset button
    const btnResetData = document.getElementById('btn-reset-data');

    // Upload element
    const csvFileInput = document.getElementById('csv-file-input');
    const uploadDragZone = document.getElementById('upload-drag-zone');

    // ==========================================
    // 1. TAB MANAGEMENT
    // ==========================================
    const tabMetadata = {
        overview: { title: "Operations Overview", subtitle: "Real-time telemetry and game management control room" },
        leaderboard: { title: "Fair Leaderboards", subtitle: "Global and regional player rankings (verified clean entries only)" },
        suspicious: { title: "Security Console", subtitle: "Anti-cheat telemetry, rule logs, and automated flagging" },
        matchmaking: { title: "Match Lobbies", subtitle: "Suggested groups balanced by latency, ping, and skill tiers" },
        submit: { title: "Submit Match Score", subtitle: "Insert game match events directly into the processing pipeline" },
        scaling: { title: "Scaling Architecture", subtitle: "Technical documentation for production scaling and monitoring" }
    };

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.getAttribute('data-tab');
            
            // Switch tabs active button
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Switch panes
            tabPanes.forEach(pane => pane.classList.remove('active'));
            document.getElementById(`tab-${tabId}`).classList.add('active');

            // Update Titles
            const meta = tabMetadata[tabId];
            if (meta) {
                pageTitle.textContent = meta.title;
                pageSubtitle.textContent = meta.subtitle;
            }

            // Perform specific tab data refreshes
            if (tabId === 'leaderboard') refreshLeaderboardData();
            if (tabId === 'suspicious') refreshSecurityData();
            if (tabId === 'matchmaking') refreshMatchmakingData();
        });
    });

    // ==========================================
    // 2. NETWORK OPERATIONS (API REQUESTS)
    // ==========================================
    async function apiRequest(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, options);
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'API request failed');
            }
            return await response.json();
        } catch (error) {
            console.error(`Error requesting ${endpoint}:`, error);
            showNotification(error.message, 'danger');
            return null;
        }
    }

    // Refresh KPI metrics
    async function updateSystemStatus() {
        const data = await apiRequest('/api/status');
        if (data) {
            animateValue(kpiRecords, state.totalRecords, data.total_records, 800);
            animateValue(kpiPlayers, state.activePlayers, data.unique_players, 800);
            
            state.totalRecords = data.total_records;
            state.activePlayers = data.unique_players;

            statusMatches.textContent = data.total_records.toLocaleString();
            statusPlayers.textContent = data.unique_players.toLocaleString();
            
            // Trigger other endpoints to get flagged count and lobby count
            const flagged = await apiRequest('/api/flagged-players');
            if (flagged) {
                animateValue(kpiFlagged, state.flaggedCount, flagged.length, 800);
                state.flaggedCount = flagged.length;
            }

            const mm = await apiRequest('/api/matchmaking');
            if (mm) {
                animateValue(kpiLobbies, state.lobbyCount, mm.length, 800);
                state.lobbyCount = mm.length;
            }
        }
    }

    // Leaderboards
    async function refreshLeaderboardData() {
        const data = await apiRequest('/api/leaderboard');
        if (data) {
            state.globalLeaderboard = data.global;
            state.regionalLeaderboard = data.regional;
            renderLeaderboard();
        }
    }

    // Security
    async function refreshSecurityData() {
        const data = await apiRequest('/api/flagged-players');
        if (data) {
            state.flaggedPlayers = data;
            renderSecurityConsole();
        }
    }

    // Matchmaking
    async function refreshMatchmakingData() {
        const data = await apiRequest('/api/matchmaking');
        if (data) {
            state.lobbies = data;
            populateRegionFilter();
            renderMatchmaking();
        }
    }

    // ==========================================
    // 3. UI RENDERING ENGINES
    // ==========================================
    
    // Render Leaderboard Table
    function renderLeaderboard() {
        const list = state.leaderboardType === 'global' ? state.globalLeaderboard : state.regionalLeaderboard;
        const query = lbSearch.value.toLowerCase().trim();
        
        lbBody.innerHTML = '';
        
        const filteredList = list.filter(item => 
            item.player_id.toLowerCase().includes(query)
        );

        if (filteredList.length === 0) {
            lbBody.innerHTML = `<tr><td colspan="9" class="text-center" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching players found.</td></tr>`;
            return;
        }

        filteredList.forEach(p => {
            const tr = document.createElement('tr');
            
            // Rank column logic
            let rankDisp = '-';
            if (p.rank !== null && p.rank !== undefined) {
                rankDisp = p.rank;
            }
            
            // Status column badge
            let badgeClass = 'badge-success';
            let badgeText = 'Clean';
            if (p.status === 'under_review') {
                badgeClass = 'badge-danger';
                badgeText = 'Under Review';
                tr.style.opacity = '0.65';
                tr.style.backgroundColor = 'rgba(239, 68, 68, 0.02)';
            }

            tr.innerHTML = `
                <td><strong>${rankDisp}</strong></td>
                <td><span style="font-family: var(--font-heading); font-weight:600;">${p.player_id}</span></td>
                <td>${p.primary_region}</td>
                <td>${p.matches_played}</td>
                <td>${p.total_score.toLocaleString()}</td>
                <td>${p.total_kills}</td>
                <td>${p.total_deaths}</td>
                <td>${p.avg_score_per_match.toFixed(1)}</td>
                <td><span class="badge ${badgeClass}">${badgeText}</span></td>
            `;
            lbBody.appendChild(tr);
        });
    }

    // Render Security Logs Table
    function renderSecurityConsole() {
        suspiciousBody.innerHTML = '';
        if (state.flaggedPlayers.length === 0) {
            suspiciousBody.innerHTML = `<tr><td colspan="5" class="text-center" style="text-align: center; color: var(--text-muted); padding: 2rem;">All clear. No suspicious profiles detected.</td></tr>`;
            return;
        }

        state.flaggedPlayers.forEach(p => {
            const tr = document.createElement('tr');
            
            let badgeClass = 'badge-warning';
            if (p.severity === 'High') badgeClass = 'badge-danger';
            if (p.severity === 'Low') badgeClass = 'badge-info';

            // Split reasons by semicolon and make them look like tags
            const reasonsHtml = p.flag_reasons.split(';').map(reason => 
                `<span class="player-token" style="margin: 0.15rem; display: inline-block;">${reason.trim()}</span>`
            ).join('');

            tr.innerHTML = `
                <td><strong style="font-family: var(--font-heading); font-size:1rem;">${p.player_id}</strong></td>
                <td><span class="badge ${badgeClass}">${p.severity}</span></td>
                <td>${p.flagged_matches_count}</td>
                <td>${p.total_matches_count}</td>
                <td><div style="max-width: 450px; display: flex; flex-wrap: wrap;">${reasonsHtml}</div></td>
            `;
            suspiciousBody.appendChild(tr);
        });
    }

    // Populate Region Filter dropdown for Matchmaking
    function populateRegionFilter() {
        const regions = new Set();
        state.lobbies.forEach(lobby => {
            if (lobby.region && lobby.region !== 'Global') {
                regions.add(lobby.region);
            }
        });

        // Clear existing, keep "All" option
        mmRegionSelect.innerHTML = '<option value="All">All Regions</option>';
        regions.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r;
            opt.textContent = r;
            mmRegionSelect.appendChild(opt);
        });
    }

    // Render Matchmaking Lobbies as Cards
    function renderMatchmaking() {
        lobbyContainer.innerHTML = '';
        const regionFilter = mmRegionSelect.value;
        
        const filteredLobbies = state.lobbies.filter(lobby => 
            regionFilter === 'All' || lobby.region === regionFilter
        );

        if (filteredLobbies.length === 0) {
            lobbyContainer.innerHTML = `<div class="card glass" style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">No lobbies formed for selected filter.</div>`;
            return;
        }

        filteredLobbies.forEach(lobby => {
            const card = document.createElement('div');
            card.className = 'lobby-card glass';
            
            // Status Tag
            let statusBadge = '';
            if (lobby.status === 'Ready') {
                statusBadge = '<span class="badge badge-success">Ready</span>';
                card.style.borderLeft = '4px solid var(--color-success)';
            } else if (lobby.status === 'Waiting') {
                statusBadge = '<span class="badge badge-warning">Waiting</span>';
                card.style.borderLeft = '4px solid var(--color-warning)';
            } else {
                statusBadge = '<span class="badge badge-danger">Isolated</span>';
                card.style.borderLeft = '4px solid var(--color-danger)';
            }

            // Split player IDs
            const players = lobby.player_ids.split(', ');
            const playersHtml = players.map(p => {
                const isFlaggedLow = p.includes('(Flagged: Low)');
                const tokenClass = isFlaggedLow ? 'player-token flagged-low' : 'player-token';
                return `<span class="${tokenClass}">${p}</span>`;
            }).join('');

            card.innerHTML = `
                <div class="lobby-header">
                    <span class="lobby-title">${lobby.lobby_name}</span>
                    ${statusBadge}
                </div>
                <div class="lobby-stats">
                    <span>Region: <strong>${lobby.region}</strong></span>
                    <span>Ping: <strong>${lobby.ping_band}</strong></span>
                </div>
                <div class="lobby-stats">
                    <span>Tier: <strong>${lobby.skill_tier}</strong></span>
                    <span>Players: <strong>${lobby.player_count}</strong></span>
                </div>
                <div class="lobby-players-label">Roster</div>
                <div class="lobby-players-list">
                    ${playersHtml}
                </div>
            `;
            lobbyContainer.appendChild(card);
        });
    }

    // ==========================================
    // 4. INTERACTION LISTENERS & ACTIONS
    // ==========================================

    // Leaderboard Toggle button listeners
    btnGlobalLb.addEventListener('click', () => {
        btnGlobalLb.classList.add('btn-active');
        btnRegionalLb.classList.remove('btn-active');
        state.leaderboardType = 'global';
        renderLeaderboard();
    });

    btnRegionalLb.addEventListener('click', () => {
        btnRegionalLb.classList.add('btn-active');
        btnGlobalLb.classList.remove('btn-active');
        state.leaderboardType = 'regional';
        renderLeaderboard();
    });

    lbSearch.addEventListener('keyup', renderLeaderboard);
    mmRegionSelect.addEventListener('change', renderMatchmaking);

    // Reset default dataset action
    btnResetData.addEventListener('click', async () => {
        btnResetData.disabled = true;
        btnResetData.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Resetting...`;
        
        const data = await apiRequest('/api/reset', { method: 'POST' });
        if (data) {
            showNotification(data.message, 'success');
            await updateSystemStatus();
            
            // Reload whatever tab is active
            const activeTab = document.querySelector('.nav-btn.active').getAttribute('data-tab');
            if (activeTab === 'leaderboard') refreshLeaderboardData();
            if (activeTab === 'suspicious') refreshSecurityData();
            if (activeTab === 'matchmaking') refreshMatchmakingData();
        }
        
        btnResetData.disabled = false;
        btnResetData.innerHTML = `<i class="fa-solid fa-arrows-rotate"></i> Reset Defaults`;
    });

    // Score Event Submission
    formSubmitScore.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const payload = {
            player_id: document.getElementById('score-player-id').value,
            match_id: document.getElementById('score-match-id').value,
            region: document.getElementById('score-region').value,
            device: document.getElementById('score-device').value,
            ping: parseInt(document.getElementById('score-ping').value),
            score: parseFloat(document.getElementById('score-score').value),
            kills: parseInt(document.getElementById('score-kills').value),
            deaths: parseInt(document.getElementById('score-deaths').value),
            match_duration_seconds: parseInt(document.getElementById('score-duration').value)
        };

        const res = await apiRequest('/api/submit-score', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res) {
            // Display Evaluation Results Card
            resultCard.style.display = 'block';
            
            if (res.status === 'flagged') {
                feedbackIcon.className = 'feedback-icon-wrapper danger';
                feedbackIcon.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i>`;
                feedbackTitle.textContent = `Flagged: ${res.severity} Severity`;
                feedbackText.textContent = `Score event for player ${res.player_id} triggered automated anti-cheat filters.`;
                
                // Show triggered reasons
                const reasonsList = res.reasons.map(r => `<li>${r}</li>`).join('');
                feedbackDetails.innerHTML = `
                    <div style="font-weight:700; margin-bottom:0.25rem;">Security Alerts Raised:</div>
                    <ul style="padding-left:1.25rem;">${reasonsList}</ul>
                    <div style="margin-top:0.5rem; font-size:0.75rem; color:var(--text-muted);">Account state shifted to: UNDER REVIEW</div>
                `;
            } else {
                feedbackIcon.className = 'feedback-icon-wrapper success';
                feedbackIcon.innerHTML = `<i class="fa-solid fa-circle-check"></i>`;
                feedbackTitle.textContent = "Telemetry Verified";
                feedbackText.textContent = `Match recorded successfully. Player ${res.player_id} is clear.`;
                feedbackDetails.innerHTML = `
                    <div style="font-weight:700; margin-bottom:0.25rem;">Telemetry Metrics:</div>
                    <div>Score/Sec: ${(payload.score / payload.match_duration_seconds).toFixed(2)}</div>
                    <div>K/D Ratio: ${(payload.kills / Math.max(payload.deaths, 1)).toFixed(2)}</div>
                    <div style="margin-top:0.5rem; font-size:0.75rem; color:var(--text-muted);">Lobby balance verified.</div>
                `;
            }

            // Reset form inputs except player/match series incrementing convenience
            formSubmitScore.reset();
            
            // Reload status dashboard
            await updateSystemStatus();
        }
    });

    // ==========================================
    // 5. CSV UPLOAD MECHANICS
    // ==========================================
    
    // File input change
    csvFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleCSVUpload(file);
    });

    // Drag and Drop listeners
    uploadDragZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadDragZone.style.borderColor = 'var(--primary)';
        uploadDragZone.style.backgroundColor = 'rgba(111, 76, 255, 0.04)';
    });

    uploadDragZone.addEventListener('dragleave', () => {
        uploadDragZone.style.borderColor = 'var(--border-color)';
        uploadDragZone.style.backgroundColor = 'rgba(255, 255, 255, 0.01)';
    });

    uploadDragZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadDragZone.style.borderColor = 'var(--border-color)';
        uploadDragZone.style.backgroundColor = 'rgba(255, 255, 255, 0.01)';
        
        const file = e.dataTransfer.files[0];
        if (file) {
            if (file.name.endsWith('.csv')) {
                handleCSVUpload(file);
            } else {
                showNotification("Invalid file format. Please upload a CSV file.", "danger");
            }
        }
    });

    // Zone click triggering input
    uploadDragZone.addEventListener('click', () => {
        csvFileInput.click();
    });

    async function handleCSVUpload(file) {
        const formData = new FormData();
        formData.append('file', file);

        uploadDragZone.innerHTML = `
            <i class="fa-solid fa-spinner fa-spin upload-icon"></i>
            <h4>Processing Telemetry...</h4>
            <p>Parsing dataset, applying sanitization, and running fraud detection models...</p>
        `;

        const data = await apiRequest('/api/upload-csv', {
            method: 'POST',
            body: formData
        });

        if (data) {
            showNotification(data.message, 'success');
            await updateSystemStatus();
        }

        // Restore drag zone text
        uploadDragZone.innerHTML = `
            <i class="fa-solid fa-file-csv upload-icon"></i>
            <h4>Drag & Drop match telemetry CSV here</h4>
            <p>or click the "Upload CSV" button in the header. The system will automatically validate headers, drop corrupted rows, and recompute analytics.</p>
            <span class="file-spec">Required columns: player_id, match_id, region, device, ping, score, kills, deaths, match_duration_seconds</span>
        `;
    }

    // ==========================================
    // 6. ANIMATIONS & NOTIFICATIONS HELPERS
    // ==========================================
    
    // Animate numbers counting up/down smoothly
    function animateValue(obj, start, end, duration) {
        if (start === end) {
            obj.textContent = end.toLocaleString();
            return;
        }
        
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            const value = Math.floor(progress * (end - start) + start);
            obj.textContent = value.toLocaleString();
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                obj.textContent = end.toLocaleString();
            }
        };
        window.requestAnimationFrame(step);
    }

    // Create a dynamic toast notification card
    function showNotification(message, type = 'info') {
        const toast = document.createElement('div');
        toast.style.position = 'fixed';
        toast.style.bottom = '2rem';
        toast.style.right = '2rem';
        toast.style.padding = '1rem 1.5rem';
        toast.style.borderRadius = 'var(--radius)';
        toast.style.boxShadow = '0 10px 25px rgba(0,0,0,0.5)';
        toast.style.zIndex = '9999';
        toast.style.display = 'flex';
        toast.style.alignItems = 'center';
        toast.style.gap = '0.75rem';
        toast.style.fontFamily = 'var(--font-heading)';
        toast.style.fontWeight = '600';
        toast.style.fontSize = '0.9rem';
        toast.style.animation = 'slideIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        
        // CSS Style sheet references styles.css variables indirectly
        if (type === 'success') {
            toast.style.backgroundColor = 'var(--color-success-bg)';
            toast.style.color = 'var(--color-success)';
            toast.style.border = '1px solid var(--color-success)';
            toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${message}`;
        } else if (type === 'danger') {
            toast.style.backgroundColor = 'var(--color-danger-bg)';
            toast.style.color = 'var(--color-danger)';
            toast.style.border = '1px solid var(--color-danger)';
            toast.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${message}`;
        } else {
            toast.style.backgroundColor = 'rgba(255,255,255,0.06)';
            toast.style.color = 'var(--text-primary)';
            toast.style.border = '1px solid var(--border-color)';
            toast.innerHTML = `<i class="fa-solid fa-circle-info"></i> ${message}`;
        }

        document.body.appendChild(toast);

        // Slide Out and remove
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Add keyframe animations dynamically
    const styleSheet = document.createElement("style");
    styleSheet.innerText = `
        @keyframes slideIn {
            from { transform: translateX(100%) translateY(0); opacity: 0; }
            to { transform: translateX(0) translateY(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0) translateY(0); opacity: 1; }
            to { transform: translateX(120%) translateY(0); opacity: 0; }
        }
    `;
    document.head.appendChild(styleSheet);

    // Initial system load
    updateSystemStatus();
});
