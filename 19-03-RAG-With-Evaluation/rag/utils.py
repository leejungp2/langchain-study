# base.py에서 문서 포맷을 처리할 때 사용
# format_docs(docs) : 문서를 XML 형식으로 변환하여 정리
def format_docs(docs):
    return "\n".join(
        [
            f"<document><content>{doc.page_content}</content><source>{doc.metadata['source']}</source><page>{int(doc.metadata['page'])+1}</page></document>"
            for doc in docs
        ]
    )
