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
const mirrorX = document.getElementById('mirror-x');
const mirrorY = document.getElementById('mirror-y');
const layoutSelect = document.getElementById('layout-select');
const prompterSpeedSlider = document.getElementById('prompter-speed-slider');
const voiceStatusEditor = document.getElementById('voice-indicator-editor');
const voiceStatusPrompter = document.getElementById('voice-status');
const voiceToggle = document.getElementById('voice-toggle');

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
let currentSpeed = 18;
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

btnModeLocal?.addEventListener('click', () => setSyncMode('local'));
btnModeHost?.addEventListener('click', () => setSyncMode('host'));
btnModeRemote?.addEventListener('click', () => setSyncMode('remote'));

// Функція для надсилання подій
function sendEvent(data) {
  if (conn && conn.open) {
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

btnConnect?.addEventListener('click', () => {
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
    if (textInput) textInput.value = data.text;
    if (sizeSlider) sizeSlider.value = data.size;
    if (speedSlider) speedSlider.value = data.speed;
    updateUISettings();
    startPrompter();
  } 
  else if (data.type === 'PAUSE') {
    if (data.percentage !== undefined) setScrollPercentage(data.percentage);
    pausePrompter();
    // Якщо ми Host, після паузи відправляємо точну позицію Пульту, щоб Пульт підлаштувався під нас, а не навпаки
    if (syncMode === 'host') sendEvent({ type: 'SYNC_POS', percentage: getScrollPercentage() });
  }
  else if (data.type === 'RESUME') {
    if (data.percentage !== undefined) setScrollPercentage(data.percentage);
    resumePrompter();
    if (syncMode === 'host') sendEvent({ type: 'SYNC_POS', percentage: getScrollPercentage() });
  }
  else if (data.type === 'SCROLL') {
    if (data.percentage !== undefined) setScrollPercentage(data.percentage);
  }
  else if (data.type === 'SCROLL_PCT') {
    // Якщо Пульт крутить коліщатко, він надсилає свою нову абсолютну позицію
    setScrollPercentage(data.percentage);
    if (syncMode === 'host') sendEvent({ type: 'SYNC_POS', percentage: getScrollPercentage() });
  }
  else if (data.type === 'SYNC_POS') {
    setScrollPercentage(data.percentage);
  }
  else if (data.type === 'SYNC_HEIGHT') {
    window.hostScrollHeight = data.height;
    window.hostClientWidth = data.width;
    if (syncMode === 'remote' && window.hostClientWidth) {
      if (prompterContainer) prompterContainer.style.width = `${window.hostClientWidth}px`;
    }
  }
  else if (data.type === 'EXIT') {
    exitPrompter();
  }
  else if (data.type === 'SPEED_CHANGE') {
    currentSpeed = data.speed;
    if (speedSlider) speedSlider.value = currentSpeed;
    if (prompterSpeedSlider) prompterSpeedSlider.value = currentSpeed;
    if (speedValue) speedValue.textContent = currentSpeed;
  }
}

// --- ОСНОВНА ЛОГІКА СУФЛЕРА ---

function updateUISettings() {
  if (speedSlider) currentSpeed = parseInt(speedSlider.value);
  if (speedValue) speedValue.textContent = currentSpeed;
  if (sizeValue && sizeSlider) sizeValue.textContent = sizeSlider.value;
  if (prompterText && sizeSlider) prompterText.style.fontSize = `${sizeSlider.value}px`;
}

speedSlider?.addEventListener('input', (e) => {
  currentSpeed = parseInt(e.target.value);
  if (prompterSpeedSlider) prompterSpeedSlider.value = currentSpeed;
  updateUISettings();
  sendEvent({ type: 'SPEED_CHANGE', speed: currentSpeed });
});

prompterSpeedSlider?.addEventListener('input', (e) => {
  currentSpeed = parseInt(e.target.value);
  if (speedSlider) speedSlider.value = currentSpeed;
  updateUISettings();
  sendEvent({ type: 'SPEED_CHANGE', speed: currentSpeed });
});

// Щоб клік по повзунку швидкості не ставив на паузу суфлер
prompterSpeedSlider?.addEventListener('click', (e) => e.stopPropagation());
prompterSpeedSlider?.addEventListener('mousedown', (e) => e.stopPropagation());
prompterSpeedSlider?.addEventListener('touchstart', (e) => e.stopPropagation());

sizeSlider?.addEventListener('input', updateUISettings);

mirrorX?.addEventListener('change', (e) => {
  if (e.target.checked) prompterContainer.classList.add('mirrored-x');
  else prompterContainer.classList.remove('mirrored-x');
});

mirrorY?.addEventListener('change', (e) => {
  if (e.target.checked) prompterContainer.classList.add('mirrored-y');
  else prompterContainer.classList.remove('mirrored-y');
});

layoutSelect?.addEventListener('change', (e) => {
  prompterContainer.className = '';
  if (mirrorX && mirrorX.checked) prompterContainer.classList.add('mirrored-x');
  if (mirrorY && mirrorY.checked) prompterContainer.classList.add('mirrored-y');
  prompterContainer.classList.add(e.target.value);
});

function getScrollPercentage() {
  if (!prompterText || !prompterContainer || prompterText.scrollHeight === 0) return 0;
  // Математично точний відсоток тексту, що знаходиться рівно по ЦЕНТРУ контейнера
  const H_c = prompterContainer.clientHeight;
  const S_h = prompterText.scrollHeight;
  return (-scrollPosition - H_c / 2) / S_h;
}

function setScrollPercentage(percentage) {
  if (!prompterText || !prompterContainer) return;
  // Встановлюємо scrollPosition так, щоб заданий відсоток тексту опинився по ЦЕНТРУ контейнера
  const H_c = prompterContainer.clientHeight;
  const S_h = prompterText.scrollHeight;
  scrollPosition = - (percentage * S_h) - H_c / 2;
  updatePrompterTransform();
}

function updatePrompterTransform() {
  if (prompterText) prompterText.style.transform = `translateY(${scrollPosition}px)`;
}

let lastTime = 0;

function scrollLoop(timestamp) {
  if (!isPlaying) return;
  
  if (!lastTime) lastTime = timestamp;
  let deltaTime = timestamp - lastTime;
  lastTime = timestamp;

  // Обмежуємо deltaTime, щоб уникнути стрибків, якщо вкладка була неактивною
  if (deltaTime > 100) deltaTime = 16.66;
  
  // Базова швидкість: 18 * 3 = 54 пікселі в секунду (еквівалент старої швидкості при 60 FPS)
  let speedPerSecond = currentSpeed * 3; 
  
  // Якщо ми пульт, адаптуємо швидкість фізичної прокрутки до висоти екрану Host'а
  if (syncMode === 'remote' && window.hostScrollHeight && prompterText) {
    speedPerSecond = speedPerSecond * (prompterText.scrollHeight / window.hostScrollHeight);
  }
  
  // Рух не залежить від частоти кадрів монітора (60Hz, 120Hz, 144Hz)
  scrollPosition -= speedPerSecond * (deltaTime / 1000);
  updatePrompterTransform();
  
  // Host транслює свою позицію для пульта кожні 500мс
  if (syncMode === 'host' && conn && conn.open) {
    if (!window.lastSyncTime) window.lastSyncTime = 0;
    if (timestamp - window.lastSyncTime > 500) {
      window.lastSyncTime = timestamp;
      sendEvent({ type: 'SYNC_POS', percentage: getScrollPercentage() });
    }
  }
  
  // Зупиняємо, коли текст прокрутився повністю до темного екрану
  const stopTarget = -(prompterText.scrollHeight + prompterContainer.clientHeight);
  if (scrollPosition < stopTarget) {
    scrollPosition = stopTarget;
    updatePrompterTransform();
    pausePrompter();
    return;
  }

  animationFrameId = requestAnimationFrame(scrollLoop);
}

function startPrompter() {
  try {
    const text = textInput ? textInput.value.trim() : "";
    if (!text) {
      alert("Будь ласка, введіть текст для прокрутки.");
      return;
    }
    
    if (prompterText) {
      prompterText.textContent = text;
      if (sizeSlider) prompterText.style.fontSize = `${sizeSlider.value}px`;
    }
    scrollPosition = 0; // Починаємо завжди з нижнього краю свого контейнера
    updatePrompterTransform();
    
    if (syncMode === 'remote') {
      // Режим Пульта: не ховаємо редактор, а вставляємо суфлер у праву панель
      const textPanel = document.getElementById('text-panel');
      if (textInput) textInput.style.display = 'none';
      if (textPanel && prompterView) {
        textPanel.appendChild(prompterView);
        prompterView.classList.add('active');
        prompterView.classList.add('remote-preview-mode');
      }
      sendEvent({ type: 'START', text: text, speed: currentSpeed, size: sizeSlider ? sizeSlider.value : 40 });
    } else {
      // Звичайний режим: на весь екран
      editorView?.classList.remove('active');
      prompterView?.classList.add('active');
      sendEvent({ type: 'START', text: text, speed: currentSpeed, size: sizeSlider ? sizeSlider.value : 40, percentage: getScrollPercentage() });
    }
    
    // Якщо ми Екран (Host), надсилаємо свої розміри пульту
    if (syncMode === 'host') {
      setTimeout(() => {
        sendEvent({ 
          type: 'SYNC_HEIGHT', 
          height: prompterText ? prompterText.scrollHeight : 1,
          width: prompterContainer ? prompterContainer.clientWidth : 375
        });
      }, 100);
    }
    
    resumePrompter();
  } catch (err) {
    alert("Помилка запуску: " + err.message);
  }
}

function resumePrompter() {
  if (!isPlaying) {
    isPlaying = true;
    lastTime = 0; // Скидаємо таймер при відновленні
    if (voiceToggle && voiceToggle.checked && voiceStatusPrompter) voiceStatusPrompter.textContent = "🎤 Слухаю... (в роботі)";
    
    if (syncMode === 'remote') {
      sendEvent({ type: 'RESUME' }); // Пульт не нав'язує свою позицію
    } else {
      sendEvent({ type: 'RESUME', percentage: getScrollPercentage() }); // Екран диктує позицію
    }
    
    animationFrameId = requestAnimationFrame(scrollLoop);
  }
}

function pausePrompter() {
  isPlaying = false;
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  if (voiceToggle && voiceToggle.checked && voiceStatusPrompter) voiceStatusPrompter.textContent = "🎤 Пауза. Скажіть 'Суфлер старт'";
  
  if (syncMode === 'remote') {
    sendEvent({ type: 'PAUSE' }); // Пульт просто дає команду стоп, без нав'язування позиції
  } else {
    sendEvent({ type: 'PAUSE', percentage: getScrollPercentage() });
  }
}

function exitPrompter() {
  pausePrompter();
  
  if (syncMode === 'remote') {
    const app = document.getElementById('app');
    if (textInput) textInput.style.display = 'block';
    if (app && prompterView) {
      prompterView.classList.remove('active');
      prompterView.classList.remove('remote-preview-mode');
      app.appendChild(prompterView); // повертаємо в корінь
    }
  } else {
    prompterView.classList.remove('active');
    editorView.classList.add('active');
  }
  
  if (prompterContainer) prompterContainer.style.width = '';
  sendEvent({ type: 'EXIT' });
}

startBtn?.addEventListener('click', startPrompter);
stopBtn?.addEventListener('click', exitPrompter);

// ЛОКАЛЬНЕ КЕРУВАННЯ МИШКОЮ В РЕЖИМІ СУФЛЕРА
prompterContainer?.addEventListener('click', () => {
  if (isPlaying) pausePrompter();
  else resumePrompter();
});

prompterContainer?.addEventListener('wheel', (e) => {
  // Правило користувача:
  // Якщо дзеркало вимкнено (mirrorY == false), коліщатко до себе (e.deltaY > 0) -> текст йде ВНИЗ.
  // Якщо дзеркало ввімкнено (mirrorY == true), коліщатко до себе (e.deltaY > 0) -> текст йде ВГОРУ.
  
  if (mirrorY && mirrorY.checked) {
    // Ввімкнені тумблери -> текст ВГОРУ
    scrollPosition += e.deltaY;
  } else {
    // Вимкнені тумблери (або ПК) -> текст ВНИЗ (нормальна прокрутка)
    scrollPosition -= e.deltaY;
  }
  
  updatePrompterTransform();
  
  if (syncMode === 'remote') {
    // Пульт відправляє нову абсолютну позицію
    sendEvent({ type: 'SCROLL_PCT', percentage: getScrollPercentage() });
  } else {
    sendEvent({ type: 'SCROLL', percentage: getScrollPercentage() });
  }
});

let globalRecognition = null;

// Голосове управління (тільки якщо Автономно або ми Пульт)
function initVoiceControl() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Ваш браузер не підтримує голосове керування (або воно заблоковано).");
    voiceToggle.checked = false;
    return;
  }

  globalRecognition = new SpeechRecognition();
  globalRecognition.lang = 'uk-UA'; 
  globalRecognition.continuous = true;
  globalRecognition.interimResults = true;

  globalRecognition.onresult = function(event) {
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
      prompterSpeedSlider.value = currentSpeed;
      updateUISettings();
      sendEvent({ type: 'SPEED_CHANGE', speed: currentSpeed });
      commandExecuted = true;
    }
    else if (command.includes('повільніше') || command.includes('повільніш')) {
      currentSpeed = Math.max(1, currentSpeed - 10);
      speedSlider.value = currentSpeed;
      prompterSpeedSlider.value = currentSpeed;
      updateUISettings();
      sendEvent({ type: 'SPEED_CHANGE', speed: currentSpeed });
      commandExecuted = true;
    }
    else if (command.includes('вгору') || command.includes('назад') || command.includes('вище')) {
      scrollPosition += window.innerHeight / 2.5;
      updatePrompterTransform();
      sendEvent({ type: 'SCROLL', percentage: getScrollPercentage() });
      commandExecuted = true;
    }
    else if (command.includes('вниз') || command.includes('вперед') || command.includes('нижче')) {
      scrollPosition -= window.innerHeight / 2.5;
      updatePrompterTransform();
      sendEvent({ type: 'SCROLL', percentage: getScrollPercentage() });
      commandExecuted = true;
    }
    else if (command.includes('редактор') || command.includes('вихід')) {
      exitPrompter();
      commandExecuted = true;
    }

    if (commandExecuted) {
      lastCommandTime = now;
      globalRecognition.stop(); 
    }
  };

  globalRecognition.onerror = function(event) {
    if (event.error === 'not-allowed') {
        alert("Немає доступу до мікрофону.");
        voiceToggle.checked = false;
        voiceStatusEditor.style.display = 'none';
        voiceStatusPrompter.style.display = 'none';
    }
  };

  globalRecognition.onend = function() {
    if (voiceToggle.checked) {
       globalRecognition.start();
    }
  };

  try { 
    globalRecognition.start(); 
    voiceStatusEditor.style.display = 'block';
    voiceStatusPrompter.style.display = 'block';
  } catch(e) {
    alert("Помилка старту мікрофону: " + e.message);
    voiceToggle.checked = false;
  }
}

