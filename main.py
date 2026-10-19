
import io
import json
import zipfile

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------
st.set_page_config(
    page_title="전국 고령화 단계구분도",
    page_icon="🗺️",
    layout="wide",
)

POPULATION_URL = (
    "https://raw.githubusercontent.com/"
    "cns0909/population/main/population_ts_yearly_gender.zip"
)

GEOJSON_URL = (
    "https://raw.githubusercontent.com/"
    "cns0909/population/main/sigungu_kr.geojson.txt"
)

st.title("🗺️ 전국 고령화 단계구분도")
st.caption("2026년 6월 기준 · 전국 시군구별 65세 이상 인구 비율")


# --------------------------------------------------
# 데이터 다운로드 및 캐싱
# --------------------------------------------------
@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    response = requests.get(POPULATION_URL, timeout=120)
    response.raise_for_status()

    # ZIP 내부의 CSV를 읽음
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not name.startswith("__MACOSX/")
        ]

        if not csv_files:
            raise ValueError("ZIP 파일 안에서 CSV를 찾지 못했습니다.")

        # 일반적으로 CSV 파일 하나가 들어 있으므로 첫 파일 사용
        with archive.open(csv_files[0]) as file:
            df = pd.read_csv(file, dtype=str, low_memory=False)

    # 열 이름 공백 정리
    df.columns = df.columns.astype(str).str.strip()

    required = {"연도", "코드"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"인구 데이터에 필요한 열이 없습니다: {sorted(missing)}"
        )

    # 연도와 코드는 문자열로 처리
    df["연도"] = df["연도"].astype(str).str.strip()
    df["코드"] = df["코드"].str.strip()

    # 2026년 자료만 선택
    df = df[df["연도"].str.startswith("2026")].copy()

    if df.empty:
        raise ValueError("인구 데이터에서 2026년 자료를 찾지 못했습니다.")

    # 나이별 인구 열의 쉼표 제거 후 숫자로 변환
    population_cols = [
        col for col in df.columns
        if col.startswith("계_")
    ]

    if not population_cols:
        raise ValueError("'계_'로 시작하는 인구 열을 찾지 못했습니다.")

    for col in population_cols:
        df[col] = pd.to_numeric(
            df[col].str.replace(",", "", regex=False),
            errors="coerce",
        ).fillna(0)

    # 65세 이상: 계_65세부터 계_100세 이상까지
    elderly_cols = []
    for col in population_cols:
        age = col.removeprefix("계_").strip()

        if age == "100세 이상":
            elderly_cols.append(col)
            continue

        # '65세', '66세' ... 형태만 포함
        if age.endswith("세"):
            number = age[:-1]
            if number.isdigit() and int(number) >= 65:
                elderly_cols.append(col)

    if not elderly_cols:
        raise ValueError("65세 이상 인구 열을 찾지 못했습니다.")

    # 동 코드의 앞 5자리로 시군구 코드 생성
    df["시군구코드"] = df["코드"].str[:5]

    # 비정상적인 코드 제외
    df = df[df["시군구코드"].str.fullmatch(r"\d{5}", na=False)].copy()

    # 전체 인구: 모든 '계_' 열 합계
    # 고령 인구: 65세 이상 '계_' 열 합계
    df["전체인구"] = df[population_cols].sum(axis=1)
    df["고령인구"] = df[elderly_cols].sum(axis=1)

    # 시군구별 합산
    result = (
        df.groupby("시군구코드", as_index=False)
        .agg(
            전체인구=("전체인구", "sum"),
            고령인구=("고령인구", "sum"),
        )
    )

    # 전체 인구가 0인 지역은 비율 계산에서 제외
    result = result[result["전체인구"] > 0].copy()
    result["고령화율"] = (
        result["고령인구"] / result["전체인구"] * 100
    )

    return result


@st.cache_data(show_spinner="시군구 경계 지도를 불러오는 중...")
def load_geojson():
    response = requests.get(GEOJSON_URL, timeout=120)
    response.raise_for_status()

    geojson = response.json()

    if "features" not in geojson:
        raise ValueError("GeoJSON에 features 항목이 없습니다.")

    # 경계 코드도 문자열 5자리로 통일
    for feature in geojson["features"]:
        properties = feature.get("properties", {})
        code = str(properties.get("코드", "")).strip()

        # 숫자로 저장된 코드도 앞자리 0을 보존하도록 정리
        if code.endswith(".0"):
            code = code[:-2]

        properties["코드"] = code.zfill(5)
        feature["properties"] = properties

    return geojson


