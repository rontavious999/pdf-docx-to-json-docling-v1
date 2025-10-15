#!/usr/bin/env python3
"""
Train ML Field Detector on available forms
Processes forms in documents/ directory and trains ML model using self-training approach
"""

import sys
import os
from pathlib import Path
import subprocess

# Add the package to path
sys.path.insert(0, str(Path(__file__).parent))

from docling_text_to_modento.modules.ml_field_detector import initialize_ml_detector


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using docling"""
    cmd = [
        'python3', '-m', 'docling_text_to_modento.main',
        '--input', pdf_path,
        '--output', '/tmp/ml_training_output.json'
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        # Read the intermediate text file if it exists
        text_file = pdf_path.replace('.pdf', '.txt')
        if os.path.exists(text_file):
            with open(text_file, 'r', encoding='utf-8') as f:
                return f.read()
        
        # Try to read from docling output directory
        docling_out = Path('docling_output') / Path(pdf_path).with_suffix('.txt').name
        if docling_out.exists():
            with open(docling_out, 'r', encoding='utf-8') as f:
                return f.read()
                
        print(f"Warning: Could not find extracted text for {pdf_path}")
        return ""
        
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return ""


def main():
    print("=" * 80)
    print("ML Field Detector Training")
    print("=" * 80)
    
    # Find all PDF files in documents directory
    docs_dir = Path(__file__).parent / 'documents'
    pdf_files = list(docs_dir.glob('*.pdf'))
    
    print(f"\nFound {len(pdf_files)} PDF files in documents/:")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    
    # Filter out the documentation PDF
    training_pdfs = [p for p in pdf_files if 'Targeted Patches' not in p.name]
    
    print(f"\nUsing {len(training_pdfs)} PDFs for training:")
    for pdf in training_pdfs:
        print(f"  - {pdf.name}")
    
    # Process each PDF to extract text
    print("\n" + "=" * 80)
    print("Processing forms to extract text...")
    print("=" * 80)
    
    training_texts = []
    for pdf_path in training_pdfs:
        print(f"\nProcessing: {pdf_path.name}")
        
        # Run the main script to process the form
        cmd = [
            'python3', '-m', 'docling_text_to_modento.main',
            str(pdf_path)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=Path(__file__).parent
            )
            
            if result.returncode == 0:
                print(f"  ✓ Successfully processed {pdf_path.name}")
                
                # Look for the extracted text in output
                output_dir = Path(__file__).parent / 'output'
                json_file = output_dir / pdf_path.with_suffix('.json').name
                
                # Also check for intermediate text extraction
                # The main script processes and creates output, we'll read that
                if json_file.exists():
                    # Get the text content - we'll re-process to get raw text
                    import json
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Extract text from questions for training
                        text_lines = []
                        for q in data.get('questions', []):
                            text_lines.append(q.get('title', ''))
                            if 'control' in q and 'options' in q['control']:
                                for opt in q['control']['options']:
                                    text_lines.append(opt.get('name', ''))
                        
                        if text_lines:
                            training_texts.append('\n'.join(text_lines))
                            print(f"  ✓ Extracted {len(text_lines)} lines for training")
            else:
                print(f"  ✗ Error processing {pdf_path.name}: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout processing {pdf_path.name}")
        except Exception as e:
            print(f"  ✗ Error processing {pdf_path.name}: {e}")
    
    # Check if we got training data
    if not training_texts:
        print("\n⚠️  No training data extracted from forms.")
        print("Using synthetic training data for demonstration...")
        
        # Generate synthetic training examples
        training_texts = [
            """Patient Name: _________________
Date of Birth: _________________
Phone Number: _________________

Medical History:
Do you have any allergies? [ ] Yes [ ] No
Are you taking any medications? [ ] Yes [ ] No

Emergency Contact: _________________
Relationship: _________________""",
            
            """First Name: _________ MI: ___ Last Name: _________
Address: _________________________________
City: _____________ State: ___ Zip: _____

Insurance Information:
Primary Insurance: _________________
Policy Number: _________________
Group Number: _________________

Have you been hospitalized? [ ] Yes [ ] No
If yes, please explain: ________________""",
            
            """Email: _________________
Preferred Contact: [ ] Phone [ ] Email [ ] Text

Referral Source:
How did you hear about us?
[ ] Friend/Family [ ] Doctor [ ] Advertisement [ ] Other""",
        ]
        print(f"  Generated {len(training_texts)} synthetic training examples")
    
    # Initialize and train the ML detector
    print("\n" + "=" * 80)
    print("Training ML Field Detector...")
    print("=" * 80)
    
    model_path = Path(__file__).parent / 'models' / 'field_detector.pkl'
    
    print(f"\nTraining on {len(training_texts)} form texts...")
    print(f"Model will be saved to: {model_path}")
    
    try:
        detector = initialize_ml_detector(
            model_path=str(model_path),
            training_forms=training_texts
        )
        
        print("\n✅ Training complete!")
        print(f"Model saved to: {model_path}")
        print(f"Model can now be used for field detection")
        
        # Test the detector
        print("\n" + "=" * 80)
        print("Testing trained model...")
        print("=" * 80)
        
        test_lines = [
            "Patient Name: _________________",
            "Are you taking any medications? [ ] Yes [ ] No",
            "Emergency Contact: _________________",
            "If yes, please explain: _________________",
        ]
        
        for idx, line in enumerate(test_lines):
            prediction = detector.predict(
                line=line,
                prev_line=test_lines[idx-1] if idx > 0 else "",
                next_line=test_lines[idx+1] if idx < len(test_lines)-1 else "",
                line_idx=idx,
                total_lines=len(test_lines)
            )
            
            if prediction:
                print(f"\n  Line: {line[:60]}...")
                print(f"  → Type: {prediction.field_type}")
                print(f"  → Confidence: {prediction.confidence:.2f}")
        
        print("\n" + "=" * 80)
        print("✅ ML Field Detector is ready to use!")
        print("=" * 80)
        print("\nTo use in parsing:")
        print("  1. The model is saved at: models/field_detector.pkl")
        print("  2. Import: from docling_text_to_modento.modules import MLFieldDetector")
        print("  3. detector = MLFieldDetector(model_path='models/field_detector.pkl')")
        print("  4. Use detector.predict() as fallback when rules are uncertain")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during training: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
