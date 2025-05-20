import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from dotenv import load_dotenv
import pandas as pd
import PyPDF2
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent
from dart_api import DartAPI
import re
from deep_translator import GoogleTranslator

# --- 분리된 프론트엔드/백엔드 함수 import ---
from frontend.company_analysis_ui import render_info_message, render_search_box, render_financial_table
from backend.company_analysis_tools import (
    get_company_info_tool,
    get_financial_statements_tool,
    analyze_csv_tool,
    summarize_pdf_tool,
    plot_financials_tool,
    parse_financial_query
)

# .env에서 API 키 불러오기
load_dotenv()

# DART API 키 안내 메시지
if not os.getenv("DART_API_KEY"):
    st.warning(".env 파일에 DART_API_KEY를 반드시 입력하세요! 예시: DART_API_KEY=여기에_발급받은_키")

# LangChain Agent 세팅
TOOLS = [
    get_company_info_tool,
    get_financial_statements_tool,
    analyze_csv_tool,
    summarize_pdf_tool,
    plot_financials_tool,
]
llm = ChatOpenAI(model="gpt-4o", temperature=0)
agent = initialize_agent(
    TOOLS,
    llm,
    agent_type="openai-functions",
    verbose=True,
    handle_parsing_errors=True,  # 파싱 에러 발생 시 LLM 답변을 그대로 반환
    max_iterations=5,  # 반복 횟수 더 늘림
    agent_kwargs={
        "system_message": (
            "당신은 다양한 툴을 사용할 수 있는 AI 비서입니다. "
            "툴에서 '찾을 수 없습니다' 또는 '유사한 기업명 후보'가 반환되면, "
            "그 메시지를 바로 사용자에게 Final Answer로 보여주세요. "
            "모든 답변과 설명(Thought)은 반드시 한국어로 작성하세요. "
            "툴을 사용할 수 없는 경우에만 'Final Answer:'로 답변하세요. "
            "각 툴의 설명과 예시를 참고하세요.\n"
            "예시 질문: 삼성전자 2023년 재무제표 보여줘\n"
            "예시 툴 호출: get_financial_statements_tool(query='삼성전자 2023 사업보고서')\n"
        )
    }
)

# Streamlit UI
st.title("AI 기업 분석 (하이브리드)")

# 1. 자연어 챗봇
st.header("AI 챗봇")
render_info_message()
# 검색창 + 버튼 UI
user_input = st.text_input("AI에게 질문하세요!", key="ai_query_input")
search_clicked = st.button("검색")
if search_clicked and user_input:
    st.session_state['ai_query'] = user_input
if st.session_state.get('ai_query', ''):
    import traceback
    from langchain.schema import OutputParserException
    try:
        result = agent.invoke({"input": st.session_state['ai_query']}, return_intermediate_steps=True)
        answer = result["output"]
        steps = result.get("intermediate_steps", [])
        last_obs = None
        last_thought = None
        if steps:
            last_thought = steps[-1][0].log if hasattr(steps[-1][0], 'log') else None
            last_obs = steps[-1][1]
        if isinstance(answer, str) and answer.endswith(".png") and os.path.exists(answer):
            st.image(answer)
        elif not answer or (
            re.match(r"[A-Za-z]", answer.strip())
            or "unable" in answer.lower()
            or "not available" in answer.lower()
            or "cannot" in answer.lower()
            or "없습니다" in answer
        ):
            if last_obs:
                st.write(f"Observation(툴 반환값): {last_obs}")
            if last_thought:
                if re.match(r"[A-Za-z]", last_thought.strip()):
                    last_thought_kr = translate_to_ko(last_thought)
                else:
                    last_thought_kr = last_thought
                st.info(f"AI의 참고 설명:\n{last_thought_kr}\n\n한글/영문으로 바꿔서 입력을 다시 시도해 보세요.")
            elif not last_obs:
                st.warning("결과가 없습니다. 입력값을 다시 확인해 주세요.")
        else:
            st.write(answer)
    except OutputParserException:
        if 'last_obs' in locals() and last_obs:
            st.write(last_obs)
        if 'last_thought' in locals() and last_thought:
            if re.match(r"[A-Za-z]", last_thought.strip()):
                try:
                    last_thought_kr = GoogleTranslator(source='auto', target='ko').translate(last_thought)
                except Exception:
                    last_thought_kr = last_thought
            else:
                last_thought_kr = last_thought
            st.info(f"AI의 참고 설명:\n{last_thought_kr}\n\n한글/영문으로 바꿔서 입력을 다시 시도해 보세요.")
        else:
            st.error("에이전트가 반복 제한 또는 시간 제한에 걸렸습니다. 입력을 더 구체적으로 해보세요.")
    except Exception as e:
        st.error(f"에이전트 실행 중 오류 발생: {e}")
        st.text(traceback.format_exc())
    st.session_state['ai_query'] = ''

st.divider()

# 2. UI 기반 주요 기능
st.header("빠른 기능")
# 우리나라 10대 기업 리스트 + 직접 입력 옵션
company_list = [
    "직접 입력", "삼성전자", "SK하이닉스", "LG화학", "삼성바이오로직스", "현대차", "기아", "POSCO홀딩스", "삼성SDI", "NAVER", "카카오"
]
selected_company = st.selectbox("기업 선택", company_list)

# 직접 입력 선택 시 텍스트 입력창 노출
if selected_company == "직접 입력":
    custom_company = st.text_input("기업명을 직접 입력하세요")
    final_company = custom_company.strip() if custom_company else None
else:
    final_company = selected_company

# 연도 선택 추가 (2024, 2023, 2022, 2021)
year_list = ["2024", "2023", "2022", "2021"]
selected_year = st.selectbox("연도 선택", year_list, index=0)

if st.button("재무제표 보기"):
    if final_company:
        corp_code = DartAPI().find_corp_code(final_company)
        fs = DartAPI().get_financial_statements(corp_code, bsns_year=selected_year, fs_div="CFS")
        render_financial_table(fs, final_company, selected_year)
    else:
        st.warning("기업명을 입력하세요.")

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

def translate_to_ko(text):
    try:
        return GoogleTranslator(source='auto', target='ko').translate(text)
    except Exception as e:
        return f"[번역 실패] {text}" 