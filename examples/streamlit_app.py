"""Demo app for streamlit-jsme."""
import streamlit as st
from streamlit_jsme import st_jsme

st.set_page_config(page_title="streamlit-jsme demo", layout="wide")
st.title("streamlit-jsme demo")

EXAMPLES = {
    "(none)": "",
    "Aspirin":     "CC(=O)Oc1ccccc1C(=O)O",
    "Caffeine":    "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
    "Anastrozole": "CC(C)(C#N)c1cc(Cn2cncn2)cc(C(C)(C)C#N)c1",
}

def _on_example_change():
    st.session_state["mol_input"] = EXAMPLES[st.session_state["example_choice"]]

col_in, col_ex = st.columns([3, 1])
with col_ex:
    st.selectbox(
        "Load example:",
        list(EXAMPLES.keys()),
        key="example_choice",
        on_change=_on_example_change,
    )
with col_in:
    molecule = st.text_input(
        "SMILES",
        key="mol_input",
        placeholder="Paste a SMILES or pick an example…",
    )

col_fmt, col_h = st.columns([2, 2])
with col_fmt:
    fmt = st.radio(
        "Output format:",
        ["SMILES", "SMILES_NOISO", "MOL"],
        horizontal=True,
        captions=["Isomeric SMILES", "Non-isomeric SMILES", "MOL V2000"],
    )
with col_h:
    height = st.slider("Height (px)", min_value=240, max_value=600, value=420, step=20)

result = st_jsme(molecule, height=height, format=fmt, key="jsme_main")

if result:
    is_molfile = "M  END" in result
    if fmt == "MOL" and is_molfile:
        st.subheader("MOL file")
        st.code(result, language="text")
        st.download_button("Download .mol", result, file_name="molecule.mol",
                           mime="chemical/x-mdl-molfile")
    elif fmt != "MOL" and not is_molfile:
        st.success(f"SMILES: `{result}`")
