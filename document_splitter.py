"""
Helper module to split combined SRS + User Stories documents
"""

def split_combined_document(text: str) -> dict:
    """
    Split a document that contains both SRS and User Stories sections.
    
    Returns:
        dict with keys 'srs_text' and 'stories_text'
    """
    # Find the boundary between SRS and User Stories
    # Common patterns: "User Story 1", "User Stories", "US-", "Story-"
    
    lower_text = text.lower()
    
    # Search for user story markers
    markers = [
        'user story 1',
        'user story #1',
        'story 1:',
        'us-1',
        'us1:',
    ]
    
    split_index = -1
    
    for marker in markers:
        idx = lower_text.find(marker)
        if idx != -1:
            split_index = idx
            break
    
    if split_index == -1:
        # Try to find any line starting with "User Story"
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('user story'):
                # Get character position
                split_index = sum(len(l) + 1 for l in lines[:i])
                break
    
    if split_index == -1:
        # Could not find split point - assume entire document is SRS
        return {
            'srs_text': text,
            'stories_text': None,
            'has_both': False
        }
    
    # Split the document
    srs_part = text[:split_index].strip()
    stories_part = text[split_index:].strip()
    
    return {
        'srs_text': srs_part,
        'stories_text': stories_part,
        'has_both': True
    }


def detect_document_type(text: str) -> str:
    """
    Detect if a document is SRS, User Stories, or Both.
    
    Returns:
        'srs', 'user_stories', or 'both'
    """
    lower_text = text.lower()
    
    # Check for SRS indicators
    has_srs = any(indicator in lower_text for indicator in [
        'software requirements specification',
        'system requirements',
        'functional requirements',
        'non-functional requirements',
        'srs',
        'overall description',
        'external interface requirements'
    ])
    
    # Check for User Story indicators
    has_stories = any(indicator in lower_text for indicator in [
        'as a ',
        'as an ',
        'user story',
        'i want to',
        'so that'
    ])
    
    if has_srs and has_stories:
        return 'both'
    elif has_srs:
        return 'srs'
    elif has_stories:
        return 'user_stories'
    else:
        return 'unknown'