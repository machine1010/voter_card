import streamlit as st
import json
import os
import tempfile
from google import genai
from google.genai import types
##from reportlab.lib.pagesizes import letter
##from reportlab.pdfgen import canvas
from io import BytesIO

# --- Configuration & Styles ---
st.set_page_config(page_title="Voter ID Extractor", layout="wide")

# --- Constants ---
DUMMY_USER = "admin"
DUMMY_PASS = "password123"

# --- Helper Functions ---

def clean_json_response(text):
    """Cleans the raw text response from Gemini to ensure valid JSON."""
    text = text.strip()
    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def create_pdf(json_data):
    """Generates a PDF file from the JSON data."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Voter ID Extraction Report")
    
    c.setFont("Helvetica", 12)
    y_position = height - 80
    
    for key, value in json_data.items():
        # Format key for display (e.g., "election_number" -> "Election Number")
        display_key = key.replace("_", " ").title()
        text = f"{display_key}: {value}"
        
        # Simple text wrapping or truncation could be added here for very long lines
        c.drawString(50, y_position, text)
        y_position -= 20
        
        if y_position < 50: # New page if needed
            c.showPage()
            y_position = height - 50
            
    c.save()
    buffer.seek(0)
    return buffer

def process_images(credential_file, image_files):
    """Main logic to call Gemini API."""
    try:
        # 1. Setup Credentials
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_cred:
            tmp_cred.write(credential_file.getvalue())
            tmp_cred_path = tmp_cred.name
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = tmp_cred_path
        
        # Initialize Client (Assuming Project ID is inside the JSON or env)
        # We attempt to load the project ID from the JSON for robustness, 
        # or rely on default google auth behavior
        with open(tmp_cred_path, "r") as f:
            creds = json.load(f)
            project_id = creds.get("project_id") or creds.get("quota_project_id")

        client = genai.Client(
            vertexai=True,
            project=project_id,
            location="us-central1" 
        )

        # 2. Prepare Images
        contents = []
        for img_file in image_files:
            image_bytes = img_file.getvalue()
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=img_file.type
            )
            contents.append(image_part)

        # 3. Prepare Prompt (Copied from original script)
        voter_id_extraction_prompt = '''
        You are an expert OCR and document analysis specialist with deep knowledge of Indian electoral documents, including voter ID cards (EPIC - Elector's Photo Identity Card) issued by the Election Commission of India. You are highly skilled at extracting structured information from images containing text in multiple Indian languages including English, Hindi, Kannada, Telugu, Tamil, Malayalam, Bengali, Gujarati, Marathi, and others.

        ## Your Task
        Carefully analyze the provided voter ID card image(s) and extract specific information fields. You will receive one or two images - typically a front side and a back side of the voter ID card.

        ## Critical Instructions
        1. **No Hallucination**: Extract ONLY the information that is clearly visible and readable in the image. Do not infer, guess, or make up any information.
        2. **Handle Missing Information**: If any field is not present, not readable, or not visible in the image, return an empty string ("") for that field.
        3. **Language Preference**:
        - If information is available in both English and a regional language, extract the English version
        - If only regional language is present, extract in that regional language exactly as written
        - Maintain the original script (Devanagari, Kannada, Telugu, etc.)
        4. **Field Location Awareness**:
        - Election Number/EPIC Number: Usually found above or near the photograph on the front side, often in format like "ABC1234567" or "ABC/12/123/123456"
        - Name, Wife's/Husband's Name, Gender, Date of Birth: Typically on the front side
        - Address: Can be on front or back side
        - Electoral Registration Officer: Usually on back side
        - Issue Date: Usually on back side
        5. **Output Format**: Return ONLY a valid JSON object with the exact structure shown below. Do not include any explanatory text before or after the JSON.

        ## Fields to Extract
        1. **election_number**: The unique EPIC number (also called Elector's Photo Identity Card number). Often written above the photo or in a prominent position.
        2. **name**: Full name of the voter as written on the card
        3. **relation_name**: Name of father/husband/wife/mother (the relation type may vary - extract the name that appears after "Father's Name", "Husband's Name", "Wife's Name", or similar labels)
        4. **gender**: Gender of the voter (Male/Female/Transgender or ಪುರುಷ/ಮಹಿಳೆ or other regional language equivalents)
        5. **date_of_birth**: Date of birth in the format shown on the card (usually DD-MM-YYYY)
        6. **address**: Complete address as written on the card
        6.1 **city**: City where the address is mentioned
        6.2 **state**: State where the address is mentioned
        6.3 **pincode**: Pincode where the address is mentioned
        7. **electoral_registration_officer**: Name/designation of the Electoral Registration Officer
        8. **issue_date**: Date when the card was issued (usually found on back side)

        ## Expected JSON Output Structure
        {
        "election_number": "SVF5418760",
        "name": "AVINASH KUMAR",
        "relation_name": "SAIKIT KUMAR(father)",
        "gender": "Male",
        "date_of_birth": "28-06-1998",
        "address": "001, BANGALORE WEST, MARATHALLI VILLEGE -560087",
        "city": "BANGALORE",
        "state": "Karnataka",
        "pincode": "560087",
        "electoral_registration_officer": "Electoral Registration Officer, 174 Mahadevapura (SC)",
        "issue_date": "21-04-2024"
        }
        '''
        
        contents.append(voter_id_extraction_prompt)

        # 4. Generate Content
        generate_config = types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=4096
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=generate_config
        )

        # Cleanup
        os.unlink(tmp_cred_path)
        
        return response.text

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        if os.path.exists(tmp_cred_path):
            os.unlink(tmp_cred_path)
        return None

# --- Application Flow ---

def login_screen():
    st.title("Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if username == DUMMY_USER and password == DUMMY_PASS:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid credentials")

def main_app():
    st.title("Voter ID Information Extractor")
    st.write(f"Welcome, {DUMMY_USER}")
    
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.markdown("---")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Upload Credentials")
        cred_file = st.file_uploader("Upload user-credential.json", type=['json'])

    with col2:
        st.subheader("2. Upload Voter ID Images")
        uploaded_images = st.file_uploader(
            "Upload Front and Back images (Max 2)", 
            type=['jpg', 'jpeg', 'png'], 
            accept_multiple_files=True
        )

    start_process = st.button("Start Extraction Process", type="primary")

    if start_process:
        if not cred_file:
            st.warning("Please upload the credential JSON file.")
        elif not uploaded_images or len(uploaded_images) > 2:
            st.warning("Please upload exactly 1 or 2 images.")
        else:
            with st.spinner("Processing images with Gemini..."):
                raw_response = process_images(cred_file, uploaded_images)
                
                if raw_response:
                    cleaned_text = clean_json_response(raw_response)
                    try:
                        json_data = json.loads(cleaned_text)
                        
                        st.success("Extraction Complete!")
                        
                        # Display Data in User Friendly Form
                        st.subheader("Extracted Details")
                        st.json(json_data)
                        
                        # Generate PDF
                        pdf_buffer = create_pdf(json_data)
                        
                        st.download_button(
                            label="Download as PDF",
                            data=pdf_buffer,
                            file_name="voter_id_card.pdf",
                            mime="application/pdf"
                        )
                        
                    except json.JSONDecodeError:
                        st.error("Failed to parse the response as JSON.")
                        st.text_area("Raw Response", raw_response)

# --- Entry Point ---

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_screen()
    # Hint for the user
    st.info(f"Use dummy credentials: {DUMMY_USER} / {DUMMY_PASS}")
else:
    main_app()
