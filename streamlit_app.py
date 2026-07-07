import streamlit as st
import requests
from io import BytesIO
from zipfile import ZipFile
from PyPDF2 import PdfReader
import pandas as pd
from bs4 import BeautifulSoup
import re
import time


# ---------------- Page config ----------------

st.set_page_config(
    page_title="NBER Working Papers Tool",
    page_icon="📄",
    layout="wide"
)


# ---------------- Constants ----------------

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

BASE_URL = "https://www.nber.org"


# ---------------- Helpers ----------------

def clean_text(value):
    if value is None:
        return ""

    return " ".join(value.get_text(" ", strip=True).split())


def dataframe_to_excel(df, sheet_name):
    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

    excel_buffer.seek(0)

    return excel_buffer


def get_latest_working_paper_number():
    """
    Fallback method:
    NBER's listing page may be JS-rendered, so this tries recent likely paper numbers
    and returns the highest working paper page that exists.
    """

    search_start = 36000
    search_end = 30000

    for paper_number in range(search_start, search_end, -1):
        paper_url = f"{BASE_URL}/papers/w{paper_number}"

        try:
            response = requests.get(
                paper_url,
                headers=HEADERS,
                timeout=10
            )

            if response.status_code == 200 and "Page not found" not in response.text:
                return paper_number

        except Exception:
            pass

    return None


