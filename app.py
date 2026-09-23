import streamlit as st
import re
import pandas as pd
import json
import os

# ==========================================
# 1. LOAD JSON CONFIGURATION
# ==========================================
@st.cache_data
def load_mapping_config():
    file_path = "mapping_config.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

MAPPING_DATA = load_mapping_config()

# ==========================================
# 2. CORE LOGIC (100% JSON-based with Dynamic Connectors)
# ==========================================
def parse_and_convert_typekey(alt_key: str) -> dict:
    if not alt_key or not alt_key.strip():
        return {"new": "", "info": "", "error": False, "ng_size": ""}

    if not MAPPING_DATA:
        return {"new": "ERROR: mapping_config.json is missing!", "info": "", "error": True, "ng_size": ""}

    cleaned = alt_key.strip().replace(" ", "").replace("\t", "")
    raw = cleaned.upper()
    
    # General typo correction
    raw = re.sub(r'-A-', 'A', raw)
    raw = re.sub(r'-B-', 'B', raw)

    search_raw = raw 

    # 1. Find base prefix dynamically & speichere altes Präfix
    new_prefix_base = None
    found_old_prefix = None
    for old_pref, new_pref in sorted(MAPPING_DATA.get("PREFIX_MAP", {}).items(), key=lambda item: len(item[0]), reverse=True):
        if search_raw.startswith(old_pref.upper()):
            new_prefix_base = new_pref
            found_old_prefix = old_pref.upper()
            search_raw = search_raw.replace(old_pref.upper(), "", 1)
            break

    if not new_prefix_base:
        return {"new": f"ERROR: Prefix for '{raw}' not defined in JSON.", "info": "", "error": True, "ng_size": ""}

    # 2. Find spool symbol
    found_spool_new = None
    found_spool_old = None
    for old_spool, new_spool in sorted(MAPPING_DATA.get("SPOOL_MAP", {}).items(), key=lambda item: len(item[0]), reverse=True):
        if old_spool.upper() in search_raw:
            found_spool_new = new_spool
            found_spool_old = old_spool.upper()
            search_raw = search_raw.replace(found_spool_old, "", 1)
            break
            
    if not found_spool_new:
        return {"new": "ERROR: Spool symbol not found in JSON.", "info": "", "error": True, "ng_size": ""}

    # --- DYNAMIC NOMINAL SIZE (NG) CALCULATION ---
    ng_size = "UNKNOWN"
    ng_padded = ""
    
    match = re.search(r'\d+', found_spool_old)
    if match:
        num_str = match.group(0)
        if len(num_str) >= 3:
            ng_size = num_str[:2]
        elif len(num_str) == 2:
            ng_size = num_str[0]
        else:
            ng_size = num_str
            
        ng_padded = f"0{ng_size}" if len(ng_size) == 1 else ng_size

    final_prefix = f"{new_prefix_base}{ng_padded}"

    # 3. Find voltage
    found_volt_new = "VOLTAGE_MISSING"
    for old_volt, new_volt in MAPPING_DATA.get("VOLTAGE_MAP", {}).items():
        if old_volt.upper() in search_raw:
            found_volt_new = new_volt
            search_raw = search_raw.replace(old_volt.upper(), "", 1)
            break
            
    # 4. Extract options dynamically
    default_connector = MAPPING_DATA.get("DEFAULT_CONNECTOR_MAP", {}).get(found_old_prefix, "/WD")
    
    if found_volt_new == "R24":
        if ng_size == "4":
            default_connector = "/ND"
        elif ng_size in ["6", "10"]:
            default_connector = "/MD"
    elif found_volt_new in ["R115", "R230"]:
        if ng_size == "4":
            default_connector = "/VD or ND"
        elif ng_size in ["6", "10"]:
            default_connector = "/WD (option MD)"

    connector = default_connector
    
    for old_c, new_c in MAPPING_DATA.get("COIL_CONNECTOR", {}).items():
        if old_c and not old_c.startswith("_") and old_c.upper() in search_raw:
            connector = f"-{new_c}" if not new_c.startswith('-') else new_c
            search_raw = search_raw.replace(old_c.upper(), "", 1)
            break

    sealing = ""
    for old_s, new_s in MAPPING_DATA.get("SEALINGS", {}).items():
        if old_s and old_s.upper() in search_raw:
            sealing = f"-{new_s}" if not new_s.startswith('-') else new_s
            search_raw = search_raw.replace(old_s.upper(), "", 1)
            break

    sz_num = ""
    for old_sz, new_sz in MAPPING_DATA.get("S/Z-NUMBERS", {}).items():
        if old_sz and old_sz.upper() in search_raw:
            sz_num = f"-{new_sz}" if not new_sz.startswith('-') else new_sz
            break

    # 5. Hard validation rules
    if "R110" in raw:
        return {"new": "ERROR: Voltage R110 is no longer available!", "info": "", "error": True, "ng_size": ""}

    # Build target string
    new_key = f"{final_prefix}-{found_spool_new}-{found_volt_new}{connector}{sealing}{sz_num}"
    
    # Specifications info text
    info_text = (
        f"**Product Category:** 1.2 Solenoid operated spool valves\n\n"
        f"**General Specifications:** NG{ng_size} Nominal Size"
    )
    
    return {"new": new_key, "info": info_text, "error": False, "ng_size": ng_size}

