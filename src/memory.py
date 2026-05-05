from typing import List, Dict

# Global session store
# session_id -> list of messages
session_store: Dict[str, List[Dict[str, str]]] = {}

def get_history(session_id: str) -> List[Dict[str, str]]:
    """
    Get the conversation history for a given session.
    Returns an empty list if the session doesn't exist.
    """
    return session_store.get(session_id, [])

def add_message(session_id: str, role: str, content: str) -> None:
    """
    Add a message to the session history.
    role MUST be either "user" or "assistant".
    """
    if session_id not in session_store:
        session_store[session_id] = []
        
    session_store[session_id].append({
        "role": role,
        "content": content
    })
    
    # Limit history: Only keep last 5 messages
    session_store[session_id] = session_store[session_id][-5:]
