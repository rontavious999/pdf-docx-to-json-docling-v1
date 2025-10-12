"""
Constants, regex patterns, and configuration values used throughout the pipeline.
"""

import re

# ---------- Paths

DEFAULT_IN_DIR = "output"
DEFAULT_OUT_DIR = "JSONs"

# ---------- Regex / tokens

CHECKBOX_ANY = r"(?:\[\s*\]|\[x\]|☐|☑|□|■|❒|◻|✓|✔|✗|✘)"
BULLET_RE = re.compile(r"^\s*(?:[-*•·]|" + CHECKBOX_ANY + r")\s+")
CHECKBOX_MARK_RE = re.compile(r"^\s*(" + CHECKBOX_ANY + r")\s+")

INLINE_CHOICE_RE = re.compile(
    rf"(?:^|\s){CHECKBOX_ANY}\s*([^\[\]•·\-\u2022]+?)(?=(?:\s*{CHECKBOX_ANY}|\s*[•·\-]|$))"
)

YESNO_SET = {"yes", "no", "y", "n"}

PHONE_RE   = re.compile(r"\b(phone|cell|mobile|telephone)\b", re.I)
EMAIL_RE   = re.compile(r"\bemail\b", re.I)
ZIP_RE     = re.compile(r"\b(zip|postal)\b", re.I)
SSN_RE     = re.compile(r"\b(ssn|social security|soc(?:ial)?\s*sec(?:urity)?|ss#)\b", re.I)
STATE_LABEL_RE = re.compile(r"^\s*state\b", re.I)
DATE_LABEL_RE  = re.compile(r"\b(date|dob|birth)\b", re.I)
INITIALS_RE    = re.compile(r"\binitials?\b", re.I)
WITNESS_RE     = re.compile(r"\bwitness\b", re.I)

IF_GUIDANCE_RE = re.compile(r"\b(if\s+(yes|no)[^)]*|if\s+so|if\s+applicable|explain below|please explain|please list)\b", re.I)

# Enhanced "If Yes" detection patterns (Fix 2)
IF_YES_FOLLOWUP_RE = re.compile(
    r'(.+?)\s*\[\s*\]\s*Yes\s*\[\s*\]\s*No\s+If\s+yes[,:]?\s*(?:please\s+)?explain',
    re.I
)
IF_YES_INLINE_RE = re.compile(
    r'(.+?)\s*\[\s*\]\s*Yes\s*\[\s*\]\s*No\s+If\s+yes',
    re.I
)

PAGE_NUM_RE = re.compile(r"^\s*(?:page\s*\d+(?:\s*/\s*\d+)?|\d+\s*/\s*\d+)\s*$", re.I)
ADDRESS_LIKE_RE = re.compile(
    r"\b(?:street|suite|ste\.?|ave|avenue|rd|road|blvd|zip|postal|fax|tel|phone|www\.|https?://|\.com|\.net|\.org|welcome|new\s+patients)\b",
    re.I,
)

# Enhanced header filtering patterns (Archivev8 Fix 2)
DENTAL_PRACTICE_EMAIL_RE = re.compile(
    r'@.*?(?:dental|dentistry|orthodontics|smiles).*?\.(com|net|org)',
    re.I
)
BUSINESS_WITH_ADDRESS_RE = re.compile(
    r'(?:dental|dentistry|orthodontics|family|cosmetic|implant).{20,}?(?:suite|ste\.?|ave|avenue|rd|road|st\.?|street)',
    re.I
)
PRACTICE_NAME_PATTERN = re.compile(
    r'^(?:.*?(?:dental|dentistry|orthodontics|family|cosmetic|implant).*?){1,3}$',
    re.I
)

INSURANCE_PRIMARY_RE   = re.compile(r"\bprimary\b.*\binsurance\b", re.I)
INSURANCE_SECONDARY_RE = re.compile(r"\bsecondary\b.*\binsurance\b", re.I)
INSURANCE_BLOCK_RE     = re.compile(r"(dental\s+benefit\s+plan|insurance\s+information|insurance\s+details)", re.I)

SINGLE_SELECT_TITLES_RE = re.compile(r"\b(marital\s+status|relationship|gender|sex)\b", re.I)

HEAR_ABOUT_RE   = re.compile(r"how\s+did\s+you\s+hear\s+about\s+us", re.I)
REFERRED_BY_RE  = re.compile(r"\b(referred\s+by|who\s+can\s+we\s+thank)\b", re.I)

RESP_PARTY_RE   = re.compile(r"responsible\s+party.*other\s+than\s+patient", re.I)
SINGLE_BOX_RE   = re.compile(r"^\s*\[\s*\]\s*(.+)$")

# broader Y/N capture (no boxes)
YN_SIMPLE_RE = re.compile(r"(?P<prompt>.*?)(?:\bYes\b|\bY\b)\s*(?:/|,|\s+)\s*(?:\bNo\b|\bN\b)", re.I)