def scrape_single_nber_paper(paper_number):
    paper_code = f"w{paper_number}"
    paper_url = f"{BASE_URL}/papers/{paper_code}"
    pdf_url = f"{BASE_URL}/system/files/working_papers/{paper_code}/{paper_code}.pdf"

    result = {
        "Title": "",
        "WorkingPaper": paper_code,
        "Author": "",
        "Date": "",
        "Abstract": "",
        "PaperURL": paper_url,
        "PDFURL": pdf_url,
        "Publisher": "NBER",
        "Place": "Cambridge",
        "Status": ""
    }

    try:
        response = requests.get(
            paper_url,
            headers=HEADERS,
            timeout=30
        )

        if response.status_code != 200:
            result["Status"] = f"Failed - HTTP {response.status_code}"
            return result

        if "Page not found" in response.text:
            result["Status"] = "Not found"
            return result

        soup = BeautifulSoup(response.text, "html.parser")

        # Title
        title_el = soup.select_one("h1")
        result["Title"] = clean_text(title_el)

        # Abstract
        abstract_candidates = [
            soup.select_one(".page-header__intro-inner"),
            soup.select_one(".field--name-field-abstract"),
            soup.select_one(".abstract"),
            soup.find("section", {"id": "abstract"})
        ]

        for abstract_el in abstract_candidates:
            abstract_text = clean_text(abstract_el)
            if abstract_text:
                result["Abstract"] = abstract_text
                break

        # Authors
        author_links = soup.select("a[href*='/people/']")
        authors = []

        for author_link in author_links:
            author_name = clean_text(author_link)

            if author_name and author_name not in authors:
                authors.append(author_name)

        result["Author"] = ", ".join(authors)

        # Date
        page_text = soup.get_text(" ", strip=True)

        date_patterns = [
            r"Issue Date\s+([A-Za-z]+\s+\d{4})",
            r"Date\s+([A-Za-z]+\s+\d{4})",
            r"Published\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, page_text)

            if match:
                result["Date"] = match.group(1)
                break

        result["Status"] = "Scraped"

    except Exception as error:
        result["Status"] = f"Failed - {str(error)}"

    return result


def scrape_nber_range(start, end, delay_seconds=0.2):
    data = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    total = end - start + 1

    for index, paper_number in enumerate(range(start, end + 1)):
        status_text.write(f"Scraping w{paper_number}...")
        paper_data = scrape_single_nber_paper(paper_number)
        data.append(paper_data)

        progress_bar.progress((index + 1) / total)

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    status_text.write("Scraping complete.")

    return pd.DataFrame(data)


def download_pdfs_and_generate_report(start, end):
    zip_buffer = BytesIO()
    pdf_info = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    total = end - start + 1

    with ZipFile(zip_buffer, "w") as zip_file:
        for index, paper_number in enumerate(range(start, end + 1)):
            paper_code = f"w{paper_number}"
            pdf_url = (
                f"{BASE_URL}/system/files/working_papers/"
                f"{paper_code}/{paper_code}.pdf"
            )

            status_text.write(f"Downloading {paper_code}...")

            try:
                response = requests.get(
                    pdf_url,
                    headers=HEADERS,
                    timeout=30
                )

                content_type = response.headers.get("Content-Type", "")

                if response.status_code == 200 and "pdf" in content_type.lower():
                    pdf_name = f"{paper_code}.pdf"

                    zip_file.writestr(pdf_name, response.content)

                    try:
                        pdf_reader = PdfReader(BytesIO(response.content))
                        num_pages = len(pdf_reader.pages)
                    except Exception:
                        num_pages = None

                    pdf_info.append(
                        {
                            "Working Paper": paper_code,
                            "File Name": pdf_name,
                            "PDF URL": pdf_url,
                            "Number of Pages": num_pages,
                            "Status": "Downloaded"
                        }
                    )

                else:
                    pdf_info.append(
                        {
                            "Working Paper": paper_code,
                            "File Name": "",
                            "PDF URL": pdf_url,
                            "Number of Pages": None,
                            "Status": f"Failed - HTTP {response.status_code}"
                        }
                    )

            except Exception as error:
                pdf_info.append(
                    {
                        "Working Paper": paper_code,
                        "File Name": "",
                        "PDF URL": pdf_url,
                        "Number of Pages": None,
                        "Status": f"Failed - {str(error)}"
                    }
                )

            progress_bar.progress((index + 1) / total)

    status_text.write("Download complete.")

    zip_buffer.seek(0)

    report_df = pd.DataFrame(pdf_info)

    excel_buffer = dataframe_to_excel(
        report_df,
        "PDF Page Counts"
    )

    return zip_buffer, excel_buffer, report_df


# ---------------- Main app ----------------

st.title("NBER Working Papers Scraper and Downloader")

st.markdown(
    """
    This app scrapes NBER working paper metadata and downloads NBER working paper PDFs.

    It does **not** use Selenium, so it is more reliable on Streamlit Cloud.
    """
)


# ---------------- Section 1 ----------------

st.header("Scrape NBER working paper metadata by range")

st.write(
    "Enter a working paper number range. Example: `33405` to `33440`."
)

col1, col2 = st.columns(2)

with col1:
    scrape_start_range = st.text_input(
        "Scrape start number",
        value="33405"
    )

with col2:
    scrape_end_range = st.text_input(
        "Scrape end number",
        value="33440"
    )

if st.button("Scrape Paper Metadata"):
    try:
        scrape_start_number = int(scrape_start_range)
        scrape_end_number = int(scrape_end_range)

        if scrape_start_number <= 0:
            st.error("Start number must be greater than 0.")

        elif scrape_end_number < scrape_start_number:
            st.error("End number must be greater than or equal to start number.")

        else:
            with st.spinner("Scraping NBER paper pages..."):
                scraped_df = scrape_nber_range(
                    scrape_start_number,
                    scrape_end_number
                )

            successful_count = scraped_df["Status"].eq("Scraped").sum()

            st.success(
                f"Finished. {successful_count} papers scraped successfully."
            )

            st.dataframe(
                scraped_df,
                use_container_width=True
            )

            excel_file = dataframe_to_excel(
                scraped_df,
                "NBER Papers"
            )

            st.download_button(
                label="Download scraped metadata as Excel",
                data=excel_file,
                file_name="nber_working_papers_metadata.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except ValueError:
        st.error("Please enter valid numerical values.")

    except Exception as error:
        st.error("Scraping failed.")
        st.exception(error)


# ---------------- Section 2 ----------------

st.header("Download PDFs and generate page count report")

st.write(
    "Enter a range of NBER working paper numbers to download PDFs and count pages."
)

col3, col4 = st.columns(2)

with col3:
    download_start_range = st.text_input(
        "Download start number",
        value="33405"
    )

with col4:
    download_end_range = st.text_input(
        "Download end number",
        value="33440"
    )

if st.button("Download PDFs and Generate Report"):
    try:
        download_start_number = int(download_start_range)
        download_end_number = int(download_end_range)

        if download_start_number <= 0:
            st.error("Start number must be greater than 0.")

        elif download_end_number < download_start_number:
            st.error("End number must be greater than or equal to start number.")

        else:
            with st.spinner("Downloading PDFs and counting pages..."):
                zip_file, page_count_excel, report_df = download_pdfs_and_generate_report(
                    download_start_number,
                    download_end_number
                )

            downloaded_count = report_df["Status"].eq("Downloaded").sum()

            st.success(
                f"Finished. {downloaded_count} PDFs downloaded successfully."
            )

            st.dataframe(
                report_df,
                use_container_width=True
            )

            st.download_button(
                label="Download all PDFs as ZIP",
                data=zip_file,
                file_name="nber_papers.zip",
                mime="application/zip"
            )

            st.download_button(
                label="Download PDF page counts as Excel",
                data=page_count_excel,
                file_name="pdf_page_counts.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except ValueError:
        st.error("Please enter valid numerical values.")

    except Exception as error:
        st.error("PDF download failed.")
        st.exception(error)


# ---------------- Disclaimer ----------------

st.markdown("---")

st.markdown(
    """
    **Disclaimer:**
    This tool only helps access publicly available NBER working paper information and PDFs.
    Please make sure your usage follows NBER's terms, copyright rules, and fair-use guidelines.
    """
)
