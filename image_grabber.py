import streamlit as st
import requests
import io
import zipfile
import time

st.set_page_config(page_title="Image Downloader", page_icon="🖼️", layout="wide")

st.title("🖼️ Image Downloader")
st.write(
    "Search **openly-licensed / public-domain images** via the Openverse API "
    "(no random copyrighted scrapes — every result here is legally reusable, "
    "with attribution info included)."
)

HEADERS = {"User-Agent": "ImageDownloaderPractice/1.0"}
OPENVERSE_URL = "https://api.openverse.org/v1/images/"


# ---------- Search ----------

def search_images(query, count):
    params = {
        "q": query,
        "page_size": min(count, 50),  # Openverse caps page_size reasonably
        "license_type": "all-cc,commercial,modification",  # broad but still open-licensed
    }
    try:
        resp = requests.get(OPENVERSE_URL, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        st.error(f"Search failed: {e}")
        return []


# ---------- Session state setup ----------

if "results" not in st.session_state:
    st.session_state.results = []
if "selected" not in st.session_state:
    st.session_state.selected = set()


# ---------- UI: search controls ----------

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("🔍 Search term", placeholder="e.g., mountain landscape")
with col2:
    num_images = st.slider("Number of images", min_value=4, max_value=40, value=12, step=4)

if st.button("Search", type="primary"):
    if not query:
        st.warning("Enter a search term first.")
    else:
        with st.spinner(f"Searching Openverse for '{query}'..."):
            st.session_state.results = search_images(query, num_images)
        st.session_state.selected = set(range(len(st.session_state.results)))  # select all by default


# ---------- Preview grid ----------

results = st.session_state.results

if results:
    st.subheader(f"📷 Found {len(results)} image(s) — untick any you don't want")

    cols_per_row = 4
    for row_start in range(0, len(results), cols_per_row):
        row_items = results[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for i, item in enumerate(row_items):
            idx = row_start + i
            with cols[i]:
                thumb = item.get("thumbnail") or item.get("url")
                st.image(thumb, use_container_width=True)
                title = item.get("title") or "Untitled"
                st.caption(f"{title[:40]}{'...' if len(title) > 40 else ''}")
                st.caption(f"by {item.get('creator') or 'Unknown'} · {item.get('license', '').upper()}")

                checked = st.checkbox(
                    "Include",
                    value=idx in st.session_state.selected,
                    key=f"chk_{idx}",
                )
                if checked:
                    st.session_state.selected.add(idx)
                else:
                    st.session_state.selected.discard(idx)

    st.divider()
    st.write(f"**{len(st.session_state.selected)}** image(s) selected for download.")

    if st.button("📦 Build ZIP of selected images"):
        selected_items = [results[i] for i in sorted(st.session_state.selected)]

        if not selected_items:
            st.warning("Select at least one image first.")
        else:
            zip_buffer = io.BytesIO()
            attribution_lines = [
                "Attribution (required for CC-licensed images):",
                "",
            ]
            progress = st.progress(0)

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, item in enumerate(selected_items):
                    image_url = item.get("url")
                    title = (item.get("title") or f"image_{i+1}").replace(" ", "_")
                    ext = image_url.split(".")[-1].split("?")[0][:4] if image_url else "jpg"
                    filename = f"{i+1:02d}_{title[:30]}.{ext}"

                    try:
                        img_resp = requests.get(image_url, headers=HEADERS, timeout=15)
                        if img_resp.status_code == 200:
                            zf.writestr(filename, img_resp.content)
                            attribution_lines.append(
                                f"- {filename}: \"{item.get('title') or 'Untitled'}\" "
                                f"by {item.get('creator') or 'Unknown'}, "
                                f"license: {item.get('license', 'unknown').upper()} "
                                f"({item.get('license_url', 'n/a')}) — source: {item.get('foreign_landing_url', 'n/a')}"
                            )
                        else:
                            attribution_lines.append(f"- {filename}: FAILED TO DOWNLOAD (status {img_resp.status_code})")
                    except Exception as e:
                        attribution_lines.append(f"- {filename}: FAILED TO DOWNLOAD ({e})")

                    progress.progress((i + 1) / len(selected_items))
                    time.sleep(0.2)  # polite pacing

                zf.writestr("ATTRIBUTION.txt", "\n".join(attribution_lines))

            zip_buffer.seek(0)
            st.success("ZIP ready!")
            st.download_button(
                label="⬇️ Download ZIP",
                data=zip_buffer,
                file_name=f"{query.lower().replace(' ', '_')}_images.zip",
                mime="application/zip",
            )
else:
    st.info("Search for something above to see a preview grid here.")