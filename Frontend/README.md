# Dodge AI - Frontend

This is a premium, split-pane React frontend for the Dodge AI Order-to-Cash (O2C) Graph Explorer. It features an interactive 2D Graph visualization of the database alongside an AI Chatbot that parses natural language queries into Cypher statements.

## 🚀 Features

- **Interactive Graph Visualization**: Uses `react-force-graph-2d` to render Neo4j nodes (Customers, Products, Sales Orders, Journal Entries).
- **Auto-Highlighting Flow**: Any nodes or lineage paths discovered by the AI are automatically centered, zoomed, and highlighted in the graph interface.
- **Granular Overlay**: Clicking any node brings up a beautiful details card that dynamically pulls the flat JSON properties from the graph.
- **Dynamic Property Filtering**: Selectively hides internal graph state mapping fields (x, y, index) to ensure only strictly relevant business data is shown to the user.

## 📦 Getting Started

### Prerequisites
- Node.js (v18+)
- Output from the Backend FastAPI server running on port `8000`.

### Installation
1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

### 🔧 Environment Variables
Create a `.env` file in the root if your backend runs on a custom domain instead of localhost:
```env
VITE_API_URL=http://localhost:8000
```
