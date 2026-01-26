from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
import os
import json
import google.auth
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.models import GmailEvent
from app.config import Config
from app.utils.logger import get_logger

logger = get_logger("gmail_service")

class GmailService:
    """
    Service to interact with Gmail API for fetching unread emails.
    Uses Domain-wide Delegation to access user mailboxes.
    """
    # Separate scopes for Admin-only tasks and User-level tasks
    REPORTS_SCOPES = ['https://www.googleapis.com/auth/admin.reports.audit.readonly']
    GMAIL_SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    # Combined scopes for initializing the base credentials
    ALL_SCOPES = REPORTS_SCOPES + GMAIL_SCOPES

    def __init__(self):
        # Load base credentials with all necessary scopes
        self.base_creds = self._load_base_credentials(self.ALL_SCOPES)
        
        # Admin delegated creds for Reports API
        self.admin_creds = self.base_creds.with_scopes(self.REPORTS_SCOPES).with_subject(Config.ADMIN_EMAIL)
        self.admin_service = build('admin', 'reports_v1', credentials=self.admin_creds)
        
        # Default gmail service delegated to admin (for backward compatibility)
        self.creds = self.base_creds.with_scopes(self.GMAIL_SCOPES).with_subject(Config.ADMIN_EMAIL)
        self.gmail_service = build('gmail', 'v1', credentials=self.creds)

    def _load_base_credentials(self, scopes: List[str]):
        """
        Load base Google credentials from GOOGLE_APPLICATION_CREDENTIALS.
        """
        creds_env = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        if not creds_env:
            logger.info("GOOGLE_APPLICATION_CREDENTIALS not set, using default application credentials")
            creds, project = google.auth.default(scopes=scopes)
            if isinstance(creds, service_account.Credentials):
                return creds
            raise ValueError(f"Unsupported credentials type for domain-wide delegation: {type(creds)}")
        
        try:
            creds_info = json.loads(creds_env)
            return service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        except (json.JSONDecodeError, ValueError):
            return service_account.Credentials.from_service_account_file(creds_env, scopes=scopes)

    def fetch_domain_logs(self, max_results: int = 1000, start_time: Optional[str] = None, end_time: Optional[str] = None) -> List[GmailEvent]:
        """
        Fetch domain-wide email receive logs using Admin SDK Reports API.
        """
        logger.info(f"Fetching domain-wide mail logs (max {max_results})...")
        all_events = []
        next_page_token = None
        
        now = datetime.now(timezone.utc)
        if not start_time:
            start_time = (now - timedelta(days=29)).isoformat().replace('+00:00', 'Z')
        if not end_time:
            end_time = now.isoformat().replace('+00:00', 'Z')
        
        while len(all_events) < max_results:
            try:
                fetch_count = min(max_results - len(all_events), 1000)
                results = self.admin_service.activities().list(
                    userKey='all',
                    applicationName='gmail',
                    maxResults=fetch_count,
                    pageToken=next_page_token,
                    startTime=start_time,
                    endTime=end_time
                ).execute()
                
                activities = results.get('items', [])
                if not activities: break
                
                for activity in activities:
                    event = self._parse_activity(activity)
                    if event: all_events.append(event)
                
                next_page_token = results.get('nextPageToken')
                if not next_page_token or len(all_events) >= max_results: break
            except Exception as e:
                logger.error(f"Error fetching domain logs: {e}")
                break
                
        return all_events[:max_results]
    
    def _get_gmail_client_for_user(self, user_email: str):
        """
        Create a Gmail API client delegated to a specific user with ONLY Gmail scopes.
        Requesting Admin scopes for a non-admin user causes 403 error.
        """
        delegated_creds = self.base_creds.with_scopes(self.GMAIL_SCOPES).with_subject(user_email)
        return build('gmail', 'v1', credentials=delegated_creds, cache_discovery=False)

    def fetch_unread_emails(self, user_emails: List[str], max_results: int = 50) -> List[GmailEvent]:
        """
        Fetch unread emails from Gmail for multiple users in parallel.
        """
        all_events = []
        from concurrent.futures import ThreadPoolExecutor, as_completed
        max_workers = min(len(user_emails), 10)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_user = {executor.submit(self._fetch_unread_for_user, user, max_results): user for user in user_emails}
            for future in as_completed(future_to_user):
                try:
                    user_events = future.result()
                    all_events.extend(user_events)
                except Exception as e:
                    logger.error(f"Error fetching for {future_to_user[future]}: {e}")
        
        return all_events
    
    def _fetch_unread_for_user(self, user_email: str, max_results: int = 50) -> List[GmailEvent]:
        gmail_client = self._get_gmail_client_for_user(user_email)
        query = 'is:unread in:inbox newer_than:1d'
        events = []
        try:
            response = gmail_client.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = response.get('messages', [])
            for msg_ref in messages:
                message = gmail_client.users().messages().get(
                    userId='me', id=msg_ref['id'], format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date', 'Message-ID']
                ).execute()
                event = self._parse_gmail_message(message, user_email)
                if event: events.append(event)
        except Exception as e:
            logger.error(f"Gmail API error for {user_email}: {e}")
        return events
    
    def _parse_gmail_message(self, message: dict, owner_email: str) -> Optional[GmailEvent]:
        try:
            headers = message.get('payload', {}).get('headers', [])
            header_dict = {h['name'].lower(): h['value'] for h in headers}
            subject = header_dict.get('subject', '(제목 없음)')
            from_header = header_dict.get('from', '')
            message_id = header_dict.get('message-id', message['id'])
            sender = from_header
            if '<' in from_header: sender = from_header.split('<')[1].split('>')[0]
            
            timestamp = datetime.now(timezone.utc)
            if message.get('internalDate'):
                timestamp = datetime.fromtimestamp(int(message.get('internalDate')) / 1000, tz=timezone.utc)
            
            return GmailEvent(
                timestamp=timestamp, message_id=message_id, subject=subject, sender=sender,
                owner=owner_email, event_type='UNREAD',
                raw_data={'gmail_id': message['id'], 'snippet': message.get('snippet', '')}
            )
        except Exception: return None

    def _parse_activity(self, activity: dict) -> Optional[GmailEvent]:
        try:
            timestamp_str = activity.get('id', {}).get('time')
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            owner_email = activity.get('actor', {}).get('email')
            events_list = activity.get('events', [])
            if not events_list: return None
            params = {p.get('name'): p.get('value') or p.get('multiValue') for p in events_list[0].get('parameters', [])}
            message_id = params.get('message_id') or params.get('rfc2822_message_id')
            sender = params.get('from_address') or params.get('sender') or owner_email
            if not message_id: return None
            return GmailEvent(
                timestamp=timestamp, message_id=message_id, subject=params.get('subject'),
                sender=sender, owner=owner_email, event_type=events_list[0].get('name', ''),
                raw_data=activity
            )
        except Exception: return None
    
    def is_message_unread(self, message_id: str, user_email: str) -> bool:
        try:
            gmail_client = self._get_gmail_client_for_user(user_email)
            internal_id = message_id
            if '@' in message_id or message_id.startswith('<'):
                res = gmail_client.users().messages().list(userId='me', q=f'rfc822msgid:{message_id}', maxResults=1).execute()
                if not res.get('messages'): return False
                internal_id = res['messages'][0]['id']
            msg = gmail_client.users().messages().get(userId='me', id=internal_id, format='minimal').execute()
            return 'UNREAD' in msg.get('labelIds', [])
        except Exception: return True

    def mark_as_read(self, message_id: str, user_email: str) -> bool:
        """
        Mark a Gmail message as read by removing the UNREAD label.
        """
        try:
            gmail_client = self._get_gmail_client_for_user(user_email)
            internal_msg_id = message_id
            if message_id.startswith('<') or '@' in message_id:
                query = f'rfc822msgid:{message_id}'
                results = gmail_client.users().messages().list(userId='me', q=query, maxResults=1).execute()
                msgs = results.get('messages', [])
                if not msgs:
                    logger.warning(f"Message {message_id} not found to mark as read for {user_email}")
                    return False
                internal_msg_id = msgs[0]['id']

            gmail_client.users().messages().modify(
                userId='me',
                id=internal_msg_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            logger.info(f"Successfully marked message {message_id} as read for {user_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark message {message_id} as read for {user_email}: {e}")
            return False
