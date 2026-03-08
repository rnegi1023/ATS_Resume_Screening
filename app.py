import base64
import io
import json

import pdf2image
import streamlit as st
import google.generativeai as genai

# --- Configuration -----------------------------------------------------------
st.set_page_config(
    page_title="ATS Resume Scanner",
    layout="wide",
    initial_sidebar_state="expanded",
)

genai.configure(api_key=st.secrets.GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# --- Caching helpers ----------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_gemini_response(input_text: str, pdf_content: list, prompt: str) -> str:
    response = model.generate_content([input_text, pdf_content[0], prompt])
    return response.text


@st.cache_data(show_spinner=False)
def get_gemini_response_keywords(input_text: str, pdf_content: list, prompt: str) -> dict:
    response = model.generate_content([input_text, pdf_content[0], prompt])
    # Response currently returns JSON embedded in text; keep this in sync with the model's output.
    return json.loads(response.text[8:-4])


@st.cache_data(show_spinner=False)
def get_gemini_response_keywords_from_text(input_text: str, prompt: str) -> dict:
    """Extracts keywords from a plain text input (e.g., job description) without requiring a PDF."""
    response = model.generate_content([input_text, prompt])
    return json.loads(response.text[8:-4])


@st.cache_data(show_spinner=False)
def extract_pdf_first_page_as_image(uploaded_file) -> list:
    if uploaded_file is None:
        raise FileNotFoundError("No file uploaded")

    images = pdf2image.convert_from_bytes(uploaded_file.read())
    first_page = images[0]
    buf = io.BytesIO()
    first_page.save(buf, format="JPEG")
    return [{"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}]


# --- Prompts ------------------------------------------------------------------
PROMPT_RESUME_SUMMARY = """
You are an experienced Technical Human Resource Manager, your task is to review the provided resume against the job description.
Please share your professional evaluation on whether the candidate's profile aligns with the role.
Highlight the strengths and weaknesses of the applicant in relation to the specified job requirements.
"""

PROMPT_KEYWORDS_JSON = """
As an expert ATS (Applicant Tracking System) scanner with an in-depth understanding of AI and ATS functionality,
your task is to evaluate a resume against a provided job description.
Please identify the specific skills and keywords necessary to maximize the impact of the resume and
provide response in json format as {Technical Skills:[], Analytical Skills:[], Soft Skills:[]}.
Note: Please do not make up the answer; only answer from the job description provided.
"""

PROMPT_JD_KEYWORDS_JSON = """
As an expert ATS (Applicant Tracking System) scanner, analyze the provided job description and
identify the key skills and keywords a candidate should have.
Provide the response in JSON format as {Technical Skills:[], Analytical Skills:[], Soft Skills:[]}.
Do not invent skills; only extract them from the job description.
"""

PROMPT_PERCENTAGE_MATCH = """
You are a skilled ATS (Applicant Tracking System) scanner with a deep understanding of data science and ATS functionality.
Your task is to evaluate the resume against the provided job description.
Give me the percentage of match if the resume matches the job description.
First the output should come as percentage and then keywords missing and last final thoughts.
"""

# --- Sidebar (Inputs) ---------------------------------------------------------
st.sidebar.title("ATS Resume Scanner")
job_description = st.sidebar.text_area(
    "Job Description",
    placeholder="Paste the job description here (required for better results)",
    height=240,
)

resume = st.sidebar.file_uploader("Upload your resume (PDF)", type=["pdf"])

st.sidebar.markdown(
    "---\n**Tip:** Use a concise, complete job description for best matching results."
)

if "resume_file" not in st.session_state:
    st.session_state.resume_file = None

if resume is not None:
    st.session_state.resume_file = resume

# --- Main Layout --------------------------------------------------------------
tabs = st.tabs(["Summary", "Keywords", "Match Score"])

with tabs[0]:
    st.subheader("Resume Summary")
    st.write(
        "Click a button in the sidebar to analyze the resume against the job description."
    )

with tabs[1]:
    st.subheader("Extracted Keywords")
    st.write("Analyze the resume and see which skills were identified.")

with tabs[2]:
    st.subheader("Match Score")
    st.write(
        "Calculate how well this resume matches the job description, including missing keywords."
    )

# --- Actions ------------------------------------------------------------------
submit_summary = st.sidebar.button("Tell Me About the Resume")
submit_keywords = st.sidebar.button("Get Keywords")
submit_match = st.sidebar.button("Percentage Match")

# -- Helpers -------------------------------------------------------------------
def _not_ready_msg():
    if not job_description:
        st.warning("Please enter a job description in the sidebar first.")
        return True

    if st.session_state.resume_file is None:
        st.warning("Please upload a resume (PDF) in the sidebar.")
        return True

    return False


def _display_keywords_page(result: dict, job_keywords: dict | None = None):
    if not result:
        st.info("No keywords found.")
        return

    technical = result.get("Technical Skills", [])
    analytical = result.get("Analytical Skills", [])
    soft = result.get("Soft Skills", [])

    st.markdown("### Skill Coverage")
    skill_counts = {
        "Category": ["Technical", "Analytical", "Soft"],
        "Count": [len(technical), len(analytical), len(soft)],
    }
    st.bar_chart(skill_counts)

    if job_keywords:
        missing = {
            "Technical": sorted(set(job_keywords.get("Technical Skills", [])) - set(technical)),
            "Analytical": sorted(set(job_keywords.get("Analytical Skills", [])) - set(analytical)),
            "Soft": sorted(set(job_keywords.get("Soft Skills", [])) - set(soft)),
        }

        st.markdown("### Missing Skills")
        missing_counts = {
            "Category": ["Technical", "Analytical", "Soft"],
            "Count": [len(missing["Technical"]), len(missing["Analytical"]), len(missing["Soft"])],
        }
        st.bar_chart(missing_counts)

        with st.expander("View missing skills"):
            st.markdown("**Technical Skills missing from resume**")
            st.write(", ".join(missing["Technical"]) or "—")
            st.markdown("**Analytical Skills missing from resume**")
            st.write(", ".join(missing["Analytical"]) or "—")
            st.markdown("**Soft Skills missing from resume**")
            st.write(", ".join(missing["Soft"]) or "—")

    with st.expander("View extracted skills"):
        st.markdown("**Technical Skills**")
        st.write(", ".join(technical) or "—")
        st.markdown("**Analytical Skills**")
        st.write(", ".join(analytical) or "—")
        st.markdown("**Soft Skills**")
        st.write(", ".join(soft) or "—")


def _display_summary_page(text: str):
    st.markdown("### Resume Evaluation")
    st.write(text)


def _display_match_page(text: str):
    st.markdown("### Match Analysis")
    st.write(text)


# --- Main Actions -------------------------------------------------------------
if submit_summary:
    if not _not_ready_msg():
        with st.spinner("Analyzing resume…"):
            pdf_content = extract_pdf_first_page_as_image(st.session_state.resume_file)
            summary = get_gemini_response(job_description, pdf_content, PROMPT_RESUME_SUMMARY)

        with tabs[0]:
            _display_summary_page(summary)

if submit_keywords:
    if not _not_ready_msg():
        with st.spinner("Extracting keywords…"):
            pdf_content = extract_pdf_first_page_as_image(st.session_state.resume_file)
            keywords = get_gemini_response_keywords(
                job_description, pdf_content, PROMPT_KEYWORDS_JSON
            )
            job_keywords = get_gemini_response_keywords_from_text(
                job_description, PROMPT_JD_KEYWORDS_JSON
            )

        with tabs[1]:
            _display_keywords_page(keywords, job_keywords)

if submit_match:
    if not _not_ready_msg():
        with st.spinner("Calculating match score…"):
            pdf_content = extract_pdf_first_page_as_image(st.session_state.resume_file)
            match_text = get_gemini_response(job_description, pdf_content, PROMPT_PERCENTAGE_MATCH)

        with tabs[2]:
            _display_match_page(match_text)
