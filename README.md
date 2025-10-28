# PDF to JSON Converter with Unstructured for Dental Forms

This project is a powerful two-step pipeline that automates the conversion of dental patient forms (from PDF or `.docx` files) into a structured, Modento-compliant JSON format. It uses the Unstructured library for high-accuracy document text extraction and a sophisticated Python script to parse and structure the data.

## Features

- **Automated Two-Step Pipeline**: A single command orchestrates the entire workflow from PDF to JSON.
- **High-Accuracy Text Extraction**: Uses the Unstructured library with hi-res strategy for model-based layout detection and table structure inference.
- **Intelligent Form Parsing**: The script intelligently identifies and parses various form elements like checkboxes, grids, repeating sections, and composite fields.
- **Data Normalization**: Cleans, normalizes, and structures the extracted data using a predefined form dictionary to ensure consistency.
- **Modento-Compliant Output**: Generates JSON files that are structured to be compatible with the Modento system.
- **Debug and Statistics**: Includes a debug mode for detailed logs and generates a `.stats.json` sidecar file for each conversion, providing insights into the process.

## How It Works

The conversion process is handled by a sequence of scripts orchestrated by `run_all.py`:

1.  **Text Extraction (`unstructured_extract.py`)**:
    - Scans the `documents/` directory for `.pdf` and `.docx` files.
    - Uses **Unstructured** library for high-accuracy document text extraction.
    - Leverages hi-res strategy with model-based layout detection for superior accuracy.
    - Automatically infers table structures to preserve grid layouts.
    - Saves the extracted plain text into the `output/` directory.

2.  **JSON Conversion (`text_to_modento.py`)**:
    - Reads the raw text files from the `output/` directory.
    - Applies a large set of rules and regular expressions to parse the text, identifying sections, questions, and options.
    - Matches the parsed fields against the `dental_form_dictionary.json` template to create a structured, standardized output.
    - Generates the final `.modento.json` files in the `JSONs/` directory.

### Directory Structure

```
.
├── documents/          # Input: Place your PDF and DOCX forms here
├── output/             # Intermediate: Extracted plain text files are stored here
├── JSONs/              # Output: Final structured JSON files are saved here
├── run_all.py          # Main script to run the entire pipeline
├── unstructured_extract.py  # Script for local text extraction
├── text_to_modento.py # Script for parsing text and converting to JSON
└── dental_form_dictionary.json # Template for standardizing form fields
```

## Getting Started

Follow these steps to set up and run the project.

### Prerequisites

- Python 3.x
- `pip` for installing packages

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/rontavious999/pdf-docx-to-json-docling-v1.git
    cd pdf-docx-to-json-docling-v1
    ```

2.  **Install dependencies:**
    ```bash
    pip install unstructured
    ```

3.  **Optional: Install additional dependencies for specific file types:**
    ```bash
    # For better PDF support
    pip install "unstructured[pdf]"
    
    # For better image/OCR support
    pip install "unstructured[all-docs]"
    ```

### Usage

1.  **Add Documents**: Place your dental form files (`.pdf` or `.docx`) into the `documents/` directory.

2.  **Run the Pipeline**:
    Execute the main script from the root of the project directory.
    ```bash
    python3 run_all.py
    ```

3.  **Check the Output**: The final structured JSON files will be created in the `JSONs/` directory. Each output file will be named after the original input file (e.g., `PatientForm.pdf` -> `PatientForm.modento.json`).

To run the extraction and conversion steps separately:

```bash
# Step 1: Extract text from documents (default: documents -> output)
python3 unstructured_extract.py

# Step 1 (with custom input/output):
python3 unstructured_extract.py --in documents --out output

# Step 1 (with hi_res strategy for maximum accuracy):
python3 unstructured_extract.py --in documents --out output --strategy hi_res

# Step 1 (with retry on empty results):
python3 unstructured_extract.py --in documents --out output --retry

# Step 1 (with custom language support):
python3 unstructured_extract.py --in documents --out output --languages eng,spa

# Step 2: Convert text to JSON (with debug mode)
python3 text_to_modento.py --in output --out JSONs --debug

# Step 2 (with parallel processing for large batches):
python3 text_to_modento.py --in output --out JSONs --jobs 4
```

**Extraction Strategies:**
- `hi_res` (default): Best accuracy, uses model-based layout detection
- `fast`: Faster extraction, lower accuracy
- `auto`: Automatically choose based on document type
- `ocr_only`: Force OCR for all documents

*(Note: The `run_all.py` script runs both steps automatically and enables debug mode by default for the conversion step.)*

## Supported Form Types

This pipeline is designed to work with:

- **PDF files** - Both digitally-created PDFs and scanned documents
- **DOCX files** - Microsoft Word documents and compatible formats
- **Common dental intake form layouts** - Patient information, medical history, insurance, consent forms

The Unstructured library uses advanced ML models for layout detection, making it robust across various form layouts without requiring form-specific customization.

## Known Limitations

While the pipeline achieves 95%+ field capture accuracy on most forms, there are some current limitations:

### Text Extraction
- **Unstructured library dependencies**: The extraction quality depends on having the proper Unstructured dependencies installed. For best results, install `unstructured[all-docs]`.
- **Strategy selection**: The default `hi_res` strategy provides the best accuracy but is slower. Use `fast` for quicker processing if needed.

### Edge Cases in Parsing
Most common edge cases are now handled automatically:
- **Multi-sub-field labels**: ✓ **Now supported** - Fields like "Phone: Mobile ___ Home ___ Work ___" are automatically split into separate phone_mobile, phone_home, and phone_work fields.
- **Grid column headers**: ✓ **Enhanced** - In multi-column checkbox grids, category headers (e.g., "Appearance / Function / Habits") are now consistently captured and prefixed to option names (e.g., "Habits - Smoking"). Now handles flexible header counts and spanning headers.
- **Inline checkboxes**: ✓ **Now supported** - Checkboxes embedded within sentences (e.g., "[ ] Yes, send me text alerts") are now captured as separate boolean fields with meaningful labels.
- **Debug logging**: ✓ **Enhanced** - Debug mode now warns when parsed fields don't match any dictionary template, helping identify missing entries for ongoing maintenance.

These edge cases affect less than 5% of fields on typical forms and are documented in `ACTIONABLE_ITEMS.md` for future improvement.

## Best Practices

For optimal results:

- ✅ **Use hi_res strategy** - The default hi_res strategy provides the best accuracy with model-based layout detection
- ✅ **Enable table inference** - Keep `--infer-table-structure` enabled (default) to preserve grid layouts
- ✅ **Install full dependencies** - Use `pip install "unstructured[all-docs]"` for complete support
- ✅ **Test with debug mode** - Use `--debug` flag to see detailed parsing logs and field statistics
- ✅ **Review the stats.json output** - Check the generated `.stats.json` files to verify field capture accuracy

## Testing

The project includes a comprehensive test suite to ensure reliability and catch regressions.

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_text_preprocessing.py -v

# Run with coverage report (requires pytest-cov)
pip install pytest-cov
pytest tests/ --cov=text_to_modento --cov-report=term-missing
```

### Test Coverage

The test suite (99 tests) covers:
- **Text preprocessing**: Line coalescing, normalization
- **Question parsing**: Field extraction, option cleaning, splitting
- **Template matching**: Catalog loading, fuzzy matching, aliases
- **Pattern recognition**: Dates, states, checkboxes, Yes/No questions
- **Edge cases**: Multi-field labels, grid headers, inline checkboxes, OCR detection
- **Recent patches**: Category prefixing consistency, debug logging for unmatched fields

See `tests/README.md` for detailed documentation on the test suite.
