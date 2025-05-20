import requests
import os
import pandas as pd
import xml.etree.ElementTree as et
from io import BytesIO
from zipfile import ZipFile
import re
import streamlit as st

class DartAPI:
    BASE_URL = "https://opendart.fss.or.kr/api"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("DART_API_KEY")
        if not self.api_key:
            raise ValueError("DART API Key가 설정되어 있지 않습니다.")
        self.corp_code_df = self._load_corp_code_df()

    def _load_corp_code_df(self):
        """OpenDART에서 corpCode.xml을 받아와 DataFrame으로 반환"""
        u = requests.get(f'{self.BASE_URL}/corpCode.xml', params={'crtfc_key': self.api_key})
        zipfile_obj = ZipFile(BytesIO(u.content))
        xml_str = zipfile_obj.read('CORPCODE.xml').decode('utf-8')
        xroot = et.fromstring(xml_str)
        df_cols = ["corp_code", "corp_name", "stock_code", "modify_date"]
        rows = []
        for node in xroot:
            res = []
            for el in df_cols:
                res.append(node.find(el).text if node.find(el) is not None else None)
            rows.append({df_cols[i]: res[i] for i in range(len(df_cols))})
        df = pd.DataFrame(rows, columns=df_cols)
        return df

    def find_corp_code(self, corp_name):
        """
        기업명(일부 포함)으로 corp_code 반환 (정확히 일치 > 다양한 변형 일치 > 일부 포함 시 상장사 우선 > 후보 여러 개면 안내)
        한글/영문 혼용(예: 네이버/NAVER)도 후보에 포함
        """
        def clean(name):
            return re.sub(r"[\s\(\)\'\"\.,주식회사]", "", name).lower()
        corp_name_clean = clean(corp_name)
        df_clean = self.corp_code_df.copy()
        df_clean['corp_name_clean'] = df_clean['corp_name'].apply(clean)

        # 1. 정확히 일치(상장사 우선)
        exact = df_clean[(df_clean['corp_name_clean'] == corp_name_clean) & (df_clean['stock_code'].notnull()) & (df_clean['stock_code'] != '')]
        if not exact.empty:
            return exact.iloc[0].corp_code

        # 2. 다양한 변형 일치(상장사 우선)
        alt_variants = [
            corp_name,
            corp_name + '(주)',
            corp_name + '주식회사',
            corp_name.upper(),
            corp_name.lower(),
            corp_name.replace(' ', ''),
            corp_name + 'CORP',
            corp_name + 'CORPORATION',
            corp_name + 'INC',
            corp_name + 'INC.',
            corp_name + 'CO.,LTD',
            corp_name + 'CO',
            corp_name + 'LIMITED',
            corp_name + 'COMPANY',
            corp_name + '주식회사',
            corp_name + '(주)',
        ]
        for alt in alt_variants:
            alt_clean = clean(alt)
            exact = df_clean[(df_clean['corp_name_clean'] == alt_clean) & (df_clean['stock_code'].notnull()) & (df_clean['stock_code'] != '')]
            if not exact.empty:
                return exact.iloc[0].corp_code

        # 3. 일부 포함(상장사 우선)
        result = df_clean[(df_clean['corp_name_clean'].str.contains(corp_name_clean, na=False)) & (df_clean['stock_code'].notnull()) & (df_clean['stock_code'] != '')]
        if len(result) == 1:
            return result.iloc[0].corp_code
        elif len(result) > 1:
            candidates = result['corp_name'].tolist()[:3]
            return f"입력하신 기업명과 유사한 기업이 여러 개 있습니다: {candidates} 중에서 선택하거나 한글/영문으로 바꿔서 입력을 다시 시도해 보세요."

        # 4. 완전히 실패(상장사 중 매칭 없음)
        return "입력하신 기업명을 찾을 수 없습니다. 한글/영문으로 바꿔서 입력을 다시 시도해 보세요."

    def get_company_info(self, corp_code):
        """기업 개황 조회"""
        url = f"{self.BASE_URL}/company.json"
        params = {"crtfc_key": self.api_key, "corp_code": corp_code}
        res = requests.get(url, params=params)
        return res.json()

    def get_financial_statements(self, corp_code, bsns_year, reprt_code="11011", fs_div="CFS"):
        """재무제표(단일회사 주요재무) 조회"""
        url = f"{self.BASE_URL}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,  # 11011: 사업보고서, 11012: 반기, 11013: 1분기, 11014: 3분기
            "fs_div": fs_div,
        }
        res = requests.get(url, params=params)
        return res.json()

    def get_notice_list(self, corp_code, bgn_de, end_de):
        """공시목록 조회"""
        url = f"{self.BASE_URL}/list.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,  # YYYYMMDD
            "end_de": end_de,
        }
        res = requests.get(url, params=params)
        return res.json()

    # corp_code(고유코드) 매핑은 별도 유틸 함수로 구현 필요 (공식문서 참고) 

    def display_result(self, answer, last_obs):
        if isinstance(answer, str) and answer.endswith(".png") and os.path.exists(answer):
            st.image(answer)
        elif not answer:
            if last_obs:
                st.write(last_obs)
            else:
                st.warning("결과가 없습니다. 한글/영문으로 바꿔서 입력을 다시 시도해 보세요.")
        elif re.match(r"[A-Za-z]", answer.strip()):
            # answer가 영어로 시작하면 대신 last_obs(툴 반환값) 출력
            if last_obs:
                st.write(last_obs)
            else:
                st.write(answer)
        else:
            st.write(answer) 