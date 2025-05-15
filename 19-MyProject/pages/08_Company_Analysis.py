import streamlit as st
from dart_api import DartAPI
import os
import matplotlib.pyplot as plt
import pandas as pd
import PyPDF2
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent
from dotenv import load_dotenv
import re

# .env에서 API 키 불러오기
load_dotenv()

# DART API 키 안내 메시지
if not os.getenv("DART_API_KEY"):
    st.warning(".env 파일에 DART_API_KEY를 반드시 입력하세요! 예시: DART_API_KEY=여기에_발급받은_키")

# 자연어에서 기업명, 연도, 보고서 종류 파싱 함수

def parse_financial_query(query: str):
    """
    예시 입력: '삼성전자 2023 사업보고서'
    반환: {'corp_name': '삼성전자', 'year': '2023', 'report_type': '사업보고서'}
    """
    # 연도 추출 (4자리 숫자)
    year_match = re.search(r'(\d{4})', query)
    year = year_match.group(1) if year_match else "2023"

    # 보고서 종류 추출 (사업보고서, 반기보고서, 분기보고서 등)
    report_types = ['사업보고서', '반기보고서', '분기보고서']
    report_type = next((rt for rt in report_types if rt in query), "사업보고서")

    # 기업명 추출 (연도 앞까지)
    corp_name = query.split(str(year))[0].strip() if year else query

    return {
        'corp_name': corp_name,
        'year': year,
        'report_type': report_type
    }

# 1. DART API Tool
@tool
def get_company_info_tool(company_name: str) -> dict:
    """기업명을 입력하면 DART API에서 기업 정보를 반환합니다."""
    dart = DartAPI()
    corp_code = dart.find_corp_code(company_name)
    if corp_code:
        return dart.get_company_info(corp_code)
    else:
        return {"error": "기업명을 찾을 수 없습니다."}

@tool
def get_financial_statements_tool(query: str) -> dict:
    """
    기업명, 연도, 보고서 종류가 포함된 자연어 문장을 입력하면 DART API에서 재무제표를 반환합니다.
    예: '삼성전자 2023 사업보고서'
    """
    parsed = parse_financial_query(query)
    dart = DartAPI()
    corp_code = dart.find_corp_code(parsed['corp_name'])
    if corp_code:
        # report_type은 필요시 추가 활용
        return dart.get_financial_statements(corp_code, bsns_year=parsed['year'])
    else:
        return {"error": "기업명을 찾을 수 없습니다."}

# 2. CSV 분석 Tool
@tool
def analyze_csv_tool(file_path: str) -> str:
    """CSV 파일 경로를 입력하면 주요 통계와 컬럼 정보를 반환합니다."""
    df = pd.read_csv(file_path)
    return f"컬럼: {list(df.columns)}\n기초 통계:\n{df.describe().to_string()}"

# 3. PDF 요약 Tool
@tool
def summarize_pdf_tool(file_path: str) -> str:
    """PDF 파일 경로를 입력하면 앞부분 텍스트 요약을 반환합니다."""
    pdf_reader = PyPDF2.PdfReader(file_path)
    all_text = ""
    for i, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        if text:
            all_text += text
            if i >= 1:
                break
    return all_text[:1000] + ("..." if len(all_text) > 1000 else "")

# 4. 시각화 Tool (예시: 매출액, 영업이익, 당기순이익)
@tool
def plot_financials_tool(query: str) -> str:
    """
    기업명, 연도, 보고서 종류가 포함된 자연어 문장을 입력하면 주요 재무제표를 바 차트로 시각화합니다.
    예: '삼성전자 2023 사업보고서'
    """
    parsed = parse_financial_query(query)
    dart = DartAPI()
    corp_code = dart.find_corp_code(parsed['corp_name'])
    if not corp_code:
        return "기업명을 찾을 수 없습니다."
    fs = dart.get_financial_statements(corp_code, bsns_year=parsed['year'])
    if not fs.get("list"):
        return "재무 데이터가 없습니다."
    df = pd.DataFrame(fs["list"])
    main_accounts = ["매출액", "영업이익", "당기순이익"]
    df_main = df[df["account_nm"].isin(main_accounts)]
    if df_main.empty:
        return "주요 계정 데이터가 없습니다."
    df_main["thstrm_amount"] = df_main["thstrm_amount"].str.replace(",", "").astype(float)
    fig, ax = plt.subplots()
    ax.bar(df_main["account_nm"], df_main["thstrm_amount"])
    ax.set_ylabel("금액(원)")
    ax.set_title(f"{parsed['year']}년 주요 재무제표")
    plt.tight_layout()
    img_path = f".cache/{parsed['corp_name']}_{parsed['year']}_fin.png"
    fig.savefig(img_path)
    plt.close(fig)
    return img_path

# LangChain Agent 세팅
TOOLS = [
    get_company_info_tool,
    get_financial_statements_tool,
    analyze_csv_tool,
    summarize_pdf_tool,
    plot_financials_tool,
]
llm = ChatOpenAI(model="gpt-4o")
agent = initialize_agent(TOOLS, llm, agent_type="openai-functions", verbose=True)

# Streamlit UI
st.title("AI 기업 분석 (하이브리드)")

# 1. 자연어 챗봇
st.header("AI 챗봇")
user_input = st.text_input("AI에게 질문하세요!")
if user_input:
    answer = agent.run(user_input)
    # 이미지 파일 경로 반환 시 시각화
    if isinstance(answer, str) and answer.endswith(".png") and os.path.exists(answer):
        st.image(answer)
    else:
        st.write(answer)

st.divider()

# 2. UI 기반 주요 기능
st.header("빠른 기능")
company_list = ["삼성전자", "SK하이닉스", "LG화학"]
selected_company = st.selectbox("기업 선택", company_list)
if st.button("재무제표 보기"):
    corp_code = DartAPI().find_corp_code(selected_company)
    fs = DartAPI().get_financial_statements(corp_code, bsns_year="2023")
    st.subheader(f"{selected_company} 2023년 재무제표")
    st.json(fs)

uploaded_file = st.file_uploader("자료 업로드 (PDF, CSV)", type=["pdf", "csv"])
if uploaded_file:
    st.success("파일 업로드 완료!")
    if uploaded_file.type == "text/csv" or uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
        st.subheader("CSV 데이터 미리보기")
        st.dataframe(df)
        st.write("컬럼 정보:", list(df.columns))
        st.write("기초 통계:")
        st.write(df.describe())
    elif uploaded_file.type == "application/pdf" or uploaded_file.name.endswith(".pdf"):
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        num_pages = len(pdf_reader.pages)
        st.write(f"PDF 페이지 수: {num_pages}")
        all_text = ""
        for i, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            if text:
                all_text += text
                if i < 2:
                    st.subheader(f"페이지 {i+1} 미리보기")
                    st.write(text[:1000])
        if num_pages > 2:
            st.info("...이하 생략(전체 텍스트는 LLM 분석 등에서 활용 가능)") 