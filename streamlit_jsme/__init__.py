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

import json
import os

import streamlit as st

__version__ = "0.1.10"
__all__ = ["st_jsme"]

FORMATS = ("SMILES", "SMILES_NOISO", "MOL")

# ── Bundle JSME JS files inline ───────────────────────────────────────────────
# JSME is a GWT application that normally loads from an external CDN URL.
# Snowflake SiS component iframes block external script loading (CSP), so we
# bundle every required file and serve them as blob: URLs instead.

_JSME_DIR = os.path.join(os.path.dirname(__file__), "jsme")

def _read(relpath: str) -> str:
    with open(os.path.join(_JSME_DIR, relpath), encoding="utf-8") as fh:
        return fh.read()


def _build_jsme_blob_setup() -> tuple[str, str]:
    """Return (blob_setup_script, nocache_script) as JS strings."""
    perms = [
        "0ADE505A5718D4BE2E0EE1B7C54CC163",
        "4277561D0E87B89F4DFCCC3A712D5B19",
    ]

    # Map of filename-suffix → file content
    # Keys must be stable path suffixes so endsWith() matching works.
    files: dict[str, str] = {}
    for perm in perms:
        files[f"{perm}.cache.js"] = _read(f"{perm}.cache.js")
        for i in range(1, 12):
            frag = f"deferredjs/{perm}/{i}.cache.js"
            path = os.path.join(_JSME_DIR, frag)
            if os.path.exists(path):
                files[frag] = _read(frag)

    files_json = json.dumps(files, ensure_ascii=False)

    # PNG data file — bundled separately as base64 so it can use image/png MIME type.
    _PNG_NAME = "40BAF81124143A595056A9CCA0E9DBBA.cache.png"
    import base64
    with open(os.path.join(_JSME_DIR, _PNG_NAME), "rb") as fh:
        _png_b64 = base64.b64encode(fh.read()).decode()
    nocache = _read("jsme.nocache.js")

    # This script runs BEFORE jsme.nocache.js.  It:
    #   1. Creates blob: URLs for every bundled JSME file.
    #   2. Monkey-patches HTMLElement.prototype.appendChild so that whenever
    #      JSME's GWT bootstrap appends a <script src="...cache.js"> to the
    #      DOM, we swap the (CSP-blocked) CDN URL for the local blob: URL.
    blob_setup = f"""
(function() {{
  // Build blob: URL registry for all bundled JSME JS files.
  var _files = {files_json};
  window._jsmeBlobs = {{}};
  for (var k in _files) {{
    window._jsmeBlobs[k] = URL.createObjectURL(
      new Blob([_files[k]], {{type: 'text/javascript'}})
    );
  }}

  // Bundle the GWT data PNG so its broken-image icon doesn't appear.
  var _pngBytes = atob('{_png_b64}');
  var _pngArr = new Uint8Array(_pngBytes.length);
  for (var i = 0; i < _pngBytes.length; i++) _pngArr[i] = _pngBytes.charCodeAt(i);
  var _pngBlob = URL.createObjectURL(new Blob([_pngArr], {{type: 'image/png'}}));
  window._jsmeBlobs['{_PNG_NAME}'] = _pngBlob;

  // Intercept img.src (property) and img.setAttribute to serve the bundled PNG via blob: URL.
  function _remapSrc(val) {{
    if (typeof val === 'string') {{
      for (var k in window._jsmeBlobs) {{
        if (val.endsWith(k)) return window._jsmeBlobs[k];
      }}
    }}
    return val;
  }}
  var _imgSrcDesc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', {{
    get: function() {{ return _imgSrcDesc.get.call(this); }},
    set: function(val) {{ _imgSrcDesc.set.call(this, _remapSrc(val)); }},
    configurable: true
  }});
  var _origSetAttr = HTMLElement.prototype.setAttribute;
  HTMLElement.prototype.setAttribute = function(name, val) {{
    if (this.tagName === 'IMG' && name === 'src') val = _remapSrc(val);
    return _origSetAttr.call(this, name, val);
  }};

  // Suppress the non-fatal "Loading JS code failed." alert that JSME fires
  // when an optional deferred fragment can't load (widget still works).
  var _origAlert = window.alert;
  window.alert = function(msg) {{
    if (typeof msg === 'string' && msg.indexOf('Loading JS code failed') !== -1) return;
    _origAlert.call(window, msg);
  }};

  // GWT's compiled module sets: var $wnd = $wnd || window.parent;
  // Pre-setting window.$wnd = window keeps JSME in the current window context
  // regardless of iframe nesting — deferred fragments then resolve jsme correctly.
  window.$wnd = window;

  // Intercept <script src> loading so GWT's bootstrap picks up blob: URLs
  // instead of the (404 / CSP-blocked) CDN paths.
  var _origAC = HTMLElement.prototype.appendChild;
  HTMLElement.prototype.appendChild = function(node) {{
    if (node && node.tagName === 'SCRIPT' && node.src) {{
      var src = node.src;
      for (var k in window._jsmeBlobs) {{
        if (src.endsWith(k)) {{ node.src = window._jsmeBlobs[k]; break; }}
      }}
    }}
    return _origAC.call(this, node);
  }};
}})();
"""
    return blob_setup, nocache


_blob_setup_script, _nocache_script = _build_jsme_blob_setup()

# ── HTML: container div + button bar ─────────────────────────────────────────
_HTML = (
    """
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
<script>"""
    + _blob_setup_script
    + """</script>
<script>"""
    + _nocache_script
    + """</script>
<script>
// After nocache sets jsme.__startLoadingFragment (which builds CDN URLs),
// replace it so GWT gets blob: URLs for all bundled fragments.
// This works for both <script src> loading AND XHR-based loading.
(function() {
  function override() {
    if (!window.jsme || typeof window.jsme.__startLoadingFragment !== 'function') return false;
    window.jsme.__startLoadingFragment = function(fragFile) {
      if (window._jsmeBlobs && window._jsmeBlobs[fragFile]) {
        return window._jsmeBlobs[fragFile];
      }
      // Fallback: relative path from moduleBase
      return (window.jsme.__moduleBase || '') + fragFile;
    };
    return true;
  }
  if (!override()) {
    var t = setInterval(function() { if (override()) clearInterval(t); }, 10);
  }
})();
</script>
"""
)

# ── JavaScript ────────────────────────────────────────────────────────────────
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
        // JSME already loaded (inline scripts ran before this module).
        // Defer to next paint so offsetWidth reflects the real layout.
        requestAnimationFrame(doInit);
    } else {
        // JSME not ready yet — use the jsmeOnLoad callback.
        // The inline <script> tags in _HTML will call this once JSME is ready.
        window.jsmeOnLoad = doInit;
        // Fallback: if running outside SiS where CDN is allowed, load from CDN.
        if (!document.querySelector('script[src*="jsme-editor"]')
                && !document.querySelector('script[src*="jsme.nocache"]')) {
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

        * ``"SMILES"``       — isomeric SMILES (default)
        * ``"SMILES_NOISO"`` — non-isomeric SMILES (stereo stripped)
        * ``"MOL"``          — MDL MOL V2000 block with 2D coordinates
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
        on_result_change=lambda: None,
    )
    return (result.result or "") if result else ""
