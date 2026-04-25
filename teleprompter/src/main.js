// Телесуфлер - Основна Логіка (з PeerJS)

// Елементи DOM
const editorView = document.getElementById('editor-view');
const prompterView = document.getElementById('prompter-view');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const textInput = document.getElementById('text-input');
const prompterText = document.getElementById('prompter-text');
const prompterContainer = document.getElementById('prompter-container');
const speedSlider = document.getElementById('speed-slider');
const speedValue = document.getElementById('speed-value');
const sizeSlider = document.getElementById('size-slider');
const sizeValue = document.getElementById('size-value');
const mirrorToggle = document.getElementById('mirror-toggle');
const layoutSelect = document.getElementById('layout-select');
const voiceStatusEditor = document.getElementById('voice-indicator-editor');
const voiceStatusPrompter = document.getElementById('voice-status');

// Елементи для пульта
const btnModeLocal = document.getElementById('btn-mode-local');
const btnModeHost = document.getElementById('btn-mode-host');
const btnModeRemote = document.getElementById('btn-mode-remote');
const hostPanel = document.getElementById('host-panel');
const remotePanel = document.getElementById('remote-panel');
const hostCodeEl = document.getElementById('host-code');
const hostStatus = document.getElementById('host-status');
const remoteCodeInput = document.getElementById('remote-code-input');
const btnConnect = document.getElementById('btn-connect');
const remoteStatus = document.getElementById('remote-status');

// Стан додатку
let isPlaying = false;
let scrollPosition = 0;
let animationFrameId = null;
let currentSpeed = 20;
let lastCommandTime = 0;

// Стан мережі (PeerJS)
let peer = null;
let conn = null; // Поточне з'єднання
let syncMode = 'local'; // 'local', 'host', 'remote'

// --- НАЛАШТУВАННЯ МЕРЕЖІ (PEERJS) ---

function setSyncMode(mode) {
  syncMode = mode;
  btnModeLocal.classList.remove('active');
  btnModeHost.classList.remove('active');
  btnModeRemote.classList.remove('active');
  hostPanel.classList.add('hidden');
  remotePanel.classList.add('hidden');

  if (peer) { peer.destroy(); peer = null; }
  conn = null;

  if (mode === 'local') {
    btnModeLocal.classList.add('active');
  } 
  else if (mode === 'host') {
    btnModeHost.classList.add('active');
    hostPanel.classList.remove('hidden');
    initHost();
  } 
  else if (mode === 'remote') {
    btnModeRemote.classList.add('active');
    remotePanel.classList.remove('hidden');
    initRemote();
  }
}

btnModeLocal.addEventListener('click', () => setSyncMode('local'));
btnModeHost.addEventListener('click', () => setSyncMode('host'));
btnModeRemote.addEventListener('click', () => setSyncMode('remote'));

// Функція для надсилання подій (працює тільки якщо ми - Пульт)
function sendEvent(data) {
  if (syncMode === 'remote' && conn && conn.open) {
    conn.send(data);
  }
}

// Ініціалізація Екрану (Host)
function initHost() {
  const code = Math.floor(1000 + Math.random() * 9000).toString(); // 4 цифри
  hostCodeEl.textContent = code;
  hostStatus.textContent = "Створення кімнати...";
  hostStatus.className = "status waiting";

  peer = new Peer('aivtomation-tp-' + code);

  peer.on('open', () => {
    hostStatus.textContent = "Очікування підключення пульта...";
  });

  peer.on('connection', (connection) => {
    conn = connection;
    hostStatus.textContent = "Пульт підключено!";
    hostStatus.className = "status connected";

    conn.on('data', (data) => {
      console.log("Отримано команду від пульта:", data);
      handleRemoteCommand(data);
    });

    conn.on('close', () => {
      hostStatus.textContent = "Пульт відключено. Очікування...";
      hostStatus.className = "status waiting";
    });
  });

  peer.on('error', (err) => {
    hostStatus.textContent = "Помилка мережі: " + err.type;
    hostStatus.className = "status error";
  });
}

// Ініціалізація Пульта (Remote)
function initRemote() {
  peer = new Peer(); // Пульту не потрібен специфічний ID
  remoteStatus.textContent = "Введіть код та натисніть Підключитись";
  remoteStatus.className = "status";
}

