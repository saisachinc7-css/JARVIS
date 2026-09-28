"""
Google Workspace Client for JARVIS
Connects to Google Apps Script Web App for Gmail, Drive, Calendar, Sheets operations
"""

import requests
import json
import os
from typing import Dict, Any, Optional
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)


class GoogleWorkspaceClient:
    """HTTP client for Google Apps Script bridge"""
    
    # Configure via .env: APPS_SCRIPT_URL="YOUR_DEPLOYMENT_URL_HERE"
    WEB_APP_URL = os.getenv("APPS_SCRIPT_URL", "YOUR_DEPLOYMENT_URL_HERE")
    
    def __init__(self, url: Optional[str] = None):
        self.url = url or self.WEB_APP_URL
        logger.info(f"[Google Workspace] Initialized with URL: {self.url[:60]}...")
    
    def _request(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send request to Apps Script"""
        payload = {
            "action": action,
            "params": params or {}
        }
        
        logger.debug(f"[Google Workspace] → {action} with params: {params}")
        
        try:
            response = requests.post(
                self.url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "success":
                logger.info(f"[Google Workspace] [OK] {action} succeeded")
            else:
                logger.error(f"[Google Workspace] ✗ {action} failed: {result.get('error')}")
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"[Google Workspace] Timeout for {action}")
            return {
                "status": "error",
                "error": "Request timed out. Google Apps Script may be slow."
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"[Google Workspace] Request failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
        except json.JSONDecodeError as e:
            logger.error(f"[Google Workspace] Invalid JSON response: {e}")
            return {
                "status": "error",
                "error": "Invalid response from Google Apps Script"
            }
    
    # ===== TEST =====
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Apps Script"""
        return self._request("test")
    
    # ===== GMAIL METHODS =====
    
    def gmail_list_unread(self, limit: int = 10) -> Dict[str, Any]:
        """Get unread emails"""
        return self._request("gmail_list_unread", {"limit": limit})
    
    def gmail_search(self, query: str = "", from_email: str = "", 
                     subject: str = "", keyword: str = "", limit: int = 10) -> Dict[str, Any]:
        """Search Gmail"""
        params = {
            "query": query,
            "from": from_email,
            "subject": subject,
            "keyword": keyword,
            "limit": limit
        }
        return self._request("gmail_search", params)
    
    def gmail_send(self, to: str, subject: str, body: str, 
                   cc: str = "", bcc: str = "") -> Dict[str, Any]:
        """Send email"""
        params = {
            "to": to,
            "subject": subject,
            "body": body
        }
        if cc:
            params["cc"] = cc
        if bcc:
            params["bcc"] = bcc
        return self._request("gmail_send", params)
    
    def gmail_draft_reply(self, thread_id: str, reply_text: str) -> Dict[str, Any]:
        """Create draft reply"""
        return self._request("gmail_draft_reply", {
            "threadId": thread_id,
            "replyText": reply_text
        })
    
    def gmail_summarize(self, period: str = "today") -> Dict[str, Any]:
        """Summarize Gmail inbox"""
        return self._request("gmail_summarize", {"period": period})
    
    def gmail_detect_urgent(self) -> Dict[str, Any]:
        """Detect urgent emails"""
        return self._request("gmail_detect_urgent")
    
    # ===== DRIVE METHODS =====
    
    def drive_list_files(self, file_type: str = None, query: str = "", limit: int = 20) -> Dict[str, Any]:
        """List Google Drive files"""
        params = {
            "fileType": file_type,
            "query": query,
            "limit": limit
        }
        return self._request("drive_list_files", params)
    
    def drive_read_doc(self, doc_id: str = None, file_name: str = None) -> Dict[str, Any]:
        """Read Google Doc content"""
        params = {}
        if doc_id:
            params["docId"] = doc_id
        if file_name:
            params["fileName"] = file_name
        return self._request("drive_read_doc", params)
    
    def drive_create_doc(self, title: str, content: str = "", folder_id: str = None) -> Dict[str, Any]:
        """Create new Google Doc"""
        params = {
            "title": title,
            "content": content
        }
        if folder_id:
            params["folderId"] = folder_id
        return self._request("drive_create_doc", params)
    
    def drive_rename_file(self, file_id: str, new_name: str) -> Dict[str, Any]:
        """Rename a file"""
        return self._request("drive_rename_file", {
            "fileId": file_id,
            "newName": new_name
        })
    
    def drive_move_file(self, file_id: str, target_folder_id: str) -> Dict[str, Any]:
        """Move file to folder"""
        return self._request("drive_move_file", {
            "fileId": file_id,
            "targetFolderId": target_folder_id
        })
    
    def drive_delete_file(self, file_id: str) -> Dict[str, Any]:
        """Delete (trash) a file"""
        return self._request("drive_delete_file", {"fileId": file_id})
    
    # ===== CALENDAR METHODS =====
    
    def calendar_get_events(self, time_min: str = None, time_max: str = None) -> Dict[str, Any]:
        """Get calendar events"""
        params = {}
        if time_min:
            params["timeMin"] = time_min
        if time_max:
            params["timeMax"] = time_max
        return self._request("calendar_get_events", params)
    
    def calendar_get_today(self) -> Dict[str, Any]:
        """Get today's calendar events (IST timezone)"""
        from datetime import datetime, timedelta
        today = datetime.now()
        params = {
            "timeMin": today.strftime("%Y-%m-%dT00:00:00+05:30"),
            "timeMax": (today + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00+05:30")
        }
        return self._request("calendar_get_events", params)
    
    def tasks_get_today(self) -> Dict[str, Any]:
        """Get today's Google Tasks (requires tasks_list in Apps Script)"""
        from datetime import datetime, timedelta
        today = datetime.now()
        params = {
            "dueMin": today.strftime("%Y-%m-%dT00:00:00+05:30"),
            "dueMax": (today + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59+05:30"),
            "maxResults": 20
        }
        return self._request("tasks_list", params)
    
    def calendar_create_event(self, title: str, start_time: str, end_time: str,
                             description: str = "", location: str = "", 
                             attendees: list = None) -> Dict[str, Any]:
        """Create calendar event"""
        params = {
            "title": title,
            "startTime": start_time,
            "endTime": end_time,
            "description": description,
            "location": location
        }
        if attendees:
            params["attendees"] = attendees
        return self._request("calendar_create_event", params)
    
    # ===== SHEETS METHODS =====
    
    def sheets_read(self, spreadsheet_id: str, sheet_name: str = "Sheet1", 
                    range_notation: str = None) -> Dict[str, Any]:
        """Read Google Sheets data"""
        params = {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name
        }
        if range_notation:
            params["range"] = range_notation
        return self._request("sheets_read", params)
    
    def sheets_write(self, spreadsheet_id: str, sheet_name: str, 
                     range_notation: str, values: list) -> Dict[str, Any]:
        """Write to Google Sheets"""
        return self._request("sheets_write", {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name,
            "range": range_notation,
            "values": values
        })
    
    def sheets_append(self, spreadsheet_id: str, sheet_name: str, values: list) -> Dict[str, Any]:
        """Append row to Google Sheets"""
        return self._request("sheets_append", {
            "spreadsheetId": spreadsheet_id,
            "sheetName": sheet_name,
            "values": values
        })


# Global client instance
_client: Optional[GoogleWorkspaceClient] = None


def get_google_client() -> GoogleWorkspaceClient:
    """Get or create the global Google Workspace client"""
    global _client
    if _client is None:
        _client = GoogleWorkspaceClient()
    return _client


if __name__ == "__main__":
    # Test the client
    import sys
    
    print("\n" + "="*60)
    print("🔌 JARVIS Google Workspace Connection Test")
    print("="*60 + "\n")
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    client = get_google_client()
    
    # Test 1: Connection
    print("Test 1: Connection Test")
    print("-" * 60)
    result = client.test_connection()
    if result.get("status") == "success":
        print(f"[OK] SUCCESS: {result['data']['message']}")
    else:
        print(f"✗ FAILED: {result.get('error')}")
        sys.exit(1)
    print()
    
    # Test 2: Gmail
    print("Test 2: Gmail - Check Unread Emails")
    print("-" * 60)
    result = client.gmail_list_unread(3)
    if result.get("status") == "success":
        data = result["data"]
        print(f"[OK] SUCCESS: Found {data['count']} unread emails (Total: {data['totalUnread']})")
        for i, email in enumerate(data.get("emails", []), 1):
            print(f"  {i}. {email['subject']}")
            print(f"     From: {email['from']}")
    else:
        print(f"✗ FAILED: {result.get('error')}")
    print()
    
    # Test 3: Calendar
    print("Test 3: Calendar - Today's Events")
    print("-" * 60)
    result = client.calendar_get_today()
    if result.get("status") == "success":
        data = result["data"]
        print(f"[OK] SUCCESS: Found {data['count']} events today")
        for i, event in enumerate(data.get("events", []), 1):
            print(f"  {i}. {event['title']}")
    else:
        print(f"✗ FAILED: {result.get('error')}")
    print()
    
    # Test 4: Drive
    print("Test 4: Drive - List Recent Files")
    print("-" * 60)
    result = client.drive_list_files(limit=5)
    if result.get("status") == "success":
        data = result["data"]
        print(f"[OK] SUCCESS: Found {data['count']} files")
        for i, file in enumerate(data.get("files", []), 1):
            print(f"  {i}. {file['name']} ({file['mimeType'].split('.')[-1]})")
    else:
        print(f"✗ FAILED: {result.get('error')}")
    print()
    
    print("="*60)
    print("[OK] All tests completed!")
    print("="*60)
