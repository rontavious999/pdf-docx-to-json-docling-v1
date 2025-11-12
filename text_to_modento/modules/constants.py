"""
Constants, regex patterns, and configuration values used throughout the pipeline.
"""

import re

# ---------- Paths

DEFAULT_IN_DIR = "output"
DEFAULT_OUT_DIR = "JSONs"

# ---------- Regex / tokens

CHECKBOX_ANY = r"(?:\[\s*\]|\[x\]|☐|☑|□|■|❒|◻|✓|✔|✗|✘|!)"
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
DATE_LABEL_RE  = re.compile(r"\b(date|dob|birth|signed|today'?s?\s+date|"
                           r"signature\s+date|consent\s+date|treatment\s+date|"
                           r"visit\s+date|appointment\s+date|procedure\s+date)\b", re.I)
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
REFERRED_BY_RE  = re.compile(r"\b(referred\s+by|who\s+can\s+we\s+thank|referral\s+source)\b", re.I)

# Category 1 Fix 1.5: Relationship field patterns
RELATIONSHIP_RE = re.compile(r"\brelationship\s+to\s+(?:patient|insured|subscriber)\b", re.I)
EMERGENCY_CONTACT_RE = re.compile(r"\bemergency\s+contact\b", re.I)
GUARDIAN_RE = re.compile(r"\b(?:parent|guardian|responsible\s+party)\b", re.I)

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
    # Name fields - Enhanced patterns
    # Production Improvement: Use lookahead (?=[^a-zA-Z]|$) to handle underscores/dashes after labels
    'full_name': r'\bfull\s+name(?=[^a-zA-Z]|$)',
    'first_name': r'\bfirst\s+name(?=[^a-zA-Z]|$)',
    'last_name': r'\blast\s+name(?=[^a-zA-Z]|$)',
    'preferred_name': r'\bpreferred\s+name(?=[^a-zA-Z]|$)',
    'middle_initial': r'\b(?:middle\s+initial|m\.?i\.?)(?=[^a-zA-Z]|$)',
    'patient_name': r'\b(?:patient(?:\'?s)?\s+name|name\s+of\s+patient|patient\s+name\s+\(print\)|patient\s+name\s+\(please\s+print\))(?=[^a-zA-Z]|$)',
    'parent_name': r'\b(?:parent\s+name|parent\'?s?\s+name|parent/guardian\s+name)(?=[^a-zA-Z]|$)',
    'guardian_name': r'\b(?:guardian\s+name|guardian\'?s?\s+name|legal\s+guardian\s+name)(?=[^a-zA-Z]|$)',
    'printed_name': r'\b(?:name\s+\(print\)|name\s+\(please\s+print\)|printed\s+name)(?=[^a-zA-Z]|$)',
    'legal_name': r'\blegal\s+name(?=[^a-zA-Z]|$)',
    'representative_name': r'\b(?:representative\s+name|authorized\s+representative)(?=[^a-zA-Z]|$)',
    # Date/Age fields - Enhanced patterns
    'birth_date': r'\b(?:birth\s+date|date\s+of\s+birth|birthdate)(?=[^a-zA-Z]|$)',
    'dob': r'\bdob(?=[^a-zA-Z]|$)',
    'age': r'\bage(?=[^a-zA-Z]|$)',
    'mother_dob': r"\bmother'?s?\s+dob(?=[^a-zA-Z]|$)",
    'father_dob': r"\bfather'?s?\s+dob(?=[^a-zA-Z]|$)",
    'date_signed': r'\b(?:date|today\'?s?\s+date|signature\s+date|consent\s+date|signed\s+date)(?=[^a-zA-Z]|$)',
    'treatment_date': r'\b(?:treatment\s+date|procedure\s+date|visit\s+date)(?=[^a-zA-Z]|$)',
    # Demographics
    'sex': r'\bsex(?=[^a-zA-Z]|$)',
    'gender': r'\bgender(?=[^a-zA-Z]|$)',
    'marital_status': r'\b(?:marital\s+status|please\s+circle\s+one)(?=[^a-zA-Z]|$)',
    # Contact fields
    'phone_number': r'\bphone\s+number(?=[^a-zA-Z]|$)',
    'work_phone': r'\bwork\s+phone(?=[^a-zA-Z]|$)',
    'home_phone': r'\bhome\s+phone(?=[^a-zA-Z]|$)',
    'cell_phone': r'\b(?:cell|mobile)\s+phone(?=[^a-zA-Z]|$)',
    'parent_phone': r'\bparent\s+phone(?=[^a-zA-Z]|$)',
    'email': r'\be-?mail(?:\s+address)?(?=[^a-zA-Z]|$)',
    'emergency_contact': r'\bemergency\s+contact(?=[^a-zA-Z]|$)',
    'phone': r'\bphone(?=[^a-zA-Z]|$)',
    'ext': r'\bext\s*#?(?=[^a-zA-Z]|$)',
    'extension': r'\bextension(?=[^a-zA-Z]|$)',
    # Employment/Education
    'occupation': r'\boccupation(?=[^a-zA-Z]|$)',
    'employer': r'\b(?:employer|employed\s+by)(?=[^a-zA-Z]|$)',
    'parent_employer': r'\bparent\s+employer(?=[^a-zA-Z]|$)',
    'patient_employer': r'\bpatient\s+employed\s+by(?=[^a-zA-Z]|$)',
    'student': r'\b(?:full\s+time\s+)?student(?=[^a-zA-Z]|$)',
    # ID fields
    'ssn': r'\b(?:ssn|soc\.?\s*sec\.?|social\s+security)(?=[^a-zA-Z]|$)',
    'drivers_license': r'\bdrivers?\s+license\s*#?(?=[^a-zA-Z]|$)',
    'member_id': r'\bmember\s+id(?=[^a-zA-Z]|$)',
    'policy_holder': r'\bpolicy\s+holder(?=[^a-zA-Z]|$)',
    # Address fields
    'address': r'\b(?:mailing\s+)?address(?=[^a-zA-Z]|$)',
    'city': r'\bcity(?=[^a-zA-Z]|$)',
    'state': r'\bstate(?=[^a-zA-Z]|$)',
    'zip': r'\bzip(?:\s+code)?(?=[^a-zA-Z]|$)',
    'apt': r'\bapt\s*#?(?=[^a-zA-Z]|$)',
    # Insurance fields
    'group_number': r'\b(?:group\s*#|plan\s*/\s*group\s+number)(?=[^a-zA-Z]|$)',
    'local_number': r'\blocal\s*#(?=[^a-zA-Z]|$)',
    'insurance_company': r'\b(?:insurance\s+company|name\s+of\s+insurance)(?=[^a-zA-Z]|$)',
    'dental_plan_name': r'\bdental\s+plan\s+name(?=[^a-zA-Z]|$)',
    'plan_group_number': r'\bplan\s*/\s*group\s+number(?=[^a-zA-Z]|$)',
    'insured_name': r"\b(?:name\s+of\s+)?insured(?:'?s)?\s+name(?=[^a-zA-Z]|$)",
    'relationship_to_insured': r'\b(?:patient\s+)?relationship\s+to\s+insured(?=[^a-zA-Z]|$)',
    'id_number': r'\bid\s+number(?=[^a-zA-Z]|$)',
    # Misc
    'reason_for_visit': r'\breason\s+for\s+(?:today\'?s\s+)?visit(?=[^a-zA-Z]|$)',
    'previous_dentist': r'\bprevious\s+dentist(?=[^a-zA-Z]|$)',
    # Category 1 Fix 1.5: Relationship fields
    'relationship': r'\brelationship(?=[^a-zA-Z]|$)',
    'emergency_contact_name': r'\bemergency\s+contact\s+name(?=[^a-zA-Z]|$)',
    'emergency_phone': r'\bemergency\s+(?:contact\s+)?phone(?=[^a-zA-Z]|$)',
    'responsible_party_name': r'\b(?:name\s+of\s+)?responsible\s+party(?=[^a-zA-Z]|$)',
    'parent_relationship': r'\bparent\s+relationship(?=[^a-zA-Z]|$)',
    # Category 1 Fix 1.6: Referral source fields  
    'referral_source': r'\b(?:referral\s+source|how\s+did\s+you\s+hear)(?=[^a-zA-Z]|$)',
    'referred_by': r'\breferred\s+by(?=[^a-zA-Z]|$)',
    'who_referred': r'\bwho\s+can\s+we\s+thank(?=[^a-zA-Z]|$)',
    # Category 1 Fix 1.7: Enhanced date field patterns
    'date_of_service': r'\bdate\s+of\s+service(?=[^a-zA-Z]|$)',
    'appointment_date': r'\bappointment\s+date(?=[^a-zA-Z]|$)',
    'today_date': r"\btoday'?s?\s+date(?=[^a-zA-Z]|$)",
    'last_cleaning': r'\blast\s+cleaning(?=[^a-zA-Z]|$)',
    'last_xrays': r'\blast\s+(?:complete\s+)?x-?rays(?=[^a-zA-Z]|$)',
    'last_visit': r'\blast\s+(?:dental\s+)?visit(?=[^a-zA-Z]|$)',
    # Dental-specific fields
    'tooth_number': r'\btooth\s+(?:number|no\.?|#)(?=[^a-zA-Z]|$)',
    'physician_name': r'\bphysician\s+name(?=[^a-zA-Z]|$)',
    'dentist_name': r'\b(?:dentist|previous\s+dentist)\s+name(?=[^a-zA-Z]|$)',
    'dental_practice_name': r'\bname\s+of\s+(?:current|new|previous)?\s*dental\s+practice(?=[^a-zA-Z]|$)',
    'practice_name': r'\bpractice\s+name(?=[^a-zA-Z]|$)',
    'date_of_release': r'\bdate\s+of\s+release(?=[^a-zA-Z]|$)',
}
