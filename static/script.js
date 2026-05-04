// ─────────────────────────────────────────────
//  Web Audio API — seamless chunk scheduling
// ─────────────────────────────────────────────
let audioCtx = null;
let nextPlayTime = 0;

function ensureAudioCtx() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') audioCtx.resume();
}

async function scheduleAudioChunk(base64Wav, text, aiPEl) {
    ensureAudioCtx();
    const binary = atob(base64Wav);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

    try {
        const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);
        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);

        const now = audioCtx.currentTime;
        const startAt = Math.max(now + 0.05, nextPlayTime);
        source.start(startAt);
        const totalDuration = audioBuffer.duration;
        nextPlayTime = startAt + totalDuration;

        // ── Word-Level Sync Logic ──
        const words = text.split(' ');
        const totalChars = text.length;
        let cumulativeDelay = (startAt - now) * 1000;

        words.forEach((word, index) => {
            // Estimate word duration based on character length
            const wordWeight = (word.length + 1) / totalChars; 
            const wordDurationMs = wordWeight * totalDuration * 1000;

            setTimeout(() => {
                if (aiPEl) {
                    const isFirstWordOfSentence = index === 0;
                    const needsLeadingSpace = isFirstWordOfSentence && aiPEl.textContent.length > 0;
                    const space = needsLeadingSpace ? ' ' : (isFirstWordOfSentence ? '' : ' ');
                    
                    aiPEl.textContent += space + word;
                    chatDisplay.scrollTop = chatDisplay.scrollHeight;
                    statusText.textContent = 'Speaking...';
                }
            }, cumulativeDelay);

            cumulativeDelay += wordDurationMs;
        });

    } catch (err) {
        console.error('Audio decode error:', err);
    }
}

// ─────────────────────────────────────────────
//  DOM references
// ─────────────────────────────────────────────
const recordBtn    = document.getElementById('recordBtn');
const statusText   = document.getElementById('statusText');
const hintText     = document.getElementById('hintText');
const chatDisplay  = document.getElementById('chatDisplay');
const interimBar   = document.getElementById('interimBar');
const interimText  = document.getElementById('interimText');

// ─────────────────────────────────────────────
//  SpeechRecognition — live transcript display
// ─────────────────────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

function startSpeechRecognition() {
    if (!SpeechRecognition) return;
    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (!event.results[i].isFinal) interim += event.results[i][0].transcript;
        }
        interimText.textContent = interim || 'Listening...';
    };
    recognition.start();
}

function stopSpeechRecognition() {
    if (recognition) { recognition.stop(); recognition = null; }
}

// ─────────────────────────────────────────────
//  MediaRecorder — capture actual audio
// ─────────────────────────────────────────────
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;

recordBtn.addEventListener('click', async () => {
    isRecording ? stopRecording() : await startRecording();
});

async function startRecording() {
    try {
        ensureAudioCtx();
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = (e) => { if (e.data.size) audioChunks.push(e.data); };
        mediaRecorder.onstop = sendAudioToBackend;
        mediaRecorder.start();

        startSpeechRecognition();

        isRecording = true;
        recordBtn.classList.add('recording');
        interimBar.classList.add('visible');
        statusText.textContent = 'Recording...';
        hintText.textContent   = 'Click to stop';
    } catch (err) {
        alert('Microphone access denied: ' + err.message);
    }
}

function stopRecording() {
    if (mediaRecorder) mediaRecorder.stop();
    stopSpeechRecognition();
    isRecording = false;
    recordBtn.classList.remove('recording');
    interimBar.classList.remove('visible');
    statusText.textContent = 'Processing...';
}

// ─────────────────────────────────────────────
//  SSE stream handler
// ─────────────────────────────────────────────
async function sendAudioToBackend() {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    const form = new FormData();
    form.append('file', blob, 'voice.webm');

    nextPlayTime = 0;
    let aiEl = null;
    let aiPEl = null;

    try {
        const response = await fetch('/api/voice-stream', { method: 'POST', body: form });
        const reader   = response.body.getReader();
        const decoder  = new TextDecoder();
        let lineBuffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            lineBuffer += decoder.decode(value, { stream: true });
            const lines = lineBuffer.split('\n');
            lineBuffer  = lines.pop(); 

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const raw = line.slice(6).trim();
                if (!raw) continue;

                try {
                    const evt = JSON.parse(raw);

                    if (evt.type === 'user_text') {
                        addMessage(evt.text, 'user');
                    } else if (evt.type === 'audio_chunk') {
                        if (!aiEl) {
                            aiEl = addMessage('', 'system');
                            aiPEl = aiEl.querySelector('p');
                            aiPEl.classList.add('streaming');
                        }
                        scheduleAudioChunk(evt.audio, evt.text, aiPEl);
                    } else if (evt.type === 'done') {
                        const waitTime = Math.max(0, (nextPlayTime - audioCtx.currentTime) * 1000);
                        setTimeout(() => {
                            if (aiPEl) aiPEl.classList.remove('streaming');
                            statusText.textContent = 'Ready to listen';
                            hintText.textContent   = 'Click to speak';
                        }, waitTime + 100);
                    }
                } catch (e) { console.error("Event parse error", e); }
            }
        }
    } catch (err) {
        console.error('Stream error:', err);
        statusText.textContent = 'Ready to listen';
    }
}

// ─────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────
function addMessage(text, role) {
    const wrapper = document.createElement('div');
    wrapper.classList.add('message', role);
    const avatar = document.createElement('div');
    avatar.classList.add('avatar');
    avatar.textContent = role === 'system' ? 'A' : 'U';
    const p = document.createElement('p');
    p.textContent = text;
    wrapper.appendChild(avatar);
    wrapper.appendChild(p);
    chatDisplay.appendChild(wrapper);
    chatDisplay.scrollTop = chatDisplay.scrollHeight;
    return wrapper;
}
