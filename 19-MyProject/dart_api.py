import requests
import os
import pandas as pd
import xml.etree.ElementTree as et
from io import BytesIO
from zipfile import ZipFile

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
        return pd.DataFrame(rows, columns=df_cols)

    def find_corp_code(self, corp_name):
        """기업명(일부 포함)으로 corp_code 반환"""
        result = self.corp_code_df[self.corp_code_df['corp_name'].str.contains(corp_name)]
        if not result.empty:
            return result.iloc[0].corp_code
        else:
            return None

    def get_company_info(self, corp_code):
        """기업 개황 조회"""
        url = f"{self.BASE_URL}/company.json"
        params = {"crtfc_key": self.api_key, "corp_code": corp_code}
        res = requests.get(url, params=params)
        return res.json()

    def get_financial_statements(self, corp_code, bsns_year, reprt_code="11011"):
        """재무제표(단일회사 주요재무) 조회"""
        url = f"{self.BASE_URL}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,  # 11011: 사업보고서, 11012: 반기, 11013: 1분기, 11014: 3분기
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