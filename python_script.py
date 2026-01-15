import streamlit as st
import json
import os
import tempfile
from io import BytesIO

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Google Gemini imports
from google import genai
from google.genai import types

# Page configuration
st.set_page_config(
    page_title="Voter ID Extractor", 
    page_icon="🆔",
    layout="wide"
)

# Constants
DUMMY_USER = "admin"
DUMMY_PASS = "password123"

# Helper Functions
def clean_json_response(text):
    """Clean Gemini response to valid JSON."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def create_pdf(json_data):
    """Generate PDF from voter data."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 60, "🆔 Voter ID Extraction Report")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 85, "Verified Details from EPIC Card")
    
    y_position = height - 110
    fields = [
        ("Election Number", json_data.get("election_number", "")),
        ("Voter Name", json_data.get("name", "")),
        ("Relation Name", json_data.get("relation_name", "")),
        ("Gender", json_data.get("gender", "")),
        ("Date of Birth", json_data.get("date_of_birth", "")),
        ("Address", json_data.get("address", "")),
        ("City", json_data.get("city", "")),
        ("State", json_data.get("state", "")),
        ("Pincode", json_data.get("pincode", "")),
        ("ERO", json_data.get("electoral_registration_officer", "")),
        ("Issue Date", json_data.get("issue_date", ""))
    ]
    
    for label, value in fields:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y_position, f"{label}:")
        c.setFont("Helvetica", 10)
        text = str(value)[:80]  # Truncate long text
        c.drawString(150, y_position, text)
        y_position -= 22
        
        if y_position < 60:
            c.showPage()
            y_position = height - 60
    
    c.save()
    buffer.seek(0)
    return buffer

def process_images(credential_file, image_files):
    """Extract voter info using Gemini API."""
    try:
        # Setup credentials
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_cred:
            tmp_cred.write(credential_file.getvalue())
            tmp_cred_path = tmp_cred.name
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = tmp_cred_path
        
        # Load project ID from credentials
        with open(tmp_cred_path, "r") as f:
            creds = json.load(f)
            project_id = creds.get("project_id") or creds.get("quota_project_id", "gen-lang-client-0155506887")

        # Initialize client
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        
        # Prepare images
        contents = []
        for img_file in image_files:
            image_bytes = img_file.getvalue()
            image_part = types.Part.from_bytes(data=image_bytes, mime_type=img_file.type)
            contents.append(image_part)
        
        # Voter ID extraction prompt
        voter_prompt = '''You are an expert OCR specialist for Indian Voter ID cards. Extract ONLY visible text. Return JSON only.

Expected fields: election_number, name, relation_name, gender, date_of_birth, address, city, state, pincode, electoral_registration_officer, issue_date'''
        
        contents.append(voter_prompt)
        
        # Generate content
        config = types.GenerateContentConfig(temperature=0, max_output_tokens=2048)
        response = client.models.generate_content(model="gemini-2.5-flash", contents=contents, config=config)
        
        # Cleanup
        os.unlink(tmp_cred_path)
        return response.text
        
    except Exception as e:
        if 'tmp_cred_path' in locals() and os.path.exists(tmp_cred_path):
            os.unlink(tmp_cred_path)
        st.error(f"Processing error: {str(e)}")
        return None

# Login Screen
def login_screen():
    st.title("🆔 Voter ID Extractor")
    st.markdown("**Upload Voter ID images and extract information automatically**")
    
    with st.form("login"):
        username = st.text_input("👤 Username", placeholder="admin")
        password = st.text_input("🔒 Password", type="password", placeholder="password123")
        login_btn = st.form_submit_button("🚀 Login", type="primary")
        
        if login_btn:
            if username == DUMMY_USER and password == DUMMY_PASS:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ Invalid credentials!")

