# LinkedOut Chrome Extension

A Chrome extension that enriches LinkedIn profiles by extracting data via LinkedIn's Voyager API and saving it to the LinkedOut backend. It also finds the best introduction paths to any profile through mutual connections.

## Prerequisites

- Node.js 18+
- Chrome browser
- LinkedOut backend running at `http://localhost:8000`

## Development

```bash
npm install
npm run dev
```

Then load the extension in Chrome:
1. Go to `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked" and select the `.output/chrome-mv3-dev` directory

## Build

```bash
npm run build
```

Output is in `.output/chrome-mv3/`.

## Type Check

```bash
npx tsc --noEmit
```

## Architecture

The extension uses four execution contexts:

| Context | File | Responsibility |
|---------|------|----------------|
| MAIN world | `voyager.content.ts` | Voyager API calls, mutual connection extraction |
| ISOLATED world | `bridge.content.ts` | Message relay between MAIN ↔ service worker |
| Service worker | `background.ts` | Orchestration: freshness checks, rate limiting, backend API |
| Side panel | `sidepanel/App.tsx` | React UI for profile status, rate limits, Best Hop results |

See `lib/messages.ts` for the full message contract between contexts.
