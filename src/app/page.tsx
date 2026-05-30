'use client';

import React, { useState, useMemo } from 'react';

const ACCENT = '#22c55e';
const STEEL = '#64748b';
const PANEL = '#1f2937';
const BG = '#0a0a0a';

interface PhotoAnalysis {
  squareFootage?: number;
  condition?: string;
  obstruction?: string;
  description?: string;
  estimatedPrice?: number;
  confidenceScore?: number;
}

interface Metrics {
  mrr: number;
  customers: number;
  newCustomers: number;
  lostPerYear: number;
  marketingSpend: number;
}

export default function CrewRouteOS() {
  const [activeTab, setActiveTab] = useState<'pricing' | 'metrics'>('pricing');
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [photoData, setPhotoData] = useState<PhotoAnalysis | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [metrics, setMetrics] = useState<Metrics>({
    mrr: 6500,
    customers: 20,
    newCustomers: 3,
    lostPerYear: 4,
    marketingSpend: 800,
  });

  const calculatedMetrics = useMemo(() => {
    const aov = metrics.mrr / metrics.customers;
    const churnRate = (metrics.lostPerYear / 12 / metrics.customers) * 100;
    const ltv = churnRate > 0 ? aov / (churnRate / 100) : 0;
    const cac = metrics.newCustomers > 0 ? metrics.marketingSpend / metrics.newCustomers : 0;
    const ltvCacRatio = cac > 0 ? ltv / cac : 0;

    return {
      aov: Math.round(aov),
      churnRate: Math.round(churnRate * 10) / 10,
      ltv: Math.round(ltv),
      cac: Math.round(cac),
      ltvCacRatio: Math.round(ltvCacRatio * 10) / 10,
    };
  }, [metrics]);

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setIsAnalyzing(true);
    setPhotoData(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      setImagePreview(event.target?.result as string);
    };
    reader.readAsDataURL(file);

    try {
      const base64 = await new Promise<string>((resolve) => {
        const r = new FileReader();
        r.onload = () => resolve((r.result as string).split(',')[1]);
        r.readAsDataURL(file);
      });

      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image: base64,
          mode: 'estimate',
          filename: file.name,
        }),
      });

      if (!response.ok) throw new Error('Analysis failed');

      const result = await response.json();
      setPhotoData(result);
    } catch (err) {
      console.error(err);
      setUploadError('Photo analysis failed. Using demo data.');
      setPhotoData({
        squareFootage: 2450,
        condition: 'maintained',
        obstruction: 'none',
        description: 'Demo: Well-maintained front yard with mature trees. Good access.',
        estimatedPrice: 385,
        confidenceScore: 78,
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const updateMetric = (key: keyof Metrics, value: number) => {
    setMetrics(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div style={{ minHeight: '100vh', background: BG, padding: '40px 20px' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 40 }}>
          <div>
            <h1 style={{ fontSize: 42, fontWeight: 700, margin: 0, color: 'white' }}>
              CrewRoute <span style={{ color: ACCENT }}>OS</span>
            </h1>
            <p style={{ color: STEEL, marginTop: 8, fontSize: 18 }}>
              AI-Native Operating System for CJS Landscape Solutions
            </p>
          </div>
          <div style={{ 
            background: PANEL, 
            padding: '8px 16px', 
            borderRadius: 999, 
            fontSize: 13, 
            color: ACCENT,
            border: `1px solid ${ACCENT}30`
          }}>
            v0.3.1 • Main Branch • Live
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
          <button
            onClick={() => setActiveTab('pricing')}
            style={{
              padding: '12px 28px',
              background: activeTab === 'pricing' ? ACCENT : PANEL,
              color: activeTab === 'pricing' ? 'black' : 'white',
              border: 'none',
              borderRadius: 12,
              fontSize: 15,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            📸 Pricing &amp; Photo Analysis
          </button>
          <button
            onClick={() => setActiveTab('metrics')}
            style={{
              padding: '12px 28px',
              background: activeTab === 'metrics' ? ACCENT : PANEL,
              color: activeTab === 'metrics' ? 'black' : 'white',
              border: 'none',
              borderRadius: 12,
              fontSize: 15,
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
          >
            📊 LTV / CAC / AOV
          </button>
        </div>

        {/* Pricing & Photo Tab */}
        {activeTab === 'pricing' && (
          <div style={{ background: PANEL, borderRadius: 20, padding: 32, border: `1px solid ${STEEL}20` }}>
            <h2 style={{ marginTop: 0, color: 'white' }}>Instant Photo → Estimate</h2>
            <p style={{ color: STEEL, marginBottom: 24 }}>
              Upload a property photo. CrewRoute AI analyzes square footage, condition, access, and suggests pricing.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
              {/* Upload Zone */}
              <div>
                <label style={{
                  display: 'block',
                  border: `2px dashed ${STEEL}60`,
                  borderRadius: 16,
                  padding: 60,
                  textAlign: 'center',
                  cursor: 'pointer',
                  background: '#111',
                }}>
                  <input 
                    type="file" 
                    accept="image/*" 
                    onChange={handleImageUpload} 
                    style={{ display: 'none' }} 
                  />
                  <div style={{ fontSize: 48, marginBottom: 16 }}>📷</div>
                  <div style={{ fontWeight: 600, fontSize: 18, color: 'white' }}>
                    Drop property photo or click to upload
                  </div>
                  <div style={{ color: STEEL, fontSize: 14, marginTop: 8 }}>
                    JPG, PNG • Front yard, side, or aerial preferred
                  </div>
                </label>

                {imagePreview && (
                  <div style={{ marginTop: 20, borderRadius: 12, overflow: 'hidden', border: `1px solid ${STEEL}30` }}>
                    <img src={imagePreview} alt="Property preview" style={{ width: '100%', display: 'block' }} />
                  </div>
                )}
              </div>

              {/* Results */}
              <div>
                {isAnalyzing && (
                  <div style={{ padding: 40, textAlign: 'center', color: ACCENT }}>
                    <div style={{ fontSize: 24, marginBottom: 12 }}>⚡ Analyzing with Claude...</div>
                    <div style={{ color: STEEL }}>Processing image for turf, condition, access constraints...</div>
                  </div>
                )}

                {uploadError && (
                  <div style={{ color: '#f87171', background: '#3f1f1f', padding: 16, borderRadius: 12, marginBottom: 16 }}>
                    {uploadError}
                  </div>
                )}

                {photoData && !isAnalyzing && (
                  <div style={{ background: '#111', borderRadius: 16, padding: 24 }}>
                    <div style={{ color: ACCENT, fontSize: 13, fontWeight: 600, marginBottom: 12 }}>ANALYSIS COMPLETE</div>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                      <div>
                        <div style={{ color: STEEL, fontSize: 12 }}>SQUARE FOOTAGE</div>
                        <div style={{ fontSize: 28, fontWeight: 700, color: 'white' }}>
                          {photoData.squareFootage?.toLocaleString() || '—'} sq ft
                        </div>
                      </div>
                      <div>
                        <div style={{ color: STEEL, fontSize: 12 }}>EST. PRICE</div>
                        <div style={{ fontSize: 28, fontWeight: 700, color: ACCENT }}>
                          ${photoData.estimatedPrice || '—'}
                        </div>
                      </div>
                    </div>

                    <div style={{ marginBottom: 16 }}>
                      <div style={{ color: STEEL, fontSize: 12, marginBottom: 4 }}>CONDITION</div>
                      <div style={{ fontSize: 18, color: 'white', textTransform: 'capitalize' }}>
                        {photoData.condition || '—'}
                      </div>
                    </div>

                    {photoData.description && (
                      <div style={{ fontSize: 14, color: '#ccc', lineHeight: 1.5 }}>
                        {photoData.description}
                      </div>
                    )}

                    {photoData.confidenceScore && (
                      <div style={{ marginTop: 20, fontSize: 12, color: STEEL }}>
                        Confidence: {photoData.confidenceScore}%
                      </div>
                    )}
                  </div>
                )}

                {!photoData && !isAnalyzing && (
                  <div style={{ padding: 40, textAlign: 'center', color: STEEL, background: '#111', borderRadius: 16 }}>
                    Upload a photo to see AI-powered estimate and condition analysis
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Business Metrics Tab */}
        {activeTab === 'metrics' && (
          <div style={{ background: PANEL, borderRadius: 20, padding: 32, border: `1px solid ${STEEL}20` }}>
            <h2 style={{ marginTop: 0, color: 'white' }}>Business Intelligence Dashboard</h2>
            <p style={{ color: STEEL, marginBottom: 32 }}>Real-time LTV, CAC, AOV, and churn modeling for CJS operations.</p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: 32 }}>
              {/* Inputs */}
              <div>
                <h3 style={{ fontSize: 16, color: STEEL, marginBottom: 16 }}>INPUTS</h3>
                {[
                  { label: 'Monthly Recurring Revenue (MRR)', key: 'mrr' as const },
                  { label: 'Total Active Customers', key: 'customers' as const },
                  { label: 'New Customers / Month', key: 'newCustomers' as const },
                  { label: 'Customers Lost / Year', key: 'lostPerYear' as const },
                  { label: 'Monthly Marketing Spend', key: 'marketingSpend' as const },
                ].map((field) => (
                  <div key={field.key} style={{ marginBottom: 18 }}>
                    <label style={{ display: 'block', fontSize: 13, color: STEEL, marginBottom: 6 }}>
                      {field.label}
                    </label>
                    <input
                      type="number"
                      value={metrics[field.key]}
                      onChange={(e) => updateMetric(field.key, parseInt(e.target.value) || 0)}
                      style={{
                        width: '100%',
                        background: '#111',
                        border: `1px solid ${STEEL}40`,
                        color: 'white',
                        padding: '12px 16px',
                        borderRadius: 10,
                        fontSize: 16,
                      }}
                    />
                  </div>
                ))}
              </div>

              {/* Results */}
              <div>
                <h3 style={{ fontSize: 16, color: STEEL, marginBottom: 16 }}>CALCULATED METRICS</h3>
                <div style={{ display: 'grid', gap: 12 }}>
                  {[
                    { label: 'Average Order Value (AOV)', value: `$${calculatedMetrics.aov}` },
                    { label: 'Monthly Churn Rate', value: `${calculatedMetrics.churnRate}%` },
                    { label: 'Customer Lifetime Value (LTV)', value: `$${calculatedMetrics.ltv}` },
                    { label: 'Customer Acquisition Cost (CAC)', value: `$${calculatedMetrics.cac}` },
                    { 
                      label: 'LTV : CAC Ratio', 
                      value: calculatedMetrics.ltvCacRatio.toFixed(1),
                      highlight: calculatedMetrics.ltvCacRatio >= 3 
                    },
                  ].map((metric, idx) => (
                    <div key={idx} style={{ 
                      background: '#111', 
                      padding: '18px 24px', 
                      borderRadius: 14,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <div style={{ color: '#aaa' }}>{metric.label}</div>
                      <div style={{ 
                        fontSize: 22, 
                        fontWeight: 700, 
                        color: metric.highlight ? ACCENT : 'white' 
                      }}>
                        {metric.value}
                      </div>
                    </div>
                  ))}
                </div>

                <div style={{ marginTop: 24, fontSize: 13, color: STEEL, lineHeight: 1.5 }}>
                  Healthy LTV:CAC is typically 3:1 or higher. Use this to guide marketing and retention spend.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div style={{ marginTop: 48, textAlign: 'center', color: STEEL, fontSize: 13 }}>
          Built for CJS Landscape Solutions • Powered by Next.js + Claude + Supabase • 
          <span style={{ color: ACCENT }}> Main branch deployed</span>
        </div>
      </div>
    </div>
  );
}