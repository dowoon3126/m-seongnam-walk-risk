import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import plotly.graph_objects as go

# 1. 페이지 기본 설정 및 다크 모드 테마 고정
st.set_page_config(page_title="성남시 보행 위험도 대시보드", layout="wide")

# CSS: 여백 제거, 제목 크기 확대, 안내 박스 간격 조정, 배경색 고정
st.markdown("""
<style>
    /* 전체 배경 다크 고정 */
    .stApp {
        background-color: #0E1117;
    }
    
    /* 페이지 상단 여백 최소화 */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* 제목: 크기 키우고 안내 박스와 바짝 붙이기 */
    h2 {
        margin-top: 0px !important;
        margin-bottom: -15px !important; /* 박스와의 간격을 좁힘 */
        padding-bottom: 0px !important;
        font-size: 32px !important;      /* 제목 크기 대폭 확대 */
        color: white !important;
        font-weight: bold !important;
    }

    /* 파란색 안내 박스 디자인 */
    .stAlert {
        margin-top: 0px !important;
        background-color: #1E2329 !important;
        color: white !important;
        border: none !important;
    }
    
    /* 시스템 헤더 투명화 */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
    
    /* 텍스트 색상 화이트 고정 */
    .stMarkdown, p, span {
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# 제목 출력
st.markdown("<h2>성남시 보행 위험도 대시보드</h2>", unsafe_allow_html=True)
st.info("지도 상의 지역을 클릭하시면 하단에 맞춤형 분석 리포트가 생성됩니다.")

# 2. 데이터 불러오기
@st.cache_data
def load_data():
    try:
        return pd.read_csv("score.csv", encoding='utf-8')
    except:
        return pd.read_csv("score.csv", encoding='euc-kr')

@st.cache_data
def load_map():
    try:
        gdf = gpd.read_file("BND_ADM_DONG_PG.shp", encoding='euc-kr')
    except:
        gdf = gpd.read_file("BND_ADM_DONG_PG.shp", encoding='utf-8')
    
    if gdf.crs is None:
        gdf.set_crs(epsg=5179, inplace=True)
    return gdf.to_crs(epsg=4326)

df = load_data()
df.columns = df.columns.str.strip()

try:
    gdf = load_map()
    map_loaded = True
except Exception as e:
    st.error("지도 파일을 찾을 수 없습니다. (.shp, .shx, .dbf, .prj 파일 확인)")
    map_loaded = False

if map_loaded:
    map_col = 'ADM_NM'
    merged = gdf.merge(df, left_on=map_col, right_on='행정동', how='inner')
    
    col_map, col_info = st.columns([1.5, 1])
    
    with col_map:
        st.markdown("""
            <div style="display: flex; justify-content: space-between; font-size: 13px; font-weight: bold; margin-bottom: 5px;">
                <span>안전 구역</span>
                <span>위험 구역</span>
            </div>
        """, unsafe_allow_html=True)
        
        center_lat, center_lon = merged.geometry.centroid.y.mean(), merged.geometry.centroid.x.mean()
        m = folium.Map(
            location=[center_lat, center_lon], 
            zoom_start=11.3, 
            tiles="CartoDB dark_matter", # 지도를 다크 버전으로 교체
            dragging=True, 
            scrollWheelZoom=False,
            zoom_control=True
        )
        
        choro = folium.Choropleth(
            geo_data=merged, data=merged,
            columns=['행정동', '최종 보행 위험도 점수'],
            key_on=f'feature.properties.{map_col}',
            fill_color='Reds', fill_opacity=0.7, line_opacity=0.3
        ).add_to(m)
        
        # 범례 제거
        for key in list(choro._children.keys()):
            if key.startswith('color_map'):
                del(choro._children[key])
                
        folium.GeoJson(
            merged,
            style_function=lambda x: {'fillColor': '#000', 'color':'#000', 'fillOpacity': 0.0, 'weight': 0},
            tooltip=folium.features.GeoJsonTooltip(fields=[map_col], aliases=['행정동: ']),
            highlight_function=lambda x: {'weight':3, 'color':'#ff0000', 'fillOpacity': 0.2} 
        ).add_to(m)
        
        map_output = st_folium(m, use_container_width=True, height=400)
        
    with col_info:
        clicked_dong = None
        if map_output and map_output.get("last_active_drawing"):
            clicked_dong = map_output["last_active_drawing"]["properties"][map_col]
            
        if clicked_dong:
            match_df = df[df['행정동'] == clicked_dong]
            if not match_df.empty:
                dong_data = match_df.iloc[0]
                
                st.markdown(f"### [{clicked_dong}] 진단서")
                st.write(f"**종합 위험도 {dong_data['위험도 순위']}위** ({dong_data['최종 보행 위험도 점수']}점)")
                
                categories = ['평균 기울기', '골목길 비율', '교통약자 거주 인구 밀도', '교통약자 유발 시설 밀도', '안전 시설 밀도']
                values = [dong_data[c] for c in categories]
                
                # 데이터 닫기 (연결 끊김 방지)
                categories_conn = categories + [categories[0]]
                values_conn = values + [values[0]]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=values_conn, 
                    theta=categories_conn, 
                    fill='toself', 
                    fillcolor='rgba(255, 0, 0, 0.3)', 
                    line_color='red'
                ))
                
                fig.update_layout(
                    template="plotly_dark", # 다크 테마 고정
                    polar=dict(
                        bgcolor="#0E1117",
                        radialaxis=dict(
                            visible=True, 
                            range=[0, 100], 
                            tickvals=[0, 20, 40, 60, 80], # 100 제외
                            ticktext=['0', '20', '40', '60', '80'],
                            tickfont=dict(color='white', size=11, weight='bold'),
                            gridcolor='#444444'
                        ),
                        angularaxis=dict(
                            tickfont=dict(color='white', size=12, weight='bold')
                        )
                    ), 
                    paper_bgcolor="#0E1117",
                    plot_bgcolor="#0E1117",
                    showlegend=False, 
                    margin=dict(l=80, r=80, t=30, b=30), 
                    height=350
                )
                
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

                st.markdown("**💡 맞춤형 정책 제언**")
                if dong_data['안전 시설 밀도'] < 30:
                    st.error("**[안전 비상]** 제설함 및 보행자 펜스 확충 시급")
                if dong_data['평균 기울기'] >= 70:
                    st.warning("**[지형 한계]** 열선(발열매트) 설치 우선 검토")
                if dong_data['골목길 비율'] >= 80:
                    st.warning("**[보차혼용]** 미끄럼 방지 포장 및 스마트 보안등 필요")
                if dong_data['안전 시설 밀도'] >= 50 and dong_data['평균 기울기'] < 50:
                    st.success("인프라 양호 구역 (현행 유지보수 집중)")
