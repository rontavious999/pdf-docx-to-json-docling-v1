# PDF to JSON Converter with LLM for Dental Forms

This project is a powerful two-step pipeline that automates the conversion of dental patient forms (from PDF or `.docx` files) into a structured, Modento-compliant JSON format. It leverages the Unstract LLMWhisperer API for high-accuracy text extraction and uses a sophisticated Python script to parse and structure the data.

## Features

- **Automated Two-Step Pipeline**: A single command orchestrates the entire workflow from PDF to JSON.
- **High-Accuracy Text Extraction**: Uses the Unstract LLMWhisperer API to accurately extract text from complex form layouts.
- **Intelligent Form Parsing**: The script intelligently identifies and parses various form elements like checkboxes, grids, repeating sections, and composite fields.
- **Data Normalization**: Cleans, normalizes, and structures the extracted data using a predefined form dictionary to ensure consistency.
- **Modento-Compliant Output**: Generates JSON files that are structured to be compatible with the Modento system.
- **Debug and Statistics**: Includes a debug mode for detailed logs and generates a `.stats.json` sidecar file for each conversion, providing insights into the process.

## How It Works

The conversion process is handled by a sequence of scripts orchestrated by `run_all.py`:

1.  **Text Extraction (`llmwhisperer.py`)**:
    - Scans the `documents/` directory for `.pdf` and `.docx` files.
    - Sends each file to the **Unstract LLMWhisperer API** to extract text while preserving the form's layout.
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
├── llmwhisperer.py     # Script for text extraction via API
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
    git clone https://github.com/rontavious999/pdf-to-json-llm.git
    cd pdf-to-json-llm
    ```

2.  **Install dependencies:**
    The only external dependency is `requests`.
    ```bash
    pip install requests
    ```

### Configuration

You need an API key from **Unstract LLMWhisperer** to run this project.

1.  **Set the API Key**:
    The recommended way is to set an environment variable named `LLMWHISPERER_API_KEY`.

    - On macOS/Linux:
      ```bash
      export LLMWHISPERER_API_KEY="your_api_key_here"
      ```
    - On Windows:
      ```bash
      set LLMWHISPERER_API_KEY="your_api_key_here"
      ```

    Alternatively, you can directly edit the `llmwhisperer.py` file and replace the placeholder with your key:
    ```python
    # in llmwhisperer.py
    UNSTRACT_API_KEY = os.getenv("LLMWHISPERER_API_KEY", "your_api_key_here")
    ```

### Usage

1.  **Add Documents**: Place your dental form files (`.pdf` or `.docx`) into the `documents/` directory.

2.  **Run the Pipeline**:
    Execute the main script from the root of the project directory.
    ```bash
    python3 run_all.py
    ```

3.  **Check the Output**: The final structured JSON files will be created in the `JSONs/` directory. Each output file will be named after the original input file (e.g., `PatientForm.pdf` -> `PatientForm.modento.json`).

To run in debug mode for more verbose output and statistics, use the `--debug` flag:
```bash
python3 llm_text_to_modento.py --in output --out JSONs --debug
```
*(Note: The `run_all.py` script also enables debug mode by default for the conversion step.)*