const express = require('express');
const session = require('express-session');
const http = require('http');
const WebSocket = require('ws');
const path = require('path');
const fs = require('fs');
const pty = require('node-pty');

const app = express();
const server = http.createServer(app);
const PORT = process.env.PORT || 4000;
const PASSWORD = process.env.APP_PASSWORD || 'alif';
const PROJECT_ROOT = path.resolve(__dirname, '..');
const DATA_DIR = path.join(PROJECT_ROOT, 'data');

// --- Session setup ---
const sessionParser = session({
    secret: 'xacquisitor-secret-key-2026',
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: 24 * 60 * 60 * 1000 } // 24h
});

app.use(express.json());
app.use(sessionParser);
app.use(express.static(path.join(__dirname, 'public')));

// --- Auth middleware ---
function requireAuth(req, res, next) {
    if (req.session && req.session.authenticated) return next();
    res.status(401).json({ error: 'Unauthorized' });
}

// --- Auth routes ---
app.post('/api/login', (req, res) => {
    if (req.body.password === PASSWORD) {
        req.session.authenticated = true;
        res.json({ ok: true });
    } else {
        res.status(403).json({ error: 'Wrong password' });
    }
});

app.get('/api/auth-check', (req, res) => {
    res.json({ authenticated: !!(req.session && req.session.authenticated) });
});

app.post('/api/logout', (req, res) => {
    req.session.destroy();
    res.json({ ok: true });
});

// --- File Explorer API ---
app.get('/api/files', requireAuth, (req, res) => {
    const relPath = req.query.path || '';
    const absPath = path.join(DATA_DIR, relPath);

    // Security: ensure we stay within DATA_DIR
    if (!absPath.startsWith(DATA_DIR)) {
        return res.status(403).json({ error: 'Access denied' });
    }

    try {
        const stat = fs.statSync(absPath);
        if (stat.isDirectory()) {
            const entries = fs.readdirSync(absPath).map(name => {
                const fullPath = path.join(absPath, name);
                const s = fs.statSync(fullPath);
                return {
                    name,
                    type: s.isDirectory() ? 'directory' : 'file',
                    size: s.size,
                    modified: s.mtime.toISOString()
                };
            });
            entries.sort((a, b) => {
                if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
                return a.name.localeCompare(b.name);
            });
            res.json({ path: relPath, entries });
        } else {
            // Read file content (limit to 2MB)
            if (stat.size > 2 * 1024 * 1024) {
                return res.json({ path: relPath, content: '[File too large to display]', size: stat.size });
            }
            const content = fs.readFileSync(absPath, 'utf-8');
            res.json({ path: relPath, content, size: stat.size });
        }
    } catch (e) {
        res.status(404).json({ error: 'Not found' });
    }
});

