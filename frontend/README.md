# Prior frontend

React + Vite + TypeScript app with two screens: **Discover** (goal, skill chips, filters, skill chart, learning path, courses with Honest Advisor, What-If, feedback) and **Evaluation** (the saved report). Setup, usage and troubleshooting are in the [root README](../README.md).

```powershell
npm ci
npm run dev       # http://localhost:5173, proxies /api to the backend on 127.0.0.1:8100 (override with PRIOR_API)
npm run build     # type-check and production build into dist/
npm run preview   # serve dist/ on port 4173 with the same proxy
npm run lint
```

- `src/types.ts` mirrors `backend/app/schemas.py`; change both together.
- `src/api.ts` is the only place that calls the service.
- All skill, gap, path and explanation logic lives in the backend. The UI only displays what `/recommend` returns, so what the student sees is what the evaluation measures.
- Styling is plain CSS with shared tokens in `src/styles/tokens.css` (light and dark).
