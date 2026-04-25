// Телесуфлер - Основна Логіка

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

// Стан додатку
let isPlaying = false;
let scrollPosition = 0;
let animationFrameId = null;
let currentSpeed = 20;
let lastCommandTime = 0;

// Оновлення значень в UI
speedSlider.addEventListener('input', (e) => {
  currentSpeed = parseInt(e.target.value);
  speedValue.textContent = currentSpeed;
});

sizeSlider.addEventListener('input', (e) => {
  sizeValue.textContent = e.target.value;
  prompterText.style.fontSize = `${e.target.value}px`;
});

// Перемикання відображення (Дзеркало / Макет)
mirrorToggle.addEventListener('change', (e) => {
  if (e.target.checked) {
    prompterContainer.classList.add('mirrored');
  } else {
    prompterContainer.classList.remove('mirrored');
  }
});

layoutSelect.addEventListener('change', (e) => {
  prompterContainer.className = '';
  if (mirrorToggle.checked) {
    prompterContainer.classList.add('mirrored');
  }
  prompterContainer.classList.add(e.target.value);
});

// Функція плавного скролінгу
function scrollLoop() {
  if (!isPlaying) return;
  
  const speedFactor = currentSpeed * 0.05; 
  scrollPosition -= speedFactor;
  
  prompterText.style.transform = `translateY(${scrollPosition}px)`;
  
  const textRect = prompterText.getBoundingClientRect();
  if (textRect.bottom < 0) {
    exitPrompter();
    return;
  }
  
  animationFrameId = requestAnimationFrame(scrollLoop);
}

// Запуск суфлера з РЕДАКТОРА
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
  prompterText.style.transform = `translateY(${scrollPosition}px)`;
  
  resumePrompter();
}

function resumePrompter() {
  if (!isPlaying) {
    isPlaying = true;
    voiceStatusPrompter.textContent = "🎤 Слухаю... (в роботі)";
    scrollLoop();
  }
}

function pausePrompter() {
  isPlaying = false;
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  voiceStatusPrompter.textContent = "🎤 Пауза. Скажіть 'Суфлер старт'";
}

function exitPrompter() {
  pausePrompter();
  prompterView.classList.remove('active');
  editorView.classList.add('active');
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
  prompterText.style.transform = `translateY(${scrollPosition}px)`;
});

// Голосове управління
function initVoiceControl() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  
  if (!SpeechRecognition) {
    voiceStatusEditor.textContent = "❌ Ваш браузер не підтримує розпізнавання голосу.";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'uk-UA'; 
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = function(event) {
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
      speedValue.textContent = currentSpeed;
      commandExecuted = true;
    }
    else if (command.includes('повільніше') || command.includes('повільніш')) {
      currentSpeed = Math.max(1, currentSpeed - 10);
      speedSlider.value = currentSpeed;
      speedValue.textContent = currentSpeed;
      commandExecuted = true;
    }
    else if (command.includes('вгору') || command.includes('назад') || command.includes('вище')) {
      scrollPosition += window.innerHeight / 2.5;
      prompterText.style.transform = `translateY(${scrollPosition}px)`;
      commandExecuted = true;
    }
    else if (command.includes('вниз') || command.includes('вперед') || command.includes('нижче')) {
      scrollPosition -= window.innerHeight / 2.5;
      prompterText.style.transform = `translateY(${scrollPosition}px)`;
      commandExecuted = true;
    }
    else if (command.includes('редактор') || command.includes('вихід')) {
      exitPrompter();
      commandExecuted = true;
    }

    if (commandExecuted) {
      console.log("Виконано команду:", command);
      lastCommandTime = now;
      recognition.stop(); 
    }
  };

  recognition.onerror = function(event) {
    if (event.error === 'not-allowed') {
        voiceStatusEditor.textContent = "❌ Немає доступу до мікрофону.";
    }
  };

  recognition.onend = function() {
    recognition.start();
  };

  try {
    recognition.start();
  } catch(e) {}
}

window.addEventListener('DOMContentLoaded', () => {
  initVoiceControl();
  textInput.value = "Ласкаво просимо до AI Телесуфлера.\n\nСкажіть 'суфлер старт', щоб почати прокрутку.\n\nКоманди:\n- суфлер стоп\n- суфлер швидше\n- суфлер повільніше\n- суфлер вгору / вниз";
});
