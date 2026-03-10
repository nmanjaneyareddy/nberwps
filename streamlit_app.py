import streamlit as st
import requests
from io import BytesIO
from zipfile import ZipFile
from PyPDF2 import PdfReader
import pandas as pd
from bs4 import BeautifulSoup

def scrape_nber_papers():

    url = "https://www.nber.org/papers"

    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        st.error("Failed to retrieve data from NBER.")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    papers = soup.select("div.digest-card")

    if not papers:
        st.error("No papers found on the page.")
        return

    data = []

    for paper in papers:

        title = paper.select_one(".digest-card__title")
        year = paper.select_one(".digest-card__label")
        wpno = paper.select_one(".paper-card__paper_number")
        author = paper.select_one(".digest-card__items")

        data.append({
            "Source": "National Bureau of Economic Research",
            "Title": title.text.strip() if title else "",
            "Year": year.text.strip() if year else "",
            "WP_NO": wpno.text.strip() if wpno else "",
            "Place": "Cambridge",
            "Publisher": "NBER",
            "Series": "NBER Working Papers ;",
            "wpno": f"NBERWP {wpno.text.strip()}" if wpno else "",
            "Author": author.text.replace("Author(s) - ", "").strip() if author else ""
        })

    df = pd.DataFrame(data)

    df[["Title1","Subtitle"]] = df["Title"].str.split(":", n=1, expand=True).fillna("")
    df.drop("Title", axis=1, inplace=True)

    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)

    st.download_button(
        "Download NBER Papers Data",
        data=excel_buffer,
        file_name="nber_papers.xlsx"
    )
# -------- Sidebar --------
def main_sidebar():
    st.header("NBER Papers Scraper")

    if st.button("Start Scraping"):
        with st.spinner("Scraping data, please wait..."):
            scrape_nber_papers()


if __name__ == "__main__":
    main_sidebar()


# -------- Download PDFs --------
def download_pdfs_and_generate_report(start, end):

    st.write("Starting to download PDFs...")

    zip_buffer = BytesIO()
    pdf_info = []

    with ZipFile(zip_buffer, "w") as zip_file:

        for i in range(start, end + 1):

            url = f"https://www.nber.org/system/files/working_papers/w{i}/w{i}.pdf"

            response = requests.get(url)

            if response.status_code == 200:

                pdf_name = f"w{i}.pdf"

                zip_file.writestr(pdf_name, response.content)

                pdf_reader = PdfReader(BytesIO(response.content))

                num_pages = len(pdf_reader.pages)

                pdf_info.append({
                    "File Name": pdf_name,
                    "Number of Pages": num_pages
                })

            else:
                st.write(f"Failed to download: {url}")

    zip_buffer.seek(0)

    df = pd.DataFrame(pdf_info)

    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="PDF Page Counts")

    excel_buffer.seek(0)

    st.download_button(
        label="Download All PDFs as ZIP",
        data=zip_buffer,
        file_name="nber_papers.zip",
        mime="application/zip"
    )

    st.download_button(
        label="Download PDF Page Counts as Excel",
        data=excel_buffer,
        file_name="pdf_page_counts.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("PDFs downloaded and report generated successfully!")


# -------- UI --------
st.title("NBER Paper Downloader and Page Counter")

st.subheader("Download NBER PDFs and Generate Page Count Report")

start_range = st.text_input("Enter start range (e.g., 33405)", value="33405")
end_range = st.text_input("Enter end range (e.g., 33440)", value="33440")

if st.button("Download PDFs and Generate Report"):

    try:
        start_range = int(start_range)
        end_range = int(end_range)

        if start_range > 0 and end_range >= start_range:

            download_pdfs_and_generate_report(start_range, end_range)

        else:
            st.error("Enter valid numbers. End must be ≥ start.")

    except ValueError:
        st.error("Please enter valid numerical values.")


# -------- Disclaimer --------
st.markdown(
"""
**Disclaimer:**  
This tool only helps access publicly available PDFs from the NBER website.  
It does not host or modify any content. Users must comply with NBER terms of use.
""",
unsafe_allow_html=True,
)


# -------- Rating --------
st.subheader("Rate This Application")

rating = st.radio(
"Please rate your experience:",
["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
horizontal=True
)

if st.button("Submit Rating"):
    st.success(f"Thank you for rating this application {rating}!")
