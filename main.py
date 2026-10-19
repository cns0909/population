
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# 1. 기본 화면 설정
st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide",
)

# 따뜻한 색상으로 화면 꾸미기
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
    .insight-box {
        background-color: #FFF0DD;
        border-left: 5px solid #C78D62;
        padding: 14px 18px;
        border-radius: 8px;
        color: #493D35;
        margin-top: 10px;
        margin-bottom: 18px;
    }
    .warning-note {
        color: #A33A2B;
        font-weight: 700;
        font-size: 0.9rem;
        padding-top: 4px;
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


# 2. 데이터 불러오기
DATA_URL = (
    "https://raw.githubusercontent.com/"
    "cns0909/population/main/population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="전국 인구 데이터를 불러오는 중이에요...")
def load_data():
    # ZIP 압축 파일을 읽어요.
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

    # 열 이름의 불필요한 공백을 제거해요.
    df.columns = df.columns.astype(str).str.strip()

    # 연도 열을 찾아요.
    year_candidates = ["연도", "년도", "기준연도", "기준년도"]
    year_col = next(
        (col for col in year_candidates if col in df.columns),
        None,
    )

    if year_col is None:
        raise ValueError(
            f"연도 열을 찾을 수 없어요. 현재 열: {list(df.columns[:15])}"
        )

    # 지역 열이 있는지 확인해요.
    location_cols = ["시도", "시군구", "동"]
    missing_cols = [
        col for col in location_cols if col not in df.columns
    ]

    if missing_cols:
        raise ValueError(f"지역 열이 없어요: {missing_cols}")

    # 연도를 숫자로 변환해요.
    df[year_col] = pd.to_numeric(
        df[year_col].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    df = df.dropna(subset=[year_col]).copy()
    df[year_col] = df[year_col].astype(int)

    # 0세부터 100세 이상까지 나이 라벨을 만들어요.
    ages = [f"{age}세" for age in range(100)]
    ages.append("100세 이상")

    male_cols = [f"남_{age}" for age in ages]
    female_cols = [f"여_{age}" for age in ages]

    # 필요한 인구 열이 모두 있는지 확인해요.
    missing_age_cols = [
        col
        for col in male_cols + female_cols
        if col not in df.columns
    ]

    if missing_age_cols:
        raise ValueError(
            f"연령별 인구 열이 없어요: {missing_age_cols[:10]}"
        )

    # 인구 데이터를 숫자로 변환해요.
    for col in male_cols + female_cols:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        ).fillna(0)

    # 지역 이름을 정리해요.
    for col in location_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df, year_col, ages, male_cols, female_cols


# 3. 데이터 불러오기
try:
    df, year_col, ages, male_cols, female_cols = load_data()
except Exception as e:
    st.error("데이터를 불러오지 못했어요.")
    st.info("인터넷 연결, 파일 주소, CSV 열 이름을 확인해 주세요.")
    st.code(str(e))
    st.stop()


# 4. 가장 최신 연도만 선택해요.
latest_year = int(df[year_col].max())
df = df[df[year_col] == latest_year].copy()

st.caption(f"📅 분석 기준 연도: {latest_year}년")


# 5. 시도 → 시군구 → 동 선택
st.subheader("📍 지역 선택")

col1, col2, col3 = st.columns(3)

sido_list = sorted(
    value for value in df["시도"].unique() if value
)

if not sido_list:
    st.warning("선택할 수 있는 시도 데이터가 없어요.")
    st.stop()

with col1:
    selected_sido = st.selectbox("① 시도", sido_list)

sido_df = df[df["시도"] == selected_sido]

sigungu_list = sorted(
    value for value in sido_df["시군구"].unique() if value
)

if not sigungu_list:
    st.warning("시군구 데이터가 없어요.")
    st.stop()

with col2:
    selected_sigungu = st.selectbox("② 시군구", sigungu_list)

sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
]

dong_list = sorted(
    value for value in sigungu_df["동"].unique() if value
)

if not dong_list:
    st.warning("동 데이터가 없어요.")
    st.stop()

with col3:
    selected_dong = st.selectbox("③ 동", dong_list)


# 6. 선택한 동네의 인구 데이터 계산
selected_df = sigungu_df[
    sigungu_df["동"] == selected_dong
]

if selected_df.empty:
    st.warning("선택한 지역의 인구 데이터가 없어요.")
    st.stop()

# 같은 지역의 행이 여러 개라면 인구를 합산해요.
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

male_population = np.nan_to_num(
    male_population, nan=0
).astype(int)

female_population = np.nan_to_num(
    female_population, nan=0
).astype(int)

# 남자 인구는 음수로 만들어 그래프 왼쪽에 표시해요.
male_left = -male_population

# 연령별 남녀 인구를 합쳐요.
age_population = male_population + female_population

total_male = int(male_population.sum())
total_female = int(female_population.sum())
total_population = total_male + total_female


# 7. 지표 계산: 평균연령과 고령화율
# 100세 이상은 계산상 100세로 간주해요.
age_numbers = np.arange(101, dtype=float)

if total_population > 0:
    average_age = float(
        np.sum(age_population * age_numbers) / total_population
    )
else:
    average_age = 0.0

# 65세 이상 인구를 계산해요.
age_65_index = ages.index("65세")
senior_population = int(
    age_population[age_65_index:].sum()
)

# 고령화율 = 65세 이상 인구 / 전체 인구 × 100
if total_population > 0:
    aging_rate = senior_population / total_population * 100
else:
    aging_rate = 0.0

# 아이는 0~14세, 어르신은 65세 이상으로 비교해요.
child_population = int(age_population[:15].sum())

if total_population == 0:
    neighborhood_summary = (
        "인구 데이터가 없어 아이와 어르신 중 어느 쪽이 많은지 "
        "판단하기 어려워요."
    )
elif child_population > senior_population:
    neighborhood_summary = (
        f"이 동네는 0~14세 아이({child_population:,}명)가 "
        f"65세 이상 어르신({senior_population:,}명)보다 많아요."
    )
elif senior_population > child_population:
    neighborhood_summary = (
        f"이 동네는 65세 이상 어르신({senior_population:,}명)이 "
        f"0~14세 아이({child_population:,}명)보다 많아요."
    )
else:
    neighborhood_summary = (
        f"이 동네는 아이와 어르신 인구가 같아요 "
        f"({child_population:,}명)."
    )


# 8. 그래프 위에 지표 카드 3개 표시
st.markdown(
    f"### {selected_sido} {selected_sigungu} {selected_dong}"
)

card1, card2, card3 = st.columns(3)

with card1:
    st.metric(
        label="👥 총인구",
        value=f"{total_population:,}명",
    )

with card2:
    st.metric(
        label="🎂 평균연령",
        value=f"{average_age:.1f}세",
        help=(
            "연령별 인구를 이용한 가중평균이에요. "
            "100세 이상은 계산상 100세로 간주해요."
        ),
    )

with card3:
    if aging_rate > 20:
        st.metric(
            label="👵 고령화율",
            value=f"{aging_rate:.1f}%",
            delta="⚠️ 20% 초과",
            delta_color="inverse",
            help="전체 인구 중 65세 이상 인구의 비율이에요.",
        )
        st.markdown(
            '<div class="warning-note">'
            '⚠️ 고령화율이 20%를 넘어요.'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.metric(
            label="👵 고령화율",
            value=f"{aging_rate:.1f}%",
            help="전체 인구 중 65세 이상 인구의 비율이에요.",
        )


# 9. 인구 피라미드 그리기
fig = go.Figure()

# 남자는 음수로 표시해 왼쪽에 배치해요.
fig.add_trace(
    go.Bar(
        name="남자",
        y=ages,
        x=male_left,
        orientation="h",
        marker_color="#7296B8",
        customdata=male_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "남자 인구: %{customdata:,}명"
            "<extra></extra>"
        ),
    )
)

# 여자는 양수로 표시해 오른쪽에 배치해요.
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

# 좌우 인구 축 범위를 같게 설정해요.
max_population = max(
    int(male_population.max()),
    int(female_population.max()),
    1,
)

tick_step = max(
    1,
    int(np.ceil(max_population / 5 / 100) * 100),
)

tick_limit = int(
    np.ceil(max_population / tick_step) * tick_step
)

tick_values = list(
    range(-tick_limit, tick_limit + tick_step, tick_step)
)

# 왼쪽의 음수 눈금도 양수 숫자로 보여 줘요.
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

        # 나이 순서를 직접 고정해요.
        # 맨 아래 0세, 맨 위 100세 이상이 되도록 설정해요.
        categoryorder="array",
        categoryarray=ages,
        tickmode="array",
        tickvals=ages,
        ticktext=ages,
        showgrid=True,
        gridcolor="#F2E9DF",
    ),
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "📌 나이 축 확인: 맨 아래는 0세, 맨 위는 100세 이상이에요. "
    "가운데 세로선 왼쪽은 남자, 오른쪽은 여자 인구입니다."
)


# 10. 그래프 아래에 동네 특징 자동 설명
st.markdown("### 🏡 우리 동네 한눈에 보기")

st.markdown(
    f'<div class="insight-box">'
    f'이 동네는 아이가 많은 편인가요, 어르신이 많은 편인가요?'
    f'<br><strong>{neighborhood_summary}</strong>'
    f'</div>',
    unsafe_allow_html=True,
)


# 11. 연령별 인구 표와 CSV 다운로드
with st.expander("📋 연령별 인구 숫자 확인하기"):
    result_df = pd.DataFrame(
        {
            "나이": ages,
            "남자 인구": male_population,
            "여자 인구": female_population,
            "전체 인구": age_population,
        }
    )

    st.dataframe(
        result_df,
        use_container_width=True,
        hide_index=True,
    )

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
