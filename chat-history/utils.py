from langchain_core.callbacks.base import BaseCallbackHandler
import streamlit as st

# 스트리밍은 그냥 템플릿으로
class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text = ""):
        self.container = container
        self.text = initial_text
        
    def on_llm_new_token(self, token:str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text)

def print_messages():
# 이전 대화기록을 출력해주는 코드
    if "messages" in st.session_state and len(st.session_state["messages"]) > 0:
        for chat_message in st.session_state["messages"]: #튜플 형식이 아닌 ChatMessage가 담기게 됨
            st.chat_message(chat_message.role).write(chat_message.content)