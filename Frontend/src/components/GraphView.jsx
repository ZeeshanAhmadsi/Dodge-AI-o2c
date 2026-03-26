import React, { useState, useEffect, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import axios from 'axios';

const GraphView = ({ botResponseText }) => {
    const [graphData, setGraphData] = useState({ nodes: [], links: [] });
    const [activeNode, setActiveNode] = useState(null);
    const [isMinimized, setIsMinimized] = useState(false);
    const [hideOverlay, setHideOverlay] = useState(false);
    const graphRef = useRef();

    useEffect(() => {
        const fetchGraphData = async () => {
            try {
                const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                const response = await axios.get(`${API_BASE_URL}/api/v1/graph`);
                
                setGraphData({
                    nodes: response.data.nodes || [],
                    links: response.data.edges || []
                });
            } catch (error) {
                console.error("Failed to fetch graph data:", error);
            }
        };

        fetchGraphData();
    }, []);

    useEffect(() => {
        if (!botResponseText || graphData.nodes.length === 0) return;
        
        const escapeRegExp = (string) => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        
        let bestMatchNode = null;
        let lastIndexFound = -1;

        graphData.nodes.forEach(n => {
            const idStr = String(n.id);
            // Use word boundaries to prevent a node ID of "1" from matching the "1" in "2025"
            const regex = new RegExp(`\\b${escapeRegExp(idStr)}\\b`, 'g');
            let match;
            while ((match = regex.exec(botResponseText)) !== null) {
                // Keep the node that was mentioned closest to the END of the assistant's sentence
                if (match.index > lastIndexFound) {
                    bestMatchNode = n;
                    lastIndexFound = match.index;
                }
            }
        });
        
        if (bestMatchNode) {
            const nodeToHighlight = bestMatchNode;
            
            const connections = graphData.links.filter(l => 
                l.source === nodeToHighlight.id || l.target === nodeToHighlight.id || 
                (l.source && l.source.id === nodeToHighlight.id) || 
                (l.target && l.target.id === nodeToHighlight.id)
            ).length;
            
            setActiveNode({ ...nodeToHighlight, connections });
            
            // Wait slightly for ForceGraph loop if the node was just loaded or ensure .x/.y exist
            if (graphRef.current) {
                setTimeout(() => {
                    const latestNode = graphData.nodes.find(n => n.id === nodeToHighlight.id);
                    if (latestNode && latestNode.x !== undefined && latestNode.y !== undefined) {
                        graphRef.current.centerAt(latestNode.x, latestNode.y, 1000);
                        graphRef.current.zoom(8, 2000);
                    }
                }, 100);
            }
        }
    }, [botResponseText, graphData.nodes, graphData.links]);

    const handleNodeClick = (node, event) => {
        const connections = graphData.links.filter(l => 
            l.source === node.id || l.target === node.id || 
            (l.source && l.source.id === node.id) || 
            (l.target && l.target.id === node.id)
        ).length;
        
        setActiveNode({ ...node, connections });
        if (graphRef.current) {
            graphRef.current.centerAt(node.x, node.y, 1000);
            graphRef.current.zoom(8, 2000);
        }
    };

    return (
        <div style={{ width: '100%', height: '100%', background: '#ffffff', position: 'relative', overflow: 'hidden' }}>
            
            {/* Top Left Header UI */}
            <div style={{ position: 'absolute', top: '24px', left: '24px', zIndex: 10, display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {!isMinimized && (
                    <div style={{ fontSize: '1.1rem', color: '#94a3b8', fontWeight: '500', display: 'flex', alignItems: 'center' }}>
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0f172a" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '12px' }}>
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="9" y1="3" x2="9" y2="21"></line>
                        </svg>
                        Mapping <span style={{ margin: '0 8px' }}>/</span> <span style={{ color: '#0f172a', fontWeight: '700' }}>Order to Cash</span>
                    </div>
                )}
                
                <div style={{ display: 'flex', gap: '8px' }}>
                    <button 
                        onClick={() => setIsMinimized(!isMinimized)}
                        style={{ 
                            background: '#ffffff', border: '1px solid #e2e8f0', padding: '8px 16px', 
                            borderRadius: '8px', fontSize: '0.85rem', fontWeight: '600', color: '#0f172a', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', gap: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                        }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            {isMinimized ? (
                                <>
                                    <polyline points="4 14 10 14 10 20"></polyline>
                                    <polyline points="20 10 14 10 14 4"></polyline>
                                    <line x1="14" y1="10" x2="21" y2="3"></line>
                                    <line x1="3" y1="21" x2="10" y2="14"></line>
                                </>
                            ) : (
                                <>
                                    <polyline points="15 3 21 3 21 9"></polyline>
                                    <polyline points="9 21 3 21 3 15"></polyline>
                                    <line x1="21" y1="3" x2="14" y2="10"></line>
                                    <line x1="3" y1="21" x2="10" y2="14"></line>
                                </>
                            )}
                        </svg>
                        {isMinimized ? 'Maximize' : 'Minimize'}
                    </button>
                    <button 
                        onClick={() => setHideOverlay(!hideOverlay)}
                        style={{ 
                            background: hideOverlay ? '#ffffff' : '#0f172a', 
                            border: hideOverlay ? '1px solid #e2e8f0' : 'none', 
                            padding: '8px 16px', 
                            color: hideOverlay ? '#0f172a' : '#ffffff',
                            borderRadius: '8px', fontSize: '0.85rem', fontWeight: '600', cursor: 'pointer',
                            boxShadow: hideOverlay ? '0 1px 3px rgba(0,0,0,0.05)' : '0 4px 6px rgba(15, 23, 42, 0.2)'
                        }}
                    >
                        {hideOverlay ? 'Show Granular Overlay' : 'Hide Granular Overlay'}
                    </button>
                </div>
            </div>

            {/* The Graph */}
            {graphData.nodes.length > 0 ? (
                <ForceGraph2D
                    ref={graphRef}
                    graphData={graphData}
                    nodeId="id"
                    nodeRelSize={4}
                    nodeColor={node => activeNode && activeNode.id === node.id ? '#2563eb' : (node.label === 'JournalEntry' ? '#93c5fd' : '#fca5a5')}
                    linkColor={() => '#e2e8f0'}
                    linkWidth={1}
                    backgroundColor="#ffffff"
                    onNodeClick={handleNodeClick}
                    onBackgroundClick={() => setActiveNode(null)}
                    onEngineStop={() => {
                        if (graphRef.current) {
                            graphRef.current.zoomToFit(400);
                        }
                    }}
                />
            ) : (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: '#94a3b8' }}>
                    Loading Knowledge Graph...
                </div>
            )}

            {/* Floating Node Details Card */}
            {activeNode && !hideOverlay && (
                <div style={{
                    position: 'absolute',
                    top: '50%',
                    left: 'calc(50% - 180px)', // Shift left by 180px from center.
                    transform: 'translate(-100%, -50%)', // Shift left by its own full width, so it sits cleanly to the left of the node
                    background: '#ffffff',
                    padding: '24px',
                    borderRadius: '16px',
                    boxShadow: '0 12px 32px rgba(0,0,0,0.1)',
                    border: '1px solid #f1f5f9',
                    width: '320px',
                    zIndex: 100,
                    pointerEvents: 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    maxHeight: '80%',
                    overflowY: 'auto'
                }}>
                    <h3 style={{ margin: '0 0 4px 0', fontSize: '1.25rem', color: '#0f172a', fontWeight: '800' }}>
                        {activeNode.label === 'JournalEntry' ? 'Journal Entry' : activeNode.label}
                    </h3>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.9rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '4px' }}>
                            <span style={{ color: '#64748b' }}>Entity:</span> 
                            <span style={{ color: '#334155', fontWeight: '500' }}>{activeNode.label}</span>
                        </div>
                        
                        {Object.entries(activeNode.title || activeNode).map(([key, value]) => {
                            // If we are falling back to the root ForceGraph node object, hide internal rendering state
                            if (!activeNode.title && ['id', 'label', 'x', 'y', 'vx', 'vy', 'index', 'connections', 'title', 'color'].includes(key)) return null;
                            
                            // Skip completely null or undefined properties for a cleaner UI
                            if (value === null || value === undefined || value === '') return null;
                            
                            // Hide the duplicate label if it matches the entity header
                            if (activeNode.title && key === 'label') return null;
                            
                            let displayValue = value;
                            if (typeof value === 'object' && value !== null) {
                                displayValue = JSON.stringify(value);
                            }
                            
                            return (
                                <div key={key} style={{ paddingBottom: '4px', wordBreak: 'break-word' }}>
                                    <span style={{ color: '#64748b', marginRight: '4px' }}>{key}:</span> 
                                    <span style={{ color: '#334155', fontWeight: '500' }}>
                                        {String(displayValue)}
                                    </span>
                                </div>
                            );
                        })}
                        
                        <div style={{ fontWeight: '500', color: '#64748b', fontSize: '0.9rem', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e2e8f0' }}>
                            Connections: {activeNode.connections}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default GraphView;
