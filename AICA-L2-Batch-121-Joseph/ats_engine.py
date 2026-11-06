#!/usr/bin/env python3
"""
ATS Engine - High-Volume CV Screening, Parsing, and Matching Engine in Python.
Performs unbiased, weighted matching against HR criteria without inventing information.
"""

import sys
import os
import json
import re
import hashlib
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

def compute_file_hash(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()

def extract_text_from_docx(file_bytes):
    """Extract text from docx file bytes using zipfile and xml parsing."""
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as docx:
            xml_content = docx.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            paragraphs = []
            for node in tree.iter():
                if node.tag.endswith('}p'):
                    p_text = ''.join(n.text for n in node.iter() if n.text)
                    if p_text.strip():
                        paragraphs.append(p_text.strip())
            return '\n'.join(paragraphs)
    except Exception as e:
        return ""

def extract_text_from_raw_pdf(file_bytes):
    """Extract readable text streams from PDF bytes without external binary."""
    try:
        text_parts = []
        # Find stream objects
        streams = re.findall(rb'stream[\r\n]+(.*?)[\r\n]+endstream', file_bytes, re.DOTALL)
        for s in streams:
            try:
                import zlib
                decompressed = zlib.decompress(s)
                # extract Tj / TJ strings
                tj_matches = re.findall(rb'\((.*?)\)\s*Tj', decompressed)
                for tj in tj_matches:
                    try:
                        text_parts.append(tj.decode('latin1', errors='ignore'))
                    except Exception:
                        pass
                tj_array_matches = re.findall(rb'\[(.*?)\]\s*TJ', decompressed)
                for arr in tj_array_matches:
                    inner_strs = re.findall(rb'\((.*?)\)', arr)
                    for item in inner_strs:
                        try:
                            text_parts.append(item.decode('latin1', errors='ignore'))
                        except Exception:
                            pass
            except Exception:
                pass
        
        extracted = ' '.join(text_parts).strip()
        if len(extracted) > 100:
            return extracted
        
        # Fallback to ASCII strings extraction
        ascii_matches = re.findall(rb'[A-Za-z0-9 .,;:!@#\$%\^&\*\(\)_\+\-=\[\]\{\}<>\?\/\\\'\"`~]{4,}', file_bytes)
        meaningful_lines = []
        for line in ascii_matches:
            decoded = line.decode('utf-8', errors='ignore').strip()
            if any(kw in decoded.lower() for kw in ['experience', 'education', 'skills', 'university', 'curriculum', 'resume', 'cv', 'developer', 'engineer', 'manager']):
                meaningful_lines.append(decoded)
        if len(meaningful_lines) > 3:
            return '\n'.join(meaningful_lines)
        return extracted
    except Exception as e:
        return ""

def extract_candidate_name(text, filename=""):
    """Extract candidate name from header or filename without personal bias."""
    clean_filename = re.sub(r'(\.pdf|\.docx|\.doc|\.txt)$', '', filename, flags=re.I)
    clean_filename = re.sub(r'^(cv[_\s-]*|resume[_\s-]*)|([_\s-]cv|[_\s-]resume)', '', clean_filename, flags=re.I).strip()
    
    # Check lines of text
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    for line in lines[:5]:
        if len(line.split()) in [2, 3, 4] and not any(kw in line.lower() for kw in ['resume', 'curriculum', 'vitae', 'page', 'phone', 'email', 'address', 'summary', 'profile', 'contact']):
            # Looks like a clean name
            if re.match(r'^[A-Z][a-zA-Z\.\'-]+(\s+[A-Z][a-zA-Z\.\'-]+){1,3}$', line):
                return line
    
    if clean_filename and len(clean_filename.replace('_', ' ').split()) in [2, 3, 4]:
        words = clean_filename.replace('_', ' ').replace('-', ' ').split()
        return ' '.join(w.capitalize() for w in words)
        
    return clean_filename.replace('_', ' ').title() if clean_filename else "Candidate"

def extract_contact_info(text):
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    email = emails[0] if emails else "Not specified"
    phone = phones[0] if phones else "Not specified"
    return email, phone

def normalize_text(text):
    """Fold PDF ligatures (e.g. 'ﬁ' -> 'fi'), smart quotes and dashes into plain characters."""
    text = unicodedata.normalize("NFKC", text or "")
    return text.replace("’", "'").replace("‘", "'")


_MONTH_RE = (r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|'
             r'sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)')
_MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}

