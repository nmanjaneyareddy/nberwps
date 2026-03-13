import streamlit as st
import requests
from io import BytesIO
from zipfile import ZipFile
from PyPDF2 import PdfReader
import pandas as pd
from bs4 import BeautifulSoup

import streamlit as st
import pandas as pd
import time
from io import BytesIO

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


st.title("NBER Working Papers Scraper")

url = "https://www.nber.org/papers?page=1&perPage=50&sortBy=public_date#listing-77041"

def scrape_nber():

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)

    driver.get(url)

    time.sleep(5)

    papers = driver.find_elements(By.CSS_SELECTOR,"div.digest-card")

    data = []

    for paper in papers:

        try:
            title_el = paper.find_element(By.CSS_SELECTOR,".digest-card__title a")
            title = title_el.text
            link = title_el.get_attribute("href")
        except:
            title = ""
            link = ""

        try:
            wp = paper.find_element(By.CSS_SELECTOR,".paper-card__paper_number").text
        except:
            wp = ""
        try:
            author_elements = paper.find_elements(By.CSS_SELECTOR, ".digest-card__items a")
            authors = ", ".join([a.text for a in author_elements])
        except:
            authors = ""

        try:
            date = paper.find_element(By.CSS_SELECTOR,".digest-card__label").text
        except:
            date = ""

        try:
            abstract = paper.find_element(By.CSS_SELECTOR,".digest-card__summary").text
        except:
            abstract = ""

        data.append({
            "Title":title,
            "WorkingPaper":wp,
            "Author":authors,
            "Date":date,
            "Abstract":abstract,
            "PaperURL":link,
            "Publisher":"NBER",
            "Place":"Cambridge"
        })

    driver.quit()

    return pd.DataFrame(data)


if st.button("Scrape NBER Papers"):

    with st.spinner("Scraping papers..."):

        df = scrape_nber()

    st.success(f"{len(df)} papers scraped")

    st.dataframe(df)

    excel = BytesIO()
    df.to_excel(excel,index=False)
    excel.seek(0)

    st.download_button(
        "Download Excel",
        data=excel,
        file_name="nber_working_papers.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
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
