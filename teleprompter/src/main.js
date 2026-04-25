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
    prompterText.classList.add('mirrored');
  } else {
    prompterText.classList.remove('mirrored');
  }
});

layoutSelect.addEventListener('change', (e) => {
  prompterContainer.className = '';
  prompterContainer.classList.add(e.target.value);
});

// Функція плавного скролінгу
function scrollLoop() {
  if (!isPlaying) return;
  
  // Швидкість масштабується для requestAnimationFrame (1-100 перетворюємо в пікселі за кадр)
  const speedFactor = currentSpeed * 0.05; 
  scrollPosition -= speedFactor;
  
  prompterText.style.transform = `translateY(${scrollPosition}px)`;
  
  // Якщо текст прокрутився повністю вгору - зупиняємось
  const textRect = prompterText.getBoundingClientRect();
  if (textRect.bottom < 0) {
    exitPrompter();
    return;
  }
  
  animationFrameId = requestAnimationFrame(scrollLoop);
}

// Запуск суфлера з РЕДАКТОРА (з самого початку)
function startPrompter() {
  const text = textInput.value.trim();
  if (!text) {
    alert("Будь ласка, введіть текст для прокрутки.");
    return;
  }
  
  // Налаштування тексту
  prompterText.textContent = text;
  prompterText.style.fontSize = `${sizeSlider.value}px`;
  
  // Перехід до режиму прокрутки
  editorView.classList.remove('active');
  prompterView.classList.add('active');
  
  // Скидання позиції прокрутки (починаємо з середини екрану для зменшення затримки)
  scrollPosition = window.innerHeight / 2;
  prompterText.style.transform = `translateY(${scrollPosition}px)`;
  
  resumePrompter();
}

// Продовжити прокрутку (без скидання позиції)
function resumePrompter() {
  if (!isPlaying) {
    isPlaying = true;
    voiceStatusPrompter.textContent = "🎤 Слухаю... (в роботі)";
    scrollLoop();
  }
}

// Поставити на паузу (залишаючись в суфлері)
function pausePrompter() {
  isPlaying = false;
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  voiceStatusPrompter.textContent = "🎤 Пауза. Скажіть 'Продовжити' або 'Старт'";
}

// Вихід з суфлера та повернення до редактора
function exitPrompter() {
  pausePrompter();
  prompterView.classList.remove('active');
  editorView.classList.add('active');
}

// Обробники кнопок
startBtn.addEventListener('click', startPrompter);
stopBtn.addEventListener('click', exitPrompter);

// Голосове управління (Web Speech API)
function initVoiceControl() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  
  if (!SpeechRecognition) {
    voiceStatusEditor.textContent = "❌ Ваш браузер не підтримує розпізнавання голосу.";
    voiceStatusEditor.style.color = "var(--danger-color)";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'uk-UA'; // Українська мова
  recognition.continuous = true;
  recognition.interimResults = true; // УВІМКНЕНО для миттєвої реакції

  recognition.onstart = function() {
    console.log("Голосове розпізнавання запущено.");
  };

  recognition.onresult = function(event) {
    const now = Date.now();
    
    // Захист від подвійного спрацьовування (затримка 1.5 секунди між командами)
    if (now - lastCommandTime < 1500) return;

    const lastResultIndex = event.results.length - 1;
    const command = event.results[lastResultIndex][0].transcript.trim().toLowerCase();

    // ЗАХИСТ ВІД ВИПАДКОВОГО СПРАЦЬОВУВАННЯ:
    // Якщо фраза довша за 30 символів, швидше за все людина просто читає текст
    if (command.length > 30) return;

    let commandExecuted = false;

    // Обробка команд
    if (command.includes('старт') || command.includes('продовжити') || command.includes('поїхали')) {
      if (editorView.classList.contains('active')) {
        startPrompter(); // Запуск з нуля
      } else {
        resumePrompter(); // Зняття з паузи
      }
      commandExecuted = true;
    } 
    else if (command.includes('стоп') || command.includes('пауза')) {
      pausePrompter();
      commandExecuted = true;
    }
    else if (command.includes('вгору') || command.includes('назад')) {
      // Відмотати текст назад (зменшити прокрутку, щоб текст опустився нижче)
      scrollPosition += window.innerHeight / 2.5;
      prompterText.style.transform = `translateY(${scrollPosition}px)`;
      commandExecuted = true;
    }
    else if (command.includes('вниз') || command.includes('вперед')) {
      // Прокрутити текст вперед
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
      
      // Зупиняємо і запускаємо розпізнавання, щоб скинути буфер interimResults
      // Це гарантує, що одне слово не викличе команду двічі
      recognition.stop(); 
    }
  };

  recognition.onerror = function(event) {
    console.error("Помилка розпізнавання:", event.error);
    if (event.error === 'not-allowed') {
        voiceStatusEditor.textContent = "❌ Немає доступу до мікрофону.";
    }
  };

  recognition.onend = function() {
    // Перезапуск для безперервного слухання
    recognition.start();
  };

  // Запуск розпізнавання
  try {
    recognition.start();
  } catch(e) {
    console.error(e);
  }
}

// Ініціалізація
window.addEventListener('DOMContentLoaded', () => {
  initVoiceControl();
  // Початковий текст для демо
  textInput.value = "Ласкаво просимо до AI Телесуфлера.\n\nСкажіть 'старт', щоб почати прокрутку.\n\nЦей текст можна редагувати або вставити свій.";
});
