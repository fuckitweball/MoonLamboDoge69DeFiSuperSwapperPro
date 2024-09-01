import flet as ft
import pandas as pd
import numpy as np
import random
import logging
import aiohttp
import asyncio
from datetime import datetime, timezone
from millify import millify
    
BASE_COLORS = ["#BC7AF9", "#00AF91", "#FF0075", "#77D970", "#172774", "#FFE162", "#9945FF", "#00FFAB", "#2192FF"]

def create_initial_chart_container(page: ft.Page):
    return ft.Container(
        alignment=ft.alignment.top_right,
        width=page.window.width * 0.4,
        height=page.window.height * 0.4,
        border_radius=10,
    )

def interpolate_colors(base_colors, num_colors):
    base_colors_rgb = [tuple(int(color[i:i+2], 16) for i in (1, 3, 5)) for color in base_colors]
    interpolated_colors = []
    for i in range(num_colors):
        ratio = i / (num_colors - 1)
        color1, color2 = np.array(base_colors_rgb[i % len(base_colors_rgb)]), np.array(base_colors_rgb[(i + 1) % len(base_colors_rgb)])
        interpolated_color = "#{:02X}{:02X}{:02X}".format(*(color1 * (1 - ratio) + color2 * ratio).astype(int))
        interpolated_colors.append(interpolated_color)
    return interpolated_colors

#pie chart
def holdings_chart(df: pd.DataFrame):
    logging.info(f"generating chart")
    total_balance_usd, num_sections = df['BalanceUSD'].sum(), len(df)
    colors = interpolate_colors(BASE_COLORS, num_sections) if num_sections > len(BASE_COLORS) else BASE_COLORS[:num_sections]
    random.shuffle(colors)

    normal_radius, hover_radius = 80, 90
    normal_title_style = ft.TextStyle(size=9, color=ft.colors.WHITE, weight=ft.FontWeight.BOLD)
    hover_title_style = ft.TextStyle(size=10,color=ft.colors.WHITE,weight=ft.FontWeight.BOLD,)
        
    sections = [
        ft.PieChartSection(
            value=(balance_usd / total_balance_usd) * 100,
            title=f"{symbol}\n{(balance_usd / total_balance_usd) * 100:.2f}%",
            title_style=normal_title_style,
            color=colors[idx],
            radius=normal_radius,
        ) for idx, (symbol, balance_usd) in enumerate(zip(df['Symbol'], df['BalanceUSD']))
    ]
    
    def on_chart_event(e: ft.PieChartEvent):
        for idx, section in enumerate(chart.sections):
            section.radius = hover_radius if idx == e.section_index else normal_radius
            section.title_style = hover_title_style if idx == e.section_index else normal_title_style
        chart.update()
    
    chart = ft.PieChart(
        sections=sections,
        sections_space=1,
        center_space_radius=79,
        on_chart_event=on_chart_event,
        start_degree_offset=180,
        expand=True,
    )
    return chart



# line chart
async def get_ohlc(token, pool):
    url = f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool}/ohlcv/minute?aggregate=1&limit=120&currency=usd&token={token}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers={'Content-Type': 'application/json'}) as response:
                response_json = await response.json()
                data = response_json['data']['attributes']['ohlcv_list']
                chart_name = f"{response_json['meta']['base']['name']}/{response_json['meta']['quote']['name']}"
                
                df = pd.DataFrame(data, columns=["Date", "open", "high", "low", "close", "volume"]).sort_values(by='Date', ascending=False)
                df.set_index('Date', inplace=True)
                df['close'] = df['close'].apply(lambda x: millify(x, precision=6, drop_nulls=False))
                
                return df, chart_name
        except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
            logging.error(f"Failed to get_ohlc: {str(e)}")
            return pd.DataFrame(), None

async def plot_tokenline_chart(df, chart_name, swap_col2, page):
    swap_col2.controls.clear()
    if df is None:
        logging.error(f"chart data is null")
        return
    
    formatted_xlabels = [ft.ChartAxisLabel(label=ft.Text(datetime.fromtimestamp(int(x), tz=timezone.utc).strftime('%H:%M')), value=float(x)) for x in df.index]
    datapoints = [ft.LineChartDataPoint(x, y, tooltip=f"{y}\n{datetime.fromtimestamp(int(x), tz=timezone.utc).strftime('%H:%M')}",tooltip_style=ft.TextStyle(color="#EEEEEE")) for x, y in zip(df.index, df['close'])]
    datapoints.sort(key=lambda p: p.x)
    
    line_chart = ft.LineChartData(
        color=ft.colors.GREEN,
        stroke_width=2,
        curved=True,
        stroke_cap_round=True,
        below_line_gradient=ft.LinearGradient(
            begin=ft.alignment.top_center,
            end=ft.alignment.bottom_center,
            colors=[
                ft.colors.with_opacity(0.3, ft.colors.GREEN),
                "transparent",
            ],
        ),
        data_points=[]
    )

    chart = ft.LineChart(
        data_series=[line_chart],
        baseline_x=df.index.min(),
        baseline_y=df['close'].min(),
        tooltip_bgcolor=ft.colors.with_opacity(0.3, "#111418"),
        min_y = df['close'].min(),
        max_y = df['close'].max(),
        min_x = df.index.min(),
        max_x = df.index.max(),
        expand=True,
        left_axis=ft.ChartAxis(labels_size=100, show_labels=True, labels_interval=(float(df['close'].max()) - float(df['close'].min())) / 3),
        bottom_axis=ft.ChartAxis(labels=formatted_xlabels, show_labels=True, labels_size=100),
        interactive=True,
    )
    
    new_chart_container = ft.Container(
        ft.Column(
            [
                ft.Text(
                    value=f'{chart_name} on Raydium  1m',
                    size=12,
                    weight="bold",
                    text_align=ft.TextAlign.LEFT,
                ),
                ft.Container(
                    content=chart,
                    padding=10,
                    alignment=ft.alignment.bottom_center,
                    border_radius=10,
                    expand=True
                )
            ],
            spacing=10,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            expand=True
        ),
        expand=True,
        padding=0,
        alignment=ft.alignment.bottom_center,
    )
    
    swap_col2.controls.append(new_chart_container)
    for i in range(len(datapoints)):
        line_chart.data_points.append(datapoints[i])
        chart.data_series = [line_chart]
        swap_col2.page.update()
        await asyncio.sleep(0.005)
