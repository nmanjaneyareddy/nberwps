import streamlit as st
import requests
from io import BytesIO
from zipfile import ZipFile
from PyPDF2 import PdfReader
import pandas as pd


from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

# Streamlit page configuration
st.set_page_config(layout="wide")

# Function to scrape website content
def get_website_content(url):
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1200')
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        driver.get(url)
        time.sleep(5)
        html_doc = driver.page_source
        soup = BeautifulSoup(html_doc, "html.parser")
        return soup
    except Exception as e:
        st.error(f"Error fetching website content: {e}")
    finally:
        if driver is not None:
            driver.quit()
    return None

def scrape_nber_papers():
    url = 'https://www.nber.org/papers?page=1&perPage=50&sortBy=public_date#listing-77041'
    soup = get_website_content(url)

    if soup is None:
        st.error("Failed to retrieve data from the website.")
        return

    results = soup.find(class_='promo-grid__promos')
    if not results:
        st.error("No results found on the page.")
        return

    job_elems = results.find_all('div', class_='digest-card')

    data = []
    for job_elem in job_elems:
        title_elem = job_elem.find('div', class_='digest-card__title')
        year_elem = job_elem.find('span', class_="digest-card__label")
        wpno_elem = job_elem.find('a', class_="paper-card__paper_number")
        author_elem = job_elem.find('div', class_='digest-card__items')

        if None in (title_elem, year_elem, wpno_elem, author_elem):
            continue

        title_text = title_elem.text.strip()
        year = year_elem.text.strip().replace('May', '')
        wpno = wpno_elem.text.strip()
        author = author_elem.text.strip().replace('Author(s) - ', '')

        data.append({
            'Source': 'National Bureau of Economic Research',
            'Title': title_text,
            'Year': year,
            'WP_NO': wpno,
            'Place': 'Cambridge',
            'Publisher': 'NBER',
            'Series': 'NBER Working Papers ;',
            'wpno': f'NBERWP {wpno}',
            'Author': author
        })

    if not data:
        st.error("No data extracted from the webpage.")
        return

    df = pd.DataFrame(data)

    # Split 'Title' into 'Title1' and 'Subtitle'
    df[['Title1', 'Subtitle']] = df['Title'].str.split(':', n=1, expand=True).fillna('')

    # Drop the original 'Title' column
    df.drop('Title', axis=1, inplace=True)

    # Save DataFrame to Excel
    excel_file = "nber_papers.xlsx"
    df.to_excel(excel_file, index=False)

    # Provide download link for the Excel file
    with open(excel_file, "rb") as file:
        st.download_button(label="Download NBER Papers Data", data=file, file_name="nber_papers.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def main_sidebar():
    st.header("NBER Papers Scraper")
    if st.button("Start Scraping"):
        with st.spinner("Scraping data, please wait..."):
            scrape_nber_papers()

if __name__ == "__main__":
    main_sidebar()

# ------------------- download PDFs -----------------------------
def download_pdfs_and_generate_report(start, end):
    st.write("Starting to download PDFs...")
    zip_buffer = BytesIO()
    pdf_info = []

    with ZipFile(zip_buffer, 'w') as zip_file:
        for i in range(start, end + 1):
            url = f"https://www.nber.org/system/files/working_papers/w{i}/w{i}.pdf"
            response = requests.get(url)

            if response.status_code == 200:
                pdf_name = f"w{i}.pdf"
                zip_file.writestr(pdf_name, response.content)

                # Count the number of pages in the PDF
                pdf_reader = PdfReader(BytesIO(response.content))
                num_pages = len(pdf_reader.pages)

                # Store the PDF name and page count
                pdf_info.append({'File Name': pdf_name, 'Number of Pages': num_pages})
            else:
                st.write(f"Failed to download: {url}")

    zip_buffer.seek(0)

    # Create a DataFrame with the PDF information
    df = pd.DataFrame(pdf_info)

    # Write the DataFrame to an Excel file
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='PDF Page Counts')
    excel_buffer.seek(0)

    # Provide download buttons for the ZIP and Excel files
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

    st.success("PDFs have been downloaded and the report has been generated successfully!")

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
            st.error("Please enter valid positive numbers with the end range greater than or equal to the start range.")
    except ValueError:
        st.error("Please enter valid numerical values.")
# Disclaimer
st.markdown(
    """
    **Disclaimer:** This application is an independent tool designed to assist users in accessing 
    and downloading publicly available PDF files from the National Bureau of Economic Research (NBER) portal. 
    It does not host, store, or modify any content, nor does it claim ownership of any materials accessed through this platform. 
    Users are solely responsible for ensuring compliance with NBER’s terms of use, copyright policies, and applicable legal regulations.
    """,
    unsafe_allow_html=True,
)

# User Rating Feature
st.subheader("Rate This Application")

# Horizontal star rating
rating = st.radio("Please rate your experience:", ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"], horizontal=True)
if st.button("Submit Rating"):
    st.success(f"Thank you for rating this application {rating}!")

