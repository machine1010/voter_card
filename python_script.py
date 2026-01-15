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
st.set_page_config(page_title="Voter ID Extractor", layout="wide", page_icon="🆔")

# Custom CSS to make inputs look like a static form
st.markdown("""
<style>
    div[data-testid="stTextInput"] input {
        background-color: #f0f2f6;
        color: #31333F;
        font-weight: 500;
    }
    div[data-testid="stTextArea"] textarea {
        background-color: #f0f2f6;
        color: #31333F;
    }
</style>
""", unsafe_allow_html=True)

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
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Voter ID Extraction Report")
    
    c.setFont("Helvetica", 12)
    y_position = height - 80
    
    # Iterate and print fields
    for key, value in json_data.items():
        display_key = key.replace("_", " ").title()
        # Handle None or empty values gracefully for PDF
        display_value = str(value) if value else "N/A"
        text = f"{display_key}: {display_value}"
        
        # Check for page wrap
        if y_position < 50:
            c.showPage()
            y_position = height - 50
            c.setFont("Helvetica", 12)
            
        c.drawString(50, y_position, text)
        y_position -= 20
        
    c.save()
    buffer.seek(0)
    return buffer

def display_voter_form(data):
    """Displays the extracted data in a structured, read-only form layout."""
    
    st.markdown("### 📋 Extracted Voter Details")
    
    # --- Section 1: Identity Information ---
    with st.container(border=True):
        st.caption("Identity Information")
        
        # Row 1
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Election/EPIC Number", value=data.get("election_number", ""), key="d_epic")
        with c2:
            st.text_input("Date of Birth", value=data.get("date_of_birth", ""), key="d_dob")

        # Row 2
        c3, c4 = st.columns()[1][3]
        with c3:
            st.text_input("Full Name", value=data.get("name", ""), key="d_name")
        with c4:
            st.text_input("Gender", value=data.get("gender", ""), key="d_gender")
            
        # Row 3
        st.text_input("Relation Name (Father/Husband/Wife)", value=data.get("relation_name", ""), key="d_rel")

    # --- Section 2: Address Information ---
    with st.container(border=True):
        st.caption("Address Details")
        st.text_area("Full Address", value=data.get("address", ""), height=80, key="d_addr")
        
        c5, c6, c7 = st.columns(3)
        with c5:
            st.text_input("City", value=data.get("city", ""), key="d_city")
        with c6:
            st.text_input("State", value=data.get("state", ""), key="d_state")
        with c7:
            st.text_input("Pincode", value=data.get("pincode", ""), key="d_pin")

    # --- Section 3: Official Information ---
    with st.container(border=True):
        st.caption("Official Use")
        c8, c9 = st.columns()[2][3]
        with c8:
            st.text_input("Electoral Registration Officer", value=data.get("electoral_registration_officer", ""), key="d_ero")
        with c9:
            st.text_input("Issue Date", value=data.get("issue_date", ""), key="d_issue")

def process_images(credential_file, image_files):
    """Main logic to call Gemini API."""
    tmp_cred_path = None
    try:
        # 1. Setup Credentials
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_cred:
            tmp_cred.write(credential_file.getvalue())
            tmp_cred_path = tmp_cred.name

        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = tmp_cred_path
        
        # Load Project ID from JSON
        with open(tmp_cred_path, "r") as f:
            creds = json.load(f)
            # Try to get project_id, fallback to quota_project_id if needed
            project_id = creds.get("project_id") or creds.get("quota_project_id")

        if not project_id:
            st.error("Could not find 'project_id' in the uploaded JSON key.")
            return None

        # Initialize Client
        # Note: location='us-central1' is standard. 
        # If your project is in a different region (e.g., 'asia-south1'), change it here.
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
        You are an expert OCR and document analysis specialist for Indian Voter ID cards.
        Extract the following fields into a pure JSON object:
        
        Fields:
        - election_number (EPIC Number)
        - name
        - relation_name (Father/Husband Name)
        - gender
        - date_of_birth
        - address
        - city
        - state
        - pincode
        - electoral_registration_officer
        - issue_date
        
        Instructions:
        - Return ONLY valid JSON.
        - Use empty string "" for missing fields.
        - Do not include markdown formatting like ```json.
        '''
        contents.append(voter_id_extraction_prompt)

        # 4. Generate Content
        # FIX: Changed model to 'gemini-1.5-flash' (removed -001 to resolve 404 error)
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
            contents=contents
        )
        
        return response.text

    except Exception as e:
        st.error(f"Error details: {str(e)}")
        st.warning("Ensure the 'Vertex AI API' is enabled in your Google Cloud Console for this project.")
        return None
    finally:
        # Cleanup temp file
        if tmp_cred_path and os.path.exists(tmp_cred_path):
            os.remove(tmp_cred_path)

# --- Main App Logic ---

def main():
    # Session State for Login
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # Login Screen
    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.title("🔐 Login")
            with st.form("login_form"):
                user = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
                
                if submitted:
                    if user == DUMMY_USER and password == DUMMY_PASS:
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        return

    # Dashboard (After Login)
    st.sidebar.title("⚙️ Configuration")
    
    # 1. Credentials Upload
    creds_file = st.sidebar.file_uploader(
        "Upload Google Service Account JSON", 
        type=["json"],
        help="Required for Vertex AI access"
    )
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("🆔 Voter ID Data Extractor")
    st.markdown("Upload front and back images of the Voter ID to extract structured data.")

    # 2. Image Upload
    uploaded_files = st.file_uploader(
        "Upload Voter ID Images (Front & Back)", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

    if uploaded_files and creds_file:
        if st.button("🚀 Extract Data", type="primary"):
            with st.spinner("Analyzing document with AI..."):
                raw_text = process_images(creds_file, uploaded_files)
                
                if raw_text:
                    cleaned_json_str = clean_json_response(raw_text)
                    try:
                        data = json.loads(cleaned_json_str)
                        
                        # --- DISPLAY THE FORM ---
                        display_voter_form(data)
                        
                        # --- DOWNLOAD BUTTON ---
                        st.markdown("---")
                        pdf_data = create_pdf(data)
                        st.download_button(
                            label="📥 Download Report as PDF",
                            data=pdf_data,
                            file_name=f"{data.get('election_number', 'voter')}_report.pdf",
                            mime="application/pdf"
                        )
                        
                        # Optional: Show raw JSON for debugging
                        with st.expander("View Raw JSON"):
                            st.json(data)
                            
                    except json.JSONDecodeError:
                        st.error("Failed to parse API response as JSON.")
                        st.text(raw_text)
    elif not creds_file:
        st.info("Please upload your Service Account JSON in the sidebar to proceed.")

if __name__ == "__main__":
    main()
