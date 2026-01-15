import streamlit as st
import json
import os
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

# --- Try Import Vertex AI (Handle missing library gracefully) ---
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel, Part
except ImportError:
    st.error("⚠️ Library missing: 'google-cloud-aiplatform'. Please install it using: pip install google-cloud-aiplatform")
    st.stop()

# --- Configuration & Styles ---
st.set_page_config(page_title="Voter ID Extractor", layout="wide", page_icon="🆔")

# Custom CSS
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
    """Cleans the raw text response to ensure valid JSON."""
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
    
    for key, value in json_data.items():
        display_key = key.replace("_", " ").title()
        display_value = str(value) if value else "N/A"
        text = f"{display_key}: {display_value}"
        
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
    """Displays the extracted data in a structured form layout."""
    st.markdown("### 📋 Extracted Voter Details")
    
    # --- Section 1: Identity Information ---
    with st.container(border=True):
        st.caption("Identity Information")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Election/EPIC Number", value=data.get("election_number", ""), key="d_epic")
        with c2:
            st.text_input("Date of Birth", value=data.get("date_of_birth", ""), key="d_dob")

        c3, c4 = st.columns()[1][3]
        with c3:
            st.text_input("Full Name", value=data.get("name", ""), key="d_name")
        with c4:
            st.text_input("Gender", value=data.get("gender", ""), key="d_gender")
            
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

def process_images_vertex(credential_file, image_files, project_id, location, model_name):
    """Main logic using standard Vertex AI SDK."""
    tmp_cred_path = None
    try:
        # 1. Setup Credentials Environment Variable
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_cred:
            tmp_cred.write(credential_file.getvalue())
            tmp_cred_path = tmp_cred.name

        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = tmp_cred_path
        
        # 2. Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        
        # 3. Load Model
        model = GenerativeModel(model_name)

        # 4. Prepare Content Parts
        parts = []
        
        # Add Images
        for img_file in image_files:
            image_bytes = img_file.getvalue()
            parts.append(Part.from_data(image_bytes, mime_type=img_file.type))

        # Add Prompt
        prompt = '''
        You are an expert OCR specialist for Indian Voter ID cards.
        Extract the following fields into a pure JSON object:
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
        
        Output valid JSON only. No markdown formatting.
        '''
        parts.append(prompt)

        # 5. Generate Response
        response = model.generate_content(parts)
        
        return response.text

    except Exception as e:
        st.error(f"Vertex AI Error: {str(e)}")
        return None
    finally:
        if tmp_cred_path and os.path.exists(tmp_cred_path):
            os.remove(tmp_cred_path)

# --- Main App Logic ---

def main():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # Login
    if not st.session_state.logged_in:
        # FIX: Ensure we pass a list of ratios to st.columns
        c1, c2, c3 = st.columns()[3][1]
        with c2:
            st.title("🔐 Login")
            with st.form("login"):
                user = st.text_input("Username")
                password = st.text_input("Password", type="password")
                
                if st.form_submit_button("Login"):
                    if user == DUMMY_USER and password == DUMMY_PASS:
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        return

    # Sidebar Config
    st.sidebar.title("⚙️ Setup")
    creds_file = st.sidebar.file_uploader("Service Account JSON", type=["json"])
    
    # Region and Model Selection
    location = st.sidebar.selectbox("Region", ["us-central1", "us-east4", "asia-south1"], index=0)
    model_name = st.sidebar.selectbox("Model", ["gemini-1.5-flash-001", "gemini-1.5-pro-001"], index=0)

    st.title("🆔 Voter ID Extractor")
    
    uploaded_files = st.file_uploader("Upload Images", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

    if uploaded_files and creds_file:
        if st.button("🚀 Extract Data", type="primary"):
            
            # Extract Project ID
            try:
                creds_data = json.load(creds_file)
                creds_file.seek(0)
                project_id = creds_data.get("project_id")
            except:
                st.error("Invalid JSON file.")
                return

            with st.spinner("Processing..."):
                raw_text = process_images_vertex(creds_file, uploaded_files, project_id, location, model_name)
                
                if raw_text:
                    try:
                        clean_text = clean_json_response(raw_text)
                        data = json.loads(clean_text)
                        display_voter_form(data)
                        
                        pdf = create_pdf(data)
                        st.download_button("Download PDF", pdf, "report.pdf", "application/pdf")
                        
                    except Exception as e:
                        st.error(f"Parsing Error: {e}")
                        st.text(raw_text)

if __name__ == "__main__":
    main()
