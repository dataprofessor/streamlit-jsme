"""
streamlit-jsme: JSME molecule editor as a Streamlit V2 custom component.

Usage
-----
    from streamlit_jsme import st_jsme

    smiles = st_jsme("CC(=O)Oc1ccccc1C(=O)O", key="editor")
    if smiles:
        st.write(smiles)
"""
from __future__ import annotations

import streamlit as st

__version__ = "0.1.2"
__all__ = ["st_jsme"]

# ── HTML: container div + button bar ──────────────────────────────────────
# jsme_wrapper is the stable outer div — JSME never touches it so it stays
# width:100% and the ResizeObserver always sees real column-width changes.
FORMATS = ("SMILES", "SMILES_NOISO", "MOL")

_HTML = """
<div id="jsme_wrapper" style="width:100%;"></div>
<div style="padding:5px 8px;
            background:var(--secondary-background-color);
            border-top:1px solid var(--secondary-background-color);
            display:flex;justify-content:flex-end;gap:6px;">
    <button id="jsme_clear_btn"
            style="padding:4px 14px;cursor:pointer;border:1px solid #ccc;
                   background:var(--background-color);color:var(--text-color);
                   border-radius:4px;font-size:12px;">Clear</button>
    <button id="jsme_apply_btn"
            style="padding:4px 14px;cursor:pointer;background:#0068ff;
                   color:#fff;border:none;border-radius:4px;font-size:12px;">Apply</button>
</div>
"""

# ── JavaScript ─────────────────────────────────────────────────────────────
_JS = """
export default function(component) {
    const { setStateValue, parentElement, data } = component;
    const molecule = (data && data.molecule) || '';

    function wireButtons() {
        const fmt      = (data && data.format) || 'SMILES';
        // When format changes, clear the stale result so old output disappears
        if (parentElement._lastFmt !== undefined && parentElement._lastFmt !== fmt) {
            setStateValue('result', '');
        }
        parentElement._lastFmt = fmt;
        const applyBtn = parentElement.querySelector('#jsme_apply_btn');
        const clearBtn = parentElement.querySelector('#jsme_clear_btn');
        const app = parentElement._jsmeApp;
        if (applyBtn) applyBtn.onclick = () => {
            if (!app) return;
            let out;
            if      (fmt === 'MOL')          out = app.molFile()           || '';
            else if (fmt === 'SMILES_NOISO') out = app.nonisomericSmiles() || '';
            else                             out = app.smiles()            || '';
            setStateValue('result', out);
        };
        if (clearBtn) clearBtn.onclick = () => {
            if (app) { app.reset(); parentElement._lastMol = ''; }
            setStateValue('result', '');
        };
    }

    if (parentElement._jsmeApp) {
        // Already initialised: update molecule only when prop changes
        if (molecule !== parentElement._lastMol) {
            parentElement._lastMol = molecule;
            parentElement._jsmeApp.readGenericMolecularInput(molecule);
        }
        wireButtons();
        return;
    }

    parentElement._lastMol = molecule;

    function buildJSME(wrapper, w) {
        const h = (data && data.height) || 420;
        const savedMol = (parentElement._jsmeApp && parentElement._jsmeApp.smiles())
                         || parentElement._lastMol || molecule;
        // Create a fresh inner div with a unique ID — JSME will lock this,
        // not the outer wrapper, so the wrapper stays responsive.
        wrapper.innerHTML = '';
        const uid = 'jsme_inner_' + Math.random().toString(36).substr(2, 8);
        const inner = document.createElement('div');
        inner.id = uid;
        wrapper.appendChild(inner);

        parentElement._jsmeApp = new JSApplet.JSME(uid, w + 'px', h + 'px',
            { options: 'query,lingo,stereo,newlook' });
        if (savedMol) {
            parentElement._jsmeApp.readGenericMolecularInput(savedMol);
            parentElement._lastMol = savedMol;
        }
        wireButtons();
    }

    function doInit() {
        const wrapper = document.getElementById('jsme_wrapper');
        if (!wrapper) return;
        const w = wrapper.offsetWidth || 560;
        buildJSME(wrapper, w);

        // Observe the stable wrapper — JSME never modifies it, so it stays
        // width:100% and the observer correctly fires on every window resize.
        if (parentElement._ro) parentElement._ro.disconnect();
        let timer = null;
        let lastW = w;
        parentElement._ro = new ResizeObserver(function(entries) {
            const newW = Math.round(entries[0].contentRect.width);
            if (Math.abs(newW - lastW) < 5) return;
            clearTimeout(timer);
            timer = setTimeout(function() {
                lastW = newW;
                buildJSME(wrapper, newW);
            }, 150);
        });
        parentElement._ro.observe(wrapper);  // wrapper, not the JSME inner div
    }

    if (window.JSApplet) {
        // JSME already loaded (e.g. after a height remount).
        // Defer to next paint so offsetWidth reflects the real layout.
        requestAnimationFrame(doInit);
    } else {
        // First page load: use the jsmeOnLoad callback
        window.jsmeOnLoad = doInit;
        if (!document.querySelector('script[src*="jsme-editor"]')) {
            const s = document.createElement('script');
            s.src = 'https://unpkg.com/jsme-editor@2024.4.29/jsme.nocache.js';
            document.head.appendChild(s);
        }
    }

    wireButtons();

    // Cleanup: disconnect observer when component unmounts
    return function() {
        if (parentElement._ro) parentElement._ro.disconnect();
        parentElement._jsmeApp = null;
    };
}
"""

_jsme_component = st.components.v2.component(
    "jsme_editor",
    html=_HTML,
    js=_JS,
    isolate_styles=False,
)


def st_jsme(
    molecule: str = "",
    *,
    height: int = 420,
    format: str = "SMILES",
    key: str | None = None,
) -> str:
    """Render a JSME molecule editor and return a molecular representation.

    The editor expands to the full column width automatically.

    Parameters
    ----------
    molecule : str
        Initial molecule as a SMILES string.  Pass ``""`` for a blank canvas.
    height : int
        Editor height in pixels.  Default ``420``.
    format : "SMILES" | "SMILES_NOISO" | "MOL"
        Output format returned when the user clicks **Apply**:

        * ``"SMILES"``       \u2014 isomeric SMILES (default)
        * ``"SMILES_NOISO"`` \u2014 non-isomeric SMILES (stereo stripped)
        * ``"MOL"``          \u2014 MDL MOL V2000 block with 2D coordinates
    key : str, optional
        Unique widget key.

    Returns
    -------
    str
        Molecular representation in the requested format after **Apply**,
        or ``""`` if nothing has been applied yet.
    """
    if format not in FORMATS:
        raise ValueError(f"format must be one of {FORMATS}; got {format!r}")

    result = _jsme_component(
        data={"molecule": molecule, "height": height, "format": format},
        default={"result": ""},
        key=f"{key}_h{height}" if key else f"jsme_h{height}",
    )
    return (result.result or "") if result else ""
