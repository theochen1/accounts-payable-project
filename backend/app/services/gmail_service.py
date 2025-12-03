"""
Gmail API Service for sending emails

Handles OAuth2 authentication and email sending via Gmail API.
"""
import base64
import json
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class GmailService:
    """Service for sending emails via Gmail API"""
    
    def __init__(self):
        """Initialize Gmail API client"""
        self.sender_email = os.getenv('GMAIL_SENDER_EMAIL') or (settings.gmail_sender_email if hasattr(settings, 'gmail_sender_email') else None)
        self.creds = None
        self.service = None
        self.init_error = None
        
        # Log what credentials are available
        has_json = bool(os.getenv('GMAIL_CREDENTIALS_JSON'))
        has_separate = all([os.getenv('GMAIL_CLIENT_ID'), os.getenv('GMAIL_CLIENT_SECRET'), os.getenv('GMAIL_REFRESH_TOKEN')])
        
        logger.info(f"Gmail credentials check: GMAIL_CREDENTIALS_JSON={'set' if has_json else 'not set'}, "
                   f"GMAIL_CLIENT_ID={'set' if os.getenv('GMAIL_CLIENT_ID') else 'not set'}, "
                   f"GMAIL_CLIENT_SECRET={'set' if os.getenv('GMAIL_CLIENT_SECRET') else 'not set'}, "
                   f"GMAIL_REFRESH_TOKEN={'set' if os.getenv('GMAIL_REFRESH_TOKEN') else 'not set'}, "
                   f"GMAIL_SENDER_EMAIL={'set' if self.sender_email else 'not set'}")
        
        if not has_json and not has_separate:
            self.init_error = "Missing Gmail credentials. Set either GMAIL_CREDENTIALS_JSON or (GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET + GMAIL_REFRESH_TOKEN)"
            logger.warning(self.init_error)
            return
        
        if not self.sender_email:
            self.init_error = "GMAIL_SENDER_EMAIL not set"
            logger.warning(self.init_error)
            return
        
        self.creds = self._load_credentials()
        
        if self.creds:
            try:
                self.service = build('gmail', 'v1', credentials=self.creds)
                logger.info("Gmail service initialized successfully")
            except Exception as e:
                self.init_error = f"Failed to build Gmail service: {e}"
                logger.error(self.init_error)
                self.service = None
        else:
            logger.warning("Gmail credentials could not be loaded - email sending will be disabled")
    
    def _load_credentials(self) -> Optional[Credentials]:
        """Load Gmail API credentials from environment or OAuth flow"""
        # Try to load from environment variables (for Railway/production)
        credentials_json = os.getenv('GMAIL_CREDENTIALS_JSON')
        
        if credentials_json:
            try:
                creds_data = json.loads(credentials_json)
                creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
                
                # Refresh token if expired
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                
                return creds
            except Exception as e:
                logger.error(f"Failed to load credentials from GMAIL_CREDENTIALS_JSON: {e}")
        
        # Try OAuth2 flow with client ID/secret (for development)
        client_id = os.getenv('GMAIL_CLIENT_ID')
        client_secret = os.getenv('GMAIL_CLIENT_SECRET')
        refresh_token = os.getenv('GMAIL_REFRESH_TOKEN')
        
        if client_id and client_secret and refresh_token:
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=SCOPES
                )
                # Refresh to get access token
                creds.refresh(Request())
                logger.info("Successfully loaded and refreshed OAuth2 credentials")
                return creds
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to load credentials from OAuth2 tokens: {e}")
                
                # Provide more specific error guidance
                if 'unauthorized_client' in error_msg.lower():
                    logger.error("UNAUTHORIZED_CLIENT error - This usually means:")
                    logger.error("  1. The refresh token is invalid or expired")
                    logger.error("  2. The refresh token was generated with different OAuth credentials")
                    logger.error("  3. The OAuth consent screen needs to be configured")
                    logger.error("  4. The refresh token needs to be regenerated with scope: https://www.googleapis.com/auth/gmail.send")
                elif 'invalid_grant' in error_msg.lower():
                    logger.error("INVALID_GRANT error - The refresh token has expired or been revoked")
                    logger.error("  You need to generate a new refresh token")
                
                return None
        
        logger.warning("No Gmail credentials found - email sending disabled")
        return None
    
    def send_email(
        self,
        to_addresses: List[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        cc_addresses: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Send email via Gmail API
        
        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject line
            body_html: HTML email body
            body_text: Plain text email body (optional, defaults to HTML stripped)
            cc_addresses: List of CC email addresses (optional)
        
        Returns:
            dict with 'message_id', 'thread_id', 'success' if successful
            
        Raises:
            HttpError if sending fails
        """
        if not self.service:
            error_detail = self.init_error or "Gmail service not initialized - check credentials"
            raise Exception(f"Gmail service not initialized: {error_detail}")
        
        if not self.sender_email:
            raise Exception("GMAIL_SENDER_EMAIL not configured")
        
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['To'] = ', '.join(to_addresses)
            message['From'] = self.sender_email
            message['Subject'] = subject
            
            if cc_addresses:
                message['Cc'] = ', '.join(cc_addresses)
            
            # Add plain text version
            if body_text:
                part1 = MIMEText(body_text, 'plain')
                message.attach(part1)
            else:
                # Generate plain text from HTML if not provided
                import re
                plain_text = re.sub(r'<[^>]+>', '', body_html)
                part1 = MIMEText(plain_text, 'plain')
                message.attach(part1)
            
            # Add HTML version
            part2 = MIMEText(body_html, 'html')
            message.attach(part2)
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send via Gmail API
            send_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully: message_id={send_message['id']}")
            
            return {
                'message_id': send_message['id'],
                'thread_id': send_message.get('threadId'),
                'success': True
            }
            
        except HttpError as error:
            logger.error(f'Gmail API error: {error}')
            raise Exception(f"Failed to send email via Gmail API: {error}")
        except Exception as e:
            logger.error(f'Unexpected error sending email: {e}')
            raise Exception(f"Failed to send email: {e}")