# parent/guardian
PARENT_RE = re.compile(r"\b(parent|guardian|mother|father|legal\s+guardian)\b", re.I)

# Archivev12 Fix 2: Special field patterns for common fields without perfect formatting
SEX_GENDER_PATTERNS = [
    re.compile(r'\b(sex|gender)\s*[:\-]?\s*(?:M\s*or\s*F|M/F|Male/Female)', re.I),
    re.compile(r'\b(sex|gender)\s*\[\s*\]\s*(?:male|female|M|F)', re.I),
]

MARITAL_STATUS_PATTERNS = [
    re.compile(r'(?:please\s+)?circle\s+one\s*:?\s*(single|married|divorced|separated|widowed)', re.I),
    re.compile(r'\bmarital\s+status\s*:?\s*(?:\[\s*\]|single|married)', re.I),
]

PHONE_PATTERNS = [
    (r'work\s+phone', 'work_phone'),
    (r'home\s+phone', 'home_phone'),
    (r'(?:cell|mobile)\s+phone', 'cell_phone'),
]

ALLOWED_TYPES = {"input", "date", "states", "radio", "dropdown", "terms", "signature"}

PRIMARY_SUFFIX = "__primary"
SECONDARY_SUFFIX = "__secondary"

# ---------- Spell checking dictionary

SPELL_FIX = {
    "rregular": "Irregular",
    "hyploglycemia": "Hypoglycemia",
    "diabates": "Diabetes",
    "osteoperosis": "Osteoporosis",
    "artritis": "Arthritis",
    "rheurnatism": "Rheumatism",
    "e": "Email",
}

# Known field labels dictionary for pattern matching
KNOWN_FIELD_LABELS = {
    # Name fields
    'first_name': r'\bfirst\s+name\b',
    'last_name': r'\blast\s+name\b',
    'preferred_name': r'\bpreferred\s+name\b',
    'middle_initial': r'\b(?:middle\s+initial|m\.?i\.?)\b',
    'patient_name': r'\bpatient\s+name\b',
    'parent_name': r'\bparent\s+name\b',
    # Date/Age fields
    'birth_date': r'\b(?:birth\s+date|date\s+of\s+birth|birthdate)\b',
    'dob': r'\bdob\b',
    'age': r'\bage\b',
    'mother_dob': r"\bmother'?s?\s+dob\b",
    'father_dob': r"\bfather'?s?\s+dob\b",
    # Demographics
    'sex': r'\bsex\b',
    'gender': r'\bgender\b',
    'marital_status': r'\b(?:marital\s+status|please\s+circle\s+one)\b',
    # Contact fields
    'work_phone': r'\bwork\s+phone\b',
    'home_phone': r'\bhome\s+phone\b',
    'cell_phone': r'\b(?:cell|mobile)\s+phone\b',
    'parent_phone': r'\bparent\s+phone\b',
    'email': r'\be-?mail(?:\s+address)?\b',
    'emergency_contact': r'\bemergency\s+contact\b',
    'phone': r'\bphone\b',
    'ext': r'\bext\s*#?\b',
    'extension': r'\bextension\b',
    # Employment/Education
    'occupation': r'\boccupation\b',
    'employer': r'\b(?:employer|employed\s+by)\b',
    'parent_employer': r'\bparent\s+employer\b',
    'patient_employer': r'\bpatient\s+employed\s+by\b',
    'student': r'\b(?:full\s+time\s+)?student\b',
    # ID fields
    'ssn': r'\b(?:ssn|soc\.?\s*sec\.?|social\s+security)\b',
    'drivers_license': r'\bdrivers?\s+license\s*#?',
    'member_id': r'\bmember\s+id\b',
    'policy_holder': r'\bpolicy\s+holder\b',
    # Address fields
    'address': r'\b(?:mailing\s+)?address\b',
    'city': r'\bcity\b',
    'state': r'\bstate\b',
    'zip': r'\bzip(?:\s+code)?\b',
    'apt': r'\bapt\s*#?\b',
    # Insurance fields
    'group_number': r'\b(?:group\s*#|plan\s*/\s*group\s+number)\b',
    'local_number': r'\blocal\s*#',
    'insurance_company': r'\b(?:insurance\s+company|name\s+of\s+insurance)\b',
    'dental_plan_name': r'\bdental\s+plan\s+name\b',
    'plan_group_number': r'\bplan\s*/\s*group\s+number\b',
    'insured_name': r"\b(?:name\s+of\s+)?insured(?:'?s)?\s+name\b",
    'relationship_to_insured': r'\b(?:patient\s+)?relationship\s+to\s+insured\b',
    'id_number': r'\bid\s+number\b',
    # Misc
    'reason_for_visit': r'\breason\s+for\s+(?:today\'?s\s+)?visit\b',
    'previous_dentist': r'\bprevious\s+dentist\b',
}
