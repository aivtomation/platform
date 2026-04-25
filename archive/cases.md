<!-- wp:html -->
<div class="white-background">
<h1 style="text-align: center; margin-bottom: 20px;">КЕЙСИ</h1>

<!-- Вступний текст -->
<p style="text-align: center; margin-bottom: 40px;">Кожний кейс представлений нище — це окрема позитивна історія, що дала збільшення продажів, впізнаванність бренду та залучення нових клієнтів.</p>
</div>
<!-- /wp:html -->

<!-- wp:html {"UAGDisplayConditions":"none","UAGResponsiveConditions":true} -->
<div class="video-gallery-container">
    <div class="video-gallery">
        <!-- Video items will be generated via JavaScript -->
    </div>

    <!-- Modal for video popup -->
    <div id="video-modal" class="modal">
        <div class="modal-content">
            <span class="close-modal">&times;</span>
            <div class="modal-video-container">
                <iframe id="modal-video-iframe" frameborder="0" allowfullscreen></iframe>
            </div>
            <h2 id="modal-title"></h2>
            <div id="modal-description"></div>
            <div class="modal-buttons">
                <a href="https://aivtomation.com/services/" class="modal-button order-button">Замовити</a>
                <a href="tel:+380980290343" class="modal-button phone-button">Телефон</a>
            </div>
        </div>
    </div>
</div>

<style>
/* Gallery Styles */
.video-gallery-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.video-gallery {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-gap: 20px;
}

.video-item {
    margin-bottom: 20px;
}

.video-thumbnail {
    position: relative;
    overflow: hidden;
    border-radius: 15px;
    cursor: pointer;
}

.video-thumbnail img {
    width: 100%;
    height: auto;
    display: block;
    transition: transform 0.3s ease;
}

.video-thumbnail:hover img {
    transform: scale(1.05);
}

.play-icon {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 60px;
    height: 60px;
    background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23ffffff"><path d="M8 5v14l11-7z"/></svg>');
    background-size: contain;
    background-repeat: no-repeat;
    opacity: 0.8;
    transition: opacity 0.3s ease;
}

.video-thumbnail:hover .play-icon {
    opacity: 1;
}

.video-title {
    margin-top: 10px;
    font-size: 16px;
    font-weight: 600;
    text-align: center;
    cursor: pointer;
}

/* Modal Styles */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.8);
    z-index: 1000;
    overflow: auto;
}

.modal-content {
    position: relative;
    background-color: #fff;
    margin: 5% auto;
    padding: 20px;
    width: 80%;
    max-width: 800px;
    border-radius: 15px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

.close-modal {
    position: absolute;
    top: 10px;
    right: 20px;
    color: #aaa;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
    z-index: 1100;
}

.close-modal:hover {
    color: #000;
}

.modal-video-container {
    position: relative;
    padding-bottom: 56.25%; /* 16:9 aspect ratio */
    height: 0;
    overflow: hidden;
    border-radius: 15px;
    margin-bottom: 20px;
}

.modal-video-container iframe {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

#modal-title {
    font-size: 24px;
    margin-top: 20px;
    margin-bottom: 10px;
}

#modal-description {
    font-size: 16px;
    line-height: 1.5;
    margin-bottom: 20px;
}

#modal-description p {
    margin-bottom: 10px;
}

.modal-buttons {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 20px;
}

.modal-button {
    display: inline-block;
    padding: 12px 24px;
    background-color: #dd183b;
    color: white;
    text-decoration: none;
    border-radius: 5px;
    font-weight: bold;
    transition: background-color 0.3s ease;
}

.modal-button:hover {
    background-color: #b8132f;
}

