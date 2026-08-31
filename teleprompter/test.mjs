import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  
  await page.setViewport({ width: 375, height: 667, isMobile: true });
  
  page.on('console', msg => {
    console.log('Console:', msg.text());
  });
  
  page.on('response', response => {
    if (response.status() === 404) {
      console.log('404 URL:', response.url());
    }
  });
  
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle0' });
  console.log("Page loaded");
  
  await page.evaluate(() => {
    const btn = document.getElementById('start-btn');
    console.log("Start button is:", btn ? btn.tagName : 'null');
    console.log("Start button text:", btn ? btn.innerText : 'null');
    if (btn) {
      btn.addEventListener('click', () => console.log('Button clicked!'));
      btn.click();
    }
  });
  
  // Wait a bit
  await new Promise(r => setTimeout(r, 1000));
  
  const isActive = await page.$eval('#prompter-view', el => el.classList.contains('active'));
  console.log("Is prompter active?", isActive);
  
  await browser.close();
})();