btnConnect.addEventListener('click', () => {
  if (!peer) return;
  const code = remoteCodeInput.value.trim();
  if (code.length !== 4) {
    alert("Введіть 4 цифри");
    return;
  }

  remoteStatus.textContent = "Підключення...";
  remoteStatus.className = "status waiting";

  conn = peer.connect('aivtomation-tp-' + code);

  conn.on('open', () => {
    remoteStatus.textContent = "Підключено! Тепер ви керуєте екраном.";
    remoteStatus.className = "status connected";
    // Одразу відправляємо поточні налаштування на екран
    sendEvent({ type: 'UPDATE_SETTINGS', speed: currentSpeed, size: sizeSlider.value });
  });

  conn.on('close', () => {
    remoteStatus.textContent = "Відключено від екрану.";
    remoteStatus.className = "status error";
  });
});

// Обробка команд від пульта (тільки для режиму Host)
function handleRemoteCommand(data) {
  if (data.type === 'START') {
    textInput.value = data.text;
    sizeSlider.value = data.size;
    speedSlider.value = data.speed;
    updateUISettings();
    startPrompter();
  } 
  else if (data.type === 'PAUSE') {
    scrollPosition = data.position;
    pausePrompter();
    updatePrompterTransform();
  }
  else if (data.type === 'RESUME') {
    scrollPosition = data.position;
    updatePrompterTransform();
    resumePrompter();
  }
  else if (data.type === 'SCROLL') {
    scrollPosition += data.deltaY;
    updatePrompterTransform();
  }
  else if (data.type === 'EXIT') {
    exitPrompter();
  }
  else if (data.type === 'SPEED_CHANGE') {
    currentSpeed = data.speed;
    speedSlider.value = currentSpeed;
    speedValue.textContent = currentSpeed;
  }
  else if (data.type === 'SYNC') {
    // Жорстка синхронізація позиції (для вирівнювання)
    scrollPosition = data.position;
    updatePrompterTransform();
  }
}

// --- ОСНОВНА ЛОГІКА СУФЛЕРА ---

function updateUISettings() {
  currentSpeed = parseInt(speedSlider.value);
  speedValue.textContent = currentSpeed;
  sizeValue.textContent = sizeSlider.value;
  prompterText.style.fontSize = `${sizeSlider.value}px`;
}

speedSlider.addEventListener('input', (e) => {
  updateUISettings();
  sendEvent({ type: 'SPEED_CHANGE', speed: currentSpeed });
});

sizeSlider.addEventListener('input', updateUISettings);

mirrorToggle.addEventListener('change', (e) => {
  if (e.target.checked) prompterContainer.classList.add('mirrored');
  else prompterContainer.classList.remove('mirrored');
});

layoutSelect.addEventListener('change', (e) => {
  prompterContainer.className = '';
  if (mirrorToggle.checked) prompterContainer.classList.add('mirrored');
  prompterContainer.classList.add(e.target.value);
});

function updatePrompterTransform() {
  prompterText.style.transform = `translateY(${scrollPosition}px)`;
}

function scrollLoop() {
  if (!isPlaying) return;
  
  const speedFactor = currentSpeed * 0.05; 
  scrollPosition -= speedFactor;
  updatePrompterTransform();
  
  const textRect = prompterText.getBoundingClientRect();
  if (textRect.bottom < 0) {
    exitPrompter();
    return;
  }

  // Якщо ми пульт, періодично відправляємо точну позицію для синхронізації
  if (syncMode === 'remote' && Math.random() < 0.02) {
    sendEvent({ type: 'SYNC', position: scrollPosition });
  }
  
  animationFrameId = requestAnimationFrame(scrollLoop);
}

function startPrompter() {
  const text = textInput.value.trim();
  if (!text) {
    alert("Будь ласка, введіть текст для прокрутки.");
    return;
  }
  
  prompterText.textContent = text;
  prompterText.style.fontSize = `${sizeSlider.value}px`;
  
  editorView.classList.remove('active');
  prompterView.classList.add('active');
  
  scrollPosition = window.innerHeight * 0.1;
  updatePrompterTransform();
  
  sendEvent({ type: 'START', text: text, speed: currentSpeed, size: sizeSlider.value });
  
  resumePrompter();
}

