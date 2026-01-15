import streamlit as st
import json
import os
import tempfile
from io import BytesIO

# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Google Gemini imports
from google import genai
from google.genai import types

st.set_page_config(page_title="Voter ID Extractor", page_icon="🆔", layout="wide")

DUMMY_USER = "admin"
DUMMY_PASS = "password123"

def clean_json_response(text):
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    if text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return text.strip()

def create_pdf(json_data):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 60, "🆔 Voter ID Report")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 85, "Verified EPIC Details")
    
    y = height - 110
    fields = [
        ("Election Number", json_data.get("election_number", "")),
        ("Voter Name", json_data.get("name", "")),
        ("Relation", json_data.get("relation_name", "")),
        ("Gender", json_data.get("gender", "")),
        ("DOB", json_data.get("date_of_birth", "")),
        ("Address", json_data.get("address", "")),
        ("City", json_data.get("city", "")),
        ("State", json_data.get("state", "")),
        ("Pincode", json_data.get("pincode", "")),
        ("ERO", json_data.get("electoral_registration_officer", "")),
        ("Issue Date", json_data.get("issue_date", ""))
    ]
    
    for label, value in fields:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, f"{label}:")
        c.setFont("Helvetica", 10)
        text = str(value)[:70]
        c.drawString(160, y, text)
        y -= 22
        if y < 60:
            c.showPage()
            y = height - 60
    
    c.save()
    buffer.seek(0)
    return buffer

def process_images(credential_file, image_files):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(credential_file.getvalue())
            tmp_path = tmp.name
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = tmp_path
        
        with open(tmp_path, "r") as f:
            creds = json.load(f)
            project_id = creds.get("project_id", "gen-lang-client-0155506887")

        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        
        contents = []
        for img in image_files:
            img_part = types.Part.from_bytes(data=img.getvalue(), mime_type=img.type)
            contents.append(img_part)
        
        prompt = '''Extract voter ID info as JSON only:
        {"election_number":"","name":"","relation_name":"","gender":"","date_of_birth":"","address":"","city":"","state":"","pincode":"","electoral_registration_officer":"","issue_date":""}'''
        contents.append(prompt)
        
        config = types.GenerateContentConfig(temperature=0, max_output_tokens=2048)
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=contents, 
            config=config
        )
        
        os.unlink(tmp_path)
        return response.text
        
    except Exception as e:
        try: os.unlink(tmp_path)
        except: pass
        return None

def login_screen():
    st.title("🆔 Voter ID Extractor")
    st.markdown("**AI-powered Voter ID information extraction**")
    
    with st.form("login_form"):
        username = st.text_input("👤 Username")
        password = st.text_input("🔒 Password", type="password")
        if st.form_submit_button("🚀 Login", type="primary"):
            if username == DUMMY_USER and password == DUMMY_PASS:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ Invalid credentials!")

def main_app():
    st.title("🆔 Voter ID Extractor")
    
    # FIXED: Correct columns syntax
    col1, col2, col3 = st.columns()[1]
    with col2:
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
    
    st.markdown("---")
    
    col_a, col_b = st.columns()[2][1]
    with col_a:
        st.subheader("1. Credentials")
        cred_file = st.file_uploader("user-credential.json", type="json")
    with col_b:
        st.subheader("2. Images")
        images = st.file_uploader("Voter ID (1-2 images)", 
                                type=['jpg','jpeg','png'], 
                                accept_multiple_files=True)
    
    if st.button("🔍 EXTRACT INFO", type="primary"):
        if not cred_file or not images or len(images) > 2:
            st.warning("⚠️ Upload credentials + 1-2 images")
        else:
            with st.spinner("🤖 Processing..."):
                result = process_images(cred_file, images)
                if result:
                    cleaned = clean_json_response(result)
                    try:
                        data = json.loads(cleaned)
                        st.success("✅ Extracted!")
                        
                        # FORM DISPLAY
                        st.markdown("### 🔍 Verify Details")
                        
                        # Row 1
                        r1c1, r1c2 = st.columns([1.2, 1.8])
                        with r1c1: 
                            st.text_input("Election #", data.get("election_number", ""), key="en1")
                        with r1c2:
                            st.text_input("Name", data.get("name", ""), key="name1")
                        
                        # Row 2
                        r2c1, r2c2, r2c3 = st.columns([1.4, 0.9, 1.1])
                        with r2c1: 
                            st.text_input("Relation", data.get("relation_name", ""), key="rel1")
                        with r2c2:
                            st.selectbox("Gender", ["Male","Female"], key="gen1", index=0)
                        with r2c3:
                            st.text_input("DOB", data.get("date_of_birth", ""), key="dob1")
                        
                        # Address
                        st.text_area("Address", data.get("address", ""), height=60, key="addr1")
                        ac1, ac2, ac3 = st.columns(3)
                        with ac2: st.text_input("City", data.get("city", ""), key="city1")
                        with ac3: st.text_input("State", data.get("state", ""), key="state1")
                        
                        # Buttons
                        b1, b2 = st.columns(2)
                        with b1:
                            if st.button("✅ Download PDF"):
                                pdf = create_pdf(data)
                                st.download_button("PDF", pdf.getvalue(), "voter_report.pdf")
                        with b2:
                            if st.button("🔄 Retry"): st.rerun()
                            
                    except:
                        st.error("Parse error")
                        st.text(result)
                        

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_screen()
else:
    main_app()
