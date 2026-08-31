const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  
  // Emulate mobile
  await page.setViewport({ width: 375, height: 667, isMobile: true });
  
  // Catch page errors
  page.on('pageerror', err => {
    console.error('Page error: ', err);
  });
  
  page.on('console', msg => {
    if (msg.type() === 'error') console.log('Console error: ', msg.text());
  });
  
  await page.goto('http://localhost:8000/', { waitUntil: 'networkidle0' });
  
  console.log("Page loaded");
  
  // click start
  await page.click('#start-btn');
  
  // check if prompter view is active
  const isActive = await page.$eval('#prompter-view', el => el.classList.contains('active'));
  console.log("Is prompter active?", isActive);
  
  await browser.close();
})();