# --------------------------------------------------
# 데이터 불러오기
# --------------------------------------------------
try:
    population = load_population()
    geojson = load_geojson()
except Exception as error:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {error}")
    st.info(
        "GitHub 파일 주소, CSV 열 이름, 네트워크 연결을 확인해 주세요."
    )
    st.stop()


# --------------------------------------------------
# 지도 데이터 결합: 지역 이름이 아닌 코드로 매칭
# --------------------------------------------------
boundary_codes = {
    feature["properties"]["코드"]
    for feature in geojson["features"]
}

map_df = population[
    population["시군구코드"].isin(boundary_codes)
].copy()

# 경계에 없는 지역은 지도에 표시되지 않으므로 확인 가능하게 안내
population_codes = set(population["시군구코드"])
unmatched = population_codes - boundary_codes

if map_df.empty:
    st.error(
        "인구 데이터와 경계 GeoJSON의 코드가 일치하지 않습니다. "
        "두 파일의 코드 형식을 확인해 주세요."
    )
    st.stop()

# 단계구분도 색상 구간
# 고령화율이 높을수록 더 진한 색상
color_scale = [
    [0.00, "#fff7bc"],
    [0.25, "#fec44f"],
    [0.50, "#fe9929"],
    [0.75, "#ec7014"],
    [1.00, "#993404"],
]

# 시군구 코드를 키로 지도에 인구 통계 결합
fig = px.choropleth(
    map_df,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="고령화율",
    color_continuous_scale=color_scale,
    range_color=(0, max(30, float(map_df["고령화율"].max()))),
    hover_name=None,
    hover_data={
        "시군구코드": False,
        "전체인구": False,
        "고령인구": False,
        "고령화율": ":.2f",
    },
    labels={"고령화율": "고령화율(%)"},
)

# 이름은 경계 GeoJSON의 '시군구' 속성에서 가져옴
name_by_code = {
    feature["properties"]["코드"]: feature["properties"].get(
        "시군구", "이름 없음"
    )
    for feature in geojson["features"]
}

map_df["시군구명"] = map_df["시군구코드"].map(name_by_code)

# 마우스 오버에 시군구명과 고령화율 표시
fig.update_traces(
    customdata=map_df[["시군구명"]].to_numpy(),
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "고령화율: %{z:.2f}%"
        "<extra></extra>"
    ),
    marker_line_color="white",
    marker_line_width=0.45,
)

# 배경 지도 타일 없이 경계만 표시
fig.update_geos(
    visible=False,
    fitbounds="locations",
    showcountries=False,
    showcoastlines=False,
    showland=False,
    showframe=False,
)

fig.update_layout(
    height=850,
    margin=dict(l=0, r=0, t=35, b=0),
    coloraxis_colorbar=dict(
        title="고령화율(%)",
        ticksuffix="%",
        thickness=18,
    ),
)

# --------------------------------------------------
# 지표 카드
# --------------------------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("지도 표시 시군구", f"{len(map_df):,}개")
col2.metric(
    "최고 고령화율",
    f"{map_df['고령화율'].max():.2f}%",
)
col3.metric(
    "최저 고령화율",
    f"{map_df['고령화율'].min():.2f}%",
)

st.plotly_chart(fig, use_container_width=True)

if unmatched:
    st.warning(
        f"인구 데이터에는 있지만 지도 경계와 코드가 일치하지 않는 "
        f"지역이 {len(unmatched)}개 있습니다."
    )

# --------------------------------------------------
# 지역별 통계 표
# --------------------------------------------------
with st.expander("시군구별 고령화율 표 보기"):
    table = map_df[
        ["시군구명", "시군구코드", "전체인구", "고령인구", "고령화율"]
    ].copy()

    table = table.sort_values("고령화율", ascending=False)
    table["고령화율"] = table["고령화율"].map(
        lambda x: f"{x:.2f}%"
    )

    table = table.rename(
        columns={
            "시군구명": "시군구",
            "시군구코드": "코드",
            "전체인구": "전체 인구",
            "고령인구": "65세 이상 인구",
            "고령화율": "고령화율",
        }
    )

    st.dataframe(table, use_container_width=True, hide_index=True)

st.caption(
    "자료: 제공된 인구 데이터 및 시군구 경계 GeoJSON. "
    "고령화율은 65세 이상 인구를 전체 인구로 나누어 계산했습니다."
)
