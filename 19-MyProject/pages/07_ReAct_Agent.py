from attr import dataclass
import streamlit as st
from langchain_core.messages.chat import ChatMessage
from langchain_teddynote import logging
from react_agent import create_agent_executor
from dotenv import load_dotenv
from stream_handler import stream_handler, format_search_result
from custom_tools import WebSearchTool

# API KEY 정보 로드
load_dotenv()

# 프로젝트 이름 설정
logging.langsmith("ReAct Agent")

st.title("ReAct Agent 💬")

## ✅ 대화 기록 저장을 위한 세션 상태 초기화 (올바른 구조 유지)
if "messages" not in st.session_state or not isinstance(st.session_state["messages"], list): ## 리스트인지 확인 후 새 리스트로 설정
    st.session_state["messages"] = []

# ✅ ReAct Agent 초기화
if "react_agent" not in st.session_state:
    st.session_state["react_agent"] = None

# ✅ include_domains 초기화
if "include_domains" not in st.session_state:
    st.session_state["include_domains"] = []

# 🔹 사이드바 생성
with st.sidebar:
    clear_btn = st.button("대화 초기화")
    selected_model = st.selectbox("LLM 선택", ["gpt-4o", "gpt-4o-mini"], index=0)
    search_result_count = st.slider("검색 결과 개수", min_value=1, max_value=10, value=3)

    st.subheader("검색 도메인 설정")
    search_topic = st.selectbox("검색 주제", ["general", "news"], index=0)
    new_domain = st.text_input("추가할 도메인 입력")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("도메인 추가", key="add_domain"):
            if new_domain and new_domain not in st.session_state["include_domains"]:
                st.session_state["include_domains"].append(new_domain)

    st.write("등록된 도메인 목록:")
    for idx, domain in enumerate(st.session_state["include_domains"]):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.text(domain)
        with col2:
            if st.button("삭제", key=f"del_{idx}"):
                st.session_state["include_domains"].pop(idx)
                st.rerun()

    apply_btn = st.button("설정 완료", type="primary")


# ✅ 메시지 데이터 클래스 정의
@dataclass
class ChatMessageWithType:
    chat_message: ChatMessage
    msg_type: str
    tool_name: str


# ✅ 이전 대화 출력 함수 (수정 완료)
def print_messages():
    for message in st.session_state["messages"]:
        ## ✅ 리스트인지 확인 후 개별 요소 접근
        if isinstance(message, list): #message가 리스트라면 - 내부 요소 sub_message 하나씩 확인하여 msg_type 있는 경우 출력
            for sub_message in message:
                if hasattr(sub_message, "msg_type"):
                    display_message(sub_message)
        else:
            if hasattr(message, "msg_type"): #message가 리스트가 아니라면 - 직접 msg_type을 확인하고 출력
                display_message(message)


# ✅ 개별 메시지 출력 함수 (중복 코드 제거)
def display_message(message):
    if message.msg_type == "text":
        st.chat_message(message.chat_message.role).write(
            message.chat_message.content
        )
    elif message.msg_type == "tool_result":
        with st.expander(f"✅ {message.tool_name}"):
            st.markdown(message.chat_message.content)


# ✅ 새로운 메시지를 추가하는 함수 (리스트 처리 문제 해결)
def add_message(role, message, msg_type="text", tool_name=""):
    new_message = ChatMessageWithType(
        chat_message=ChatMessage(role=role, content=message),
        msg_type=msg_type,
        tool_name=tool_name,
    )

    if isinstance(st.session_state["messages"], list):
        st.session_state["messages"].append(new_message)
    else:
        st.session_state["messages"] = [new_message]  ## 만약 비정상적인 값이면 새 리스트 생성


# ✅ 초기화 버튼이 눌리면 대화 기록 삭제
if clear_btn:
    st.session_state["messages"] = []

# ✅ 이전 대화 기록 출력
print_messages()

# ✅ 사용자 입력 처리
user_input = st.chat_input("궁금한 내용을 물어보세요!")

# ✅ 경고 메시지를 띄우기 위한 빈 공간
warning_msg = st.empty()

# ✅ 설정 버튼이 눌리면 ReAct Agent 설정
if apply_btn:
    tool = WebSearchTool().create()
    tool.max_results = search_result_count
    tool.include_domains = st.session_state["include_domains"]
    tool.topic = search_topic
    st.session_state["react_agent"] = create_agent_executor(
        model_name=selected_model,
        tools=[tool],
    )

# ✅ 사용자의 입력이 들어오면 실행
if user_input:
    agent = st.session_state["react_agent"]

    if agent is not None:
        config = {"configurable": {"thread_id": "abc123"}}
        system_message = "한글로 친절하게 답변하세요. 최대한 자세하게 전문적인 어조로 답변하세요"

        st.chat_message("user").write(user_input)

        with st.chat_message("assistant"):
            container = st.empty()
            ai_answer = ""

            container_messages, tool_args, agent_answer = stream_handler(
                container,
                agent,
                {
                    "messages": [
                        ("human", system_message + "\n\n" + user_input),
                    ]
                },
                config,
            )

            # ✅ 대화기록 저장
            add_message("user", user_input)
            for tool_arg in tool_args:
                add_message(
                    "assistant",
                    tool_arg["tool_result"],
                    "tool_result",
                    tool_arg["tool_name"],
                )
            add_message("assistant", agent_answer)
    else:
        warning_msg.warning("사이드바에서 설정을 완료해주세요.")