/* Responsive styles */
@media (max-width: 768px) {
    .video-gallery {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .modal-content {
        width: 95%;
        margin: 10% auto;
    }
    
    .modal-buttons {
        flex-direction: column;
        gap: 10px;
    }
    
    .modal-button {
        display: block;
        text-align: center;
    }
}

@media (max-width: 480px) {
    .video-gallery {
        grid-template-columns: 1fr;
    }
}
</style>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Video data with properly formatted descriptions
    const videoData = [
        {
            id: 'FXON5_DZPAY',
            title: '800 тис. переглядів за ролик',
            description: `Ця компанія вже мала досвід відеозйомки і вела свій Youtube канал до звернення в AIVTOMATION.  

Ми разом обговорили стратегію і бачення на 2024 рік, вказали на те, що залишимо, і те що потрібно змінити. 
Результат не заставив себе довго чекати. Третє відео стрельнуло і наразі набрало уже 803 тисячі переглядів і додало +10 тисяч нових підписників, тобто таку ж саму кількість яка була до цього на каналі.

Також канал підключений до монетизації Youtube і приніс власнику в 10 ки разів більше коштів ніж він затратив за наші послуги.
 
І найголовніше його телефон зараз розривається від дзвінків його клієнтів які переглянули його відео.
Ми далі працюємо і стабільно випускаємо по 2 відео ролика в тиждень.`,
            customThumbnail: ''
        },
        {
            id: 'CHrrQtCbe04',
            title: 'Показати найкомфортнішу поїздку',
            description: `Компанія пасажирських перевезень, через 3D анімацію, показала, що їх автобуси найкомфортніші, а водії найвічиливіші.

Ми показали: автоматичне відкривання дверей, висувні сходинки, поручні, зручні регульовані крісла, usb входи, безлімітний WI-Fi та привітного водія у білій сорочці.

Тепер клієнти цієї компанію мають уявлення, що до них приїде найкомфотніший новесенький Opel Movano з охайним і привітним водієм.`,
            customThumbnail: ''
        },
        // Остальные видео сохраняются без изменений
        {
            id: 'eGJaz_uRgrk',
            title: 'Промо для концерту',
            description: `До нас звернулись організатори концерту співачки Jerry Heil.

Задача була проста, зробити промо-ролик для концерту, щоб максимальна кількість глядачів прийшла на цей виступ.

Так як треба було зробити це швидко, ми вирішили зробити 2D анімацію, з використанням кадрів з концертів Jerry Heil.

Результатом нашої успішної роботи був забитий зал в БК "Дружби Народів".`,
            customThumbnail: ''
        },
        {
            id: 't3uS4m9ihOQ',
            title: 'Відеокаталог продукту HYBRID™',
            description: `Це один із наших перших клієнтів, що постійно замовляє відео по цей час. 

Власник компанії має декілька продуктів, один із них HYBRID™ - система керамічного опалення.

Наша задача була показати всьому світу цей продукт у трьох варіантах. Просто показувати характеристики в PDF файлі нудна історія. Тому треба було все це оживити.

Результатом такого відео була більша залученість і зацікавленість продуктом HYBRID™. Відео стало своєрідним вирішенням для тих хто ще не визначився яку саме панель опалення йому купити. 

Наразі компанія у своїй ніші займає перше місце в Україні і лідируючі місця у світі.`,
            customThumbnail: ''
        },
        {
            id: 'YSD1A0E0en8',
            title: 'Анімація лого COSMOLOT',
            description: `Задача була показати преміальність компанії через їх логотип.

Обрали 3D анімацію лого з використанням текстури золота. 

Анімація вийшла лаконічною і вишуканою одночасно. Головне, що замовнику сподобалось.`,
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-6.jpg'
        },
        {
            id: 'spSdUsKUuew',
            title: '№1 по ключовому запиту в Google та YouTube',
            description: `Замовник - власник інтернет магазину одягу. Один із видів його одягу це компресійний одяг.

Наша ціль була стати лідером продаж у ніші саме компресійного одягу. Тому крім відеооглядів, які продають його товар ми почали робити корисний і цікавий контент про властивості, переваги та недоліки компресійного одягу. Результат не заставив себе чекати:

Якщо в Google ви введете "компрессионная одежда видео", то на першому місці вам покаже цей відеоролик. 

Якщо в YouTube ви введете "компрессионная одежда", то також побачите нас на першій сходинці. 

Для досягення цілі вийти в топ Google і Youtube, фундаментальним інструментом для нас було CEO просування. І аналізуючи конкурентів ми уже 7 років знаходимось на першій сходинці по ключовому запиту.`,
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-7.jpg'
        },
        {
            id: 'nLS_GKNJwzQ',
            title: 'Моршинська Pine Water',
            description: `Для організації святкового заходу компанії "Моршинська" треба було зробити ролик на LED екрані, щоб показити один із видів продукту "Pine Water".

Для оптимізації часу ми купили проект на майданчику стоків. Потім взялись за формування дизайну на жестянній баночці "Моршинська".
Далі трохи погрались з кольорами і в результаті вийшов такий от ролик.

Замовнику сподобалось, а це найголовніше.`,
            customThumbnail: ''
        },
        {
            id: 'gZXDnnGEkB0',
            title: 'Проста анімація лого Transfer',
            description: `Замовник - компанія, що займається пасажирськими перевезення ми по Україні.

Активно співпрацюємо з 2018 року. Цей раз була задача анімувати лого яке буде перед кожним наступним відео компанії.

Замовник одобрив анімацію без жодної правки, що може бути кращим?`,
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-8.jpg'
        },
        {
            id: 'JIF6t9aeUNs',
            title: '"Майфон" - анімація лого',
            description: `"Майфон" - мережа магазинів мобільних телефонів. 

Замовнику треба було анімувати лого до 10 секунд, щоб це була проста, але зрозуміла анімація.

Результат вийшов досить гарний і власник щедро оплатив проект.`,
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-5.jpg'
        },
        {
            id: '1Sz2bTBjwz4',
            title: 'Лого для відеографа',
            description: `Знайомий відеограм попросив анімувати лого його компанії. 

Основне прохання, щоб це була проста і легка анімація, без нагруженості спецефектами.

Після декількох правок вийшов такий от результат.`,
            customThumbnail: ''
        },
        {
            id: 'GgzV0D4Q6jY',
            title: 'Анімація лого для фітнес клубу',
            description: `Нам дали картинку і сказали зробити, щось просте на свій розсуд. 

Ми загнали картинку в 3D програму і відобразили лого в 3D форматі. Занімували як котиться гриф з блінами в руки персонажа з лого, який робить станову тягу.

Замовнику така ідея зайшла і ми успішно закрили проект.`,
            customThumbnail: ''
        },
        {
            id: '1VZjkNdkBQ8',
            title: 'Анімація для мобільного застосунку',
            description: `Один із топових моушн дизайнерів займається на майданчиках для відеостоків. Він попросив нас зробити заготовку для мобільного додатку на IOS.

Збоку мав підлітати айфон, а зліва мав бути короткий опис тексту. Про додаток і його можливості.`,
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-4.jpg'
        },
        {
            id: 'u58Qe5LY6r0',
            title: '7 переваг продукту',
            description: 'Було чітке технічне завдання від власника бізнесу, котрі займаються системами керамічних панелей. Була задача максимально дуступно і лаконічно показати 7 переваг їх продукту. Ми використали слайдшоу картинок з невеликими блоками тексту. Власнику сподобалось. Ціль була досягнути.',
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-2.jpg'
        },
        {
            id: 'aOrQzE805hM',
            title: 'Анімація лого організації заходів',
            description: 'Надіслали картинку-лого в звичайні якості. Технічне завдання було коротке: "анімуйте лого". Переглянули чим займається компанія, щоб створити відповідний настрій анімації. Вони займаються технічною підтримкою заходів: сцени, світло, костюми, шатри, мультимедіа, меблі, караоке та інше. Збільшили картинку в 4 рази так як вона була не досить якісна. Перевели її у вектор і розбили на шари. Закинули в програму After Effects і зробили відповідну анімацію до свого бачення. Додали трохи аудіодизайну. Відправили в потрібному форматі замовнику на затвердження. Отримали позитивну відповідь і оплату роботи.',
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-3.jpg'
        },
        {
            id: 'isLMJ9SPQ10',
            title: 'Запрошення до нового магазину "Спартак"',
            description: 'Магазин мобільних аксесуарів "Спартак" відкрив новий магазин у центрі міста Черкас. Потрібно було зробити відеозапрошення для нових відвідувачів, вказати де саме магазин і що в ньому продається. Після успішного промо проекту в перші дні до магазину завітала максимальна кількість покупців мобільних аксесуарів. Власник залишився максимально задоволеним. ',
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Screenshot_36.jpg'
        },
        {
            id: 'SC9VWbTdAPQ',
            title: 'Анімація QR коду',
            description: 'Нам надіслали просто картинку QR коду і сказали зробити його анімацію для рекламних LED екранів. Протягом 4х годин ми відправили результат, бо замовлення було термінове.',
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/Untitled-1.jpg'
        },
        {
            id: 'nxY-65J0rSo',
            title: 'Перші в Google та YouTube',
            description: 'Замовник власник інтернет магазину одягу. Один із брендів які він продає, є відома американська фірма Under Armour. Наша ціль була стати лідером продаж у ніші продажу саме цієї фірми одягу фірми Under Armour. Тому крім відеооглядів які продають його товар ми почали робити корисний і цікавий контент про цю компанію. Результат не заставив себе чекати: Якщо в Google ви введете "где производят Under Armour", то на першому місці вам покаже цей відеоролик. Якщо в YouTube ви введете "где производят Under Armour", то також побачите нас на першій сходинці. Для досягення цілі вийти в топ Google і Youtube, фундаментальним інструментом для нас було  CEO просування. І аналізуючи конкурентів ми уже 7 років знаходимось на першій сходинці по ключовому запиту.',
            customThumbnail: 'https://aivtomation.com/wp-content/uploads/2025/03/prewiews_services/maxresdefault.jpg'
        },
        {
            id: 'wwrGPDjfIrA',
            title: 'Hi-tech рушникосушка',
            description: 'В даному відео показана інструкція з користування скляною рушникосушкою ONYX. Це новинка на ринку України, для якої ми зробили відповідне відео і вказали на її сильні сторони і легкість в кориттуванні одним дотиком пальця. Послуга називається зйомка + монтаж, тому якщо вам потрібна жива говоряча людина або справжня картинка то замовляйте саме цю послугу. ',
            customThumbnail: ''
        },
    ];
    
    // Generate video items
    const videoGallery = document.querySelector('.video-gallery');
    
    videoData.forEach((video, index) => {
        const videoItem = document.createElement('div');
        videoItem.className = 'video-item';
        
        // Определяем URL для превью - используем пользовательское, если оно есть и не пустое
        const thumbnailUrl = (video.customThumbnail && video.customThumbnail.trim() !== '') 
            ? video.customThumbnail 
            : `https://img.youtube.com/vi/${video.id}/maxresdefault.jpg`;
        
        videoItem.innerHTML = `
            <div class="video-thumbnail" data-video-id="${video.id}">
                <img src="${thumbnailUrl}" alt="${video.title}" onerror="this.onerror=null; this.src='https://img.youtube.com/vi/${video.id}/maxresdefault.jpg';">
                <div class="play-icon"></div>
            </div>
            <h3 class="video-title">${video.title}</h3>
        `;
        
        videoGallery.appendChild(videoItem);
    });
    
    // Elements
    const videoItems = document.querySelectorAll('.video-thumbnail');
    const videoTitles = document.querySelectorAll('.video-title');
    const modal = document.getElementById('video-modal');
    const modalVideo = document.getElementById('modal-video-iframe');
    const modalTitle = document.getElementById('modal-title');
    const modalDescription = document.getElementById('modal-description');
    const closeModal = document.querySelector('.close-modal');
    
    // Check if device is mobile
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    // Play video on hover for desktop devices
    if (!isMobile) {
        videoItems.forEach((item, index) => {
            const videoId = item.getAttribute('data-video-id');
            
            item.addEventListener('mouseenter', function() {
                // Create and append iframe for hover preview
                const previewIframe = document.createElement('iframe');
                previewIframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&controls=0&modestbranding=1&showinfo=0&rel=0`;
                previewIframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
                previewIframe.classList.add('hover-video');
                previewIframe.style.position = 'absolute';
                previewIframe.style.top = '0';
                previewIframe.style.left = '0';
                previewIframe.style.width = '100%';
                previewIframe.style.height = '100%';
                previewIframe.style.border = 'none';
                previewIframe.style.zIndex = '1';
                
                // Remove image and play icon while hovering
                const img = item.querySelector('img');
                const playIcon = item.querySelector('.play-icon');
                img.style.visibility = 'hidden';
                playIcon.style.visibility = 'hidden';
                
                // Add iframe
                item.appendChild(previewIframe);
            });
            
            item.addEventListener('mouseleave', function() {
                // Remove iframe and restore image and play icon
                const hoverVideo = item.querySelector('.hover-video');
                if (hoverVideo) {
                    item.removeChild(hoverVideo);
                }
                
                const img = item.querySelector('img');
                const playIcon = item.querySelector('.play-icon');
                img.style.visibility = 'visible';
                playIcon.style.visibility = 'visible';
            });
        });
    }
    
    // Open modal on click (for both desktop and mobile)
    function openVideoModal(index) {
        const video = videoData[index];
        
        // Set modal content
        modalVideo.src = `https://www.youtube.com/embed/${video.id}?autoplay=1&rel=0`;
        modalTitle.textContent = video.title;
        
        // Format description with paragraphs
        const formattedDescription = video.description.replace(/\n\n/g, '<p></p>').replace(/\n/g, '<br>');
        modalDescription.innerHTML = formattedDescription;
        
        // Show modal
        modal.style.display = 'block';
        
        // Prevent body scrolling
        document.body.style.overflow = 'hidden';
    }
    
    // Click event for video thumbnails
    videoItems.forEach((item, index) => {
        item.addEventListener('click', function(e) {
            openVideoModal(index);
        });
    });
    
    // Click event for video titles
    videoTitles.forEach((title, index) => {
        title.addEventListener('click', function(e) {
            openVideoModal(index);
        });
    });
    
    // Close modal
    closeModal.addEventListener('click', function() {
        modal.style.display = 'none';
        modalVideo.src = '';
        document.body.style.overflow = 'visible';
    });
    
    // Close modal when clicking outside the content
    window.addEventListener('click', function(e) {
        if (e.target === modal) {
            modal.style.display = 'none';
            modalVideo.src = '';
            document.body.style.overflow = 'visible';
        }
    });
});
</script>
<!-- /wp:html -->

<!-- wp:paragraph {"className":"/* Стилі для галереї */ .video-gallery {     display: grid;     grid-template-columns: repeat(3, 1fr);     gap: 20px;     padding: 20px; }  .video-item {     border-radius: 15px;     overflow: hidden;     position: relative; }  .video-item iframe {     border-radius: 15px; }  .video-item h3 {     text-align: center;     margin-top: 10px;     font-size: 16px; }  /* Мобільна версія */ @media (max-width: 768px) {     .video-gallery {         grid-template-columns: 1fr;     } }  /* Стилі для модального вікна */ .modal {     display: none;     position: fixed;     z-index: 1;     left: 0;     top: 0;     width: 100%;     height: 100%;     overflow: auto;     background-color: rgba(0, 0, 0, 0.4); }  .modal-content {     background-color: #fefefe;     margin: 10% auto;     padding: 20px;     border: 1px solid #888;     width: 80%;     max-width: 900px;     display: flex;     position: relative; }  .modal-video {     flex: 1; }  .modal-text {     flex: 1;     padding-left: 20px; }  .modal-text h2 {     margin-top: 0; }  .close {     position: absolute;     top: 10px;     right: 10px;     font-size: 24px;     cursor: pointer;     background: none;     border: none; }  .buttons {     margin-top: 20px; }  .button {     padding: 10px 20px;     background-color: #dd183b;     color: white;     text-decoration: none;     border-radius: 5px;     margin-right: 10px;     display: inline-block; }"} -->
<p class="/* Стилі для галереї */ .video-gallery {     display: grid;     grid-template-columns: repeat(3, 1fr);     gap: 20px;     padding: 20px; }  .video-item {     border-radius: 15px;     overflow: hidden;     position: relative; }  .video-item iframe {     border-radius: 15px; }  .video-item h3 {     text-align: center;     margin-top: 10px;     font-size: 16px; }  /* Мобільна версія */ @media (max-width: 768px) {     .video-gallery {         grid-template-columns: 1fr;     } }  /* Стилі для модального вікна */ .modal {     display: none;     position: fixed;     z-index: 1;     left: 0;     top: 0;     width: 100%;     height: 100%;     overflow: auto;     background-color: rgba(0, 0, 0, 0.4); }  .modal-content {     background-color: #fefefe;     margin: 10% auto;     padding: 20px;     border: 1px solid #888;     width: 80%;     max-width: 900px;     display: flex;     position: relative; }  .modal-video {     flex: 1; }  .modal-text {     flex: 1;     padding-left: 20px; }  .modal-text h2 {     margin-top: 0; }  .close {     position: absolute;     top: 10px;     right: 10px;     font-size: 24px;     cursor: pointer;     background: none;     border: none; }  .buttons {     margin-top: 20px; }  .button {     padding: 10px 20px;     background-color: #dd183b;     color: white;     text-decoration: none;     border-radius: 5px;     margin-right: 10px;     display: inline-block; }"></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p></p>
<!-- /wp:paragraph -->