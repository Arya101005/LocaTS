import React, { useState } from 'react';

const API = '/api';

export default function AuditVerify() {
  const [orderId, setOrderId] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const verify = async () => {
    if (!orderId.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/audit/verify/${orderId}`);
      setResult(await res.json());
    } catch (e) {
      setResult({ verification_result: 'Verification failed — server unreachable.', exists: false });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#F0F9F4', fontFamily: 'Inter, sans-serif' }}>
      <div style={{ background: '#fff', borderBottom: '1px solid #E5E7EB', padding: '16px 20px' }}>
        <div style={{ maxWidth: 600, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: '#16A34A', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800, fontSize: 16 }}>L</div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#111827' }}>Order Verification</div>
            <div style={{ fontSize: 12, color: '#6B7280' }}>Verify the integrity of a relocation order</div>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '24px 16px' }}>
        <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #E5E7EB', padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 8, color: '#111827' }}>Verify Relocation Order</h2>
          <p style={{ fontSize: 14, color: '#6B7280', marginBottom: 16, lineHeight: 1.5 }}>
            Paste an order ID below to check if it has been tampered with. This verification uses SHA-256 hash chain integrity.
          </p>

          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <input
              value={orderId}
              onChange={e => setOrderId(e.target.value)}
              placeholder="e.g. order-abc12345"
              style={{ flex: 1, padding: '12px 16px', borderRadius: 10, border: '1px solid #D1D5DB', fontSize: 14 }}
              onKeyDown={e => { if (e.key === 'Enter') verify(); }}
            />
            <button
              onClick={verify}
              disabled={loading || !orderId.trim()}
              style={{ padding: '12px 24px', background: '#16A34A', color: '#fff', border: 'none', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: loading ? 'default' : 'pointer', opacity: loading || !orderId.trim() ? 0.6 : 1 }}
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>
          </div>

          {result && (
            <div style={{ padding: 20, background: result.hash_match ? '#F0FDF4' : '#FEF2F2', borderRadius: 12, border: `1px solid ${result.hash_match ? '#BBF7D0' : '#FCA5A5'}` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: result.hash_match ? '#22C55E' : '#DC2626', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {result.hash_match ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M5 13l4 4L19 7"/></svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M6 18L18 6M6 6l12 12"/></svg>
                  )}
                </div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: result.hash_match ? '#16A34A' : '#DC2626' }}>
                    {result.exists ? (result.hash_match ? 'VERIFIED' : 'WARNING') : 'NOT FOUND'}
                  </div>
                  <div style={{ fontSize: 13, color: '#4B5563' }}>{result.verification_result}</div>
                </div>
              </div>

              <div style={{ fontSize: 14, color: '#374151', lineHeight: 1.6 }}>{result.plain_explanation}</div>

              {result.exists && (
                <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div style={{ padding: '8px 12px', background: '#fff', borderRadius: 8, border: '1px solid #E5E7EB' }}>
                    <div style={{ fontSize: 11, color: '#94A3B8', textTransform: 'uppercase' }}>Order ID</div>
                    <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace' }}>{result.order_id}</div>
                  </div>
                  <div style={{ padding: '8px 12px', background: '#fff', borderRadius: 8, border: '1px solid #E5E7EB' }}>
                    <div style={{ fontSize: 11, color: '#94A3B8', textTransform: 'uppercase' }}>Issued</div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{result.issued_at?.replace('T', ' ')}</div>
                  </div>
                  <div style={{ padding: '8px 12px', background: '#fff', borderRadius: 8, border: '1px solid #E5E7EB' }}>
                    <div style={{ fontSize: 11, color: '#94A3B8', textTransform: 'uppercase' }}>People Relocated</div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{result.total_relocated?.toLocaleString()}</div>
                  </div>
                  <div style={{ padding: '8px 12px', background: '#fff', borderRadius: 8, border: '1px solid #E5E7EB' }}>
                    <div style={{ fontSize: 11, color: '#94A3B8', textTransform: 'uppercase' }}>Hash</div>
                    <div style={{ fontSize: 13, fontWeight: 600, fontFamily: 'monospace' }}>{result.audit_hash}...</div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div style={{ textAlign: 'center', marginTop: 20, fontSize: 12, color: '#9CA3AF' }}>
          <a href="/" style={{ color: '#16A34A', textDecoration: 'none' }}>Back to Home</a>
        </div>
      </div>
    </div>
  );
}