// --- Pipeline Data Explorer API ---
app.get('/api/pipeline', requireAuth, (req, res) => {
    try {
        const result = { stages: {}, summary: {} };
        const files = {
            state: 'state.json',
            profiles_raw: 'profiles_raw.json',
            profiles_enriched: 'profiles_enriched.json',
            profiles_filtered: 'profiles_filtered.json',
            profiles_scored: 'profiles_scored.json',
            profiles_classified: 'profiles_classified.json',
            results: 'results.json'
        };

        for (const [key, filename] of Object.entries(files)) {
            const fp = path.join(DATA_DIR, filename);
            if (fs.existsSync(fp)) {
                try {
                    const raw = fs.readFileSync(fp, 'utf-8');
                    const data = JSON.parse(raw);
                    result.stages[key] = data;
                } catch (e) {
                    result.stages[key] = { error: 'Parse error' };
                }
            }
        }

        // Build summary from state
        if (result.stages.state && result.stages.state.profiles) {
            const profiles = result.stages.state.profiles;
            const stageCounts = { mined: 0, enriched: 0, filtered: 0, scored: 0, classified: 0, exported: 0 };
            for (const handle of Object.keys(profiles)) {
                const stages = profiles[handle].stages || {};
                for (const stage of Object.keys(stages)) {
                    if (stageCounts[stage] !== undefined) stageCounts[stage]++;
                }
            }
            const topics = result.stages.state.pipeline?.topics_mined || {};
            result.summary = {
                totalProfiles: Object.keys(profiles).length,
                stageCounts,
                topicsTotal: typeof topics === 'object' ? Object.keys(topics).length : 0,
                topicsCompleted: typeof topics === 'object'
                    ? Object.values(topics).filter(t => t.status === 'completed').length
                    : 0,
                topics: topics
            };
        }

        // Add counts for data files
        for (const key of ['profiles_raw', 'profiles_enriched', 'profiles_filtered', 'profiles_scored', 'profiles_classified']) {
            if (Array.isArray(result.stages[key])) {
                result.summary[key + '_count'] = result.stages[key].length;
            }
        }

        if (result.stages.results && result.stages.results.profiles) {
            result.summary.results_count = result.stages.results.profiles.length;
        }

        res.json(result);
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// --- Restart endpoint ---
app.post('/api/restart', requireAuth, (req, res) => {
    const sessionId = req.sessionID;
    const ptyInfo = ptyProcesses.get(sessionId);
    if (ptyInfo) {
        try { ptyInfo.pty.kill(); } catch (e) { }
        ptyProcesses.delete(sessionId);
    }
    res.json({ ok: true, message: 'Terminal restarted. Reconnect to get a new session.' });
});

// --- WebSocket Terminal ---
const wss = new WebSocket.Server({ noServer: true });
const ptyProcesses = new Map(); // sessionId -> { pty, ws }

// Command validation removed: restricted shell handles this directly
server.on('upgrade', (request, socket, head) => {
    // Parse session from cookie
    sessionParser(request, {}, () => {
        if (!request.session || !request.session.authenticated) {
            socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
            socket.destroy();
            return;
        }

        wss.handleUpgrade(request, socket, head, (ws) => {
            wss.emit('connection', ws, request);
        });
    });
});

wss.on('connection', (ws, request) => {
    const sessionId = request.session.id;

    // Check if there's an existing PTY for this session
    let ptyInfo = ptyProcesses.get(sessionId);

    if (ptyInfo && ptyInfo.pty) {
        // Reattach to existing PTY
        ptyInfo.clients.add(ws);
        if (ptyInfo.buffer) {
            // Restore visual state
            ws.send(JSON.stringify({ type: 'output', data: ptyInfo.buffer }));
        }
    } else {
        // Create new PTY with custom restricted shell wrapper
        const ptyProc = pty.spawn('bash', ['webapp/shell.sh'], {
            name: 'xterm-256color',
            cols: 120,
            rows: 30,
            cwd: PROJECT_ROOT,
            env: {
                ...process.env,
                TERM: 'xterm-256color',
                HOME: process.env.HOME,
                PATH: process.env.PATH,
                VIRTUAL_ENV: path.join(PROJECT_ROOT, 'venv'),
            }
        });

        ptyInfo = { pty: ptyProc, clients: new Set([ws]), buffer: '' };
        ptyProcesses.set(sessionId, ptyInfo);

        ptyProc.onData((data) => {
            const info = ptyProcesses.get(sessionId);
            if (info) {
                // Keep the last 50,000 characters in memory for visual persistence
                info.buffer += data;
                if (info.buffer.length > 50000) {
                    info.buffer = info.buffer.slice(-50000);
                }
                info.clients.forEach(client => {
                    if (client.readyState === WebSocket.OPEN) {
                        client.send(JSON.stringify({ type: 'output', data }));
                    }
                });
            }
        });

        ptyProc.onExit(() => {
            ptyProcesses.delete(sessionId);
            info.clients.forEach(client => {
                if (client.readyState === WebSocket.OPEN) {
                    client.send(JSON.stringify({ type: 'exit' }));
                }
            });
        });
    }

    ws.on('message', (msg) => {
        try {
            const parsed = JSON.parse(msg.toString());

            if (parsed.type === 'input') {
                const info = ptyProcesses.get(sessionId);
                if (info && info.pty) {
                    // Send directly to PTY — the custom shell handles validation seamlessly
                    info.pty.write(parsed.data);
                }
            } else if (parsed.type === 'resize') {
                const info = ptyProcesses.get(sessionId);
                if (info && info.pty) {
                    info.pty.resize(parsed.cols || 120, parsed.rows || 30);
                }
            }
        } catch (e) {
            // Ignore parse errors
        }
    });

    ws.on('close', () => {
        // Remove this client from the connection list but keep the pty process alive
        const info = ptyProcesses.get(sessionId);
        if (info && info.clients) {
            info.clients.delete(ws);
        }
    });
});

// --- Fallback to index.html ---
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`Xacquisitor webapp running on http://0.0.0.0:${PORT}`);
});