# "July 2014 - June 2019", "Jan 2022 – Present", "2016-2018", "2019 to date"
_DATE_RANGE_RE = re.compile(
    rf'(?:({_MONTH_RE})\.?,?\s+)?\b((?:19|20)\d\d)\s*(?:-|–|—|to|till|until)\s*'
    rf'(?:({_MONTH_RE})\.?,?\s+)?((?:19|20)\d\d|present|current|date|now|today)\b', re.I)

# "over 12 years of finance and accounting experience", "6+ years hands-on professional experience",
# "12 years' experience" - up to 7 words may sit between "years" and "experience" within one sentence
_EXPLICIT_YEARS_RE = re.compile(
    r'(\d{1,2})\s*\+?\s*(?:years?|yrs?)\'?((?:\s+[^\s.;:!?]+){0,7}?)\s+experience', re.I)
# "experience of over 12 years"
_EXPERIENCE_OF_RE = re.compile(
    r'experience\s+of\s+(?:over\s+|more\s+than\s+|about\s+|nearly\s+)?(\d{1,2})\s*\+?\s*(?:years?|yrs?)', re.I)


def calculate_years_experience(text):
    """Estimate years of experience from explicit statements or employment date ranges.

    Explicit statements such as "over 12 years of finance experience" count at their stated
    number; date ranges (with or without month names) are merged so overlapping jobs count once.
    The larger of the two estimates is returned.
    """
    text = normalize_text(text)
    explicit_years = [int(g[0]) for g in _EXPLICIT_YEARS_RE.findall(text) if int(g[0]) <= 45]
    explicit_years += [int(m) for m in _EXPERIENCE_OF_RE.findall(text) if int(m) <= 45]

    now = datetime.now()
    now_idx = now.year * 12 + now.month
    intervals = []
    for start_mon, start_yr, end_mon, end_str in _DATE_RANGE_RE.findall(text):
        try:
            start_idx = int(start_yr) * 12 + (_MONTHS[start_mon[:3].lower()] if start_mon else 1)
            if end_str.lower() in ('present', 'current', 'date', 'now', 'today'):
                end_idx = now_idx + 1
            else:
                # A month name marks an inclusive end month; bare years count as year differences
                end_idx = int(end_str) * 12 + (_MONTHS[end_mon[:3].lower()] + 1 if end_mon else 1)
            if 1970 * 12 <= start_idx < end_idx <= now_idx + 13:
                intervals.append((start_idx, end_idx))
        except (KeyError, ValueError):
            continue

    range_years = 0
    if intervals:
        # Merge overlapping intervals
        intervals.sort()
        merged = [intervals[0]]
        for curr in intervals[1:]:
            prev_start, prev_end = merged[-1]
            if curr[0] <= prev_end:
                merged[-1] = (prev_start, max(prev_end, curr[1]))
            else:
                merged.append(curr)
        range_years = sum(e - s for s, e in merged) // 12

    return max(explicit_years + [range_years, 0])


# Professional credentials: acronym -> full titles. An item naming any of these is met when the CV
# shows the acronym (e.g. "CA", "CA-qualified") or the full title (e.g. "Chartered Accountant").
CREDENTIALS = {
    "CA": ["chartered accountant"],
    "CPA": ["certified public accountant"],
    "ACCA": ["association of chartered certified accountants", "chartered certified accountant"],
    "CMA": ["certified management accountant"],
    "CIMA": ["chartered institute of management accountants", "chartered management accountant"],
    "CFA": ["chartered financial analyst"],
    "CIA": ["certified internal auditor"],
    "CISA": ["certified information systems auditor"],
    "MBA": ["master of business administration"],
}

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "for", "with", "to", "at", "by", "as", "from",
    "including", "such", "e", "g", "eg", "etc", "is", "are", "be", "must", "should", "will", "have",
    "has", "any", "other", "related", "similar", "equivalent", "field", "minimum", "maximum", "least",
    "over", "more", "than", "strong", "good", "excellent", "solid", "demonstrated", "proven",
    "proficiency", "proficient", "knowledge", "ability", "relevant", "prior", "experience",
    "experienced", "years", "year", "advanced", "skills", "skill", "required", "preferred",
}


def _item_terms(item):
    words = re.findall(r"[a-z0-9]+", normalize_text(item).lower())
    return [w for w in words if w not in _STOPWORDS and (len(w) > 2 or w.isdigit())]


def _term_in_text(term, text_lower):
    """Word-start match with light stemming: 'coordination' finds 'coordinating', 'controls' finds 'control'."""
    if len(term) <= 3:
        return re.search(r'\b' + re.escape(term) + r'\b', text_lower) is not None
    if term.endswith('s') and len(term) > 4:
        term = term[:-1]
    stem = term[:6] if len(term) >= 7 else term
    return re.search(r'\b' + re.escape(stem), text_lower) is not None


