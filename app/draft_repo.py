"""
Draft Repository Module
SQLite persistence for email drafts
"""
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class DraftRepository:
    def __init__(self, db_path: str = "drafts.db"):
        """
        Initialize the draft repository with SQLite
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        self._create_tables_if_not_exist()
    
    def _create_tables_if_not_exist(self) -> None:
        """Create the necessary tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create drafts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            draft_id TEXT NOT NULL,
            reply_text TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_draft(self, message_id: str, draft_id: str, reply_text: str, status: str = "pending") -> int:
        """
        Save a new draft to the database
        
        Args:
            message_id: Gmail message ID
            draft_id: Gmail draft ID
            reply_text: The text of the reply
            status: Status of the draft (pending, sent_no_edit, sent_with_edit, rejected)
            
        Returns:
            int: The ID of the inserted record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO drafts (message_id, draft_id, reply_text, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (message_id, draft_id, reply_text, status, datetime.now(), datetime.now()))
        
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return last_id
    
    def update_draft_status(self, db_id: int, status: str, updated_text: Optional[str] = None) -> bool:
        """
        Update the status of a draft
        
        Args:
            db_id: Database ID of the draft
            status: New status
            updated_text: Updated reply text (if edited)
            
        Returns:
            bool: Success status
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if updated_text:
            cursor.execute('''
            UPDATE drafts
            SET status = ?, reply_text = ?, updated_at = ?
            WHERE id = ?
            ''', (status, updated_text, datetime.now(), db_id))
        else:
            cursor.execute('''
            UPDATE drafts
            SET status = ?, updated_at = ?
            WHERE id = ?
            ''', (status, datetime.now(), db_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    def get_draft(self, db_id: int) -> Optional[Dict]:
        """
        Get a draft by its database ID
        
        Args:
            db_id: Database ID of the draft
            
        Returns:
            Optional[Dict]: Draft data or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM drafts WHERE id = ?', (db_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_pending_drafts(self) -> List[Dict]:
        """
        Get all pending drafts
        
        Returns:
            List[Dict]: List of pending drafts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM drafts WHERE status = ? ORDER BY created_at DESC', ('pending',))
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_all_drafts(self, limit: int = 100) -> List[Dict]:
        """
        Get all drafts with pagination
        
        Args:
            limit: Maximum number of drafts to return
            
        Returns:
            List[Dict]: List of drafts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM drafts ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_draft(self, db_id: int) -> bool:
        """
        Delete a draft from the database
        
        Args:
            db_id: Database ID of the draft
            
        Returns:
            bool: Success status
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM drafts WHERE id = ?', (db_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
