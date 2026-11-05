import re
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="급식 규칙 찾기", layout="wide")


# 1. 데이터 로드 및 전처리
@st.cache_data
def load_and_preprocess_data():
    url = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"
    df = pd.read_csv(url, encoding="utf-8")

    transactions = []
    all_items = set()

    for raw_menu in df["메뉴"].dropna():
        # 세로줄(|) 기준 분리
        items = raw_menu.split("|")
        cleaned_items = set()

        for item in items:
            # 괄호 및 괄호 안 내용 제거 (예: 쌀밥(자율) -> 쌀밥)
            cleaned = re.sub(r"\(.*?\)", "", item).strip()
            if cleaned:
                cleaned_items.add(cleaned)
                all_items.add(cleaned)

        if cleaned_items:
            transactions.append(cleaned_items)

    return transactions, sorted(list(all_items))


# 2. 연관 규칙 산출 및 단일 메뉴 출현 빈도 계산
@st.cache_data
def generate_association_rules(transactions):
    total_tx = len(transactions)

    # 항목별 출현 빈도 (단일 메뉴 지지도 계산용)
    item_counts = {}
    # 메뉴 쌍 출현 빈도
    pair_counts = {}

    for tx in transactions:
        for item in tx:
            item_counts[item] = item_counts.get(item, 0) + 1

        for item1, item2 in combinations(sorted(tx), 2):
            pair = (item1, item2)
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    rules = []
    for (item1, item2), count_both in pair_counts.items():
        # 방향 1: item1 -> item2
        supp = count_both / total_tx
        conf1 = count_both / item_counts[item1]
        lift1 = conf1 / (item_counts[item2] / total_tx)

        rules.append(
            {
                "조건": item1,
                "결과": item2,
                "동시": count_both,
                "지지도": round(supp, 4),
                "신뢰도": round(conf1, 4),
                "향상도": round(lift1, 4),
            }
        )

        # 방향 2: item2 -> item1
        conf2 = count_both / item_counts[item2]
        lift2 = conf2 / (item_counts[item1] / total_tx)

        rules.append(
            {
                "조건": item2,
                "결과": item1,
                "동시": count_both,
                "지지도": round(supp, 4),
                "신뢰도": round(conf2, 4),
                "향상도": round(lift2, 4),
            }
        )

    rules_df = pd.DataFrame(rules)
    return rules_df, len(pair_counts), item_counts


# 데이터 로딩
transactions, all_items = load_and_preprocess_data()
rules_df, unique_pair_count, item_counts = generate_association_rules(transactions)

st.title("🍱 송탄고 급식 규칙 찾기")

# 메트릭 표시 (급식 일수, 메뉴 종류 수, 함께 나온 적이 있는 메뉴 쌍의 수)
st.metric(
    label="급식 요약 정보",
    value=f"급식 일수: {len(transactions)}일 | 메뉴 종류 수: {len(all_items)}개 | 함께 나온 메뉴 쌍 수: {unique_pair_count}쌍",
)

st.divider()

# 사이드바 / 필터 및 정렬 옵션
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    selected_menu = st.selectbox(
        "검색할 메뉴를 선택하세요 (전체 보기: '전체')", ["전체"] + all_items
    )

with col2:
    sort_option = st.selectbox(
        "정렬 기준을 선택하세요",
        ["향상도 순", "신뢰도 순", "동시 순"],
    )

with col3:
    min_cooccurrence = st.slider(
        "최소 동시 일수 선택", min_value=1, max_value=10, value=1
    )

# 조건 필터링: 최소 동시 일수
filtered_df = rules_df[rules_df["동시"] >= min_cooccurrence].copy()

# 조건 필터링: 메뉴 선택
if selected_menu != "전체":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu)
        | (filtered_df["결과"] == selected_menu)
    ]

# 정렬 적용
sort_mapping = {
    "향상도 순": ["향상도", "신뢰도", "동시"],
    "신뢰도 순": ["신뢰도", "향상도", "동시"],
    "동시 순": ["동시", "향상도", "신뢰도"],
}
filtered_df = filtered_df.sort_values(
    by=sort_mapping[sort_option], ascending=False
).reset_index(drop=True)

# 남은 규칙 수 출력
st.markdown(f"**현재 조건에 어울리는 규칙 수:** `{len(filtered_df)}`개")

# 향상도 상위 10개 가로 막대그래프 (Plotly)
st.subheader("📊 향상도 상위 10개 규칙")
top_10_df = filtered_df.nlargest(10, "향상도").copy()

if not top_10_df.empty:
    top_10_df["규칙"] = top_10_df["조건"] + " ➔ " + top_10_df["결과"]
    top_10_df = top_10_df.sort_values(by="향상도", ascending=True)

    fig = px.bar(
        top_10_df,
        x="향상도",
        y="규칙",
        orientation="h",
        text="향상도",
        title="향상도(Lift) Top 10",
        color="향상도",
        color_continuous_scale="Viridis",
    )
    fig.update_layout(xaxis_title="향상도", yaxis_title="규칙 (조건 ➔ 결과)")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("선택한 조건에 해당하는 규칙이 없습니다.")

# 연관 규칙 데이터 프레임 출력
st.subheader("📋 연관 규칙 목록")
st.dataframe(filtered_df, use_container_width=True)

st.divider()

# 함께 나온 적 없는 짝 분석 세션
st.subheader("🔍 함께 나온 적 없는 짝 찾기")
st.write(
    "선택한 메뉴와 **한 번도 같은 날에 나온 적이 없으면서**, **혼자서는 10일 이상** 등장했던 메뉴 목록을 보여줍니다."
)

target_menu = st.selectbox("조회할 메뉴를 선택하세요", all_items, key="unpaired_menu_select")

if target_menu:
    target_count = item_counts.get(target_menu, 0)
    st.write(f"📌 **{target_menu}** (이 메뉴가 나온 날 수: **{target_count}일**)")

    # 선택한 메뉴와 함께 나온 적이 있는 상대 메뉴들 수집
    co_occurring_items = set()
    for tx in transactions:
        if target_menu in tx:
            co_occurring_items.update(tx)

    # 한 번도 같이 나오지 않고, 단독으로 10일 이상 나온 메뉴 필터링
    unpaired_list = []
    for item, count in item_counts.items():
        if item != target_menu and item not in co_occurring_items:
            if count >= 10:
                unpaired_list.append({"메뉴": item, "나온 날 수": count})

    unpaired_df = pd.DataFrame(unpaired_list)

    if not unpaired_df.empty:
        unpaired_df = unpaired_df.sort_values(by="나온 날 수", ascending=False).reset_index(
            drop=True
        )
        st.dataframe(unpaired_df, use_container_width=True)
    else:
        st.info("조건에 충족하는 '함께 나온 적 없는 짝' 메뉴가 없습니다.")
