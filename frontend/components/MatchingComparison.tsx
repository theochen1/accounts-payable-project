'use client';

import { InvoiceDetail, PurchaseOrder, MatchingResult } from '../lib/api';

interface MatchingComparisonProps {
  invoice: InvoiceDetail;
  po: PurchaseOrder;
  matchingResult: MatchingResult;
}

export default function MatchingComparison({ invoice, po, matchingResult }: MatchingComparisonProps) {
  const formatCurrency = (amount: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
    }).format(amount);
  };

  return (
    <div className="card">
      <h2>Matching Results</h2>
      
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className={`status-badge status-${matchingResult.status}`}>
            {matchingResult.status.replace('_', ' ').toUpperCase()}
          </span>
          {matchingResult.overall_match && (
            <span className="match">✓ Fully Matched</span>
          )}
        </div>
      </div>

      {matchingResult.issues && matchingResult.issues.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h3>Issues</h3>
          {matchingResult.issues.map((issue, idx) => (
            <div
              key={idx}
              className={issue.severity === 'exception' ? 'issue-error' : 'issue-warning'}
            >
              <strong>{issue.type.replace('_', ' ').toUpperCase()}</strong>: {issue.message}
            </div>
          ))}
        </div>
      )}

      <div className="matching-comparison">
        <div>
          <h3>Invoice</h3>
          <div className="form-group">
            <label>Vendor</label>
            <div>{invoice.vendor_name || 'N/A'}</div>
          </div>
          <div className="form-group">
            <label>Total</label>
            <div>{formatCurrency(invoice.total_amount || 0, invoice.currency)}</div>
          </div>
          <div className="form-group">
            <label>Currency</label>
            <div>{invoice.currency}</div>
          </div>
        </div>

        <div>
          <h3>Purchase Order</h3>
          <div className="form-group">
            <label>Vendor</label>
            <div>{po.vendor_name || 'N/A'}</div>
          </div>
          <div className="form-group">
            <label>Total</label>
            <div>{formatCurrency(po.total_amount, po.currency)}</div>
          </div>
          <div className="form-group">
            <label>Currency</label>
            <div>{po.currency}</div>
          </div>
        </div>
      </div>

      {matchingResult.total_difference !== undefined && (
        <div style={{ marginTop: '20px', padding: '12px', background: '#f9fafb', borderRadius: '6px' }}>
          <strong>Total Difference:</strong> {formatCurrency(matchingResult.total_difference, invoice.currency)}
          {matchingResult.total_difference_percent !== undefined && (
            <span> ({matchingResult.total_difference_percent.toFixed(2)}%)</span>
          )}
        </div>
      )}

      {matchingResult.line_item_matches && matchingResult.line_item_matches.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h3>Line Item Matches</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Invoice Line</th>
                <th>PO Line</th>
                <th>Status</th>
                <th>Issues</th>
              </tr>
            </thead>
            <tbody>
              {matchingResult.line_item_matches.map((match, idx) => (
                <tr key={idx}>
                  <td>{match.invoice_line_no > 0 ? match.invoice_line_no : 'N/A'}</td>
                  <td>{match.po_line_no || 'N/A'}</td>
                  <td>
                    {match.matched ? (
                      <span className="match">Matched</span>
                    ) : (
                      <span className="mismatch">Mismatch</span>
                    )}
                  </td>
                  <td>
                    {match.issues.length > 0 ? (
                      <ul style={{ margin: 0, paddingLeft: '20px' }}>
                        {match.issues.map((issue, i) => (
                          <li key={i} style={{ fontSize: '12px' }}>{issue}</li>
                        ))}
                      </ul>
                    ) : (
                      'None'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