function resumePrompter() {
  if (!isPlaying) {
    isPlaying = true;
    voiceStatusPrompter.textContent = "🎤 Слухаю... (в роботі)";
    sendEvent({ type: 'RESUME', position: scrollPosition });
    scrollLoop();
  }
}

function pausePrompter() {
  isPlaying = false;
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  voiceStatusPrompter.textContent = "🎤 Пауза. Скажіть 'Суфлер старт'";
  sendEvent({ type: 'PAUSE', position: scrollPosition });
}

function exitPrompter() {
  pausePrompter();
  prompterView.classList.remove('active');
  editorView.classList.add('active');
  sendEvent({ type: 'EXIT' });
}

startBtn.addEventListener('click', startPrompter);
stopBtn.addEventListener('click', exitPrompter);

// ЛОКАЛЬНЕ КЕРУВАННЯ МИШКОЮ В РЕЖИМІ СУФЛЕРА
prompterContainer.addEventListener('click', () => {
  if (isPlaying) pausePrompter();
  else resumePrompter();
});

prompterContainer.addEventListener('wheel', (e) => {
  // Коліщатко миші для прокрутки вгору/вниз
  scrollPosition -= e.deltaY;
  updatePrompterTransform();
  sendEvent({ type: 'SCROLL', deltaY: -e.deltaY }); // Відправляємо на екран
});

// Голосове управління (тільки якщо Автономно або ми Пульт)
function initVoiceControl() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;

  const recognition = new SpeechRecognition();
  recognition.lang = 'uk-UA'; 
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = function(event) {
    if (syncMode === 'host') return; // Екран не слухає команди, він тільки показує

    const now = Date.now();
    if (now - lastCommandTime < 1500) return;

    const lastResultIndex = event.results.length - 1;
    const command = event.results[lastResultIndex][0].transcript.trim().toLowerCase();

    const hasWakeWord = command.includes('суфлер');
    if (!hasWakeWord || command.length > 30) return;

    let commandExecuted = false;

    if (command.includes('старт') || command.includes('продовжити') || command.includes('поїхали')) {
      if (editorView.classList.contains('active')) startPrompter();
      else resumePrompter();
      commandExecuted = true;
    } 
    else if (command.includes('стоп') || command.includes('пауза')) {
      pausePrompter();
      commandExecuted = true;
    }
    else if (command.includes('швидше') || command.includes('скоріше')) {
      currentSpeed = Math.min(100, currentSpeed + 10);
      speedSlider.value = currentSpeed;
      updateUISettings();
      sendEvent({ type: 'SPEED_CHANGE', speed: currentSpeed });
      commandExecuted = true;
    }
    else if (command.includes('повільніше') || command.includes('повільніш')) {
      currentSpeed = Math.max(1, currentSpeed - 10);
      speedSlider.value = currentSpeed;
      updateUISettings();
      sendEvent({ type: 'SPEED_CHANGE', speed: currentSpeed });
      commandExecuted = true;
    }
    else if (command.includes('вгору') || command.includes('назад') || command.includes('вище')) {
      scrollPosition += window.innerHeight / 2.5;
      updatePrompterTransform();
      sendEvent({ type: 'SCROLL', deltaY: window.innerHeight / 2.5 });
      commandExecuted = true;
    }
    else if (command.includes('вниз') || command.includes('вперед') || command.includes('нижче')) {
      scrollPosition -= window.innerHeight / 2.5;
      updatePrompterTransform();
      sendEvent({ type: 'SCROLL', deltaY: -(window.innerHeight / 2.5) });
      commandExecuted = true;
    }
    else if (command.includes('редактор') || command.includes('вихід')) {
      exitPrompter();
      commandExecuted = true;
    }

    if (commandExecuted) {
      lastCommandTime = now;
      recognition.stop(); 
    }
  };

  recognition.onend = function() { recognition.start(); };
  try { recognition.start(); } catch(e) {}
}

window.addEventListener('DOMContentLoaded', () => {
  initVoiceControl();
  textInput.value = "Ласкаво просимо до AI Телесуфлера.\n\nТепер ви можете використовувати комп'ютер як пульт для телефону.\n\nКоманди:\n- суфлер старт\n- суфлер стоп\n- суфлер швидше\n- суфлер повільніше";
});
