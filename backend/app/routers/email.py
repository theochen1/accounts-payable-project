"""
Email API router - handles email drafting and sending for document pair escalations
"""
import logging
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.email_log import EmailLog
from app.models.document_pair import DocumentPair
from app.models.validation_issue import ValidationIssue
from app.models.invoice import Invoice
from app.models.purchase_order import PurchaseOrder
from app.schemas.email import (
    EmailDraftRequest,
    EmailDraftResponse,
    EmailSendRequest,
    EmailSendResponse,
    EmailLogResponse
)
from app.services.email_template_service import EmailTemplateService
from app.services.gmail_service import GmailService, SCOPES
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])

# Initialize services
email_template_service = EmailTemplateService()
gmail_service = GmailService()


@router.get("/status")
def get_email_service_status():
    """
    Check the status of the email service.
    Returns whether Gmail is properly configured.
    """
    import os
    has_client_id = bool(os.getenv('GMAIL_CLIENT_ID'))
    has_client_secret = bool(os.getenv('GMAIL_CLIENT_SECRET'))
    has_refresh_token = bool(os.getenv('GMAIL_REFRESH_TOKEN'))
    has_credentials_json = bool(os.getenv('GMAIL_CREDENTIALS_JSON'))
    
    return {
        "gmail_service_initialized": gmail_service.service is not None,
        "gmail_sender_email": gmail_service.sender_email or "not configured",
        "credentials_loaded": gmail_service.creds is not None,
        "error": gmail_service.init_error,
        "env_vars": {
            "GMAIL_CLIENT_ID": "set" if has_client_id else "not set",
            "GMAIL_CLIENT_SECRET": "set" if has_client_secret else "not set",
            "GMAIL_REFRESH_TOKEN": "set" if has_refresh_token else "not set",
            "GMAIL_CREDENTIALS_JSON": "set" if has_credentials_json else "not set",
            "GMAIL_SENDER_EMAIL": "set" if gmail_service.sender_email else "not set"
        },
        "troubleshooting": {
            "needs_refresh_token": not has_refresh_token and not has_credentials_json,
            "instructions": "To get a refresh token, use OAuth 2.0 Playground: https://developers.google.com/oauthplayground/ with scope: https://www.googleapis.com/auth/gmail.send"
        },
        "oauth_available": has_client_id and has_client_secret
    }


@router.get("/oauth/authorize")
def get_oauth_authorize_url(redirect_uri: str = Query(..., description="Frontend redirect URI after OAuth")):
    """
    Generate Google OAuth authorization URL.
    
    Returns the URL that the user should be redirected to for Google login.
    """
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be configured"
        )
    
    try:
        from google_auth_oauthlib.flow import Flow
        
        # Create OAuth flow
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Generate authorization URL
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to get refresh token
        )
        
        logger.info(f"Generated OAuth authorization URL with state: {state}")
        
        return {
            "auth_url": authorization_url,
            "state": state
        }
    except Exception as e:
        logger.error(f"Failed to generate OAuth URL: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate OAuth authorization URL: {str(e)}"
        )


