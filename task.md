# Graph-Based Data Modeling and Query System
## 1. Project Setup
- [x] Repurpose `swiftex-sense` backend (FastAPI).
- [x] Repurpose `swiftex-sense-client` frontend (React/Vite).
- [x] Clear unnecessary relational Database boilerplate.

## 2. Data Ingestion & Graph Construction
- [x] Download and analyze the dataset.
- [x] Define Graph Schema (Nodes, Edges).
- [x] Write Python script to parse dataset and load into Neo4j.

## 3. Backend API Development
- [x] Create endpoint for fetching graph data (nodes and edges) for visualization.
- [x] Integrate LLM (Gemini/Groq/etc.) with LangChain for Text-to-Cypher capability.
- [x] Create endpoint for chat/query processing.
- [x] Implement Guardrails to restrict queries to dataset context.

## 4. Frontend UI Development
- [x] Build layout (Graph view on left, Chat on right).
- [x] Implement Graph visualization component (using `react-force-graph` or `cyctoscape.js`).
- [x] Implement Chat Interface component.
- [x] Connect Frontend to Backend APIs.

## 5. Testing & Refinement
- [ ] Test complex queries (trace document flow, identify broken flows).
- [ ] Refine LLM prompts to ensure accurate and grounded responses.
- [ ] Test guardrails against off-topic questions.

## 6. Deployment & Submission
- [ ] Deploy backend (e.g., Render/Railway).
- [ ] Deploy frontend (e.g., Vercel/Netlify).
- [ ] Write README with architectural decisions and prompting strategy.
- [ ] Prepare session logs for submission.
