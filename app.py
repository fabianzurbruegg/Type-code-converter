import streamlit as st
import re
import pandas as pd
import json
import os
from datetime import datetime

# ==========================================
# 1. LOAD JSON CONFIGURATION & HISTORY
# ==========================================
CONFIG_FILE = "mapping_config.json"

def load_mapping_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "HISTORY_LOG" not in data:
                data["HISTORY_LOG"] = []
            data["HISTORY_LOG"] = sorted(
                data["HISTORY_LOG"], 
                key=lambda x: x.get("Timestamp", ""), 
                reverse=True
            )
            return data
    return None

MAPPING_DATA = load_mapping_config()

def save_final_mapping(old_prefix, new_code, details, author_initials):
    if not MAPPING_DATA:
        return False, "Configuration file missing!"
    
    if old_prefix not in MAPPING_DATA["PREFIX_MAP"]:
        MAPPING_DATA["PREFIX_MAP"][old_prefix] = {}
        
    if isinstance(MAPPING_DATA["PREFIX_MAP"][old_prefix], str):
        MAPPING_DATA["PREFIX_MAP"][old_prefix] = {"new_code": new_code, "breakdown": [details]}
    else:
        MAPPING_DATA["PREFIX_MAP"][old_prefix]["new_code"] = new_code
        MAPPING_DATA["PREFIX_MAP"][old_prefix]["breakdown"] = [details]
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history_entry = {
        "Timestamp": timestamp,
        "Author": author_initials.upper(),
        "Old Prefix": old_prefix,
        "New Base Code": new_code,
        **details
    }
    
    if "HISTORY_LOG" not in MAPPING_DATA:
        MAPPING_DATA["HISTORY_LOG"] = []
    
    MAPPING_DATA["HISTORY_LOG"].insert(0, history_entry)
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(MAPPING_DATA, f, indent=4, ensure_ascii=False)
        
    return True, f"Prefix '{old_prefix}' successfully saved and logged!"

