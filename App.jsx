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
  const [activeTab, setActiveTab] = useState("pricing");
  const [metrics, setMetrics] = useState(DEFAULT_METRICS);
  const [imgPreview, setImgPreview] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [customPhotoData, setCustomPhotoData] = useState({
    size: "6500",
    obstruction: "None",
    condition: "maintained",
    desc: ""
  });

  const updateMetrics = (field, value) => {
    setMetrics(prev => ({ ...prev, [field]: value }));
  };

  const calculated = useMemo(() => {
    const { mrr, customers, newCustomers, lostPerYear, marketingSpend } = metrics;
    const aov = customers > 0 ? Math.round(mrr / customers) : 0;
    const monthlyChurn = lostPerYear / 12;
    const churnRate = customers > 0 ? parseFloat(((monthlyChurn / customers) * 100).toFixed(2)) : 0;
    const ltv = churnRate > 0 ? Math.round(aov / (churnRate / 100)) : 0;
    const cac = newCustomers > 0 ? Math.round(marketingSpend / newCustomers) : 0;
    const ratio = cac > 0 ? parseFloat((ltv / cac).toFixed(1)) : 0;

    return { aov, churnRate, ltv, cac, ratio };
  }, [metrics]);

  const handlePhotoUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64Data = reader.result.split(",")[1];
      const mediaType = file.type || "image/jpeg";

      setImgPreview(reader.result);
      setIsUploading(true);

      try {
        const response = await fetch("/api/analyze-photo", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: base64Data, mediaType })
        });

        if (!response.ok) throw new Error("Backend error");

        const result = await response.json();

        setCustomPhotoData({
          size: String(result.square_footage || 6500),
          obstruction: result.obstruction || "None",
          condition: result.condition || "maintained",
          desc: result.raw_description || ""
        });

      } catch (err) {
        console.error(err);
      } finally {
        setIsUploading(false);
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div style={{ background: STEEL, color: TEXT, minHeight: "100vh", padding: "20px", fontFamily: "system-ui" }}>
      <h1 style={{ fontSize: "22px", marginBottom: "16px" }}>CrewRoute OS</h1>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "20px", flexWrap: "wrap" }}>
        {["pricing", "metrics"].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              background: activeTab === tab ? ACCENT : PANEL,
              color: activeTab === tab ? "#000" : TEXT,
              border: "none",
              fontWeight: "bold"
            }}
          >
            {tab === "pricing" ? "Pricing & Photo" : "LTV / CAC / AOV"}
          </button>
        ))}
      </div>

      {/* Pricing + Photo Tab */}
      {activeTab === "pricing" && (
        <div style={{ background: PANEL, padding: "20px", borderRadius: "12px" }}>
          <h2>Photo Analysis</h2>
          <input type="file" accept="image/*" onChange={handlePhotoUpload} />
          
          {imgPreview && (
            <img src={imgPreview} alt="preview" style={{ width: "100%", maxHeight: "200px", objectFit: "cover", marginTop: "12px", borderRadius: "8px" }} />
          )}

          {isUploading && <p>Analyzing photo...</p>}

          <div style={{ marginTop: "20px" }}>
            <p><strong>Size:</strong> {customPhotoData.size} sq ft</p>
            <p><strong>Condition:</strong> {customPhotoData.condition}</p>
            <p><strong>Obstruction:</strong> {customPhotoData.obstruction}</p>
          </div>
        </div>
      )}

      {/* Business Metrics Tab */}
      {activeTab === "metrics" && (
        <div style={{ background: PANEL, padding: "20px", borderRadius: "12px" }}>
          <h2>Business Metrics</h2>

          <div style={{ marginTop: "16px" }}>
            <label>Monthly Revenue (MRR)</label>
            <input type="number" value={metrics.mrr} onChange={e => updateMetrics('mrr', parseFloat(e.target.value) || 0)} style={{ width: "100%", padding: "8px", marginTop: "6px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }} />
          </div>

          <div style={{ marginTop: "12px" }}>
            <label>Number of Customers</label>
            <input type="number" value={metrics.customers} onChange={e => updateMetrics('customers', parseInt(e.target.value) || 0)} style={{ width: "100%", padding: "8px", marginTop: "6px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }} />
          </div>

          <div style={{ marginTop: "12px" }}>
            <label>New Customers per Month</label>
            <input type="number" value={metrics.newCustomers} onChange={e => updateMetrics('newCustomers', parseFloat(e.target.value) || 0)} style={{ width: "100%", padding: "8px", marginTop: "6px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }} />
          </div>

          <div style={{ marginTop: "12px" }}>
            <label>Customers Lost per Year</label>
            <input type="number" value={metrics.lostPerYear} onChange={e => updateMetrics('lostPerYear', parseFloat(e.target.value) || 0)} style={{ width: "100%", padding: "8px", marginTop: "6px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }} />
          </div>

          <div style={{ marginTop: "12px" }}>
            <label>Monthly Marketing Spend ($)</label>
            <input type="number" value={metrics.marketingSpend} onChange={e => updateMetrics('marketingSpend', parseFloat(e.target.value) || 0)} style={{ width: "100%", padding: "8px", marginTop: "6px", background: STEEL, color: TEXT, border: `1px solid ${BORDER}` }} />
          </div>

          <div style={{ marginTop: "24px", padding: "16px", background: "#0A0C14", borderRadius: "10px" }}>
            <h3 style={{ color: GREEN, marginBottom: "12px" }}>Results</h3>
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