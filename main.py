
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# --------------------------------------------------
# 1. 기본 화면 설정
# --------------------------------------------------
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

# 따뜻한 크림색과 차분한 색상을 사용해 화면을 꾸며요.
st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFF9F0;
        color: #493D35;
    }

    h1, h2, h3 {
        color: #704C3B !important;
    }

    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F0DFCD;
        padding: 16px;
        border-radius: 12px;
    }

    div[data-testid="stSelectbox"] label {
        color: #704C3B;
        font-weight: 600;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏘️ 동네별 인구 피라미드")
st.write(
    "우리 동네의 연령별 인구를 살펴보세요. "
    "남자는 왼쪽, 여자는 오른쪽에 표시됩니다."
)


# --------------------------------------------------
# 2. 데이터 불러오기
# --------------------------------------------------
# GitHub의 파일 화면 주소가 아닌 실제 ZIP 파일 주소를 사용해요.
DATA_URL = (
    "https://raw.githubusercontent.com/"
    "cns0909/population/main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중이에요...")
def load_data():
    """ZIP 파일을 읽고 분석에 필요한 열을 정리해요."""

    # 압축 파일 안에 CSV 파일이 하나 들어 있다고 가정해요.
    # 한글 인코딩이 다를 경우를 대비해 두 가지 방법을 시도해요.
    try:
        df = pd.read_csv(
            DATA_URL,
            compression="zip",
            encoding="utf-8-sig",
        )
    except UnicodeDecodeError:
        df = pd.read_csv(
            DATA_URL,
            compression="zip",
            encoding="cp949",
        )

    # 열 이름 앞뒤에 붙은 불필요한 공백을 제거해요.
    df.columns = df.columns.astype(str).str.strip()

    # 연도 열 이름을 확인해요.
    year_candidates = ["연도", "년도", "기준연도", "기준년도"]
    year_col = next(
        (col for col in year_candidates if col in df.columns),
        None,
    )

    if year_col is None:
        raise ValueError(
            "연도 열을 찾을 수 없어요. "
            f"현재 열 이름: {list(df.columns[:15])}"
        )

    # 지역을 선택할 때 사용할 열이 있는지 확인해요.
    location_cols = ["시도", "시군구", "동"]
    missing_cols = [
        col for col in location_cols if col not in df.columns
    ]

    if missing_cols:
        raise ValueError(
            f"지역 열을 찾을 수 없어요: {missing_cols}"
        )

    # 연도에 쉼표 등이 있어도 숫자로 바꿀 수 있도록 정리해요.
    df[year_col] = pd.to_numeric(
        df[year_col].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )

    df = df.dropna(subset=[year_col]).copy()
    df[year_col] = df[year_col].astype(int)

    # 0세부터 99세까지, 마지막은 100세 이상으로 만들어요.
    ages = [f"{age}세" for age in range(100)]
    ages.append("100세 이상")

    # 연령별 남녀 인구 열이 실제로 존재하는지 확인해요.
    male_cols = [f"남_{age}" for age in ages]
    female_cols = [f"여_{age}" for age in ages]

    missing_age_cols = [
        col
        for col in male_cols + female_cols
        if col not in df.columns
    ]

    if missing_age_cols:
        raise ValueError(
            "일부 연령별 인구 열을 찾을 수 없어요. "
            f"누락된 열 예시: {missing_age_cols[:10]}"
        )

    # 인구 열에 쉼표가 있더라도 숫자로 변환해요.
    for col in male_cols + female_cols:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        ).fillna(0)

    # 지역 이름이 비어 있는 행은 선택 목록에서 제외해요.
    for col in location_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 나중에 사용할 열 이름과 나이 목록도 함께 돌려줘요.
    return df, year_col, ages, male_cols, female_cols


# --------------------------------------------------
# 3. 데이터 불러오기 및 오류 안내
# --------------------------------------------------
try:
    df, year_col, ages, male_cols, female_cols = load_data()

except Exception as e:
    st.error("데이터를 불러오지 못했어요.")
    st.info(
        "인터넷 연결, GitHub 파일 주소, CSV의 열 이름을 확인해 주세요."
    )
    st.code(str(e))
    st.stop()


# --------------------------------------------------
# 4. 가장 최신 연도만 선택하기
# --------------------------------------------------
latest_year = int(df[year_col].max())
df = df[df[year_col] == latest_year].copy()

st.caption(f"📅 분석 기준 연도: {latest_year}년")


# --------------------------------------------------
# 5. 시도 → 시군구 → 동 드롭다운 만들기
# --------------------------------------------------
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

# 첫 번째 드롭다운: 시도
sido_list = sorted(
    value for value in df["시도"].unique() if value
)

if not sido_list:
    st.warning("선택할 수 있는 시도 데이터가 없어요.")
    st.stop()

with col1:
    selected_sido = st.selectbox(
        "① 시도",
        options=sido_list,
    )

# 두 번째 드롭다운: 선택한 시도에 속한 시군구
sido_df = df[df["시도"] == selected_sido]

sigungu_list = sorted(
    value for value in sido_df["시군구"].unique() if value
)

if not sigungu_list:
    st.warning("선택한 시도에 시군구 데이터가 없어요.")
    st.stop()

with col2:
    selected_sigungu = st.selectbox(
        "② 시군구",
        options=sigungu_list,
    )

# 세 번째 드롭다운: 선택한 시군구에 속한 동
sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
]

dong_list = sorted(
    value for value in sigungu_df["동"].unique() if value
)