# ==========================================
# 3. HELPER: DYNAMIC DATASHEET TABLE
# ==========================================
def render_datasheet_table(ng_size):
    st.markdown(f"### 📄 Technical Datasheets (NG{ng_size})")
    
    if str(ng_size) == "4":
        st.markdown("""
| Series / Version | Datasheet No. | Direct Link |
| :--- | :--- | :--- |
| **Old Series (NG4)** | 1.2-31E | [Open Old Datasheet (PDF)](https://www.wandfluh.com/fileadmin/user_upload/Wandfluh/Products/Components/DataSheets/Englisch/1.2%20Solenoid%20operated%20spool%20valves%20direct%20operated/1_2_31_e.pdf) |
| **New Series (NG4)** | 1.2-33E | [Open New Datasheet (PDF)](https://www.wandfluh.com/fileadmin/user_upload/Wandfluh/Products/Components/DataSheets/Englisch/1.2%20Solenoid%20operated%20spool%20valves%20direct%20operated/1_2_33_e.pdf) |
        """)
    elif str(ng_size) == "6":
        st.markdown("""
| Series / Version | Datasheet No. | Direct Link |
| :--- | :--- | :--- |
| **Old Series (NG6)** | 1.2-57E | [Open Old Datasheet (PDF)](https://www.wandfluh.com/fileadmin/user_upload/Wandfluh/Products/Components/DataSheets/Englisch/1.2%20Solenoid%20operated%20spool%20valves%20direct%20operated/1_2_57_e.pdf) |
| **New Series (NG6)** | 1.2-59E | [Open New Datasheet (PDF)](https://www.wandfluh.com/fileadmin/user_upload/Wandfluh/Products/Components/DataSheets/Englisch/1.2%20Solenoid%20operated%20spool%20valves%20direct%20operated/1_2_59_e.pdf) |
        """)
    else:
        # Fallback für NG10 (oder unbekannte)
        st.markdown("""
| Series / Version | Datasheet No. | Direct Link |
| :--- | :--- | :--- |
| **Old Series (NG10)** | 1.2-71D | [Open Old Datasheet (PDF)](https://www.wandfluh.com/fileadmin/user_upload/Wandfluh/Products/Components/DataSheets/Englisch/1.2%20Solenoid%20operated%20spool%20valves%20direct%20operated/1_2_71_e.pdf) |
| **New Series (NG10)** | 1.2-76D | [Open New Datasheet (PDF)](https://www.wandfluh.com/fileadmin/user_upload/Wandfluh/Products/Components/DataSheets/Englisch/1.2%20Solenoid%20operated%20spool%20valves%20direct%20operated/1_2_76_e.pdf) |
        """)

# ==========================================
# 4. STREAMLIT USER INTERFACE
# ==========================================
st.set_page_config(page_title="Type Code Converter", page_icon="🔄", layout="centered")



st.image("logo.png", width=300)

st.title("Type Code Converter")
if not MAPPING_DATA:
    st.error("⚠️: mapping_config.json not found. Tool is out of order.")

tab1, tab2 = st.tabs(["Single Query", "Batch Conversion"])

with tab1:
    st.subheader("Looking for a replacement type code?")
    
    st.markdown("""
        <style>
        input[aria-label="Enter the old type code:"] {
            font-size: 20px !important;
            font-family: monospace !important;
            font-weight: bold !important;
            padding: 10px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    single_input = st.text_input("Enter the old type code below - good luck :-)", placeholder="e.g., AM4J60-G24")
    
    if single_input:
        result = parse_and_convert_typekey(single_input)
        if result["error"]:
            st.error(result["new"])
        else:
            st.success("✅ Successfully converted!")
            
            st.markdown("### Replacement Type")
            st.markdown(
                f"<div style='font-size: 24px; font-weight: bold; font-family: monospace; background-color: #e6f4ea; padding: 12px; border-radius: 5px; color: #137333; border: 1px solid #ceead6;'>{result['new']}</div>", 
                unsafe_allow_html=True
            )
            
            st.markdown(
                """
                <div style="background-color: #fff3cd; color: #856404; padding: 16px; border-radius: 6px; border-left: 5px solid #ffeeba; font-family: sans-serif; margin-bottom: 15px;">
                    <span style="font-weight: bold; font-size: 16px;">⚠️ Warning - Replacement Type:</span><br><br>
                    Please note the changed hydraulic performance data and valve dimensions. Check the valve for suitability in your application.
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            if result["info"]:
                st.info(result["info"])
            
            # Dynamische Datenblatt-Tabelle basierend auf NG
            render_datasheet_table(result["ng_size"])

with tab2:
    st.subheader("Convert Multiple Type Codes")
    batch_input = st.text_area("Enter multiple old type codes (one per line):", height=200, 
                               placeholder="BE4D41-G24\nAM4J100-G24")
    
    if st.button("Convert"):
        if batch_input:
            lines = batch_input.split('\n')
            results = []
            found_ngs = set()
            
            for line in lines:
                if line.strip():
                    res = parse_and_convert_typekey(line)
                    results.append({"Old": line.strip(), "New": res["new"], "Status": "Error" if res["error"] else "OK"})
                    if not res["error"] and res["ng_size"]:
                        found_ngs.add(res["ng_size"])
            
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            
            # Dynamische Datenblatt-Tabellen für alle in der Batch gefundenen Nenngrössen
            if found_ngs:
                st.markdown("---")
                for ng in sorted(list(found_ngs)):
                    render_datasheet_table(ng)
            
            csv = df.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name='conversion_results.csv',
                mime='text/csv',
            )