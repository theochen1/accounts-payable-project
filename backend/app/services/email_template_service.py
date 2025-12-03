"""
Email Template Service - AI-powered email generation for invoice-PO discrepancies

Uses OpenAI to generate professional AP emails with issue context and formatted tables.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from openai import AsyncOpenAI

from app.config import settings
from app.models import DocumentPair, ValidationIssue, Invoice, PurchaseOrder

logger = logging.getLogger(__name__)


class EmailTemplateService:
    """Generate professional AP emails using AI"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.openai_client = None
        if settings.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            logger.info("EmailTemplateService initialized with OpenAI")
        else:
            logger.warning("OpenAI API key not configured - email generation will be disabled")
    
    async def generate_escalation_email(
        self,
        document_pair: DocumentPair,
        issues: List[ValidationIssue],
        invoice: Invoice,
        po: Optional[PurchaseOrder]
    ) -> Dict[str, Any]:
        """
        Generate professional email draft for invoice-PO discrepancies
        
        Args:
            document_pair: The document pair with issues
            issues: List of unresolved validation issues
            invoice: The invoice record
            po: The purchase order record (optional)
        
        Returns:
            {
                'subject': str,
                'body_text': str,  # Plain text version
                'body_html': str,  # HTML version with formatted table
                'summary': str     # One-line summary for UI
            }
        """
        if not self.openai_client:
            raise Exception("OpenAI client not initialized - check OPENAI_API_KEY")
        
        # Prepare context for LLM
        context = self._prepare_email_context(document_pair, issues, invoice, po)
        
        # Generate email with LLM
        prompt = self._build_email_prompt(context)
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an experienced Accounts Payable Manager writing professional emails to resolve invoice discrepancies. Write clear, respectful, solution-oriented emails."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent, professional tone
                max_tokens=1000
            )
            
            llm_response = response.choices[0].message.content
            
            # Parse LLM response
            email_content = self._parse_email_response(llm_response, context)
            
            # Generate HTML version with formatted table
            email_content['body_html'] = self._format_email_html(
                email_content['body_text'],
                context['issues_table']
            )
            
            logger.info(f"Generated email draft for pair {document_pair.id}")
            return email_content
            
        except Exception as e:
            logger.error(f"Failed to generate email: {e}")
            raise Exception(f"Failed to generate email draft: {e}")
    
    def _prepare_email_context(
        self,
        pair: DocumentPair,
        issues: List[ValidationIssue],
        invoice: Invoice,
        po: Optional[PurchaseOrder]
    ) -> Dict[str, Any]:
        """Prepare structured context for email generation"""
        
        # Build issues table data
        issues_table = []
        for issue in issues:
            invoice_val = issue.invoice_value
            po_val = issue.po_value
            
            # Format values for display
            invoice_display = self._format_value_for_display(invoice_val)
            po_display = self._format_value_for_display(po_val)
            
            issues_table.append({
                'field': issue.field or issue.category,
                'invoice_value': invoice_display,
                'po_value': po_display,
                'issue': issue.description,
                'severity': issue.severity
            })
        
        # Get vendor name
        vendor_name = None
        if invoice.vendor:
            vendor_name = invoice.vendor.name
        
        return {
            'invoice_number': invoice.invoice_number,
            'po_number': po.po_number if po else None,
            'vendor_name': vendor_name or 'Vendor',
            'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else None,
            'total_amount': float(invoice.total_amount) if invoice.total_amount else None,
            'issues_count': len(issues),
            'issues': issues,
            'issues_table': issues_table,
        }
    
    def _format_value_for_display(self, value: Any) -> str:
        """Format a value for display in email"""
        if value is None:
            return 'N/A'
        if isinstance(value, (int, float, Decimal)):
            if isinstance(value, Decimal):
                return f"${float(value):,.2f}"
            return f"${value:,.2f}"
        if isinstance(value, str):
            return value
        return str(value)
    
    def _build_email_prompt(self, context: Dict[str, Any]) -> str:
        """Build LLM prompt for email generation"""
        
        total_amt_str = f"${context['total_amount']:,.2f}" if context.get('total_amount') else 'N/A'
        
        prompt = f"""You are an experienced Accounts Payable Manager writing a professional email to resolve invoice discrepancies.

Context:
- Invoice: #{context['invoice_number']} from {context['vendor_name']}
- Purchase Order: #{context['po_number'] if context['po_number'] else 'N/A'}
- Total Amount: {total_amt_str}
- Issues Found: {context['issues_count']}

Issues Detected:
"""
        
        for i, issue in enumerate(context['issues'], 1):
            prompt += f"\n{i}. {issue.description}"
            if issue.invoice_value and issue.po_value:
                invoice_val = self._format_value_for_display(issue.invoice_value)
                po_val = self._format_value_for_display(issue.po_value)
                prompt += f"\n   Invoice shows: {invoice_val}"
                prompt += f"\n   PO shows: {po_val}"
        
        prompt += """

Write a professional email that:
1. Greets the vendor contact warmly but professionally
2. References the specific invoice and PO numbers
3. Clearly explains the discrepancy(ies) found
4. Requests specific action to resolve (corrected invoice, clarification, etc.)
5. Provides a reasonable timeline (e.g., "within 3 business days")
6. Thanks them for their cooperation
7. Signs off professionally

Tone: Semi-formal, professional, respectful, solution-oriented
Length: 150-200 words
Format: Standard business email

Generate the email with:
- Subject line (on first line, format: "Subject: [subject text]")
- Email body (on following lines)

Do not include placeholders like [Your Name] - use "Accounts Payable Team" as the sender.
"""
        
        return prompt
    
    def _parse_email_response(self, llm_response: str, context: Dict[str, Any]) -> Dict[str, str]:
        """Parse LLM response into structured email parts"""
        
        lines = llm_response.strip().split('\n')
        
        # Extract subject (usually first line or after "Subject:")
        subject = ""
        body_start_idx = 0
        
        for i, line in enumerate(lines):
            if line.lower().startswith('subject:'):
                subject = line.split(':', 1)[1].strip()
                body_start_idx = i + 1
                break
        
        if not subject:
            # Default subject if not found
            subject = f"Invoice Discrepancy - Action Required (Invoice #{context['invoice_number']})"
        
        # Rest is body
        body_text = '\n'.join(lines[body_start_idx:]).strip()
        
        # Generate summary (first sentence)
        if '.' in body_text:
            summary = body_text.split('.')[0] + '.'
        else:
            summary = body_text[:100] + '...' if len(body_text) > 100 else body_text
        
        return {
            'subject': subject,
            'body_text': body_text,
            'summary': summary
        }
    
    def _format_email_html(self, body_text: str, issues_table: List[Dict[str, Any]]) -> str:
        """Convert plain text email to HTML with formatted table"""
        
        # Convert body text to HTML paragraphs
        paragraphs = body_text.split('\n\n')
        html_body = ''.join([f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()])
        
        # Build issues table
        table_html = """
        <table style="border-collapse: collapse; width: 100%; margin: 20px 0; font-family: Arial, sans-serif;">
          <thead>
            <tr style="background-color: #f3f4f6;">
              <th style="border: 1px solid #d1d5db; padding: 12px; text-align: left;">Field</th>
              <th style="border: 1px solid #d1d5db; padding: 12px; text-align: left;">Invoice Value</th>
              <th style="border: 1px solid #d1d5db; padding: 12px; text-align: left;">PO Value</th>
              <th style="border: 1px solid #d1d5db; padding: 12px; text-align: left;">Issue</th>
            </tr>
          </thead>
          <tbody>
        """
        
        for issue in issues_table:
            severity_color = {
                'critical': '#fef2f2',
                'warning': '#fffbeb',
                'info': '#eff6ff'
            }.get(issue['severity'], '#ffffff')
            
            table_html += f"""
            <tr style="background-color: {severity_color};">
              <td style="border: 1px solid #d1d5db; padding: 12px;">{self._escape_html(issue['field'])}</td>
              <td style="border: 1px solid #d1d5db; padding: 12px;">{self._escape_html(str(issue['invoice_value']))}</td>
              <td style="border: 1px solid #d1d5db; padding: 12px;">{self._escape_html(str(issue['po_value']))}</td>
              <td style="border: 1px solid #d1d5db; padding: 12px;">{self._escape_html(issue['issue'])}</td>
            </tr>
            """
        
        table_html += """
          </tbody>
        </table>
        """
        
        # Combine into full HTML email
        html_email = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #374151; padding: 20px;">
            {html_body}
            
            <h3 style="color: #1f2937; margin-top: 20px;">Discrepancies Found:</h3>
            {table_html}
            
            <p style="margin-top: 20px;">Thank you for your prompt attention to this matter.</p>
            
            <p>Best regards,<br>
            <strong>Accounts Payable Team</strong></p>
          </body>
        </html>
        """
        
        return html_email
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        if not text:
            return ''
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

