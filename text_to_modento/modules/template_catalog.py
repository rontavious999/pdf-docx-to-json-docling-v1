"""
Template matching and field standardization using the dental form dictionary.

This module handles matching parsed form fields against a template dictionary
to standardize field keys, titles, types, and options across different forms.

Classes:
- FindResult - Dataclass for template match results
- TemplateCatalog - Main template matching class

Functions:
- merge_with_template - Merge parsed field with template
- _dedupe_keys_dicts - Deduplicate keys in field dictionaries
- Helper functions for text normalization and matching
"""

import copy
import re
import json
from pathlib import Path
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Set, Tuple

# Import constants
from .constants import PRIMARY_SUFFIX, SECONDARY_SUFFIX, PARENT_RE, HEAR_ABOUT_RE

# Import utility functions from question_parser
from .question_parser import normalize_opt_name

# Note: DebugLogger will be imported from modules.debug_logger when needed

# Helper function for text sanitization
def _sanitize_words(s: str) -> str:
    """Sanitize text for matching: lowercase, remove punctuation, normalize whitespace."""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ---------- Template dictionary (matching)

def _norm_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("date of birth", "dob").replace("birth date", "dob")
    s = s.replace("zip code", "zipcode").replace("e-mail", "email")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s

def _slug_key_norm(s: str) -> str:
    s = _norm_text(s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s: s = "q"
    if re.match(r"^\d", s): s = "q_" + s
    return s[:64]

def _token_set_ratio(a: str, b: str) -> float:
    A = set(_norm_text(a).split())
    B = set(_norm_text(b).split())
    if not A or not B: return 0.0
    inter = len(A & B); union = len(A | B)
    return inter / union if union else 0.0

EXTRA_ALIASES = {
    # General
    "birth date": "date_of_birth", "dob": "date_of_birth",
    "patient date of birth": "date_of_birth", "date of birth": "date_of_birth",
    "birthdate": "date_of_birth",
    "zip": "zipcode", "zip code": "zipcode",
    "cell phone": "mobile_phone", "mobile": "mobile_phone",
    "home phone": "home_phone", "e mail": "email", "email address": "email",
    "emergency contact": "emergency_name", "emergency contact name": "emergency_name",
    "emergency phone": "emergency_phone", "relationship to patient": "emergency_relationship",
    "drivers license": "drivers_license", "driver's license": "drivers_license",
    "drivers license #": "drivers_license",
    "person responsible for account": "responsible_party_name",
    "responsible party": "responsible_party_name",
    "occupation": "occupation",
    "spouse's name": "spouse_name", "name of spouse": "spouse_name",
    "date": "date_signed", "today's date": "date_signed", "todays date": "date_signed",
    "signature date": "date_signed", "signed date": "date_signed",
    "patient name": "full_name", "patient's name": "full_name",
    "name of patient": "full_name", "name (print)": "full_name",
    "name (please print)": "full_name", "printed name": "full_name",
    "patients name": "full_name", "patients name please print": "full_name",
    # Parent/Guardian - Enhanced
    "parent ssn": "parent_ssn", "guardian ssn": "parent_ssn",
    "parent phone": "parent_phone", "guardian phone": "parent_phone",
    "parent name": "parent_name", "guardian name": "parent_name",
    "parent/guardian name": "parent_name", "parent guardian name": "parent_name",
    "parents name": "parent_name", "guardians name": "parent_name",
    "parent or guardian name": "parent_name",
    # Insurance (avoid tiny 'id #' tokens)
    "insureds name": "insurance_holder", "insured name": "insurance_holder",
    "subscriber name": "insurance_holder", "member name": "insurance_holder",
    "policy holder name": "insurance_holder",
    "name of insurance company": "insurance_company",
    "primary insurance": "insurance_company", "secondary insurance": "insurance_company",
    "relationship to insured": "insurance_relationship",
    "relationship to subscriber": "insurance_relationship",
    "relationship to policy holder": "insurance_relationship",
    "relationship to member": "insurance_relationship",
    "subscriber id": "insurance_id_number", "subscriber #": "insurance_id_number",
    "policy #": "insurance_id_number", "member #": "insurance_id_number",
    "id number": "insurance_id_number", "id no": "insurance_id_number",
    "member id": "insurance_id_number", "policy id": "insurance_id_number",
    "identification number": "insurance_id_number",
    "group number": "insurance_group_number", "group #": "insurance_group_number",
    "grp #": "insurance_group_number", "plan group number": "insurance_group_number",
    "insurance company": "insurance_company",
    "insurance phone": "insurance_phone_number", "insurance phone #": "insurance_phone_number",
    "customer service phone": "insurance_phone_number", "cust svc phone": "insurance_phone_number",
    "address on card": "insurance_address_card", "insurance address": "insurance_address",
    # Referrals
    "who can we thank": "referred_by", "referred by": "referred_by",
    "how did you hear about us": "referred_by", "referred by (who)": "referred_by",
    # Procedure/Treatment specific
    "number": "tooth_number", "tooth number": "tooth_number",
    "diagnosis": "diagnosis", "treatment": "treatment_type",
    # Relationship fields
    "relationship": "relationship", "relationship to patient": "relationship",
}

# helper: detect conditions-like control to gate matching
_COND_TOKENS = {"diabetes","arthritis","rheumat","hepatitis","asthma","stroke","ulcer",
                "thyroid","cancer","anemia","glaucoma","osteoporosis","seizure","tb","tuberculosis",
                "hiv","aids","blood","pressure","heart","kidney","liver","bleeding","sinus",
                "smoke","chew","alcohol","drug","allergy","pregnan","anxiety","depression","pacemaker",
                "irregular","rregular"}

def _is_conditions_control(parsed_q: Optional[dict]) -> bool:
    if not parsed_q: return False
    if parsed_q.get("type") != "dropdown": return False
    ctrl = parsed_q.get("control") or {}
    if not ctrl.get("multi"): return False
    opts = ctrl.get("options") or []
    if len(opts) < 8: return False
    hits = 0
    for o in opts:
        w = re.sub(r"[^\w\s]","", (o.get("name") or "").lower())
        if any(t in w for t in _COND_TOKENS): hits += 1
    return hits >= 3

def _sanitize_words_set(s: str) -> Set[str]:
    return set(_sanitize_words(s).split())

def _alias_tokens_ok(alias_phrase: str, title: str) -> bool:
    alias_tokens = [t for t in _sanitize_words(alias_phrase).split() if len(t) >= 2]
    if not alias_tokens: return False
    tks = _sanitize_words_set(title)
    return all(tok in tks for tok in alias_tokens)

@dataclass
class FindResult:
    tpl: Optional[dict]
    scope: str
    reason: str
    score: float
    coverage: float
    best_key: Optional[str]

class TemplateCatalog:
    def __init__(self, by_key: Dict[str, dict], alias_map: Dict[str, str], titles_map: Dict[str, str]):
        merged_aliases = dict(alias_map)
        for a, k in EXTRA_ALIASES.items():
            merged_aliases.setdefault(_norm_text(a), k)
        self.by_key = by_key
        self.alias_map = merged_aliases
        self.titles_map = titles_map  # norm_title -> key

    @classmethod
    def from_path(cls, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        by_key: Dict[str, dict] = {}
        titles_map: Dict[str, str] = {}
        for cat, items in data.items():
            if cat.startswith("_") or cat == "aliases":
                continue
            if not isinstance(items, list):
                continue
            for obj in items:
                k = obj.get("key")
                if not k: 
                    continue
                by_key.setdefault(k, obj)
                t = obj.get("title") or ""
                titles_map.setdefault(_norm_text(t), k)
        alias_map: Dict[str, str] = {}
        for a, canonical in (data.get("aliases") or {}).items():
            alias_map[_norm_text(a)] = canonical
        return cls(by_key, alias_map, titles_map)

    def _strip_scope(self, key: str) -> Tuple[str, str]:
        if key.endswith(PRIMARY_SUFFIX):   return key[:-len(PRIMARY_SUFFIX)], PRIMARY_SUFFIX
        if key.endswith(SECONDARY_SUFFIX): return key[:-len(SECONDARY_SUFFIX)], SECONDARY_SUFFIX
        return key, ""

    def _options_overlap(self, parsed_q: dict, tpl_q: dict) -> float:
        if not parsed_q or not tpl_q: return 1.0
        p_opts = [o.get("name","") for o in (parsed_q.get("control",{}).get("options") or [])]
        t_opts = [o.get("name","") for o in (tpl_q.get("control",{}).get("options") or [])]
        if not p_opts or not t_opts: return 1.0
        P = {normalize_opt_name(x) for x in p_opts if x}
        T = {normalize_opt_name(x) for x in t_opts if x}
        if not P or not T: return 1.0
        inter = len(P & T); union = len(P | T)
        return inter/union if union else 1.0

    def _context_adjust(self, parsed_section: str, tpl_section: str) -> float:
        if not parsed_section or not tpl_section:
            return 0.0
        if parsed_section == tpl_section:
            return 0.05
        a = parsed_section.lower(); b = tpl_section.lower()
        if ("insurance" in a) ^ ("insurance" in b):
            return -0.10
        return 0.0

    def find(self, key: Optional[str], title: Optional[str], parsed_q: Optional[dict]=None) -> FindResult:
        scope = ""; reason = ""; score = 0.0; coverage = 0.0; best_key = None
        parsed_section = (parsed_q or {}).get("section","")
        is_conditions = _is_conditions_control(parsed_q)
        norm_title = _norm_text(title or "")
        long_title = len(norm_title) > 120 or len(norm_title.split()) > 15
        has_parent = bool(PARENT_RE.search(title or ""))

        # 1) Exact key (incl. scope base)
        if key:
            base, scope = self._strip_scope(key)
            if key in self.by_key:
                return FindResult(self.by_key[key], scope, "key_exact", 1.0, 1.0, key)
            if base in self.by_key:
                return FindResult(self.by_key[base], scope, "key_base_exact", 0.98, 1.0, base)

        if not title:
            return FindResult(None, "", "", 0.0, 0.0, None)

        # 2) Title exact (normalized)
        tk = self.titles_map.get(norm_title)
        if tk and tk in self.by_key:
            tpl = self.by_key[tk]
            ov = self._options_overlap(parsed_q, tpl)
            sc = 0.95*ov + self._context_adjust(parsed_section, tpl.get("section",""))
            return FindResult(tpl, "", "title_exact", sc, 1.0, tk)

        # 3) Alias exact
        alias_key = self.alias_map.get(norm_title)
        if alias_key and alias_key in self.by_key:
            # guard: if alias points to generic SSN but title contains parent terms, skip
            if alias_key == "ssn" and has_parent:
                return FindResult(None, "", "", 0.0, 0.0, None)
            tpl = self.by_key[alias_key]
            ov = self._options_overlap(parsed_q, tpl)
            sc = 0.96*ov + self._context_adjust(parsed_section, tpl.get("section",""))
            return FindResult(tpl, "", "alias_exact", sc, 1.0, alias_key)

        # Special: “How did you hear...” should never be hijacked by aliases/fuzzy
        if HEAR_ABOUT_RE.search(title or ""):
            return FindResult(None, "", "", 0.0, 0.0, None)

        # Long titles without options → block alias/fuzzy
        if long_title and parsed_q:
            has_opts = bool((parsed_q.get("control") or {}).get("options"))
            if not has_opts:
                return FindResult(None, "", "", 0.0, 0.0, None)

        # 4) Alias contains — token-boundary & context rules
        for alias_phrase, canonical in self.alias_map.items():
            # guard generics: don't allow generic ssn to match parent/guardian titles
            if canonical == "ssn" and has_parent:
                continue
            tpl = self.by_key.get(canonical)
            if not tpl:
                continue
            if not _alias_tokens_ok(alias_phrase, title or ""):
                continue
            if ("insurance" in (tpl.get("section","").lower() or "")) and ("insurance" not in (parsed_section or "").lower()):
                continue
            ov = self._options_overlap(parsed_q, tpl)
            sc = 0.93*ov + self._context_adjust(parsed_section, tpl.get("section",""))
            return FindResult(tpl, "", "alias_contains", sc, 1.0, canonical)

        # 5) Fuzzy (gated): never for conditions collectors
        if is_conditions:
            return FindResult(None, "", "", 0.0, 0.0, None)

        best_k, best_score, best_cov = None, 0.0, 0.0
        for cand_title_norm, cand_key in self.titles_map.items():
            jac = _token_set_ratio(norm_title, cand_title_norm)
            seq = SequenceMatcher(None, norm_title, cand_title_norm).ratio()
            cand_tokens = set(cand_title_norm.split()); title_tokens = set(norm_title.split())
            cov_needed = 0.8 if len(cand_tokens) > 3 else 0.65
            cov = len(cand_tokens & title_tokens) / max(1, len(cand_tokens))
            sc = 0.45 * jac + 0.45 * seq
            if cov >= cov_needed:
                if sc > best_score:
                    best_k, best_score, best_cov = cand_key, sc, cov

        if best_k:
            tpl = self.by_key[best_k]
            ov = self._options_overlap(parsed_q, tpl)
            sc = best_score + 0.10 * ov + self._context_adjust(parsed_section, tpl.get("section",""))
            
            # Parity Improvement #5: Lower threshold for medical/common fields
            # Check if this is a medical or patient info field (more lenient matching)
            section_lower = (tpl.get("section", "") or "").lower()
            is_medical_patient = any(keyword in section_lower for keyword in 
                                    ['medical', 'health', 'patient', 'insurance', 'emergency'])
            
            # Keyword-based matching boost
            keyword_match_boost = 0.0
            tpl_title_lower = (tpl.get("title", "") or "").lower()
            for keyword in ['physician', 'hospitalized', 'medication', 'allergy', 'surgery']:
                if keyword in norm_title and keyword in tpl_title_lower:
                    keyword_match_boost += 0.05
            
            sc += keyword_match_boost
            
            # Lower threshold for medical/patient fields: 0.82 instead of 0.85
            threshold = 0.82 if is_medical_patient else 0.85
            
            if sc >= threshold:
                return FindResult(tpl, "", "fuzzy", sc, best_cov, best_k)
            if sc >= 0.75:
                return FindResult(None, "", "near", sc, best_cov, best_k)

        return FindResult(None, "", "", 0.0, 0.0, None)

def merge_with_template(parsed_q: dict, template_q: dict, scope_suffix: str = "") -> dict:
    merged = copy.deepcopy(template_q)
    if parsed_q.get("title"):
        merged["title"] = parsed_q["title"]
    if parsed_q.get("section"):
        merged["section"] = parsed_q["section"]
    if "optional" in parsed_q:
        merged["optional"] = bool(parsed_q["optional"])
    out_key = merged.get("key") or parsed_q.get("key") or _slug_key_norm(parsed_q.get("title") or "")
    if scope_suffix and not out_key.endswith(scope_suffix):
        out_key = f"{out_key}{scope_suffix}"
    merged["key"] = out_key
    return merged

def _dedupe_keys_dicts(items: List[dict]) -> List[dict]:
    """
    Deduplicate keys in field dictionaries, including nested questions in multiradio controls.
    Ensures global uniqueness as required by Modento schema.
    """
    seen: Dict[str, int] = {}
    out: List[dict] = []
    
    def dedupe_dict_question(q: dict) -> None:
        """Deduplicate a single question dict and its nested questions recursively."""
        key = q.get("key") or "q"
        if q.get("type") == "signature":
            q["key"] = "signature"
        else:
            base = key
            if base not in seen:
                seen[base] = 1
                q["key"] = base
            else:
                seen[base] += 1
                q["key"] = f"{base}_{seen[base]}"
        
        # Handle nested questions in multiradio controls
        if q.get("type") == "multiradio" and "control" in q and "questions" in q.get("control", {}):
            nested_questions = q["control"].get("questions", [])
            for nested_q in nested_questions:
                if isinstance(nested_q, dict):
                    nested_key = nested_q.get("key", "q")
                    if nested_key in seen:
                        seen[nested_key] += 1
                        nested_q["key"] = f"{nested_key}_{seen[nested_key]}"
                    else:
                        seen[nested_key] = 1
    
    for q in items:
        dedupe_dict_question(q)
        out.append(q)
    return out


def smart_alias_match(parsed_label: str, template_key: str, template_data: Dict, context: Dict = None) -> Tuple[bool, float, str]:
    """
    Improvement #9: Smart alias matching with context awareness and negative patterns.
    
    Prevents incorrect matches like "Name of Employer" → "first_name" by:
    1. Using context (section, nearby fields)
    2. Applying negative patterns (what shouldn't match)
    3. Weighing key-based matches higher than alias matches
    4. Semantic coherence checking
    
    Args:
        parsed_label: The label from parsed form
        template_key: Candidate template key to match
        template_data: The template dictionary entry
        context: Optional context dict (section, prev_fields, etc.)
        
    Returns:
        Tuple of (is_match, confidence_score, reason)
    """
    context = context or {}
    parsed_lower = _norm_text(parsed_label)
    template_title = template_data.get('title', '')
    template_title_lower = _norm_text(template_title)
    
    # Negative patterns: combinations that should NOT match
    negative_patterns = [
        # "Name of X" should not match "first_name" or "last_name"
        (r'name.*of\s+(employer|insurance|company|practice)', ['first_name', 'last_name', 'middle_name']),
        
        # "Employer" or "Company" should not match personal name fields
        (r'employer|company|practice|business', ['first_name', 'last_name', 'patient_name']),
        
        # "Relationship" fields should not match "name" fields
        (r'relationship', ['first_name', 'last_name', 'full_name']),
        
        # "Group" or "Policy" numbers should not match SSN or personal IDs
        (r'group|policy|plan.*number', ['ssn', 'patient_id']),
        
        # "Phone" specifics shouldn't cross-match
        (r'mobile|cell', ['home_phone', 'work_phone', 'fax']),
        (r'home.*phone', ['mobile_phone', 'work_phone', 'cell_phone']),
        (r'work.*phone', ['mobile_phone', 'home_phone', 'cell_phone']),
    ]
    
    # Check negative patterns
    for pattern, forbidden_keys in negative_patterns:
        if re.search(pattern, parsed_lower) and template_key in forbidden_keys:
            return (False, 0.0, f"negative_pattern: {pattern} -> {template_key}")
    
    # Positive matching with context weighting
    base_score = 0.0
    match_reason = "no_match"
    
    # 1. Exact key match (highest confidence)
    if _slug_key_norm(parsed_label) == template_key:
        base_score = 1.0
        match_reason = "key_exact"
    
    # 2. Title exact match
    elif parsed_lower == template_title_lower:
        base_score = 0.95
        match_reason = "title_exact"
    
    # 3. Alias match (check EXTRA_ALIASES)
    elif parsed_lower in EXTRA_ALIASES and EXTRA_ALIASES[parsed_lower] == template_key:
        base_score = 0.9
        match_reason = "alias_exact"
    
    # 4. Token set similarity (fuzzy match)
    else:
        token_score = _token_set_ratio(parsed_label, template_title)
        if token_score >= 0.7:
            base_score = 0.7 + (token_score - 0.7) * 0.5  # 0.7 to 0.85
            match_reason = f"token_fuzzy_{token_score:.2f}"
    
    # Context-based adjustments
    if context and base_score > 0:
        section = context.get('section', '').lower()
        
        # Boost score if field makes sense in section
        section_boosts = {
            'insurance': ['insurance', 'policy', 'group', 'member', 'subscriber'],
            'emergency': ['emergency', 'contact', 'notify'],
            'patient': ['patient', 'name', 'birth', 'address'],
        }
        
        for section_key, boost_words in section_boosts.items():
            if section_key in section:
                if any(word in template_key for word in boost_words):
                    base_score = min(1.0, base_score + 0.05)
                    match_reason += "+context_boost"
                    break
    
    # Return match if score is above threshold
    is_match = base_score >= 0.7
    return (is_match, base_score, match_reason)


def apply_context_aware_matching(parsed_fields: List[Dict], templates: Dict, debug: bool = False) -> List[Dict]:
    """
    Apply smart alias matching to all parsed fields.
    
    Args:
        parsed_fields: List of parsed field dicts
        templates: Template dictionary
        debug: Print debug info
        
    Returns:
        List of fields with improved template matches
    """
    context = {'prev_fields': []}
    
    for i, field in enumerate(parsed_fields):
        parsed_label = field.get('title', '')
        section = field.get('section', '')
        
        # Update context
        context['section'] = section
        context['field_index'] = i
        
        # Find best template match using smart matching
        best_match_key = None
        best_score = 0.0
        best_reason = None
        
        for template_key, template_data in templates.items():
            is_match, score, reason = smart_alias_match(
                parsed_label, 
                template_key, 
                template_data, 
                context
            )
            
            if is_match and score > best_score:
                best_score = score
                best_match_key = template_key
                best_reason = reason
        
        # Apply best match if found
        if best_match_key and best_score >= 0.7:
            if debug:
                print(f"[smart_match] '{parsed_label}' -> {best_match_key} (score={best_score:.2f}, reason={best_reason})")
            field['template_match'] = {
                'key': best_match_key,
                'score': best_score,
                'reason': best_reason
            }
        
        # Add to context for next iteration
        context['prev_fields'].append(field)
    
    return parsed_fields

