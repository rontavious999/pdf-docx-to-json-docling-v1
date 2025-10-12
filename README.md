# PDF to JSON Converter with Docling for Dental Forms

This project is a powerful two-step pipeline that automates the conversion of dental patient forms (from PDF or `.docx` files) into a structured, Modento-compliant JSON format. It uses local document extraction libraries (PyMuPDF and python-docx) for text extraction and a sophisticated Python script to parse and structure the data.

## Features

- **Automated Two-Step Pipeline**: A single command orchestrates the entire workflow from PDF to JSON.
- **Local Text Extraction**: Uses PyMuPDF (for PDFs) and python-docx (for DOCX files) to extract text locally without requiring external APIs.
- **Intelligent Form Parsing**: The script intelligently identifies and parses various form elements like checkboxes, grids, repeating sections, and composite fields.
- **Data Normalization**: Cleans, normalizes, and structures the extracted data using a predefined form dictionary to ensure consistency.
- **Modento-Compliant Output**: Generates JSON files that are structured to be compatible with the Modento system.
- **Debug and Statistics**: Includes a debug mode for detailed logs and generates a `.stats.json` sidecar file for each conversion, providing insights into the process.

## How It Works

The conversion process is handled by a sequence of scripts orchestrated by `run_all.py`:

1.  **Text Extraction (`docling_extract.py`)**:
    - Scans the `documents/` directory for `.pdf` and `.docx` files.
    - Uses **PyMuPDF** (fitz) for PDF text extraction and **python-docx** for DOCX files.
    - Extracts text locally without requiring external APIs or internet connection.
    - Saves the extracted plain text into the `output/` directory.

2.  **JSON Conversion (`llm_text_to_modento.py`)**:
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
├── docling_extract.py  # Script for local text extraction
├── llm_text_to_modento.py # Script for parsing text and converting to JSON
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
    pip install pymupdf python-docx
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
# Step 1: Extract text from documents
python3 docling_extract.py --in documents --out output

# Step 2: Convert text to JSON (with debug mode)
python3 docling_text_to_modento.py --in output --out JSONs --debug
```

*(Note: The `run_all.py` script runs both steps automatically and enables debug mode by default for the conversion step.)*