# ==========================================
# 2. CORE LOGIC (PARSER)
# ==========================================
def parse_and_convert_typekey(alt_key: str) -> dict:
    if not alt_key or not alt_key.strip():
        return {"new": "", "specs_old": [], "ds_old": [], "specs_new": [], "ds_new": [], "error": False, "ng_size": ""}

    if not MAPPING_DATA:
        return {"new": "ERROR: mapping_config.json is missing!", "specs_old": [], "ds_old": [], "specs_new": [], "ds_new": [], "error": True, "ng_size": ""}

    # Originalen String behalten (damit Kleinbuchstaben wie 'a' oder 'b' erhalten bleiben)
    original_cleaned = alt_key.strip().replace(" ", "").replace("\t", "")
    original_cleaned = re.sub(r'-A-', 'A', original_cleaned, flags=re.IGNORECASE)
    original_cleaned = re.sub(r'-B-', 'B', original_cleaned, flags=re.IGNORECASE)

    # Für die rein technische Suche nutzen wir eine Grossbuchstaben-Kopie
    search_raw = original_cleaned.upper()

    new_prefix_base = None
    found_old_prefix = None
    prefix_config = {}
    
    prefix_map = MAPPING_DATA.get("PREFIX_MAP", {})
    sorted_prefixes = sorted(prefix_map.keys(), key=lambda item: len(item), reverse=True)
    
    normalized_search = search_raw.replace(".", "_")
    
    # Vorab-Check, ob es NG10 oder NG6 ist, falls nur das Basispräfix (z.B. AM4) eingegeben wurde
    is_ng10_input = "10" in normalized_search or "100" in normalized_search
    is_ng6_input = ".6" in normalized_search or "_6" in normalized_search or "60" in normalized_search or "61" in normalized_search or "62" in normalized_search or "63" in normalized_search or "64" in normalized_search or "65" in normalized_search
    
    for json_key in sorted_prefixes:
        base_prefix = json_key.split('_')[0].upper()
        json_normalized = json_key.replace(".", "_").split('_')[0].upper()
        
        # Gezielte Zuordnung bei NG10 und NG6
        if is_ng10_input and ("10" not in json_key and "_10" not in json_key):
            continue
        if is_ng6_input and ("6" not in json_key and "_6" not in json_key and ".6" not in json_key):
            continue
            
        if normalized_search.startswith(json_normalized) or search_raw.startswith(base_prefix):
            found_old_prefix = json_key
            p_data = prefix_map[json_key]
            if isinstance(p_data, dict):
                new_prefix_base = p_data.get("new_code")
                prefix_config = p_data
            else:
                new_prefix_base = p_data
            
            matched_len = len(json_normalized) if normalized_search.startswith(json_normalized) else len(base_prefix)
            search_raw = search_raw[matched_len:]
            if search_raw.startswith('.'):
                search_raw = search_raw[1:]
            break

    # Fallback, falls der gezielte Filter zu streng war
    if not new_prefix_base:
        for json_key in sorted_prefixes:
            base_prefix = json_key.split('_')[0].upper()
            if search_raw.startswith(base_prefix) or search_raw.startswith(json_key.split('.')[0].upper()):
                found_old_prefix = json_key
                p_data = prefix_map[json_key]
                if isinstance(p_data, dict):
                    new_prefix_base = p_data.get("new_code")
                    prefix_config = p_data
                else:
                    new_prefix_base = p_data
                search_raw = search_raw.replace(base_prefix, "", 1)
                break

    if not new_prefix_base:
        return {"new": f"ERROR: Prefix for '{original_cleaned}' not defined in JSON.", "specs_old": [], "ds_old": [], "specs_new": [], "ds_new": [], "error": True, "ng_size": ""}

    # --- INTELLIGENTE KOLBEN-ERKENNUNG (Beibehaltung des originalen 'a'/'b') ---
    found_spool_new = None
    found_spool_old = None
    
    all_new_spools = set(MAPPING_DATA.get("SPOOL_MAP", {}).values())
    for new_spool in sorted(all_new_spools, key=lambda item: len(item), reverse=True):
        if new_spool.upper() in search_raw:
            found_spool_new = new_spool
            found_spool_old = new_spool
            search_raw = search_raw.replace(new_spool.upper(), "", 1)
            break
            
    if not found_spool_new:
        # Hier prüfen wir gegen den Uppercase-Suchstring, holen uns aber den exakten Original-Substrings aus original_cleaned oder mappen sauber
        for old_spool, new_spool in sorted(MAPPING_DATA.get("SPOOL_MAP", {}).items(), key=lambda item: len(item[0]), reverse=True):
            if old_spool.upper() in search_raw:
                found_spool_new = new_spool
                # Wir suchen die Position und extrahieren das Original inklusive Kleinbuchstaben
                idx = search_raw.find(old_spool.upper())
                if idx != -1:
                    found_spool_old = original_cleaned[len(original_cleaned) - len(search_raw) + idx : len(original_cleaned) - len(search_raw) + idx + len(old_spool)]
                else:
                    found_spool_old = old_spool
                search_raw = search_raw.replace(old_spool.upper(), "", 1)
                break
            
    if not found_spool_new:
        return {"new": "ERROR: Spool symbol not found in JSON.", "specs_old": [], "ds_old": [], "specs_new": [], "ds_new": [], "error": True, "ng_size": ""}

    # --- PRÄZISE NENNGRÖSSEN-ERMITTELUNG ---
    ng_size = "4"
    ng_match = re.search(r'NG\s*(\d+)', original_cleaned, re.IGNORECASE)
    if ng_match:
        ng_size = ng_match.group(1)
    elif found_spool_old:
        spool_digits_match = re.search(r'(\d+)', found_spool_old)
        if spool_digits_match:
            digits_str = spool_digits_match.group(1)
            if digits_str.startswith("10"):
                ng_size = "10"
            elif digits_str.startswith("6"):
                ng_size = "6"
            elif digits_str.startswith("4"):
                ng_size = "4"
            elif digits_str.startswith("3"):
                ng_size = "3"
    elif found_old_prefix:
        if "10" in found_old_prefix or "_10" in found_old_prefix:
            ng_size = "10"
        elif "6" in found_old_prefix or "_6" in found_old_prefix or ".6" in found_old_prefix:
            ng_size = "6"
            
    if new_prefix_base.endswith("06") or new_prefix_base.endswith("10") or (found_old_prefix and any(sub in found_old_prefix for sub in ["04", "06", "10", "1.2.51", "_6", "_10"])):
        final_prefix = new_prefix_base
    else:
        ng_padded = f"0{ng_size}" if len(ng_size) == 1 else ng_size
        final_prefix = f"{new_prefix_base}{ng_padded}"

    found_volt_new = "VOLTAGE_MISSING"
    for old_volt, new_volt in MAPPING_DATA.get("VOLTAGE_MAP", {}).items():
        if old_volt.upper() in search_raw:
            found_volt_new = new_volt
            search_raw = search_raw.replace(old_volt.upper(), "", 1)
            break

    json_coil_type = prefix_config.get("coil_connector_type", "WD")
    json_coil_option = prefix_config.get("coil_connector_option", "")
    allowed_overrides = prefix_config.get("allowed_manual_overrides", [])
    
    connector = json_coil_type

    manual_override_code = ""
    manual_map = MAPPING_DATA.get("MANUAL_OVERRIDE_MAP", {})
    sorted_manuals = sorted(manual_map.keys(), key=lambda x: len(str(x)), reverse=True)
    
    for old_h in sorted_manuals:
        new_h = manual_map[old_h]
        if old_h and old_h.upper() in search_raw:
            if not allowed_overrides or new_h.replace("-", "") in [a.replace("-", "") for a in allowed_overrides]:
                manual_override_code = new_h.replace("-", "")
                search_raw = search_raw.replace(old_h.upper(), "", 1)
                break

    sealing = ""
    for old_s, new_s in MAPPING_DATA.get("SEALINGS", {}).items():
        if old_s and old_s.upper() in search_raw:
            sealing = new_s.replace("-", "").replace("/", "")
            search_raw = search_raw.replace(old_s.upper(), "", 1)
            break

    sz_num = ""
    for old_sz, new_sz in MAPPING_DATA.get("S/Z-NUMBERS", {}).items():
        if old_sz and old_sz.upper() in search_raw:
            sz_num = new_sz.replace("-", "")
            break
 
    new_key = f"{final_prefix}-{found_spool_new}-{found_volt_new}"
    if connector:
        new_key += f"/{connector}"
    if sealing:
        new_key += f"-{sealing}"
    if sz_num:
        new_key += f"-{sz_num}"
    if manual_override_code:
        new_key += f"-{manual_override_code}"

    breakdown = list(prefix_config.get("breakdown", []))
    coil_ref = prefix_config.get("coil_ref")
    if coil_ref and "COIL_POOL" in MAPPING_DATA:
        coil_obj = MAPPING_DATA["COIL_POOL"].get(coil_ref)
        if coil_obj and coil_obj not in breakdown:
            breakdown.append(coil_obj)
    
    specs_old = [
        {"Property": "Nominal Size", "Value": f"NG{ng_size}"},
        {"Property": "Spool Symbol", "Value": found_spool_old},
        {"Property": "Voltage / Actuation", "Value": found_volt_new}
    ]

    specs_new = [
        {"Property": "Replacement Type Code", "Value": new_key},
        {"Property": "Nominal Size", "Value": f"NG{ng_size}"},
        {"Property": "New Spool Symbol", "Value": found_spool_new},
        {"Property": "Voltage & Connections", "Value": f"{found_volt_new}/{connector}"}
    ]

    ds_old = []
    ds_new = []
    seen_old = set()
    seen_new = set()
    
    for item in breakdown:
        desc_text = item.get("desc", "").upper()
        if ng_size in ["6", "10"] and "NG4" in desc_text:
            continue
        if ng_size == "4" and ("NG6" in desc_text or "NG10" in desc_text):
            continue
            
        old_doc = item.get("old_ds") or item.get("old_coil")
        new_doc = item.get("new_ds") or item.get("new_coil")
        
        if old_doc and old_doc not in seen_old:
            ds_old.append({
                "Document": old_doc,
                "Description": f"Datasheet/Component for {item.get('component')} (Old)",
                "Link": item.get("old_ds_link", "")
            })
            seen_old.add(old_doc)
            
        if new_doc and new_doc not in seen_new:
            ds_new.append({
                "Document": new_doc,
                "Description": f"Datasheet/Component for {item.get('component')} (New)",
                "Link": item.get("new_ds_link", "")
            })
            seen_new.add(new_doc)

    return {
        "new": new_key, 
        "specs_old": specs_old, 
        "ds_old": ds_old, 
        "specs_new": specs_new, 
        "ds_new": ds_new, 
        "error": False, 
        "ng_size": ng_size,
        "old_prefix": found_old_prefix,
        "new_base": new_prefix_base,
        "spool_old": found_spool_old,
        "spool_new": found_spool_new,
        "voltage": found_volt_new,
        "connector": connector,
        "json_coil_option": json_coil_option,
        "manual_override": manual_override_code
    }

