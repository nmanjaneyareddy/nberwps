import streamlit as st
import requests
from io import BytesIO
from zipfile import ZipFile
from PyPDF2 import PdfReader
import pandas as pd
from bs4 import BeautifulSoup


# ---------------- Page config ----------------

st.set_page_config(
    page_title="NBER Working Papers Tool",
    page_icon="📄",
    layout="wide"
)


# ---------------- Constants ----------------

NBER_PAPERS_URL = "https://www.nber.org/papers?page=1&perPage=50&sortBy=public_date#listing-77041"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


# ---------------- Scrape NBER papers ----------------

def scrape_nber():
    response = requests.get(
        NBER_PAPERS_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    papers = soup.select("div.digest-card")

    data = []

    for paper in papers:
        title_el = paper.select_one(".digest-card__title a")
        title = title_el.get_text(strip=True) if title_el else ""
        link = title_el.get("href", "") if title_el else ""

        if link.startswith("/"):
            link = "https://www.nber.org" + link

        wp_el = paper.select_one(".paper-card__paper_number")
        working_paper = wp_el.get_text(strip=True) if wp_el else ""

        author_elements = paper.select(".digest-card__items a")
        authors = ", ".join(
            [author.get_text(strip=True) for author in author_elements]
        )

        date_el = paper.select_one(".digest-card__label")
        date = date_el.get_text(strip=True) if date_el else ""

        abstract_el = paper.select_one(".digest-card__summary")
        abstract = abstract_el.get_text(" ", strip=True) if abstract_el else ""

        data.append(
            {
                "Title": title,
                "WorkingPaper": working_paper,
                "Author": authors,
                "Date": date,
                "Abstract": abstract,
                "PaperURL": link,
                "Publisher": "NBER",
                "Place": "Cambridge"
            }
        )

    return pd.DataFrame(data)


# ---------------- Convert DataFrame to Excel ----------------

def dataframe_to_excel(df):
    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="NBER Papers")

    excel_buffer.seek(0)

    return excel_buffer


# ---------------- Download PDFs and generate page count report ----------------

def download_pdfs_and_generate_report(start, end):
    zip_buffer = BytesIO()
    pdf_info = []

    with ZipFile(zip_buffer, "w") as zip_file:
        for paper_number in range(start, end + 1):
            pdf_url = (
                f"https://www.nber.org/system/files/working_papers/"
                f"w{paper_number}/w{paper_number}.pdf"
            )

            try:
                response = requests.get(
                    pdf_url,
                    headers=HEADERS,
                    timeout=30
                )

                if response.status_code == 200:
                    pdf_name = f"w{paper_number}.pdf"

                    zip_file.writestr(pdf_name, response.content)

                    try:
                        pdf_reader = PdfReader(BytesIO(response.content))
                        num_pages = len(pdf_reader.pages)
                    except Exception:
                        num_pages = None

                    pdf_info.append(
                        {
                            "Working Paper": f"w{paper_number}",
                            "File Name": pdf_name,
                            "PDF URL": pdf_url,
                            "Number of Pages": num_pages,
                            "Status": "Downloaded"
                        }
                    )

                else:
                    pdf_info.append(
                        {
                            "Working Paper": f"w{paper_number}",
                            "File Name": "",
                            "PDF URL": pdf_url,
                            "Number of Pages": None,
                            "Status": f"Failed - HTTP {response.status_code}"
                        }
                    )

            except Exception as error:
                pdf_info.append(
                    {
                        "Working Paper": f"w{paper_number}",
                        "File Name": "",
                        "PDF URL": pdf_url,
                        "Number of Pages": None,
                        "Status": f"Failed - {str(error)}"
                    }
                )

    zip_buffer.seek(0)

    report_df = pd.DataFrame(pdf_info)

    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        report_df.to_excel(
            writer,
            index=False,
            sheet_name="PDF Page Counts"
        )

    excel_buffer.seek(0)

    return zip_buffer, excel_buffer, report_df


# ---------------- Main app ----------------

st.title("NBER Working Papers Scraper and Downloader")

st.markdown(
    """
    This app lets you scrape recent NBER working paper metadata and download
    NBER working paper PDFs by paper-number range.

    This version uses `requests` and `BeautifulSoup` instead of Selenium,
    so it should deploy more reliably on Streamlit Cloud.
    """
)


# ---------------- Section 1 - Scrape latest papers ----------------

st.header("Scrape latest NBER working papers")

st.write(
    "Click the button below to scrape the latest papers from the NBER working papers listing page."
)

if st.button("Scrape NBER Papers"):
    with st.spinner("Scraping NBER papers..."):
        try:
            df = scrape_nber()

            if df.empty:
                st.warning(
                    "No papers were found. The NBER page structure may have changed."
                )
            else:
                st.success(f"{len(df)} papers scraped successfully.")

                st.dataframe(
                    df,
                    use_container_width=True
                )

                excel_file = dataframe_to_excel(df)

                st.download_button(
                    label="Download scraped papers as Excel",
                    data=excel_file,
                    file_name="nber_working_papers.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as error:
            st.error("Scraping failed.")
            st.exception(error)


# ---------------- Section 2 - Download PDFs ----------------

st.header("Download NBER PDFs and generate page count report")

st.write(
    "Enter a range of NBER working paper numbers. "
    "For example, `33405` to `33440`."
)

col1, col2 = st.columns(2)

with col1:
    start_range = st.text_input(
        "Enter start range",
        value="33405"
    )

with col2:
    end_range = st.text_input(
        "Enter end range",
        value="33440"
    )

if st.button("Download PDFs and Generate Report"):
    try:
        start_number = int(start_range)
        end_number = int(end_range)

        if start_number <= 0:
            st.error("Start range must be greater than 0.")

        elif end_number < start_number:
            st.error("End range must be greater than or equal to start range.")

        else:
            with st.spinner("Downloading PDFs and counting pages..."):
                zip_file, page_count_excel, report_df = download_pdfs_and_generate_report(
                    start_number,
                    end_number
                )

            downloaded_count = (
                report_df["Status"]
                .eq("Downloaded")
                .sum()
            )

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
