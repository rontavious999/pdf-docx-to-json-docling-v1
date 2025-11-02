# How to View the Generated Outputs

## Overview

The pipeline has been run and generated fresh output for all 38 dental forms. This guide shows you how to examine the TXT files and JSON files that were created.

## Generated Files Location

```
📁 output/              # Extracted text files (38 .txt files)
📁 JSONs/               # Generated JSON files (76 files total)
   ├── *.modento.json        # 38 structured JSON outputs
   └── *.modento.stats.json  # 38 processing statistics
📄 run_output.log       # Full debug log from processing
```

**Note**: These directories are in `.gitignore` and not tracked by git. They are generated fresh each time you run the pipeline.

---

## Viewing Extracted Text Files

### List All Text Files
```bash
ls -lh output/
```

### View a Simple Form
```bash
# Patient registration form (medium complexity)
cat output/npf.txt
```

### View a Complex Form
```bash
# Comprehensive patient form (most fields)
cat output/npf1.txt

# Medical history form
cat output/Chicago-Dental-Solutions_Form.txt
```

### View a Consent Form
```bash
# Shows the "instructional text as fields" problem
cat output/CFGingivectomy.txt
```

### Compare Text Quality
```bash
# Show forms sorted by size
ls -lhS output/
```

---

## Viewing Generated JSON Files

### Pretty-Print a JSON File
```bash
# Registration form (100% dictionary match)
python3 -m json.tool JSONs/npf.modento.json

# Complex form with multiple sections
python3 -m json.tool JSONs/npf1.modento.json

# Consent form (low match rate)
python3 -m json.tool JSONs/CFGingivectomy.modento.json
```

### View Field Titles Only
```bash
python3 << 'EOF'
import json
data = json.load(open('JSONs/npf.modento.json'))
for i, field in enumerate(data, 1):
    print(f"{i}. {field['title']} ({field['type']})")
EOF
```

### Count Fields in a JSON
```bash
python3 -c "import json; print(len(json.load(open('JSONs/npf.modento.json'))), 'fields')"
```

---

## Viewing Statistics Files

### Pretty-Print Statistics
```bash
# Shows processing details, match rates, sections
python3 -m json.tool JSONs/npf.modento.stats.json
```

### Key Statistics to Check
```bash
python3 << 'EOF'
import json
stats = json.load(open('JSONs/npf.modento.stats.json'))
print(f"File: {stats['file']}")
print(f"Total fields: {stats['total_items']}")
print(f"Dictionary match: {stats['reused_pct']:.1f}%")
print(f"Sections: {stats['counts_by_section']}")
print(f"Field types: {stats['counts_by_type']}")
EOF
```

---

## Comparing All Forms

### Summary Statistics
```bash
python3 << 'EOF'
import json, os

print("Form Statistics Summary")
print("=" * 70)
print(f"{'Form Name':<40} {'Fields':>8} {'Match %':>8} {'Sections':>8}")
print("-" * 70)

for f in sorted(os.listdir('JSONs')):
    if f.endswith('.modento.stats.json'):
        with open(f'JSONs/{f}') as fp:
            s = json.load(fp)
        name = f.replace('.modento.stats.json', '')[:40]
        print(f"{name:<40} {s['total_items']:>8} {s['reused_pct']:>7.0f}% {len(s['counts_by_section']):>8}")
EOF
```

### Forms by Complexity
```bash
# Show forms sorted by number of fields
python3 << 'EOF'
import json, os
stats = []
for f in os.listdir('JSONs'):
    if f.endswith('.stats.json'):
        with open(f'JSONs/{f}') as fp:
            s = json.load(fp)
        stats.append((f.replace('.modento.stats.json', ''), s['total_items'], s['reused_pct']))

stats.sort(key=lambda x: x[1], reverse=True)
print("Top 10 Most Complex Forms:")
for name, items, match in stats[:10]:
    print(f"  {name}: {items} fields, {match:.0f}% match")
EOF
```

### Forms by Match Rate
```bash
# Show forms sorted by dictionary match rate
python3 << 'EOF'
import json, os
stats = []
for f in os.listdir('JSONs'):
    if f.endswith('.stats.json'):
        with open(f'JSONs/{f}') as fp:
            s = json.load(fp)
        stats.append((f.replace('.modento.stats.json', ''), s['total_items'], s['reused_pct']))

stats.sort(key=lambda x: x[2])
print("Forms with Lowest Dictionary Match:")
for name, items, match in stats[:10]:
    print(f"  {name}: {match:.0f}% match, {items} fields")
EOF
```

---

## Examining Specific Issues

### Find Forms with Warnings
```bash
# Search for dictionary match warnings
grep "\[warn\]" run_output.log | head -20

# Count warnings per form
grep "No dictionary match" run_output.log | wc -l
```

### Find Duplicate Fields
```bash
# Find forms with duplicate fields
grep "duplicate" run_output.log | grep -E "(date_of_birth|signature|phone)" | head -20
```

### Find Grid Detection
```bash
# See which forms had grids detected
grep "grid" run_output.log | grep "SUCCESS" | head -10

# See malformed grids
grep "malformed_grid" run_output.log
```