# Main Application
def main_app():
    st.title("🆔 Voter ID Information Extractor")
    
    # Logout button
    col1, col2, col3 = st.columns()[1]
    with col2:
        if st.button("🚪 Logout", type="secondary"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.markdown("---")
    
    # File Upload Section
    col_cred, col_img = st.columns()[2][1]
    
    with col_cred:
        st.subheader("📁 1. Upload Credentials")
        cred_file = st.file_uploader("user-credential.json", type="json")
    
    with col_img:
        st.subheader("📸 2. Upload Images")
        uploaded_images = st.file_uploader(
            "Voter ID Front + Back (Max 2)", 
            type=['jpg','jpeg','png'], 
            accept_multiple_files=True
        )
    
    # Process Button
    if st.button("🔍 **START EXTRACTION**", type="primary", use_container_width=True):
        if not cred_file:
            st.warning("⚠️ Please upload credential JSON")
        elif not uploaded_images or len(uploaded_images) > 2:
            st.warning("⚠️ Upload exactly 1-2 images")
        else:
            with st.spinner("🤖 Analyzing with Gemini AI..."):
                raw_response = process_images(cred_file, uploaded_images)
                
                if raw_response:
                    cleaned = clean_json_response(raw_response)
                    try:
                        json_data = json.loads(cleaned)
                        
                        st.success("✅ **Extraction Complete!**")
                        
                        # ========================================
                        # USER-FRIENDLY EDITABLE FORM
                        # ========================================
                        st.markdown("---")
                        st.markdown("### 🔍 **Verify & Edit Extracted Details**")
                        st.markdown("*Review accuracy and edit if needed*")
                        
                        # Row 1: Election + Name
                        r1_c1, r1_c2 = st.columns([1.2, 1.8])
                        with r1_c1:
                            st.markdown("**📄 Election Number**")
                            election_num = st.text_input(
                                "", value=json_data.get("election_number", ""),
                                key="elec_num"
                            )
                        with r1_c2:
                            st.markdown("**👤 Voter Name**")
                            voter_name = st.text_input(
                                "", value=json_data.get("name", ""),
                                key="voter_name"
                            )
                        
                        # Row 2: Relation + Gender + DOB
                        r2_c1, r2_c2, r2_c3 = st.columns([1.4, 0.9, 1.1])
                        with r2_c1:
                            st.markdown("**👨‍👩‍👦 Relation**")
                            relation = st.text_input(
                                "", value=json_data.get("relation_name", ""),
                                key="relation"
                            )
                        with r2_c2:
                            st.markdown("**⚧️ Gender**")
                            gender_opts = ["Male", "Female", "Other"]
                            gender = st.selectbox(
                                "", options=gender_opts,
                                index=gender_opts.index(json_data.get("gender", "Male")),
                                key="gender_sel"
                            )
                        with r2_c3:
                            st.markdown("**🎂 DOB**")
                            dob = st.text_input(
                                "", value=json_data.get("date_of_birth", ""),
                                key="dob"
                            )
                        
                        # Address
                        st.markdown("**🏠 Address Information**")
                        addr_col1, addr_col2, addr_col3, addr_col4 = st.columns([2.2, 1, 1, 0.8])
                        
                        address = st.text_area(
                            "Full Address", 
                            value=json_data.get("address", ""),
                            height=55, key="address_full"
                        )
                        
                        with addr_col2:
                            city = st.text_input("City", value=json_data.get("city", ""), key="city")
                        with addr_col3:
                            state = st.text_input("State", value=json_data.get("state", ""), key="state")
                        with addr_col4:
                            pincode = st.text_input("Pin", value=json_data.get("pincode", ""), key="pin")
                        
                        # Additional
                        st.markdown("**📋 Other Details**")
                        add_c1, add_c2 = st.columns(2)
                        with add_c1:
                            ero = st.text_input(
                                "Electoral Officer",
                                value=json_data.get("electoral_registration_officer", ""),
                                key="ero"
                            )
                        with add_c2:
                            issue_date = st.text_input(
                                "Issue Date", value=json_data.get("issue_date", ""),
                                key="issue"
                            )
                        
                        # Action Buttons
                        st.markdown("---")
                        btn_col1, btn_col2, btn_col3 = st.columns(3)
                        
                        with btn_col1:
                            if st.button("✅ **APPROVE & DOWNLOAD**", type="primary"):
                                final_data = {
                                    "election_number": election_num,
                                    "name": voter_name,
                                    "relation_name": relation,
                                    "gender": gender,
                                    "date_of_birth": dob,
                                    "address": address,
                                    "city": city,
                                    "state": state,
                                    "pincode": pincode,
                                    "electoral_registration_officer": ero,
                                    "issue_date": issue_date
                                }
                                
                                pdf_buf = create_pdf(final_data)
                                st.download_button(
                                    "📥 PDF Report",
                                    pdf_buf.getvalue(),
                                    "voter_id_report.pdf",
                                    "application/pdf"
                                )
                                
                                json_str = json.dumps(final_data, indent=2)
                                st.download_button(
                                    "💾 JSON Data",
                                    json_str,
                                    "voter_id_data.json",
                                    "application/json"
                                )
                                st.balloons()
                        
                        with btn_col2:
                            if st.button("🔄 Re-extract"):
                                st.rerun()
                        
                        with btn_col3:
                            if st.button("📋 Raw JSON"):
                                st.code(json.dumps(json_data, indent=2))
                                
                    except:
                        st.error("JSON Parse Error")
                        st.text_area("Raw:", raw_response)

# Main App Flow
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_screen()
    st.info("💡 **Demo:** admin / password123")
else:
    main_app()
