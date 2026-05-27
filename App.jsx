import React, { useState, useMemo, useEffect } from "react";

const ACCENT = "#FF6B35";
const GREEN = "#00C853";
const BLUE = "#3B82F6";
const PURPLE = "#A78BFA";
const STEEL = "#0A0C14";
const PANEL = "#11151F";
const BORDER = "#1F2635";
const MUTED = "#8A95A8";
const TEXT = "#E8ECF1";

const DEFAULT_METRICS = {
  mrr: 6500,
  customers: 20,
  newCustomers: 1.5,
  lostPerYear: 1.5,
  marketingSpend: 400
};

export default function App() {
  const = useState("pricing");
  const = useState(DEFAULT_METRICS);

  const updateMetrics = (field, value) => {
    setMetrics(prev => ({ ...prev, : value }));
  };

  const calculated = useMemo(() => {
    const { mrr, customers, newCustomers, lostPerYear, marketingSpend } = metrics;
    const aov = customers > 0 ? Math.round(mrr / customers) : 0;
    const monthlyChurn = lostPerYear / 12;
    const churnRate = customers > 0 ? (monthlyChurn / customers * 100).toFixed(2) : 0;
    const ltv = churnRate > 0 ? Math.round(aov * 100 / churnRate) : 0;
    const cac = newCustomers > 0 ? Math.round(marketingSpend / newCustomers) : 0;
    const ratio = cac > 0 ? (ltv / cac).toFixed(1) : 0;

    return { aov, churnRate, ltv, cac, ratio: parseFloat(ratio) };
  }, );

  return (
    <div style={{ background: STEEL, color: TEXT, minHeight: "100vh", padding: "20px", fontFamily: "system-ui" }}>
      <h1 style={{ fontSize: "24px", marginBottom: "20px" }}>CrewRoute OS</h1>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px", flexWrap: "wrap" }}>
        { .map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "10px 16px",
              borderRadius: "8px",
              background: activeTab === tab ? ACCENT : PANEL,
              color: activeTab === tab ? "#000" : TEXT,
              border: "none",
              fontWeight: "bold"
            }}
          >
            {tab === "pricing" ? "Pricing Simulator" : "LTV / CAC / AOV"}
          </button>
        ))}
      </div>

      {/* Pricing Tab */}
      {activeTab === "pricing" && (
        <div style={{ background: PANEL, padding: "20px", borderRadius: "12px" }}>
          <h2>Pricing Simulator</h2>
          <p>Photo upload and pricing engine will go here.</p>
        </div>
      )}

      {/* Business Metrics Tab */}
      {activeTab === "metrics" && (
        <div style={{ background: PANEL, padding: "20px", borderRadius: "12px" }}>
          <h2>Business Metrics</h2>
          
          <div style={{ marginTop: "20px" }}>
            <label>Monthly Revenue (MRR): </label>
            <input 
              type="number" 
              value={metrics.mrr} 
              onChange={(e) => updateMetrics('mrr', parseFloat(e.target.value) || 0)}
              style={{ width: "100%", padding: "8px", marginTop: "5px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }}
            />
          </div>

          <div style={{ marginTop: "15px" }}>
            <label>Number of Customers: </label>
            <input 
              type="number" 
              value={metrics.customers} 
              onChange={(e) => updateMetrics('customers', parseInt(e.target.value) || 0)}
              style={{ width: "100%", padding: "8px", marginTop: "5px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }}
            />
          </div>

          <div style={{ marginTop: "15px" }}>
            <label>New Customers per Month: </label>
            <input 
              type="number" 
              value={metrics.newCustomers} 
              onChange={(e) => updateMetrics('newCustomers', parseFloat(e.target.value) || 0)}
              style={{ width: "100%", padding: "8px", marginTop: "5px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }}
            />
          </div>

          <div style={{ marginTop: "15px" }}>
            <label>Customers Lost per Year: </label>
            <input 
              type="number" 
              value={metrics.lostPerYear} 
              onChange={(e) => updateMetrics('lostPerYear', parseFloat(e.target.value) || 0)}
              style={{ width: "100%", padding: "8px", marginTop: "5px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }}
            />
          </div>

          <div style={{ marginTop: "15px" }}>
            <label>Monthly Marketing Spend ($): </label>
            <input 
              type="number" 
              value={metrics.marketingSpend} 
              onChange={(e) => updateMetrics('marketingSpend', parseFloat(e.target.value) || 0)}
              style={{ width: "100%", padding: "8px", marginTop: "5px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }}
            />
          </div>

          <div style={{ marginTop: "30px", padding: "20px", background: "#0A0C14", borderRadius: "12px" }}>
            <h3 style={{ color: GREEN }}>Results</h3>
            <p><strong>AOV:</strong> ${calculated.aov}</p>
            <p><strong>LTV:</strong> ${calculated.ltv}</p>
            <p><strong>CAC:</strong> ${calculated.cac}</p>
            <p><strong>LTV:CAC Ratio:</strong> {calculated.ratio}:1</p>
          </div>
        </div>
      )}
    </div>
  );
}