# ==========================================
# 3. STREAMLIT USER INTERFACE
# ==========================================
st.set_page_config(page_title="Wandfluh Replacement Valve Finder", page_icon="🔄", layout="centered")

st.markdown("""
<style>
.component-card {
    background-color: #f8f9fa;
    border: 1px solid #e9ecef;
    padding: 14px;
    border-radius: 8px;
    margin-bottom: 12px;
}
.component-title {
    font-weight: 600;
    font-size: 15px;
    color: #333333;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)

if os.path.exists("logo.png"):
    st.image("logo.png", width=300)

st.title("Replacement Valve Finder")

# Hinzugefügter Prototyp-Hinweis
st.markdown("""
<div style='background-color: #f1f3f4; border-left: 4px solid #5f6368; padding: 10px 14px; border-radius: 4px; margin-bottom: 20px; font-size: 14px; color: #3c4043;'>
    <b>Prototyp:</b> Funktioniert erst für 1.2 Schieberventile, Standardtypen NG4-Mini, NG4, NG6 und NG10. Nichts konfigurierbar, was nicht auf dem Datenblatt aufgeführt ist, keine S, Z Nummern, keine Sonderspulen. — <b>ZUF</b>
</div>
""", unsafe_allow_html=True)

if not MAPPING_DATA:
    st.error("⚠: mapping_config.json not found. Tool is out of order.")

tab1, tab2, tab3 = st.tabs(["Single Query", "Batch Conversion", "Add a New Valve"])

with tab1:
    st.subheader("Valve Analysis & Datasheet Finder")
    single_input = st.text_input("Enter the old type code below:", placeholder="e.g., BE4D41-G24")
    
    if single_input:
        result = parse_and_convert_typekey(single_input)
        if result["error"]:
            st.error(result["new"])
        else:
            st.success("✅ Analysis completed successfully!")
            
            st.markdown("---")
            st.markdown(f"### 📂 1. Old Valve (`{single_input.strip()}`)")
            df_old_specs = pd.DataFrame(result["specs_old"])
            st.dataframe(df_old_specs, hide_index=True, use_container_width=True)
            
            df_old_ds = pd.DataFrame(result["ds_old"])
            if not df_old_ds.empty:
                st.dataframe(df_old_ds, column_config={"Link": st.column_config.LinkColumn("PDF Link", display_text="📥 Open Old Datasheet")}, hide_index=True, use_container_width=True)

            st.markdown("---")
            st.markdown("### 2. Replacement Type Suggestion")
            st.markdown(f"<div style='font-size: 24px; font-weight: bold; font-family: monospace; background-color: #e6f4ea; padding: 12px; border-radius: 5px; color: #137333; border: 1px solid #ceead6;'>{result['new']}</div>", unsafe_allow_html=True)
            
            st.markdown("""
            <div style='background-color: #fef3c7; border: 1px solid #f59e0b; padding: 16px; border-radius: 8px; margin-top: 10px; margin-bottom: 15px; color: #92400e;'>
                <b>⚠️ Warning - Replacement Type:</b><br><br>
                Please note the changed hydraulic performance data and valve dimensions. Check the valve for suitability in your application.
            </div>
            """, unsafe_allow_html=True)
            
            if result.get("json_coil_option"):
                alt_key_with_option = result['new'].replace(f"/{result['connector']}", f"/{result['json_coil_option']}")
                st.info(f"💡 **Alternative option - on request only - :** `{alt_key_with_option}` (Coil option `{result['json_coil_option']}`)")

            st.markdown("---")
            df_new_specs = pd.DataFrame(result["specs_new"])
            st.dataframe(df_new_specs, hide_index=True, use_container_width=True)
            
            df_new_ds = pd.DataFrame(result["ds_new"])
            if not df_new_ds.empty:
                st.dataframe(df_new_ds, column_config={"Link": st.column_config.LinkColumn("PDF Link", display_text="📥 Open New Datasheet")}, hide_index=True, use_container_width=True)

with tab2:
    st.subheader("Convert Multiple Type Codes")
    batch_input = st.text_area("Enter multiple old type codes (one per line):", height=200, placeholder="BE4D41-G24\nAM4D62-G24")
    
    if st.button("Convert"):
        if batch_input:
            lines = batch_input.split('\n')
            results = []
            for line in lines:
                if line.strip():
                    res = parse_and_convert_typekey(line)
                    results.append({"Old": line.strip(), "New": res["new"], "Status": "Error" if res["error"] else "OK"})
            
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False, sep=';').encode('utf-8')
            st.download_button(label="📥 Download as CSV", data=csv, file_name='conversion_results.csv', mime='text/csv')

with tab3:
    st.subheader("Add a New Valve")
    st.markdown("Gib einen unbekannten alten Typ ein. Das Tool schlägt dir die passenden Bausteine in übersichtlichen Kacheln vor.")
    
    if "smart_input_key" not in st.session_state:
        st.session_state.smart_input_key = ""

    with st.form("smart_lookup_form"):
        sample_old_input = st.text_input("Alter Typ (Eingabe zur automatischen Erkennung):", placeholder="z.B. AM4Z60a-G12")
        lookup_btn = st.form_submit_button("Typ analysieren & Vorschläge generieren")
        
        if lookup_btn and sample_old_input:
            st.session_state.smart_input_key = sample_old_input.strip().upper()
            st.session_state.parsed_preview = parse_and_convert_typekey(st.session_state.smart_input_key)

    if "parsed_preview" in st.session_state and not st.session_state.parsed_preview.get("error", True):
        res = st.session_state.parsed_preview
        st.markdown("---")
        st.markdown("### 📋 Strukturierter Komponenten-Abgleich (Kacheln)")
        
        with st.form("smart_save_form"):
            edit_author = st.text_input("Deine Initials / Kürzel (z.B. FZ):", placeholder="FZ")
            st.markdown("---")
            
            st.markdown("<div class='component-card'><div class='component-title'>Ventil / Grundtyp</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                edit_old_prefix = st.text_input("Alt", value=res.get("old_prefix", ""))
            with c2:
                edit_new_base = st.text_input("Neu", value=res.get("new_base", "WDMFA"))
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='component-card'><div class='component-title'>Kolben / Spool Symbol</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                edit_old_spool = st.text_input("Alt ", value=res.get("spool_old", ""))
            with c2:
                edit_new_spool = st.text_input("Neu ", value=res.get("spool_new", "AB1"))
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='component-card'><div class='component-title'>Spannung</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                edit_volt = st.text_input("Alt  ", value=res.get("voltage", ""))
            with c2:
                edit_volt_new = st.text_input("Neu  ", value=res.get("voltage", ""))
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='component-card'><div class='component-title'>Spulenausführung (ohne '/')</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                edit_coil_old = st.text_input("Alt   ", value="—")
            with c2:
                edit_coil_new = st.text_input("Neu   ", value=res.get("connector", "VD"))
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='component-card'><div class='component-title'>Option (ohne '/')</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                edit_opt_old = st.text_input("Alt    ", value="—")
            with c2:
                edit_opt_new = st.text_input("Neu    ", value=res.get("json_coil_option", "ND"))
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='component-card'><div class='component-title'>Handnotbetätigung (ohne '-')</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                edit_h_old = st.text_input("Alt     ", value="H1")
            with c2:
                edit_h_new = st.text_input("Neu     ", value=res.get("manual_override", "HF1"))
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("---")
            ds_c1, ds_c2 = st.columns(2)
            with ds_c1:
                edit_old_ds = st.text_input("Datenblatt Alt (Referenz):", value="1.2-31E")
            with ds_c2:
                edit_new_ds = st.text_input("Datenblatt Neu (Referenz):", value="1.2-33E")
            
            save_btn = st.form_submit_button("Bestätigen & In Konfiguration speichern")
            if save_btn:
                if not edit_author.strip():
                    st.warning("Bitte gib dein Kürzel ein.")
                else:
                    coil_formatted = f"/{edit_coil_new.strip()}" if edit_coil_new.strip() and not edit_coil_new.strip().startswith("/") else edit_coil_new.strip()
                    opt_formatted = f"/{edit_opt_new.strip()}" if edit_opt_new.strip() and not edit_opt_new.strip().startswith("/") else edit_opt_new.strip()
                    h_formatted = f"-{edit_h_new.strip()}" if edit_h_new.strip() and not edit_h_new.strip().startswith("-") else edit_h_new.strip()

                    details = {
                        "Old Prefix": edit_old_prefix,
                        "New Base Code": edit_new_base,
                        "NG Size": res.get("ng_size", "4"),
                        "Valve Alt": edit_old_prefix,
                        "Valve Neu": edit_new_base,
                        "Kolben Alt": edit_old_spool,
                        "Kolben Neu": edit_new_spool,
                        "Spannung": edit_volt,
                        "Spulenausführung": coil_formatted,
                        "Option": opt_formatted,
                        "Handnotbetätigung Alt": edit_h_old,
                        "Handnotbetätigung Neu": h_formatted,
                        "Old Datasheet": edit_old_ds,
                        "New Datasheet": edit_new_ds
                    }
                    
                    final_built_code = f"{edit_new_base.strip()}{res.get('ng_size','4')}-{edit_new_spool.strip()}-{edit_volt.strip()}{coil_formatted}{h_formatted}"
                    
                    success, msg = save_final_mapping(
                        edit_old_prefix.strip().upper(),
                        edit_new_base.strip().upper(),
                        details,
                        edit_author.strip()
                    )
                    if success:
                        st.success(f"{msg} (Generated Code: {final_built_code})")
                        st.info("Erfolgreich gespeichert! Bitte starte Streamlit neu.")
                        del st.session_state.parsed_preview
                        MAPPING_DATA.update(load_mapping_config())
                    else:
                        st.error(msg)

    st.markdown("---")
    st.subheader("📜 Recent Mapping Change History (Audit Log)")
    history_log = MAPPING_DATA.get("HISTORY_LOG", [])
    if history_log:
        df_history = pd.DataFrame(history_log)
        if "Timestamp" in df_history.columns:
            df_history = df_history.sort_values(by="Timestamp", ascending=False)
        st.dataframe(df_history, hide_index=True, use_container_width=True)
    else:
        st.info("No custom mappings recorded yet.")