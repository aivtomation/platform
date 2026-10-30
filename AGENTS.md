# Aivtomation Multi-Product & CRM Unit Economics Standard

> **MANDATORY SYSTEM DIRECTIVE FOR ALL AGENTS & SESSIONS:**
> Whenever building, modifying, or architecting products in the **Aivtomation** ecosystem (Crossposting, Real Estate Photo Editor, OpenVoice, Teleprompter, etc.), you MUST strictly follow this unified schema and architectural contract. No product is allowed to have isolated billing, disconnected users, or unmonitored server/API expenses.

---

## 1. Single Identity & Unified Accounts
- All products MUST authenticate against the single central table `aiv_clients`.
- Primary Key: `aiv_clients.id`.
- Session Management: Always initialize via `require_once __DIR__ . '/session_helper.php'; $user = initAivSession();`.
- Cookie standards: `aiv_auth_token` and `crossposter_auth` stored on root domain `/`.
- Never create standalone, product-isolated user databases.

## 2. Unified Credit Wallet (`CreditManager`)
- All consumable actions across all products (AI photo editing, video montage, subtitles generation, voice cloning, extra daily posts) MUST consume credits via `CreditManager::charge($clientId, $amount, $service, $description, $refId)`.
- Top-ups MUST only be processed via the central payment pipeline (`wayforpay_topup.php`, `wayforpay_callback.php`, or crypto/manual admin top-up) using `CreditManager::add()`.
- Every product MUST define its credit cost clearly in constants or config (e.g. 1 photo upscale = 1 credit, 1 min AI video subtitles = 2 credits).

## 3. Product Identification (`product_slug`)
Every product must be identified across transactions, logs, and CRM by a registered slug:
- `crossposting` — SMM Auto-Crossposting to 8 platforms & AI montage.
- `social_downloader` — Universal Social Media Downloader (TikTok, Instagram, YouTube, Facebook, Twitter, Threads).
- `real_estate_editor` — Batch AI photo enhancement & virtual renovation.
- `openvoice` — AI voice cloning and audio generation.
- `teleprompter` — Voice-controlled smart teleprompter.
- `agency_services` — Custom B2B automation services.

## 4. Hardware, Energy & API Unit Economics Contract (`aiv_resource_logs`)
Every background worker, render job, or API request MUST record its exact unit costs for the CRM platform:
1. **API Costs**:
   - OpenAI Whisper: recorded per audio minute ($0.006/min) converted to UAH.
   - LLM (GPT-4o / Claude / Gemini): input/output tokens logged with cost.
2. **Local Hardware Compute Time**:
   - `gpu_duration_sec` & `cpu_duration_sec`.
3. **Electricity Cost Formula (Tariff: 4.24 UAH / kWh)**:
   - Peak GPU load (RTX 3080 + Ryzen 5900X system) ~ 520W (0.52 kW).
   - Moderate CPU load ~ 180W (0.18 kW).
   - Formula:
     $$\text{kWh} = \frac{\text{Watts}}{1000} \times \frac{\text{Seconds}}{3600}$$
     $$\text{Cost}_{\text{Electricity}} = \text{kWh} \times 4.24 \text{ UAH}$$
4. **Hardware Amortization & Wear**:
   - Depreciated rate: `0.0007 UAH / second` of GPU compute.
5. **Total COGS**:
   $$\text{COGS} = \text{API Cost} + \text{Cost}_{\text{Electricity}} + \text{Cost}_{\text{Hardware}} + \text{Bandwidth/Storage}$$

## 5. Traffic Attribution & Customer Acquisition Cost (CAC)
- Every registration must capture attribution metadata: `traffic_source`, `utm_source`, `utm_campaign`, `utm_medium`, `referral_code`.
- Registrations flow through `/crossposting/app/api_client.php` (Google OAuth, Telegram Login, Email verification). This endpoint records UTMs directly into `aiv_clients`.
- The CRM platform allows assigning or calculating `cac_cost_uah` per client or per campaign.
- Unit Economics per Client:
  $$\text{Gross Profit} = \text{Revenue (LTV)} - \text{COGS}$$
  $$\text{Contribution Margin} = \text{Gross Profit} - \text{CAC}$$
  $$\text{Margin \%} = \frac{\text{Gross Profit}}{\text{Revenue}} \times 100\%$$