@router.get("/oauth/callback")
def oauth_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(None, description="State parameter for CSRF protection"),
    redirect_uri: str = Query(..., description="Redirect URI used in authorization")
):
    """
    Handle OAuth callback from Google.
    
    Exchanges the authorization code for access and refresh tokens.
    Returns the refresh token that should be set as GMAIL_REFRESH_TOKEN.
    """
    client_id = os.getenv('GMAIL_CLIENT_ID')
    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail="GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be configured"
        )
    
    try:
        from google_auth_oauthlib.flow import Flow
        
        # Create OAuth flow
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Exchange authorization code for tokens
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        if not credentials.refresh_token:
            raise HTTPException(
                status_code=400,
                detail="No refresh token received. Make sure 'prompt=consent' is used in authorization."
            )
        
        logger.info("Successfully obtained OAuth credentials")
        
        # Return the refresh token and other info
        return {
            "success": True,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": client_secret,  # Return for convenience, user should keep it secure
            "scopes": credentials.scopes,
            "instructions": "Set GMAIL_REFRESH_TOKEN environment variable with the refresh_token value above"
        }
    except Exception as e:
        logger.error(f"Failed to exchange OAuth code: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )


@router.post("/draft", response_model=EmailDraftResponse)
async def draft_email(
    request: EmailDraftRequest,
    db: Session = Depends(get_db)
):
    """
    Generate email draft for document pair issues
    
    TO: invoice.contact_email (vendor contact)
    CC: purchase_order.requester_email (internal procurement)
    """
    # Get document pair
    pair = db.query(DocumentPair).filter(DocumentPair.id == request.document_pair_id).first()
    if not pair:
        raise HTTPException(status_code=404, detail="Document pair not found")
    
    # Get invoice and PO
    invoice = db.query(Invoice).filter(Invoice.id == pair.invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    po = None
    if pair.po_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == pair.po_id).first()
    
    # Get unresolved issues
    query = db.query(ValidationIssue).filter(
        ValidationIssue.document_pair_id == pair.id,
        ValidationIssue.resolved == False
    )
    
    if request.issue_ids:
        query = query.filter(ValidationIssue.id.in_(request.issue_ids))
    
    issues = query.all()
    
    if not issues:
        raise HTTPException(status_code=400, detail="No unresolved issues found for this document pair")
    
    # Generate email draft
    try:
        email_content = await email_template_service.generate_escalation_email(
            document_pair=pair,
            issues=issues,
            invoice=invoice,
            po=po
        )
    except Exception as e:
        logger.error(f"Failed to generate email draft: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate email draft: {str(e)}")
    
    # Determine recipients
    to_addresses = []
    if invoice.contact_email:
        to_addresses = [invoice.contact_email]
    else:
        raise HTTPException(status_code=400, detail="Invoice missing contact_email - cannot send email")
    
    cc_addresses = []
    if po and po.requester_email:
        cc_addresses = [po.requester_email]
    
    # Create email log entry
    issue_ids_list = [issue.id for issue in issues]
    
    email_log = EmailLog(
        document_pair_id=pair.id,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses if cc_addresses else None,
        subject=email_content['subject'],
        body_text=email_content['body_text'],
        body_html=email_content['body_html'],
        issue_ids=issue_ids_list,
        status='draft',
        drafted_by='system'  # TODO: Get from auth context
    )
    
    db.add(email_log)
    db.commit()
    db.refresh(email_log)
    
    logger.info(f"Created email draft {email_log.id} for pair {pair.id}")
    
    return EmailDraftResponse(
        email_log_id=email_log.id,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses if cc_addresses else None,
        subject=email_content['subject'],
        body_text=email_content['body_text'],
        body_html=email_content['body_html'],
        summary=email_content['summary'],
        status='draft'
    )


@router.post("/send", response_model=EmailSendResponse)
async def send_email(
    request: EmailSendRequest,
    db: Session = Depends(get_db)
):
    """
    Send drafted email via Gmail (with optional edits)
    """
    # Get email log
    email_log = db.query(EmailLog).filter(EmailLog.id == request.email_log_id).first()
    if not email_log:
        raise HTTPException(status_code=404, detail="Email log not found")
    
    if email_log.status == 'sent':
        raise HTTPException(status_code=400, detail="Email already sent")
    
    # Use provided values or fall back to draft values
    subject = request.subject or email_log.subject
    body_text = request.body_text or email_log.body_text
    body_html = request.body_html or email_log.body_html
    to_addresses = request.to_addresses or email_log.to_addresses
    cc_addresses = request.cc_addresses if request.cc_addresses is not None else email_log.cc_addresses
    
    # Send via Gmail
    try:
        result = gmail_service.send_email(
            to_addresses=to_addresses,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            cc_addresses=cc_addresses
        )
        
        # Update email log
        email_log.status = 'sent'
        email_log.gmail_message_id = result['message_id']
        email_log.gmail_thread_id = result.get('thread_id')
        email_log.sent_at = db.query(func.now()).scalar()  # Use SQL now()
        email_log.sent_by = 'system'  # TODO: Get from auth context
        
        # Update subject/body if edited
        if request.subject:
            email_log.subject = subject
        if request.body_text:
            email_log.body_text = body_text
        if request.body_html:
            email_log.body_html = body_html
        if request.to_addresses:
            email_log.to_addresses = to_addresses
        if request.cc_addresses is not None:
            email_log.cc_addresses = cc_addresses
        
        db.commit()
        
        logger.info(f"Sent email {email_log.id} via Gmail: {result['message_id']}")
        
        return EmailSendResponse(
            email_log_id=email_log.id,
            message_id=result['message_id'],
            thread_id=result.get('thread_id'),
            success=True,
            status='sent'
        )
        
    except Exception as e:
        logger.error(f"Failed to send email {email_log.id}: {e}")
        
        # Update email log with error
        email_log.status = 'failed'
        email_log.error_message = str(e)
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.get("/pair/{pair_id}/emails", response_model=List[EmailLogResponse])
def get_pair_emails(
    pair_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get all emails for a document pair
    """
    # Verify pair exists
    pair = db.query(DocumentPair).filter(DocumentPair.id == pair_id).first()
    if not pair:
        raise HTTPException(status_code=404, detail="Document pair not found")
    
    # Get all emails for this pair
    emails = db.query(EmailLog).filter(
        EmailLog.document_pair_id == pair_id
    ).order_by(EmailLog.created_at.desc()).all()
    
    return emails

