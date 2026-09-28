"""
Contact Manager for WhatsApp Automation
Handles contact lookup with fuzzy matching support.
"""

import json
import os
from typing import List, Dict, Optional, Any
from pathlib import Path

# Try to import rapidfuzz for fuzzy matching
try:
    from rapidfuzz import fuzz, process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    print("[ContactManager] Warning: rapidfuzz not installed. Using exact matching only.")


class ContactManager:
    """
    Manage contacts database with fuzzy matching for name resolution.
    """
    
    def __init__(self, contacts_path: Optional[str] = None):
        """
        Initialize contact manager.
        
        Args:
            contacts_path: Path to contacts.json file. 
                          If None, uses default path in DATA folder.
        """
        if contacts_path is None:
            # Default to DATA/contacts.json relative to JARVIS root
            jarvis_root = Path(__file__).parent.parent.parent
            contacts_path = jarvis_root / "DATA" / "contacts.json"
        
        self.contacts_path = Path(contacts_path)
        self.contacts: List[Dict[str, Any]] = []
        self._load_contacts()
    
    def _load_contacts(self):
        """Load contacts from JSON file."""
        if self.contacts_path.exists():
            try:
                with open(self.contacts_path, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                    self.contacts = data.get("contacts", [])
                print(f"[ContactManager] Loaded {len(self.contacts)} contacts")
            except Exception as e:
                print(f"[ContactManager] Error loading contacts: {e}")
                self.contacts = []
        else:
            print(f"[ContactManager] No contacts file found at {self.contacts_path}")
            self._create_sample_contacts()
    
    def _create_sample_contacts(self):
        """Create a sample contacts file."""
        sample = {
            "contacts": [
                {
                    "name": "Example Contact",
                    "aliases": ["example", "test"],
                    "phone": "YOUR_PHONE_NUMBER",
                    "notes": "This is a sample contact. Replace with your real contacts."
                }
            ]
        }
        
        try:
            self.contacts_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.contacts_path, 'w', encoding='utf-8') as f:
                json.dump(sample, f, indent=2)
            print(f"[ContactManager] Created sample contacts file at {self.contacts_path}")
            self.contacts = sample["contacts"]
        except Exception as e:
            print(f"[ContactManager] Could not create sample file: {e}")
    
    def resolve(self, query: str, threshold: int = 70) -> Dict[str, Any]:
        """
        Resolve a contact name to phone number.
        
        Args:
            query: Contact name or alias to look up
            threshold: Minimum fuzzy match score (0-100)
            
        Returns:
            Dict with:
                - found: bool
                - contact: Dict with name, phone (if found)
                - matches: List of potential matches (if ambiguous)
                - error: str (if not found)
        """
        query = query.lower().strip()
        
        # First try exact match on name or aliases
        for contact in self.contacts:
            name = contact.get("name", "").lower()
            aliases = [a.lower() for a in contact.get("aliases", [])]
            
            if query == name or query in aliases:
                return {
                    "found": True,
                    "contact": contact,
                    "confidence": 100
                }
        
        # Try fuzzy matching if available
        if FUZZY_AVAILABLE and self.contacts:
            return self._fuzzy_resolve(query, threshold)
        
        # No match found
        return {
            "found": False,
            "error": f"Contact '{query}' not found",
            "suggestions": self._get_suggestions(query)
        }
    
    def _fuzzy_resolve(self, query: str, threshold: int) -> Dict[str, Any]:
        """Use fuzzy matching to find contacts."""
        # Build list of all searchable names
        searchable = []
        for contact in self.contacts:
            # Add main name
            searchable.append((contact["name"], contact))
            # Add aliases
            for alias in contact.get("aliases", []):
                searchable.append((alias, contact))
        
        if not searchable:
            return {"found": False, "error": "No contacts in database"}
        
        # Find best matches
        names = [s[0] for s in searchable]
        matches = process.extract(query, names, scorer=fuzz.WRatio, limit=5)
        
        # Filter by threshold
        good_matches = [(name, score) for name, score, _ in matches if score >= threshold]
        
        if not good_matches:
            return {
                "found": False,
                "error": f"No close matches for '{query}'",
                "suggestions": [m[0] for m in matches[:3]]
            }
        
        # Get the best match
        best_name, best_score = good_matches[0]
        
        # Find the contact for best match
        for name, contact in searchable:
            if name == best_name:
                # Check if there are other equally good matches (ambiguous)
                if len(good_matches) > 1 and good_matches[1][1] >= best_score - 5:
                    # Ambiguous - multiple close matches
                    unique_contacts = []
                    seen_phones = set()
                    for match_name, _ in good_matches:
                        for n, c in searchable:
                            if n == match_name and c["phone"] not in seen_phones:
                                unique_contacts.append(c)
                                seen_phones.add(c["phone"])
                    
                    if len(unique_contacts) > 1:
                        return {
                            "found": False,
                            "ambiguous": True,
                            "matches": unique_contacts[:3],
                            "message": f"Multiple contacts match '{query}'. Please be more specific."
                        }
                
                return {
                    "found": True,
                    "contact": contact,
                    "confidence": best_score
                }
        
        return {"found": False, "error": "Unexpected error in fuzzy matching"}
    
    def _get_suggestions(self, query: str) -> List[str]:
        """Get name suggestions based on partial match."""
        suggestions = []
        query_lower = query.lower()
        
        for contact in self.contacts:
            name = contact.get("name", "")
            if query_lower in name.lower():
                suggestions.append(name)
            else:
                for alias in contact.get("aliases", []):
                    if query_lower in alias.lower():
                        suggestions.append(name)
                        break
        
        return suggestions[:3]
    
    def add_contact(self, name: str, phone: str, aliases: Optional[List[str]] = None) -> bool:
        """
        Add a new contact.
        
        Args:
            name: Contact display name
            phone: Phone number with country code (e.g., YOUR_PHONE_NUMBER)
            aliases: Optional list of nicknames/aliases
            
        Returns:
            True if added successfully
        """
        contact = {
            "name": name,
            "phone": phone,
            "aliases": aliases or []
        }
        
        self.contacts.append(contact)
        return self._save_contacts()
    
    def _save_contacts(self) -> bool:
        """Save contacts to JSON file."""
        try:
            with open(self.contacts_path, 'w', encoding='utf-8') as f:
                json.dump({"contacts": self.contacts}, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ContactManager] Error saving contacts: {e}")
            return False
    
    def list_all(self) -> List[Dict[str, Any]]:
        """Return all contacts."""
        return self.contacts


if __name__ == "__main__":
    # Test the contact manager
    cm = ContactManager()
    
    print("\nAll contacts:")
    for c in cm.list_all():
        print(f"  - {c['name']}: {c['phone']}")
    
    print("\nTest lookups:")
    test_names = ["example", "test", "unknown", "exampl"]  # Last one tests fuzzy
    for name in test_names:
        result = cm.resolve(name)
        print(f"  '{name}': {result}")
