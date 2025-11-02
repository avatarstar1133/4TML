#!/usr/bin/env python3
"""
Document Splitter - Helper to split combined SRS + User Stories documents.
Language-agnostic logic but tuned for common ENGLISH markers.
Never modifies the original text content; only slices and returns as-is.
"""

def split_combined_document(text: str) -> dict:
    lower_text = text.lower()
    markers = ['user story 1', 'user story #1', 'story 1:', 'us-1', 'us1:', 'user story:']
    split_index = -1

    for marker in markers:
        idx = lower_text.find(marker)
        if idx != -1:
            split_index = idx
            break

    if split_index == -1:
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if line.strip().lower().startswith('user story'):
                split_index = sum(len(l) + 1 for l in lines[:i])
                break

    if split_index == -1:
        return {'srs_text': text, 'stories_text': None, 'has_both': False}

    srs_part = text[:split_index].strip()
    stories_part = text[split_index:].strip()
    return {'srs_text': srs_part, 'stories_text': stories_part, 'has_both': True}


def detect_document_type(text: str) -> str:
    lower_text = text.lower()
    srs_indicators = [
        'software requirements specification', 'system requirements',
        'functional requirements', 'non-functional requirements', 'srs',
        'overall description', 'external interface requirements', 'system features',
        'performance requirements'
    ]
    story_indicators = [
        'as a ', 'as an ', 'user story', 'i want to', 'so that',
        'acceptance criteria', 'given when then'
    ]
    has_srs = any(ind in lower_text for ind in srs_indicators)
    has_stories = any(ind in lower_text for ind in story_indicators)
    if has_srs and has_stories:
        return 'both'
    if has_srs:
        return 'srs'
    if has_stories:
        return 'user_stories'
    return 'unknown'


def extract_sections(text: str) -> dict:
    sections = {
        'introduction': [], 'functional_requirements': [],
        'non_functional_requirements': [], 'user_stories': [], 'other': []
    }
    lines = text.split('\n')
    current = 'other'
    for line in lines:
        lower = line.lower().strip()
        if 'introduction' in lower or 'overview' in lower:
            current = 'introduction'
        elif 'functional requirement' in lower:
            current = 'functional_requirements'
        elif 'non-functional requirement' in lower or 'non functional' in lower:
            current = 'non_functional_requirements'
        elif 'user story' in lower or 'user stories' in lower:
            current = 'user_stories'
        if line.strip():
            sections[current].append(line)
    return {k: '\n'.join(v) if v else '' for k, v in sections.items()}


def validate_document_quality(text: str) -> dict:
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    words = text.split()
    metrics = {
        'total_lines': len(lines),
        'total_words': len(words),
        'total_chars': len(text),
        'avg_line_length': len(text) / len(lines) if lines else 0,
        'has_headers': False,
        'has_numbering': False,
        'has_requirements': False,
    }
    for line in lines:
        low = line.lower()
        if ':' in line or any(w in low for w in ['section', 'chapter', 'overview']):
            metrics['has_headers'] = True
        if line[0].isdigit() and ('.' in line[:5] or ')' in line[:5]):
            metrics['has_numbering'] = True
        if any(w in low for w in ['shall', 'must', 'should', 'will']):
            metrics['has_requirements'] = True
    factors = [
        metrics['total_words'] > 100,
        metrics['has_headers'],
        metrics['has_numbering'],
        metrics['has_requirements'],
        metrics['avg_line_length'] > 20,
    ]
    metrics['quality_score'] = sum(factors) / len(factors)
    return metrics