## 6. Hostinger Infrastructure Quota: Node.js Applications (Max 5 Apps)
> **HARD LIMIT:** Hostinger Business hosting plan permits **at most 5 managed Node.js applications**.
> 
> - **Compilation Strategy**: Whenever building frontends in Next.js or Vite (e.g. `crossposting/dashboard`, `teleprompter`), always prioritize static exports (`next.config.ts` -> `output: 'export'`, or Vite `npm run build` -> `dist/`). This allows the app to run directly via LiteSpeed without occupying a Node.js daemon slot.
> - **Slot Allocation**: A Node.js slot may only be consumed when persistent Node.js runtime/SSR/WebSockets are required.
> - **Never spin up a 6th Node.js app** without archiving or consolidating an existing one.

## 7. Autonomous AI SRE & Self-Healing Architecture (`aiv_problem_logs` + GPT-5.5)
Whenever any product or background worker encounters an execution or API failure (SMM posting, video render, AI model call, auth expiration), it MUST NOT fail silently or spawn separate error tables:
1. **Single Knowledge Base (`aiv_problem_logs`)**:
   - Every incident is indexed by `platform`, `error_signature` (SHA256 signature hash), `error_message`, and `occurrence_count`.
   - Never create duplicate error tables.
2. **AI Diagnostic & Remediation Engine**:
   - Model: **GPT-5.5** (`gpt-5.5-2026-04-23`), with fallback to `gpt-5.4`.
   - Input context: full error trace + exact codebase poster/worker file context (up to 5500 chars).
   - Knowledge Base Caching: If `error_signature` already exists in `aiv_problem_logs`, the cached recipe is applied instantly (1-2 ms) at **0.00 UAH ($0.00)** cost.
   - Novel bugs incur ~0.35–0.50 UAH ($0.008–$0.012) logged in `aiv_resource_logs`.
3. **Two-Tier Auto-Healing Contract**:
   - **Tier 1 (Runtime Auto-Heal & Retry)**: Automated payload sanitization (`slice_media_10`, `shorten_caption`, `refresh_token`, `strip_location`, `delay_retry`) followed by immediate execution retry.
   - **Tier 2 (Safe Sandboxed Code Patching)**: Restricted strictly to whitelisted workers/posters (`libs/*Poster.php`). MUST create an atomic timestamped backup in `backups/` and pass PHP syntax linting (`token_get_all` + `php -l`) prior to writing.
4. **Human-in-the-Loop (Telegram `@log_problems_aivtomation_bot`)**:
   - Immediate Telegram alert with incident summary, diagnosis, action taken, and a 1-click Rollback URL.
   - Formatted 1-click Antigravity prompt block for human verification in chat:
     `"Перевір автоматичне виправлення багу #ID: [Platform: X, Error: Y]. Чи все зроблено вірно?"`
5. **Circuit Breaker & Anti-Loop Safeguards**:
   - **LLM Rate Limiter**: Maximum 3 AI SRE calls per client per 15-minute window (checked via `aiv_resource_logs`). If exceeded, trips safe fallback (`circuit_breaker_cooldown`, 0 токенів / 0.00 UAH).
   - **Telegram Anti-Flood**: Cooldown of 15 minutes per error signature or job ID to prevent alert storming.
   - **Database Deduplication**: Repeated errors within 15 minutes increment `occurrence_count` on the existing row instead of spawning duplicate entries.
   - **UI Max Retries (Max 3)**: Each job tracks `retry_count`. After 3 failed attempts, the UI locks the retry action with `Спроб вичерпано (3/3)` and guides user to token renewal or support.

---
*Created: October 2026 | Antigravity AI Engine for Aivtomation Ecosystem*

