import streamlit as st

def display_voter_form(data):
    """
    Displays the extracted JSON data in a professional form layout 
    matching the structure of a physical document.
    """
    st.markdown("## 📋 Voter Details Form")
    
    # --- Section 1: Identity Information ---
    with st.container(border=True):
        st.markdown("### 👤 Identity Details")
        
        # Row 1: EPIC Number & Date of Birth
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Election/EPIC Number", value=data.get("election_number", ""), disabled=True)
        with c2:
            st.text_input("Date of Birth", value=data.get("date_of_birth", ""), disabled=True)

        # Row 2: Full Name & Gender
        c3, c4 = st.columns([2, 1])
        with c3:
            st.text_input("Full Name", value=data.get("name", ""), disabled=True)
        with c4:
            st.text_input("Gender", value=data.get("gender", ""), disabled=True)
            
        # Row 3: Relation (Father/Husband/etc)
        st.text_input("Relation Name (Father/Husband/Wife)", value=data.get("relation_name", ""), disabled=True)

    # --- Section 2: Address Information ---
    with st.container(border=True):
        st.markdown("### 📍 Address Details")
        
        # Full Address Block
        st.text_area("Full Address", value=data.get("address", ""), height=100, disabled=True)
        
        # Row 4: City, State, Pincode
        c5, c6, c7 = st.columns(3)
        with c5:
            st.text_input("City", value=data.get("city", ""), disabled=True)
        with c6:
            st.text_input("State", value=data.get("state", ""), disabled=True)
        with c7:
            st.text_input("Pincode", value=data.get("pincode", ""), disabled=True)

    # --- Section 3: Official Information ---
    with st.container(border=True):
        st.markdown("### 🏛️ Official Use")
        
        c8, c9 = st.columns([2, 1])
        with c8:
            st.text_input("Electoral Registration Officer", value=data.get("electoral_registration_officer", ""), disabled=True)
        with c9:
            st.text_input("Issue Date", value=data.get("issue_date", ""), disabled=True)

# --- Usage in your Main Loop ---
# Assuming 'extracted_data' is the dictionary returned from Gemini:
# extracted_data = json.loads(cleaned_text)
# display_voter_form(extracted_data)