def _credentials_in(item):
    item_norm = normalize_text(item)
    found = []
    for acronym, titles in CREDENTIALS.items():
        if re.search(r'\b' + acronym + r'\b', item_norm, re.I) or any(t in item_norm.lower() for t in titles):
            found.append(acronym)
    return found


def _has_credential(acronym, text, text_lower):
    # Acronyms are matched in their capitalised form so "ca" inside ordinary words never counts
    if re.search(r'(?<![A-Za-z])' + acronym + r'(?![A-Za-z])', text):
        return True
    return any(t in text_lower for t in CREDENTIALS[acronym])


def match_item(item, text, text_lower):
    """Returns (met, cue_words) for one criteria line against normalised CV text."""
    creds = _credentials_in(item)
    if creds:
        hits = [c for c in creds if _has_credential(c, text, text_lower)]
        needs_all = re.search(r'\band\b', item, re.I) and not re.search(r'\bor\b|/', item, re.I)
        met = len(hits) == len(creds) if needs_all else bool(hits)
        cues = [c.lower() for c in hits] + [t for c in hits for t in CREDENTIALS[c]]
        return met, cues or [c.lower() for c in creds]

    terms = _item_terms(item)
    if not terms:
        return False, []
    phrase = " ".join(terms)
    if phrase in text_lower:
        return True, terms
    matched = [t for t in terms if _term_in_text(t, text_lower)]
    # Short items (1-2 key words) need every word; longer sentence-style items need half of them
    needed = len(terms) if len(terms) <= 2 else -(-len(terms) // 2)
    return len(matched) >= needed, matched or terms


def _evidence_sentence(text, cues, fallback):
    sentences = re.split(r'[.\n\r]+', text)
    return next((s.strip() for s in sentences
                 if any(c in s.lower() for c in cues) and len(s.strip()) > 10), fallback)

def evaluate_cv(cv_data, criteria):
    """
    Evaluates a single CV against HR criteria.
    cv_data: { "id", "filename", "text", "file_hash", "is_ocr_scanned" }
    criteria: {
        "job_title": str,
        "description": str,
        "weights": { "qualifications": int, "skills": int, "experience": int, "mandatory": int },
        "qualifications": list[str],
        "skills": list[str],
        "experience": { "required_years": int, "domains": list[str] },
        "mandatory": list[str],
        "threshold": float,
        "top_n": int
    }
    """
    filename = cv_data.get("filename", "")
    text = normalize_text(cv_data.get("text", ""))
    text_lower = text.lower()
    
    # Check readability
    if not text.strip() or len(text.strip()) < 40:
        return {
            "id": cv_data.get("id"),
            "filename": filename,
            "name": extract_candidate_name("", filename),
            "email": "N/A",
            "phone": "N/A",
            "matching_percentage": 0.0,
            "category_scores": {"qualifications": 0, "skills": 0, "experience": 0, "mandatory": 0},
            "mandatory_met": False,
            "strengths": [],
            "missing_requirements": ["Document content unreadable or empty"],
            "evidence": [],
            "unreadable": True,
            "ocr_needed": True,
            "flags": ["Unreadable CV / Scanned image with no extractable text layer"],
            "status": "Needs HR Review",
            "file_hash": cv_data.get("file_hash", "")
        }

    name = extract_candidate_name(text, filename)
    email, phone = extract_contact_info(text)
    
    weights = criteria.get("weights", {"qualifications": 25, "skills": 35, "experience": 25, "mandatory": 15})
    total_weight = sum(weights.values()) or 100
    
    evidence_list = []
    strengths = []
    missing = []
    flags = []

    # 1. Mandatory Requirements
    mandatory_reqs = criteria.get("mandatory", [])
    mandatory_passed = 0
    mandatory_total = len(mandatory_reqs)
    all_mandatory_met = True

    for req in mandatory_reqs:
        req_clean = req.strip()
        if not req_clean:
            continue
        # Check if mandatory requirement is satisfied
        # E.g. "5+ years", "Bachelor", "CA or CPA qualification", "React"
        # Experience check if mandatory specifies years
        years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', req_clean, re.I)
        if years_match:
            req_years = int(years_match.group(1))
            cand_years = calculate_years_experience(text)
            if cand_years >= req_years:
                mandatory_passed += 1
                evidence_list.append(f"[Mandatory Met] {req_clean}: Candidate demonstrates ~{cand_years} years experience")
            else:
                all_mandatory_met = False
                missing.append(f"Mandatory requirement not met: {req_clean} (Found {cand_years} years, required {req_years})")
            continue
        met, cues = match_item(req_clean, text, text_lower)
        if met:
            mandatory_passed += 1
            evidence_snippet = _evidence_sentence(text, cues, req_clean)
            evidence_list.append(f"[Mandatory Met] {req_clean}: \"{evidence_snippet[:120]}\"")
        else:
            all_mandatory_met = False
            missing.append(f"Mandatory requirement not met: {req_clean}")

    mandatory_score = 100.0 if mandatory_total == 0 else (mandatory_passed / mandatory_total * 100.0)

    # 2. Qualifications
    quals = criteria.get("qualifications", [])
    quals_passed = 0
    quals_total = len(quals)
    for q in quals:
        q_clean = q.strip()
        if not q_clean:
            continue
        met, cues = match_item(q_clean, text, text_lower)
        if met:
            quals_passed += 1
            snippet = _evidence_sentence(text, cues, q_clean)
            evidence_list.append(f"[Qualification] {q_clean}: \"{snippet[:120]}\"")
            strengths.append(f"Holds required qualification: {q_clean}")
        else:
            missing.append(f"Missing qualification: {q_clean}")
            
    quals_score = 100.0 if quals_total == 0 else (quals_passed / quals_total * 100.0)

    # 3. Skills
    skills_list = criteria.get("skills", [])
    skills_passed = 0
    skills_total = len(skills_list)
    for sk in skills_list:
        sk_clean = sk.strip()
        if not sk_clean:
            continue
        # Search word boundaries, or key words for sentence-style skills
        pattern = r'\b' + re.escape(sk_clean.lower()) + r'\b'
        if re.search(pattern, text_lower) or sk_clean.lower() in text_lower:
            met, cues = True, [sk_clean.lower()]
        else:
            met, cues = match_item(sk_clean, text, text_lower)
        if met:
            skills_passed += 1
            snippet = _evidence_sentence(text, cues, sk_clean)
            evidence_list.append(f"[Skill Match] {sk_clean}: \"{snippet[:110]}\"")
            strengths.append(f"Proficient in {sk_clean}")
        else:
            missing.append(f"Lacks key skill: {sk_clean}")
            
    skills_score = 100.0 if skills_total == 0 else (skills_passed / skills_total * 100.0)

    # 4. Experience
    cand_years = calculate_years_experience(text)
    exp_config = criteria.get("experience", {})
    req_years = exp_config.get("required_years", 3)
    exp_domains = exp_config.get("domains", [])
    
    # Years component (up to 70% of experience score)
    years_ratio = min(1.0, cand_years / max(1, req_years))
    
    # Domains component (30% of experience score)
    domain_matches = 0
    for dom in exp_domains:
        dom_clean = dom.strip()
        if not dom_clean:
            continue
        years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', dom_clean, re.I)
        if years_match:
            dom_met = cand_years >= int(years_match.group(1))
        else:
            dom_met = dom_clean.lower() in text_lower or match_item(dom_clean, text, text_lower)[0]
        if dom_met:
            domain_matches += 1
            evidence_list.append(f"[Domain Experience] {dom_clean}: Identified relevant domain background in CV")
            strengths.append(f"Experience in {dom_clean}")
        else:
            missing.append(f"Limited evidence in domain: {dom_clean}")
            
    domain_ratio = (domain_matches / len(exp_domains)) if exp_domains else 1.0
    exp_score = (years_ratio * 70.0) + (domain_ratio * 30.0)
    
    if cand_years >= req_years:
        evidence_list.append(f"[Experience Duration] Demonstrates {cand_years} years experience (Required: {req_years}+ years)")
        strengths.append(f"{cand_years} years of accumulated professional experience")
    else:
        flags.append(f"Years of experience below target ({cand_years} years vs {req_years} required)")

    # Weighted Total Score
    w_q = weights.get("qualifications", 25)
    w_s = weights.get("skills", 35)
    w_e = weights.get("experience", 25)
    w_m = weights.get("mandatory", 15)
    
    weighted_total = (
        (quals_score * w_q) +
        (skills_score * w_s) +
        (exp_score * w_e) +
        (mandatory_score * w_m)
    ) / total_weight
    
    matching_percentage = round(weighted_total, 1)
    
    threshold = float(criteria.get("threshold", 90.0))
    
    # Status determination:
    # Candidates meeting threshold AND mandatory requirements are eligible for shortlist
    status = "Under Review"
    if not all_mandatory_met:
        status = "Disqualified (Mandatory Requirement Missing)"
        flags.append("Failed one or more mandatory dealbreakers")
    elif matching_percentage >= threshold:
        status = "Eligible for Shortlist"
    else:
        status = "Under Threshold"

    return {
        "id": cv_data.get("id"),
        "filename": filename,
        "name": name,
        "email": email,
        "phone": phone,
        "years_experience": cand_years,
        "matching_percentage": matching_percentage,
        "category_scores": {
            "qualifications": round(quals_score, 1),
            "skills": round(skills_score, 1),
            "experience": round(exp_score, 1),
            "mandatory": round(mandatory_score, 1)
        },
        "mandatory_met": all_mandatory_met,
        "strengths": strengths[:6],
        "missing_requirements": missing[:6],
        "evidence": evidence_list[:8],
        "unreadable": False,
        "ocr_needed": cv_data.get("is_ocr_scanned", False),
        "flags": flags,
        "status": status,
        "file_hash": cv_data.get("file_hash", "")
    }

def rank_and_shortlist(evaluations, threshold=90.0, top_n=10):
    """
    Ranks candidates by matching percentage descending.
    Proposes only candidates meeting the threshold and mandatory requirements.
    If fewer qualify, shows the actual number without lowering the threshold.
    """
    # Sort descending by matching percentage
    sorted_candidates = sorted(evaluations, key=lambda x: (x["mandatory_met"], x["matching_percentage"]), reverse=True)
    
    shortlisted_count = 0
    ranked_results = []
    
    for rank_idx, cand in enumerate(sorted_candidates, 1):
        cand["rank"] = rank_idx
        if cand["mandatory_met"] and cand["matching_percentage"] >= threshold and not cand["unreadable"]:
            if shortlisted_count < top_n:
                cand["status"] = "Shortlisted"
                cand["shortlisted"] = True
                shortlisted_count += 1
            else:
                cand["status"] = "Qualified (Exceeds Top N Limit)"
                cand["shortlisted"] = False
        else:
            cand["shortlisted"] = False
            if cand["unreadable"]:
                cand["status"] = "Needs HR Review (Unreadable)"
            elif not cand["mandatory_met"]:
                cand["status"] = "Disqualified (Mandatory Not Met)"
            else:
                cand["status"] = "Under Threshold"
                
        ranked_results.append(cand)
        
    return {
        "ranked_candidates": ranked_results,
        "qualifying_count": shortlisted_count,
        "total_evaluated": len(evaluations),
        "threshold_applied": threshold,
        "top_n_cap": top_n
    }

def process_screening_batch(payload):
    """
    Main entry point for screening batches.
    Detects duplicates, parses documents, runs evaluations, ranks candidates.
    """
    cvs = payload.get("cvs", [])
    criteria = payload.get("criteria", {})
    threshold = float(criteria.get("threshold", 90.0))
    top_n = int(criteria.get("top_n", 10))
    
    seen_hashes = {}
    evaluated = []
    duplicates_found = []
    
    for cv in cvs:
        f_hash = cv.get("file_hash") or compute_file_hash(cv.get("text", "").encode("utf-8"))
        cv["file_hash"] = f_hash
        
        # Check duplicate
        if f_hash in seen_hashes:
            orig = seen_hashes[f_hash]
            duplicates_found.append({
                "duplicate_file": cv.get("filename"),
                "original_file": orig.get("filename"),
                "candidate_name": orig.get("name")
            })
            # Still evaluate but flag as duplicate
            res = evaluate_cv(cv, criteria)
            res["flags"].append(f"Duplicate file of '{orig.get('filename')}'")
            res["is_duplicate"] = True
            res["original_match"] = orig.get("filename")
            evaluated.append(res)
        else:
            seen_hashes[f_hash] = cv
            res = evaluate_cv(cv, criteria)
            res["is_duplicate"] = False
            evaluated.append(res)
            
    ranking = rank_and_shortlist(evaluated, threshold, top_n)
    ranking["duplicates"] = duplicates_found
    ranking["processed_at"] = datetime.now().isoformat()
    return ranking

if __name__ == "__main__":
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"error": "Empty input payload"}))
            sys.exit(1)
        data = json.loads(raw_input)
        result = process_screening_batch(data)
        print(json.dumps(result))
    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()
        print(json.dumps({"error": str(e), "traceback": err_detail}))
        sys.exit(1)
