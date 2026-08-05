# -*- coding: utf-8 -*-
"""
Product Documentation Finder — Streamlit app.

Run with:
    streamlit run app.py
"""

import streamlit as st

from scraper import (
    BASE_URL,
    CAMERA_CATEGORIES,
    CLOUD_CONNECTOR_CATEGORIES,
    get_all_camera_products,
    get_products_in_category,
    get_spec_sheets,
    resolve_document,
)

st.set_page_config(
    page_title="Product Documentation Finder",
    page_icon="📄",
    layout="centered"
)

st.title("📄 Product Documentation Finder")
st.caption("Quickly locate and download product datasheets and fact sheets.")

st.divider()


def build_spec_sheet_list(page_url):
    """Fetch a product page and turn its docs into a flat list of options."""
    doc_links = get_spec_sheets(page_url)
    return [{"label": label, "url": url} for label, url in doc_links.items()]


def render_spec_sheet_picker(spec_sheets, key_prefix):
    """Shared UI for picking + downloading/opening a spec sheet."""
    if not spec_sheets:
        st.warning("No documentation found for this product.")
        return

    selected_sheet = st.selectbox(
        "Spec Sheet",
        ["Select a spec sheet..."] + [s["label"] for s in spec_sheets],
        index=0,
        key=f"{key_prefix}_spec_sheet"
    )

    if selected_sheet == "Select a spec sheet...":
        return

    sheet = next(s for s in spec_sheets if s["label"] == selected_sheet)

    with st.spinner("Checking document..."):
        try:
            resolved = resolve_document(sheet["url"])
        except Exception as e:
            st.error(f"Could not reach this document: {e}")
            return

    if resolved["kind"] == "pdf":
        st.download_button(
            "⬇ Download Spec Sheet",
            data=resolved["content"],
            file_name=resolved["filename"],
            mime="application/pdf",
            key=f"{key_prefix}_download"
        )
    else:
        st.info("This document isn't a direct PDF — it opens in Avigilon's documentation portal.")
        st.link_button("Open Documentation Portal", resolved["url"])


# ---------------------------------------------------------------------------
# Search
#
# We load every camera product once (cached) and hand the full list to a
# single selectbox. Streamlit's selectbox has built-in type-ahead filtering
# that happens instantly in the browser as you type — no Enter key and no
# server rerun needed until you actually pick a product.
# ---------------------------------------------------------------------------
st.subheader("🔍 Search Product")

with st.spinner("Loading product list..."):
    all_products = get_all_camera_products()

product_options = ["Type to search e.g. H6A, X6, PTZ..."] + [p["name"] for p in all_products]

selected_search_product = st.selectbox(
    "Search Product",
    product_options,
    index=0,
    key="search_product_select",
    label_visibility="collapsed"
)

if selected_search_product != product_options[0]:
    selected_product = next(p for p in all_products if p["name"] == selected_search_product)

    with st.spinner("Loading spec sheets..."):
        spec_sheets = build_spec_sheet_list(selected_product["url"])

    render_spec_sheet_picker(spec_sheets, key_prefix="search")

st.divider()
st.caption("Or browse by category below.")

# ---------------------------------------------------------------------------
# Browse by category
# ---------------------------------------------------------------------------
product_type = st.radio("Select Product Type", ["Camera", "Cloud Connector"])

if product_type == "Camera":
    categories = ["Select a category..."] + list(CAMERA_CATEGORIES.keys())
    category = st.selectbox("Camera Category", categories, index=0)

    if category != "Select a category...":
        with st.spinner("Loading products..."):
            products = get_products_in_category(CAMERA_CATEGORIES[category])

        if products:
            product_names = ["Select a product..."] + [p["name"] for p in products]
            selected_product_name = st.selectbox("Product", product_names)

            if selected_product_name != "Select a product...":
                selected = next(p for p in products if p["name"] == selected_product_name)

                with st.spinner("Loading spec sheets..."):
                    spec_sheets = build_spec_sheet_list(selected["url"])

                render_spec_sheet_picker(spec_sheets, key_prefix="camera")
        else:
            st.warning("No products found in this category.")

else:
    connector_names = ["Select a cloud connector..."] + list(CLOUD_CONNECTOR_CATEGORIES.keys())
    connector = st.selectbox("Cloud Connector Type", connector_names, index=0)

    if connector != "Select a cloud connector...":
        page_url = BASE_URL + CLOUD_CONNECTOR_CATEGORIES[connector]

        with st.spinner("Loading spec sheets..."):
            spec_sheets = build_spec_sheet_list(page_url)

        render_spec_sheet_picker(spec_sheets, key_prefix="connector")
