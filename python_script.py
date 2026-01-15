import streamlit as st
import json
import os
import tempfile
from google import genai
from google.genai import types
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
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
        display_key = key.replace("_", " ").title()
        text = f"{display_key}: {value}"
        c.drawString(50, y_position, text)
        y_position -= 20
        
        if y_position < 50:
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

        # 3. Prepare Prompt
        voter_id_extraction_prompt = '''
        You are an expert OCR and document analysis specialist with deep knowledge of Indian electoral documents.
        
        ## Your Task
        Carefully analyze the provided voter ID card image(s) and extract specific information fields.

        ## Fields to Extract
        1. **election_number**: The unique EPIC number.
        2. **name**: Full name of the voter.
        3. **relation_name**: Name of father/husband/wife/mother.
        4. **gender**: Gender of the voter.
        5. **date_of_birth**: Date of birth (DD-MM-YYYY).
        6. **address**: Complete address.
        6.1 **city**: City.
        6.2 **state**: State.
        6.3 **pincode**: Pincode.
        7. **electoral_registration_officer**: Name/designation of the Officer.
        8. **issue_date**: Date when the card was issued.

        ## Output Format
        Return ONLY a valid JSON object.
        '''
        
        contents.append(voter_id_extraction_prompt)

        # 4. Generate Content
        generate_config = types.GenerateContentConfig(
            temperature=0,
            max_output_tokens=4096
        )

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp", # Updated to a valid model name or keep gemini-1.5-flash
            contents=contents,
            config=generate_config
        )

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

    # --- Initialize Session State for Data ---
    if "extracted_data" not in st.session_state:
        st.session_state.extracted_data = None

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
                        # Store in session state to persist across reruns
                        st.session_state.extracted_data = json.loads(cleaned_text)
                        st.success("Extraction Complete!")
                    except json.JSONDecodeError:
                        st.error("Failed to parse the response as JSON.")
                        st.text_area("Raw Response", raw_response)

    # --- Display Form if Data Exists ---
    if st.session_state.extracted_data:
        data = st.session_state.extracted_data
        
        st.subheader("Extracted Details")
        st.info("You can edit the fields below before downloading.")

        # --- Form Layout ---
        with st.container():
            c1, c2 = st.columns(2)
            with c1:
                data["election_number"] = st.text_input("Election Number", value=data.get("election_number", ""))
                data["name"] = st.text_input("Name", value=data.get("name", ""))
                data["gender"] = st.text_input("Gender", value=data.get("gender", ""))
            
            with c2:
                data["issue_date"] = st.text_input("Issue Date", value=data.get("issue_date", ""))
                data["relation_name"] = st.text_input("Relation Name", value=data.get("relation_name", ""))
                data["date_of_birth"] = st.text_input("Date of Birth", value=data.get("date_of_birth", ""))

            data["address"] = st.text_area("Address", value=data.get("address", ""))

            c3, c4, c5 = st.columns(3)
            with c3:
                data["city"] = st.text_input("City", value=data.get("city", ""))
            with c4:
                data["state"] = st.text_input("State", value=data.get("state", ""))
            with c5:
                data["pincode"] = st.text_input("Pincode", value=data.get("pincode", ""))
            
            data["electoral_registration_officer"] = st.text_input("Electoral Registration Officer", value=data.get("electoral_registration_officer", ""))

        # --- Update Session State with Edits ---
        st.session_state.extracted_data = data

        st.markdown("---")
        
        # Generate PDF from CURRENT (possibly edited) data
        pdf_buffer = create_pdf(st.session_state.extracted_data)
        
        st.download_button(
            label="Download as PDF",
            data=pdf_buffer,
            file_name="voter_id_card.pdf",
            mime="application/pdf"
        )

# --- Entry Point ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_screen()
    st.info(f"Use dummy credentials: {DUMMY_USER} / {DUMMY_PASS}")
else:
    main_app()
