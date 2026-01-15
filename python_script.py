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
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Voter ID Extraction Report")
    
    # Content
    c.setFont("Helvetica", 12)
    y_position = height - 80
    
    for key, value in json_data.items():
        # Format key for display (e.g., "election_number" -> "Election Number")
        display_key = key.replace("_", " ").title()
        text = f"{display_key}: {value}"
        
        # specific handling for address to avoid cut-off
        if len(text) > 80:
             c.drawString(50, y_position, text[:80])
             y_position -= 20
             c.drawString(60, y_position, text[80:]) # Indent continuation
        else:
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
        
        # Initialize Client
        with open(tmp_cred_path, "r") as f:
            creds = json.load(f)
        
        project_id = creds.get("project_id") or creds.get("quota_project_id")
        
        # Initialize GenAI Client
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
        You are an expert OCR and document analysis specialist with deep knowledge of Indian electoral documents...
        (keeping your original prompt instructions here for brevity in logic)
        ...
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
        # Using a model suitable for vision tasks
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp", 
            contents=contents
        )
        
        # 5. Parse Response
        cleaned_text = clean_json_response(response.text)
        json_output = json.loads(cleaned_text)
        
        # Cleanup temp file
        os.unlink(tmp_cred_path)
        
        return json_output

    except Exception as e:
        return {"error": str(e)}

# --- Main Streamlit App ---

st.title("🆔 Voter ID Data Extractor")
st.markdown("Upload your Google Cloud Credentials and Voter ID images to extract structured data.")

# Sidebar for Credentials
with st.sidebar:
    st.header("🔑 Configuration")
    creds_file = st.file_uploader("Upload Service Account JSON", type=["json"], help="Your Google Cloud Service Account Key")

# Main Content Area
col1, col2 = st.columns()[1]

with col1:
    st.subheader("📤 Upload Images")
    uploaded_files = st.file_uploader("Upload Voter ID Images (Front/Back)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    
    if uploaded_files:
        st.success(f"{len(uploaded_files)} images uploaded.")
        # Optional: Preview images
        with st.expander("Preview Images"):
            for img in uploaded_files:
                st.image(img, caption=img.name, use_container_width=True)

if st.button("🚀 Extract Information", type="primary"):
    if not creds_file:
        st.error("Please upload your Google Cloud credentials JSON in the sidebar.")
    elif not uploaded_files:
        st.error("Please upload at least one Voter ID image.")
    else:
        with st.spinner("Processing images with Gemini AI..."):
            extracted_data = process_images(creds_file, uploaded_files)
            
            if "error" in extracted_data:
                st.error(f"An error occurred: {extracted_data['error']}")
            else:
                st.success("Extraction Complete!")
                
                # --- NEW: TABBED VIEW FOR FORM AND JSON ---
                tab_form, tab_json = st.tabs(["📝 Form View", "💻 JSON View"])
                
                # 1. Form View (Fields in boxes)
                with tab_form:
                    st.markdown("### Extracted Details")
                    
                    # Grouping fields for better layout
                    
                    # Row 1: Basic Identity
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.text_input("Election Number (EPIC)", value=extracted_data.get("election_number", ""), disabled=True)
                    with c2:
                        st.text_input("Full Name", value=extracted_data.get("name", ""), disabled=True)
                    with c3:
                        st.text_input("Gender", value=extracted_data.get("gender", ""), disabled=True)
                        
                    # Row 2: Personal Details
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Relation Name (Father/Husband)", value=extracted_data.get("relation_name", ""), disabled=True)
                    with c2:
                        st.text_input("Date of Birth", value=extracted_data.get("date_of_birth", ""), disabled=True)

                    # Row 3: Address (Full width)
                    st.text_area("Full Address", value=extracted_data.get("address", ""), disabled=True)
                    
                    # Row 4: Address Details
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.text_input("City", value=extracted_data.get("city", ""), disabled=True)
                    with c2:
                        st.text_input("State", value=extracted_data.get("state", ""), disabled=True)
                    with c3:
                        st.text_input("Pincode", value=extracted_data.get("pincode", ""), disabled=True)
                        
                    # Row 5: Official Details
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Issue Date", value=extracted_data.get("issue_date", ""), disabled=True)
                    with c2:
                        st.text_input("Registration Officer", value=extracted_data.get("electoral_registration_officer", ""), disabled=True)

                # 2. JSON View
                with tab_json:
                    st.markdown("### Raw JSON Output")
                    st.json(extracted_data)
                    
                    # Download JSON Button
                    json_str = json.dumps(extracted_data, indent=4)
                    st.download_button(
                        label="📥 Download JSON",
                        data=json_str,
                        file_name="voter_id_data.json",
                        mime="application/json"
                    )

                # PDF Download (Available outside tabs)
                st.markdown("---")
                pdf_buffer = create_pdf(extracted_data)
                st.download_button(
                    label="📄 Download Report as PDF",
                    data=pdf_buffer,
                    file_name="voter_id_report.pdf",
                    mime="application/pdf"
                )
