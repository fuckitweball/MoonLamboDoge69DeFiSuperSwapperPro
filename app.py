import flet as ft
from fletmint.utils import change_app_icon

import asyncio
import threading
import string

from config import *
from constants import *
from logs import *
from utils import *
from chart import *

new_icon_path = "assets/icon.png"
change_app_icon(icon_path=new_icon_path)

log_file = create_log_file()
setup_logging(log_file)
logging.info(f"Initializing session")

initialize_wallets_map(wallets_map)

async def text_animation_effect(title: str, widget: ft.Text):
    letters = string.ascii_uppercase
    for i in range(len(title) * 4):
        widget.value = ''.join(title[j] if j < i // 4 else random.choice(letters) for j in range(len(title)))
        widget.update()
        await asyncio.sleep(0.02)
    widget.value = title
    widget.update()

async def main(page: ft.Page):
    page.title = "MoonLamboDoge69DeFiSuperSwapperPro"
    page.window.width = 1680
    page.windowmax_width = 1680
    page.window.height = 1050
    page.windowmax_height = 1050
    page.window.resizable = True
    page.scroll = ft.ScrollMode.AUTO
    page.bgcolor = "black"
    page.window.top = 0
    page.window.left = 0
    
    title_widget = ft.Text(value="MoonLamboDoge69DeFiSuperSwapperPro", text_align=ft.TextAlign.LEFT, size=24, color="#14F195", bgcolor=ft.colors.TRANSPARENT, weight=ft.FontWeight.BOLD)
        
    async def on_appbar_hover(e):
        if e.data == "true":
            await text_animation_effect("MoonLamboDoge69DeFiSuperSwapperPro", title_widget)
        else:
            title_widget.value = "MoonLamboDoge69DeFiSuperSwapperPro"
            title_widget.update()
        
    page.appbar = ft.AppBar(
        title=ft.Container(content=title_widget, on_hover=on_appbar_hover, width=625, bgcolor=ft.colors.TRANSPARENT,alignment=ft.alignment.center_left, expand=True),
        leading=ft.Container(padding=10, content=ft.Image(src="icon.png"), bgcolor=ft.colors.TRANSPARENT, expand=True, alignment=ft.alignment.center_left),
        leading_width=50,
        toolbar_height=60,
        center_title=False,
        bgcolor="black"
    )
    page.update()


    def create_button(label, color, wrapper):
        return ft.ElevatedButton(
            content=ft.Row(
                [ft.Text(value=label, color=color, size=14, weight="bold")],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
            ),
            style=ft.ButtonStyle(
                color={
                    ft.MaterialState.HOVERED: color,
                    ft.MaterialState.FOCUSED: color,
                    ft.MaterialState.DEFAULT: "#EEEEEE",
                },
                bgcolor={ft.MaterialState.FOCUSED: color, "": "black"},
                padding={ft.MaterialState.HOVERED: 20},
                overlay_color=ft.colors.TRANSPARENT,
                elevation={"pressed": 0, "": 1},
                animation_duration=500,
                side={
                    ft.MaterialState.DEFAULT: ft.BorderSide(1, "#EEEEEE"),
                    ft.MaterialState.HOVERED: ft.BorderSide(2, color),
                },
                shape={
                    ft.MaterialState.HOVERED: ft.RoundedRectangleBorder(radius=20),
                    ft.MaterialState.DEFAULT: ft.RoundedRectangleBorder(radius=15),
                },
            ),        
            on_click=lambda e: asyncio.run(wrapper()),
        )
        
    def create_text_field(label, hint_text, read_only=False):
        def on_focus_event(e):
            e.control.border_color = "#9945FF"
            e.control.border_width = 2
            e.control.content_padding = 20
            e.control.border_radius=ft.border_radius.all(25)
            e.control.update()

        def on_blur_event(e):
            e.control.border_color = "EEEEEE"
            e.control.border_width = 1
            e.control.content_padding = 10
            e.control.border_radius=ft.border_radius.all(10)
            e.control.update()

        return ft.TextField(
            label=label,
            autocorrect=False,
            label_style=ft.TextStyle(color="#9945FF", size=14),
            hint_text=hint_text,
            hint_style=ft.TextStyle(color="#EEEEEE", size=11),
            width=350,
            height=50,
            text_size=14,
            content_padding=10,
            text_align=ft.TextAlign.LEFT,
            text_vertical_align=ft.VerticalAlignment.CENTER,
            bgcolor='black',
            border_color="#EEEEEE",
            border_width = 1,
            border_radius=ft.border_radius.all(10),
            color="#EEEEEE",
            read_only=read_only,
            on_focus=on_focus_event,
            on_blur=on_blur_event,
        )


    def create_column(controls, alignment=ft.alignment.top_left, spacing=10, expand=True):
        return ft.Column(controls=controls, alignment=alignment, spacing=spacing, expand=expand)

    def create_row(controls, alignment=ft.alignment.top_left, spacing=10):
        return ft.Row(controls=controls, alignment=alignment, spacing=spacing)
    
    def create_container(content, alignment=ft.alignment.top_left, padding=20, expand=True):
        return ft.Container(content=content, alignment=alignment, padding=ft.padding.all(padding), expand=expand)

    async def token_input_box_wrapper():
        logging.info(f"validating token")
        spinner.visible = True
        page.update()
        pair_address = await validate_address(token_input_box, warning_text, token_balance_text, holdings_dropdown.value, swap_col)
        await update_swap_tab(holdings_dropdown.value, swap_row.controls[1], page, spinner, token_input_box.value, pair_address)
        spinner.visible = False
        page.update()

    async def handle_click_wrapper(operation):
        if holdings_dropdown.value:
            logging.info(f"Initiating {operation}")
            spinner.visible = True
            page.update()
            await globals()[f"{operation}"](token_input_box.value, wallets_map[holdings_dropdown.value]["keypair"], swap_col, warning_text, token_balance_text, page)
            selected_wallet = holdings_dropdown.value
            if selected_wallet:
                logging.info(f"Refreshing data")
                await update_holdings_tab(selected_wallet, data_table, holding_row.controls[1], page, spinner)
            spinner.visible = False
            page.update()
        else:
            logging.warning(f"Please select a wallet first!")
            warning_text.value = "Please select a wallet first!"
            warning_text.update()
            await asyncio.sleep(5)
            warning_text.value = ""
            warning_text.update()
    
    holdings_dropdown = ft.Dropdown(
        label="Wallet Manager",
        label_style=ft.TextStyle(color="#9945FF", size=18),
        hint_text="Select Wallet",
        hint_style=ft.TextStyle(color="#14F195", size=12),
        options=[ft.dropdown.Option(wallet_id) for wallet_id in wallets_map.keys()],
        width=200,
        height=40,
        text_size=12,
        padding=0,
        alignment=ft.alignment.center_right,
        bgcolor='#111418',
        border_color="#EEEEEE",
        border_radius=10,
        color="#14F195",        
    )

    spinner = ft.ProgressRing(width=10, height=10, stroke_width=2, color="#EEEEEE", visible=False)
    refresh_button = ft.ElevatedButton(
            "Reload", icon=ft.icons.REFRESH_OUTLINED,
            style=ft.ButtonStyle(
                color={
                    ft.MaterialState.HOVERED: "#14F195",
                    ft.MaterialState.FOCUSED: "#14F195",
                    ft.MaterialState.DEFAULT: "#EEEEEE",
                },
                bgcolor={ft.MaterialState.FOCUSED: "#14F195", "": "black"},
                padding={ft.MaterialState.HOVERED: 15},
                overlay_color=ft.colors.TRANSPARENT,
                elevation={"pressed": 0, "": 1},
                animation_duration=500,
                side={
                    ft.MaterialState.DEFAULT: ft.BorderSide(1, "#EEEEEE"),
                    ft.MaterialState.HOVERED: ft.BorderSide(2, "#14F195"),
                },
                shape={
                    ft.MaterialState.HOVERED: ft.RoundedRectangleBorder(radius=20),
                    ft.MaterialState.DEFAULT: ft.RoundedRectangleBorder(radius=15),
                },
            ),        
            on_click=lambda e: asyncio.run(refresh_holdings_page()),
        )
    warning_text = ft.Text(value="", color="#FF8F00", size=10, weight="bold")

    selection_row = create_row([holdings_dropdown, refresh_button, spinner, warning_text], spacing=20)
    data_table = create_empty_data_table(page)
    initial_chart_container = create_initial_chart_container(page)
    holding_row = create_row([create_column([data_table]), create_column([initial_chart_container], alignment=ft.alignment.top_right)], alignment=ft.MainAxisAlignment.CENTER)
    
    token_input_box = create_text_field("Enter Token Address", "e.g., 3n5Qo2FW2oNx...")
    token_input_box.on_change = lambda e: asyncio.run(token_input_box_wrapper())

    buy_button = create_button("Buy", "#14F195", lambda: handle_click_wrapper('raydium_buy'))
    sell_button = create_button("Sell", "#FFAF00", lambda: handle_click_wrapper('raydium_sell'))
    burn_button = create_button("Burn", "#FF204E", lambda: handle_click_wrapper('burn_tokens'))
    close_button = create_button("Close", "#F9E400", lambda: handle_click_wrapper('close_token_account'))

    swap_buttons_row = create_row([buy_button, sell_button, burn_button, close_button], alignment=ft.MainAxisAlignment.CENTER)
    token_balance_text = create_text_field("Token Balance", "", read_only=True)

    swap_col = create_column([create_row([token_input_box, swap_buttons_row], spacing=50), token_balance_text, create_text_field("Enter Swap Amount In", "e.g., 0.1 for Sol or 69420 for tokens (not in lamports)", read_only=False), create_text_field("Set Compute Unit Limit (Optional)", "e.g., 100000", read_only=False), create_text_field("Set Compute Unit Price (Optional)", "e.g., 5000000 (in lamports)", read_only=False)])
    swap_row = create_row([create_container(swap_col), create_column([], alignment=ft.alignment.bottom_left)], alignment=ft.MainAxisAlignment.SPACE_EVENLY)

    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        indicator_border_radius=1,
        indicator_color="#EEEEEE",
        label_color="#14F195",
        scrollable=True,
        unselected_label_color="#EEEEEE",
        tabs=[
            ft.Tab(text="Holdings", icon=ft.icons.SHOPPING_BAG_OUTLINED, content=holding_row),
            ft.Tab(text="Swap", icon=ft.icons.SWAP_VERT_SHARP, content=swap_row),
        ],
        expand=1,
    )

    global log_column
    log_column = ft.Column(expand=True, scroll=ft.ScrollMode.HIDDEN, alignment=ft.MainAxisAlignment.START, horizontal_alignment=ft.CrossAxisAlignment.START, spacing=-1)
    threading.Thread(target=read_log_file, args=(log_column, log_file), daemon=True).start()

    async def refresh_holdings_page():
        selected_wallet = holdings_dropdown.value
        if selected_wallet:
            logging.info(f"Refreshing data")
            await update_holdings_tab(selected_wallet, data_table, holding_row.controls[1], page, spinner)
        else:
            logging.warning(f"Please select a wallet first!")
            warning_text.value = "Please select a wallet first!"
            warning_text.update()
            await asyncio.sleep(5)
            warning_text.value = ""
            warning_text.update()

    holdings_dropdown.on_change = lambda event: asyncio.run(refresh_holdings_page())

    selection_conatiner = ft.Container(
        content=selection_row,
        width=page.window.width,
    )
    tab_container = ft.Container(
        content=tabs,
        height=page.window.height * 0.5,
        width=page.window.width,
        
    )
    log_conatiner = ft.Container(
        content=log_column,
        height=page.window.height * 0.25,
        width=page.window.width,
        border=ft.border.all(width=0.5, color="#EEEEEE"),
        bgcolor="#111111",
        padding=5,
        clip_behavior=ft.ClipBehavior.NONE,
    )
    
    page.add(
        ft.Column(
            controls=[
                selection_conatiner,
                tab_container,
                log_conatiner
            ],
        )
    )

ft.app(target=main)