if not dong_list:
    st.warning("선택한 시군구에 동 데이터가 없어요.")
    st.stop()

with col3:
    selected_dong = st.selectbox(
        "③ 동",
        options=dong_list,
    )


# --------------------------------------------------
# 6. 선택한 동네의 인구 데이터 가져오기
# --------------------------------------------------
selected_df = sigungu_df[
    sigungu_df["동"] == selected_dong
]

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없어요.")
    st.stop()

# 같은 지역에 행이 여러 개 있더라도 연령별 인구를 합쳐요.
# 한 행만 있는 지역에서도 동일하게 작동해요.
male_population = (
    selected_df[male_cols]
    .sum()
    .to_numpy(dtype=float)
)

female_population = (
    selected_df[female_cols]
    .sum()
    .to_numpy(dtype=float)
)

# 인구 수는 정수로 표시하고, 남자 값만 음수로 바꿔요.
male_population = np.nan_to_num(
    male_population, nan=0
).astype(int)

female_population = np.nan_to_num(
    female_population, nan=0
).astype(int)

male_left = -male_population


# --------------------------------------------------
# 7. 전체 인구와 남녀 인구 요약
# --------------------------------------------------
total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female

st.markdown(
    f"### {selected_sido} {selected_sigungu} {selected_dong}"
)

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "전체 인구",
    f"{total_population:,}명",
)

metric2.metric(
    "남자 인구",
    f"{total_male:,}명",
)

metric3.metric(
    "여자 인구",
    f"{total_female:,}명",
)


# --------------------------------------------------
# 8. 인구 피라미드 그리기
# --------------------------------------------------
fig = go.Figure()

# 남자는 음수이므로 중앙의 왼쪽에 표시돼요.
fig.add_trace(
    go.Bar(
        name="남자",
        y=ages,
        x=male_left,
        orientation="h",
        marker_color="#7296B8",
        hovertemplate=(
            "나이: %{y}<br>"
            "남자 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
        customdata=male_population,
    )
)

# 여자는 양수이므로 중앙의 오른쪽에 표시돼요.
fig.add_trace(
    go.Bar(
        name="여자",
        y=ages,
        x=female_population,
        orientation="h",
        marker_color="#D99A9A",
        hovertemplate=(
            "나이: %{y}<br>"
            "여자 인구: %{x:,}명"
            "<extra></extra>"
        ),
    )
)

# 남자 쪽 숫자는 음수 대신 양수로 보이게 눈금 글자를 지정해요.
max_population = max(
    int(male_population.max()),
    int(female_population.max()),
    1,
)

# 그래프 좌우가 비슷한 크기로 보이도록 눈금 범위를 맞춰요.
tick_step = max(1, int(np.ceil(max_population / 5 / 100) * 100))
tick_limit = int(np.ceil(max_population / tick_step) * tick_step)

tick_values = list(
    range(-tick_limit, tick_limit + tick_step, tick_step)
)
tick_text = [f"{abs(value):,}" for value in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 인구 분포 ({latest_year}년)",
        "x": 0.5,
        "xanchor": "center",
    },
    barmode="overlay",
    bargap=0.12,
    height=1100,
    plot_bgcolor="#FFFDF9",
    paper_bgcolor="#FFF9F0",
    font=dict(
        family="Malgun Gothic, AppleGothic, sans-serif",
        color="#493D35",
        size=12,
    ),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="center",
        x=0.5,
    ),
    margin=dict(l=75, r=35, t=100, b=60),
    xaxis=dict(
        title="인구 수 (명)",
        tickmode="array",
        tickvals=tick_values,
        ticktext=tick_text,
        range=[-tick_limit, tick_limit],
        zeroline=True,
        zerolinecolor="#A58B76",
        zerolinewidth=2,
        gridcolor="#EDE1D5",
    ),
    yaxis=dict(
        title="나이",
        type="category",

        # 중요: 나이 라벨을 0세부터 100세 이상까지 직접 지정해요.
        # 값 크기순 정렬이나 축 전체 뒤집기를 사용하지 않아요.
        categoryorder="array",
        categoryarray=ages,

        # 맨 아래가 0세, 맨 위가 100세 이상인지 확인할 수 있도록
        # 라벨을 0세부터 순서대로 고정해요.
        tickmode="array",
        tickvals=ages,
        ticktext=ages,
        showgrid=True,
        gridcolor="#F2E9DF",
    ),
)

st.plotly_chart(fig, use_container_width=True)

# 축 순서가 올바른지 화면에서도 확인할 수 있도록 안내해요.
st.caption(
    "📌 나이 축 확인: 맨 아래는 0세, 맨 위는 100세 이상이에요. "
    "가운데 세로선 왼쪽은 남자, 오른쪽은 여자 인구입니다."
)

# --------------------------------------------------
# 9. 연령별 인구 표
# --------------------------------------------------
with st.expander("📋 연령별 인구 숫자 확인하기"):
    result_df = pd.DataFrame(
        {
            "나이": ages,
            "남자 인구": male_population,
            "여자 인구": female_population,
            "전체 인구": male_population + female_population,
        }
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True,
    )

    # 표를 CSV로 저장할 수도 있어요.
    csv_data = result_df.to_csv(
        index=False,
        encoding="utf-8-sig",
    )

    st.download_button(
        label="연령별 인구 표 다운로드",
        data=csv_data,
        file_name=f"{selected_dong}_{latest_year}_인구.csv",
        mime="text/csv",
    )