### Find Section Inference
```bash
# See how sections were inferred
grep "section_inference" run_output.log | head -20
```

---

## Side-by-Side Comparison

### Compare Text vs JSON for a Form
```bash
# Pick a form to examine
FORM="npf"

echo "=== TEXT FILE ==="
head -30 output/$FORM.txt

echo ""
echo "=== JSON FIELDS ==="
python3 -c "
import json
data = json.load(open('JSONs/$FORM.modento.json'))
for field in data[:10]:
    print(f\"  {field['title']} ({field['type']})\")
print(f'... and {len(data)-10} more fields')
"

echo ""
echo "=== STATISTICS ==="
python3 -c "
import json
stats = json.load(open('JSONs/$FORM.modento.stats.json'))
print(f\"  Total fields: {stats['total_items']}\")
print(f\"  Dictionary match: {stats['reused_pct']:.1f}%\")
print(f\"  Sections: {', '.join(stats['counts_by_section'].keys())}\")
"
```

### Compare Two Similar Forms
```bash
# Compare two patient registration forms
echo "=== NPF ==="
python3 -c "import json; print(len(json.load(open('JSONs/npf.modento.json'))), 'fields')"

echo "=== NPF1 ==="
python3 -c "import json; print(len(json.load(open('JSONs/npf1.modento.json'))), 'fields')"
```

---

## Debugging Specific Forms

### Check Why a Form Has Low Match Rate
```bash
FORM="CFGingivectomy"

# 1. Check the text extraction quality
echo "=== First 50 lines of text ==="
head -50 output/$FORM.txt

# 2. Check what fields were captured
echo ""
echo "=== Fields captured ==="
python3 << EOF
import json
data = json.load(open('JSONs/$FORM.modento.json'))
for i, field in enumerate(data, 1):
    print(f"{i}. {field['title']}")
EOF

# 3. Check warnings
echo ""
echo "=== Warnings for this form ==="
grep -A2 "$FORM" run_output.log | grep "\[warn\]" | head -10
```

### Check for Missing Fields
```bash
# Compare text file line count to JSON field count
echo "Text lines:"
wc -l output/npf.txt

echo "JSON fields:"
python3 -c "import json; print(len(json.load(open('JSONs/npf.modento.json'))))"

echo "Ratio:"
python3 << 'EOF'
import json
text_lines = len(open('output/npf.txt').readlines())
json_fields = len(json.load(open('JSONs/npf.modento.json')))
print(f"{json_fields/text_lines:.2f} fields per line of text")
EOF
```

---

## Examining Parity Issues

### See Examples of Each Issue Type

**Instructional Text as Fields** (Issue #1)
```bash
python3 << 'EOF'
import json
data = json.load(open('JSONs/CFGingivectomy.modento.json'))
print("Fields that look like instructions:")
for field in data:
    title = field['title']
    if len(title) > 50 or 'Terms' in title:
        print(f"  - {title[:80]}...")
EOF
```

**Compound Field Issues** (Issue #2)
```bash
# Look at fields with "Patient Name - " prefix
python3 << 'EOF'
import json
data = json.load(open('JSONs/npf.modento.json'))
print("Compound field examples:")
for field in data:
    if 'Patient Name -' in field['title']:
        print(f"  - {field['title']}")
EOF
```

**Duplicate Fields** (Issue #3)
```bash
# Look for fields with #2, #3 suffixes
python3 << 'EOF'
import json
data = json.load(open('JSONs/npf1.modento.json'))
print("Duplicate fields:")
for field in data:
    if '#2' in field['title'] or '#3' in field['title']:
        print(f"  - {field['title']}")
EOF
```

---

## Quick Commands Reference

```bash
# View all text files
ls -1 output/

# View all JSON files  
ls -1 JSONs/*.modento.json

# Count total output
echo "Text files: $(ls output/ | wc -l)"
echo "JSON files: $(ls JSONs/*.modento.json | wc -l)"
echo "Stats files: $(ls JSONs/*.stats.json | wc -l)"

# Average statistics
python3 << 'EOF'
import json, os
stats = [json.load(open(f'JSONs/{f}'))['reused_pct'] 
         for f in os.listdir('JSONs') if f.endswith('.stats.json')]
print(f"Average dictionary match: {sum(stats)/len(stats):.1f}%")
EOF
```

---

## Regenerating Output

If you want to re-run the pipeline with changes:

```bash
# 1. Clean previous output
rm -rf output/ JSONs/ *.stats.json

# 2. Run pipeline
python3 run_all.py

# 3. Check new statistics
python3 << 'EOF'
import json, os
stats = [json.load(open(f'JSONs/{f}'))['reused_pct'] 
         for f in os.listdir('JSONs') if f.endswith('.stats.json')]
print(f"Average dictionary match: {sum(stats)/len(stats):.1f}%")
EOF
```

---

## Next Steps

1. **Browse the outputs** using the commands above
2. **Identify specific issues** in forms you care about
3. **Read the analysis** in `PARITY_ANALYSIS_2025.md`
4. **Prioritize improvements** based on your use case
5. **Implement and test** following `IMPROVEMENTS_QUICK_REFERENCE.md`

For questions or issues, refer to the comprehensive analysis documents in the repository root.
