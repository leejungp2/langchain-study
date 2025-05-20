import re
from langchain.tools import tool
from dart_api import DartAPI
import pandas as pd
import PyPDF2
import yaml
import os


def parse_financial_query(query: str):
    """
    자연어에서 기업명, 연도, 보고서 종류를 파싱합니다.
    예시 입력: '삼성전자 2023 사업보고서'
    반환: {'corp_name': '삼성전자', 'year': '2023', 'report_type': '사업보고서'}
    """
    year_match = re.search(r'(\d{4})', query)
    year = year_match.group(1) if year_match else "2023"
    report_types = ['사업보고서', '반기보고서', '분기보고서']
    report_type = next((rt for rt in report_types if rt in query), "사업보고서")
    corp_name = query.split(str(year))[0].strip() if year else query
    return {
        'corp_name': corp_name,
        'year': year,
        'report_type': report_type
    }

@tool
def get_company_info_tool(input: str) -> str:
    """
    기업명을 입력하면 DART API에서 기업 정보를 반환합니다.
    입력 예시: input='삼성전자'
    출력 예시: '기업명: 삼성전자, 종목코드: 005930, ...'
    """
    def clean(name):
        return re.sub(r"[\s\(\)\'\"\.,주식회사]", "", name).lower()
    company_name = input.strip()
    dart = DartAPI()
    df = dart.corp_code_df.copy()
    df['corp_name_clean'] = df['corp_name'].apply(clean)
    input_clean = clean(company_name)
    # 상장사만 필터링
    candidates = df[(df['stock_code'].notnull()) & (df['stock_code'] != '')]
    # 정확히 일치하는 상장사만
    exact = candidates[candidates['corp_name_clean'] == input_clean]
    if not exact.empty:
        corp_code = exact.iloc[0]['corp_code']
        info = dart.get_company_info(corp_code)
        if info.get('status') == '000':
            keys = ["corp_name", "stock_code", "ceo_nm", "corp_cls", "adres"]
            result = []
            for k in keys:
                if k in info:
                    result.append(f"• {k}: {info[k]}")
            return '\n'.join(result) if result else str(info)
        else:
            return "입력하신 기업명을 찾을 수 없습니다. 한글/영문으로 바꿔서 입력을 다시 시도해 보세요."
    # 정확히 일치하는 상장사가 없으면, 유사 후보 안내만
    # 부분 포함(유사) 후보 리스트 안내
    similar = candidates[candidates['corp_name_clean'].str.contains(input_clean, na=False)]
    if not similar.empty:
        candidate_names = similar['corp_name'].tolist()[:3]
        return (
            f"DART API에서 '{company_name}'의 기업 정보를 찾을 수 없습니다. "
            f"유사한 기업명 후보: {candidate_names} 중에서 선택하거나, "
            "공식 웹사이트나 금융 관련 포털 사이트에서 기본 정보를 확인해 보세요."
        )
    return "입력하신 기업명을 찾을 수 없습니다. 한글/영문으로 바꿔서 입력을 다시 시도해 보세요."

@tool
def get_financial_statements_tool(input: str) -> str:
    """
    기업명, 연도, 보고서 종류가 포함된 자연어 문장을 입력하면 DART API에서 재무제표를 반환합니다.
    입력 예시: input='삼성전자 2023 사업보고서'
    출력 예시: '매출액: 1000, 영업이익: 200, ...'
    """
    query = input
    parsed = parse_financial_query(query)
    dart = DartAPI()
    corp_code = dart.find_corp_code(parsed['corp_name'])
    if corp_code:
        data = dart.get_financial_statements(corp_code, bsns_year=parsed['year'])
        if not data.get('list'):
            return "재무 데이터가 없습니다. (최종 답변)"
        main_accounts = ["매출액", "영업이익", "당기순이익"]
        result = []
        for item in data['list']:
            if item.get('account_nm') in main_accounts:
                result.append(f"{item['account_nm']}: {item['thstrm_amount']}")
        return '\n'.join(result) if result else "주요 계정 데이터가 없습니다. (최종 답변)"
    else:
        return "기업명을 찾을 수 없습니다. (최종 답변)"

@tool
def analyze_csv_tool(input: str) -> str:
    """
    CSV 파일 경로를 입력하면 주요 통계와 컬럼 정보를 반환합니다.
    입력 예시: input='data/재무정보.csv'
    출력 예시: '컬럼: [...], 기초 통계: ...'
    """
    file_path = input
    df = pd.read_csv(file_path)
    return f"컬럼: {list(df.columns)}\n기초 통계:\n{df.describe().to_string()}"

@tool
def summarize_pdf_tool(input: str) -> str:
    """
    PDF 파일 경로를 입력하면 앞부분 텍스트 요약을 반환합니다.
    입력 예시: input='data/사업보고서.pdf'
    출력 예시: '요약 텍스트 ...'
    """
    file_path = input
    try:
        pdf_reader = PyPDF2.PdfReader(file_path)
    except FileNotFoundError:
        return f"파일이 존재하지 않습니다: {file_path}"
    all_text = ""
    for i, page in enumerate(pdf_reader.pages):
        text = page.extract_text()
        if text:
            all_text += text
            if i >= 1:
                break
    return all_text[:1000] + ("..." if len(all_text) > 1000 else "")

@tool
def plot_financials_tool(input: str) -> str:
    """
    기업명, 연도, 보고서 종류가 포함된 자연어 문장을 입력하면 주요 재무제표를 바 차트로 시각화합니다.
    입력 예시: input='삼성전자 2023 사업보고서'
    출력 예시: '.cache/삼성전자_2023_fin.png'
    """
    import matplotlib.pyplot as plt
    query = input
    parsed = parse_financial_query(query)
    dart = DartAPI()
    corp_code = dart.find_corp_code(parsed['corp_name'])
    if not corp_code:
        return "기업명을 찾을 수 없습니다. (최종 답변)"
    fs = dart.get_financial_statements(corp_code, bsns_year=parsed['year'])
    if not fs.get("list"):
        return "재무 데이터가 없습니다. (최종 답변)"
    df = pd.DataFrame(fs["list"])
    main_accounts = ["매출액", "영업이익", "당기순이익"]
    df_main = df[df["account_nm"].isin(main_accounts)]
    if df_main.empty:
        return "주요 계정 데이터가 없습니다. (최종 답변)"
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

def load_general_prompt():
    """prompts/general.yaml에서 프롬프트 템플릿을 불러옴"""
    prompt_path = os.path.join(os.path.dirname(__file__), "../prompts/general.yaml")
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["template"] 