voiceToggle?.addEventListener('change', (e) => {
  if (e.target.checked) {
    initVoiceControl();
  } else {
    if (globalRecognition) {
      globalRecognition.stop();
    }
    voiceStatusEditor.style.display = 'none';
    voiceStatusPrompter.style.display = 'none';
  }
});

window.onerror = function(message, source, lineno, colno, error) {
  alert(`Глобальна помилка: ${message}\nРядок: ${lineno}\nКолонка: ${colno}`);
  return true;
};

window.addEventListener('DOMContentLoaded', () => {
  try {
    // Розумні налаштування за замовчуванням
    const isMobile = window.innerWidth < 768 || navigator.userAgent.match(/Mobi/i);
    if (isMobile) {
      if (mirrorX) mirrorX.checked = false;
      if (mirrorY) mirrorY.checked = true;
      if (layoutSelect) layoutSelect.value = 'layout-left';
    } else {
      if (mirrorX) mirrorX.checked = false;
      if (mirrorY) mirrorY.checked = false;
      if (layoutSelect) layoutSelect.value = 'layout-full';
    }
    
    if (mirrorX && mirrorX.checked) prompterContainer?.classList.add('mirrored-x');
    if (mirrorY && mirrorY.checked) prompterContainer?.classList.add('mirrored-y');
    if (layoutSelect) prompterContainer?.classList.add(layoutSelect.value);
    
    if (textInput) textInput.value = "Ласкаво просимо до AI Телесуфлера.\n\nТепер ви можете використовувати комп'ютер як пульт для телефону.\n\nКоманди:\n- суфлер старт\n- суфлер стоп\n- суфлер швидше\n- суфлер повільніше";
  } catch(e) {
    alert("Помилка ініціалізації: " + e.message);
  }
});
