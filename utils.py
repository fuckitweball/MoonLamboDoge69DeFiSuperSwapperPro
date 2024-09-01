from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TokenAccountOpts, MemcmpOpts, TxOpts
from solana.rpc.commitment import Confirmed, Finalized, Processed
from solana.transaction import Signature, AccountMeta

from solders.keypair import Keypair
from solders.instruction import Instruction
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.system_program import create_account
import solders.system_program as system_program

from spl.token.instructions import create_associated_token_account, get_associated_token_address, initialize_account, InitializeAccountParams, close_account, CloseAccountParams, burn, BurnParams, CloseAccountParams, close_account

from config import *
from constants import *
from layouts import *
from chart import *

import flet as ft
import asyncio
import base58
import aiohttp
import logging
import re
import time
import json
import pandas as pd
from millify import millify



global global_pool_keys, global_decimals, global_pair_address, global_token_balance
global_pool_keys = None
global_decimals = None
global_pair_address = None
global_token_balance = None

current_sort_column = None
sort_ascending = True

def initialize_wallets_map(wallets_map):
    logging.info(f"Initializing wallets")
    for wallet_id, wallet_data in wallets_map.items():
        try:
            keypair = Keypair.from_base58_string(wallet_data["private_key"])
            wallet_data.update({"keypair": keypair, "pubkey": str(keypair.pubkey())})
        except Exception as e:
            logging.error(f"Error processing wallet {wallet_id}: {e}")
            raise

async def get_balance(public_key):
    logging.info(f"Fetching native balance")
    try:
        return (await AsyncClient(rpc).get_balance(public_key, commitment="processed")).value / LAMPORTS_PER_SOL
    except Exception as e:
        logging.error(f"Error in get_balance: {e}")
        return 'N/A'

async def get_sol_data():
    logging.info("Fetching Sol market data")
    url = "https://api.geckoterminal.com/api/v2/networks/solana/tokens/So11111111111111111111111111111111111111112"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            try:
                data = await response.json()
                return data['data']['attributes']['price_usd'], data['data']['attributes']['fdv_usd']
            except Exception as e:
                logging.error(f"Failed to get_sol_data: {e}")
                return None, None        


async def get_token_details(mint_balance_map):
    logging.info("Fetching token data")
    token_details = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(mint_balance_map), 30):
            chunk = list(mint_balance_map.keys())[i:i+30]
            url = f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/multi/{','.join(chunk)}"
            try:
                async with session.get(url) as response:
                    data = await response.json()
                    for pair in data.get('data', []):
                        attrs = pair['attributes']
                        address = attrs['address']
                        if address in mint_balance_map:
                            balance = float(mint_balance_map[address])
                            token_details.append({
                                "Logo": attrs['image_url'],
                                'Mint': address,
                                'Name': attrs['name'],
                                'Symbol': attrs['symbol'],
                                'Balance': millify(balance, precision=2),
                                'BalanceUSD': float(attrs['price_usd'] or 0) * balance,
                                'FDV': f"$ {millify(attrs['fdv_usd'], precision=2) if attrs['fdv_usd'] else 0}",
                            })
            except Exception as e:
                logging.error(f"Failed to get_token_details for chunk: {e}")
    return token_details

async def get_token_accounts_by_owner_json_parsed(keypair):
    logging.info("Fetching token balances")
    try:
        opts = TokenAccountOpts(program_id=TOKEN_PROGRAM, encoding="jsonParsed")
        token_accounts_response = await AsyncClient(rpc).get_token_accounts_by_owner_json_parsed(keypair.pubkey(), opts, commitment="processed")
        return {info['mint']: info['tokenAmount']['uiAmount'] for account in token_accounts_response.value for info in [account.account.data.parsed.get("info")] if info}
    except Exception as e:
        logging.error(f"Error in get_token_accounts_by_owner_json_parsed: {e}")
        raise

async def create_dataframe_for_wallet(selected_wallet):
    try:
        logging.info(f"Updating table for {selected_wallet}")
        balance = await get_balance(wallets_map[selected_wallet]["keypair"].pubkey())
        price_usd, fdv = await get_sol_data()
        data = [{
            "Logo": solana_logo_url,
            'Mint': "So11111111111111111111111111111111111111112",
            "Name": "Solana",
            "Symbol": "SOL",
            "Balance": millify(balance, precision=4),
            "BalanceUSD": balance * float(price_usd) if price_usd else 0,
            "FDV": f"$ {millify(fdv, precision=2) if fdv else 0}"
        }]
        mint_balance_map = await get_token_accounts_by_owner_json_parsed(wallets_map[selected_wallet]["keypair"])
        token_details = await get_token_details(mint_balance_map) if mint_balance_map else []
        return pd.DataFrame(data + token_details).sort_values(by='BalanceUSD', ascending=False)
    except Exception as e:
        logging.error(f"Error creating DataFrame for wallet {selected_wallet}: {e}")
        return pd.DataFrame()

def get_token_names_from_df(df):
    return [ft.dropdown.Option(f'{row["Name"]} ({row["Mint"]})') for _, row in df.iterrows()] if df is not None else []

    
def create_empty_data_table(page):
    logging.info(f"Setting table")
    return ft.DataTable(
        columns=[ft.DataColumn(ft.Text(col)) for col in ["Logo", "Name", "Symbol", "Balance", "BalanceUSD", "FDV"]],
        rows=[],
        horizontal_lines=ft.BorderSide(width=0.1, color="#EEEEEE"),
        width=page.window.width * 0.6,
        column_spacing=10,
        data_row_min_height=36,
        data_row_max_height=36,
        heading_row_color={ft.ControlState.HOVERED: "#111418"},
        heading_text_style=ft.TextStyle(color="#14F195"),
        data_row_color={"hovered": "#111418"},
        sort_ascending=False,
    )


def show_snackbar(text):
    return (ft.SnackBar(
        ft.Text(text, size=11, color="#EEEEEE"),
        behavior=ft.SnackBarBehavior.FLOATING,
        bgcolor="#111418",
        show_close_icon=True,
        close_icon_color="red",
        dismiss_direction=ft.DismissDirection.START_TO_END,
        duration=5000,
        margin=400,
        padding=ft.padding.all(8),
        shape=ft.RoundedRectangleBorder(radius=5),
        width=150,
    ))

def show_confirm_snackbar(signature):
    text = ft.Text(
        spans=[
            ft.TextSpan("Tx "),
            ft.TextSpan(
                "link",
                url=f"https://solscan.io/tx/{signature}",
                style=ft.TextStyle(
                    color="#3EDBF0",
                    decoration=ft.TextDecoration.UNDERLINE,
                ),
            ),
        ],
        size=11,
        color="#EEEEEE",
        text_align=ft.TextAlign.CENTER
    )

    return (ft.SnackBar(
        text,
        behavior=ft.SnackBarBehavior.FLOATING,
        bgcolor="#111418",
        show_close_icon=True,
        close_icon_color="red",
        dismiss_direction=ft.DismissDirection.START_TO_END,
        duration=5000,
        margin=400,
        padding=ft.padding.all(8),
        shape=ft.RoundedRectangleBorder(radius=5),
        width=150,
    ))


def sort_dataframe(df, column, ascending):
    logging.info(f"sorting table by {column}: ascending {ascending}")
    return df.sort_values(by=column, ascending=ascending)

def header_on_click(e, col_name, data_table, page):
    global current_sort_column, sort_ascending, df
    if df is None:
        return

    sort_ascending = not sort_ascending if current_sort_column == col_name else True
    current_sort_column = col_name
    sorted_df = sort_dataframe(df, col_name, sort_ascending)
    data_table.rows.clear()
    data_table.rows.extend(create_data_table_from_df(sorted_df))
    page.update()
    return current_sort_column, sort_ascending

def create_data_table_from_df(df):
    def copy_mint(e, mint):
        e.page.set_clipboard(mint)
        e.page.open(show_snackbar("Copied address"))
        logging.info(f'Copied address: {mint}')

    return [ft.DataRow(
        cells=[
            ft.DataCell(ft.Image(src=row['Logo'], width=20, height=20) if row['Logo'] else ft.Container()),
            ft.DataCell(ft.Text(row['Name'], color="#EEEEEE", size=12)),
            ft.DataCell(ft.Text(row['Symbol'], color="#EEEEEE", size=12)),
            ft.DataCell(ft.Text(str(row['Balance']), color="#EEEEEE", size=12)),
            ft.DataCell(ft.Text(f"${row['BalanceUSD']:.2f}", color="#EEEEEE", size=12)),
            ft.DataCell(ft.Text(str(row['FDV']), color="#EEEEEE", size=12))
        ],
        on_select_changed=lambda e, mint=row['Mint']: copy_mint(e, mint)
    ) for _, row in df.iterrows()]


async def update_holdings_tab(selected_wallet, data_table, holding_col2, page, spinner):
    global df
    if selected_wallet:
        spinner.visible = True
        data_table.rows.clear()
        holding_col2.controls.clear()
        page.update()

        df = await create_dataframe_for_wallet(selected_wallet)
        df = df.fillna('N/A')
        if not df.empty:
            data_table.columns = [ft.DataColumn(
                                    ft.GestureDetector(
                                        content=ft.Text(column),
                                        mouse_cursor=ft.MouseCursor.CLICK,
                                    ),
                                    on_sort=lambda e, col=column: header_on_click(e, col, data_table, page),
                                ) for column in ["Logo", "Name", "Symbol", "Balance", "BalanceUSD", "FDV"]]

            data_table.rows.extend(create_data_table_from_df(df)) 
            piechart = holdings_chart(df)
            
            new_chart_container = ft.Row([
                ft.Container(
                    content=piechart,
                    padding=10,
                    alignment=ft.alignment.top_right,
                    width=page.window.width * 0.4,
                    height=page.window.height * 0.4,
                    border_radius=10,
                    expand=True
                )],
                spacing=10,
            )
            
            holding_col2.controls.append(new_chart_container)
                       
        spinner.visible = False
        page.update()

async def update_swap_tab(selected_wallet, swap_col2, page, spinner, token, pool):
    global token_df
    logging.info(f"Checking wallet")
    if selected_wallet:
        spinner.visible = True
        swap_col2.controls.clear()
        page.update()

        token_df, chart_name = await get_ohlc(token, pool)
        logging.info(f"Fetched chart data")
        if token_df is not pd.DataFrame():
            token_df = token_df.fillna('N/A')
        if not token_df.empty:
            logging.info(f"Plotting chart")
            await plot_tokenline_chart(token_df, chart_name, swap_col2, page)
                       
        spinner.visible = False
        page.update()

def is_valid_solana_address(address):
    if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
        return False
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except ValueError:
        return False
    
async def get_token_account_info_from_rpc(keypair, mint):
    try:
        opts = TokenAccountOpts(mint=Pubkey.from_string(mint), encoding="jsonParsed")
        token_accounts_response = await AsyncClient(rpc).get_token_accounts_by_owner_json_parsed(keypair.pubkey(), opts)
        accounts = token_accounts_response.value
        if accounts:
            token_account = accounts[0].pubkey
            parsed_data = accounts[0].account.data.parsed
            if "info" in parsed_data:
                info = parsed_data["info"]
                token_amount = info.get("tokenAmount", {})
                return token_account, token_amount.get("uiAmount"), token_amount.get("amount"), token_amount.get("decimals")
        return None, None, None, None
    except Exception as e:
        logging.error(f"Error in get_token_account_info_from_rpc: {e}")
        raise

async def enable_controls(swap_col):
    swap_col.controls[2].read_only = False
    swap_col.controls[2].disabled = False            
    swap_col.update()
        
async def validate_address(token_input_box, warning_text, token_balance_text, selected_wallet, swap_col):
    global global_pool_keys, global_decimals, global_pair_address
    address = token_input_box.value
    if selected_wallet:
        keypair = wallets_map[selected_wallet]["keypair"]
        if is_valid_solana_address(address):
            await enable_controls(swap_col)
            warning_text.value, warning_text.color = "Valid Solana Address", "#14F195"
            warning_text.update()
            token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(keypair, address)
            token_balance_text.value = f"{balance}" if balance else "0"
            try:
                pair_address = await get_pair_address_from_rpc(str(address))
                if pair_address:         
                    pool_keys = await fetch_pool_keys(str(pair_address))
                    token_balance_text.update()
                    decimals = pool_keys['base_decimals'] if address == str(pool_keys['base_mint']) else pool_keys['quote_decimals'] if address == str(pool_keys['quote_mint']) else None
                    warning_text.value = ""
                    warning_text.update()
                    global_token_balance, global_pool_keys, global_decimals, global_pair_address = balance, pool_keys, decimals, pair_address
                return pair_address
            except Exception as e:
                logging.error(f"Error: {e}")
        else:
            warning_text.value, warning_text.color = "Invalid Solana Address!", "RED"
    else:
        warning_text.value = "Please select a wallet first!"
    warning_text.update()
    await asyncio.sleep(5)
    warning_text.value = ""
    warning_text.update()
    
async def get_pair_address_from_rpc(token_address: str) -> str:
    BASE_OFFSET, QUOTE_OFFSET, DATA_LENGTH_FILTER = 400, 432, 752
    QUOTE_MINT = SOL

    try:
        #base_mint at BASE_OFFSET, QUOTE_MINT at QUOTE_OFFSET
        filters = [DATA_LENGTH_FILTER, MemcmpOpts(offset=BASE_OFFSET, bytes=bytes(Pubkey.from_string(token_address))), MemcmpOpts(offset=QUOTE_OFFSET,bytes=bytes(Pubkey.from_string(QUOTE_MINT)))]
        response = await AsyncClient(rpc).get_program_accounts(pubkey=RAY_V4, commitment=Confirmed, filters=filters, encoding="jsonParsed")
        if response.value:
            return str(response.value[0].pubkey)

        #QUOTE_MINT at BASE_OFFSET, base_mint at QUOTE_OFFSET
        filters = [DATA_LENGTH_FILTER, MemcmpOpts(offset=BASE_OFFSET, bytes=bytes(Pubkey.from_string(QUOTE_MINT))), MemcmpOpts(offset=QUOTE_OFFSET, bytes=bytes(Pubkey.from_string(token_address)))]
        response = await AsyncClient(rpc).get_program_accounts(pubkey=RAY_V4, commitment=Confirmed, filters=filters, encoding="jsonParsed")
        if response.value:
            return str(response.value[0].pubkey)
        
    except Exception as e:
        logging.error(f"Error fetching pair_address_from_rpc: {e}")
    return None

async def fetch_pool_keys(pair_address: str) -> dict:
    try:
        async with AsyncClient(rpc) as client:
            amm_id = Pubkey.from_string(pair_address)
            amm_data_response = await client.get_account_info(amm_id, encoding="jsonParsed")
            amm_data = amm_data_response.value.data
            amm_data_decoded = LIQUIDITY_STATE_LAYOUT_V4.parse(amm_data)
            OPEN_BOOK_PROGRAM = Pubkey.from_bytes(amm_data_decoded.serumProgramId)
            marketId = Pubkey.from_bytes(amm_data_decoded.serumMarket)
            market_info_response = await client.get_account_info(marketId, encoding="jsonParsed")
            marketInfo = market_info_response.value.data
            market_decoded = MARKET_STATE_LAYOUT_V3.parse(marketInfo)

            return {
                "amm_id": amm_id,
                "base_mint": Pubkey.from_bytes(market_decoded.base_mint),
                "quote_mint": Pubkey.from_bytes(market_decoded.quote_mint),
                "lp_mint": Pubkey.from_bytes(amm_data_decoded.lpMintAddress),
                "version": 4,
                "base_decimals": amm_data_decoded.coinDecimals,
                "quote_decimals": amm_data_decoded.pcDecimals,
                "lpDecimals": amm_data_decoded.coinDecimals,
                "programId": RAY_V4,
                "authority": RAY_AUTHORITY_V4,
                "open_orders": Pubkey.from_bytes(amm_data_decoded.ammOpenOrders),
                "target_orders": Pubkey.from_bytes(amm_data_decoded.ammTargetOrders),
                "base_vault": Pubkey.from_bytes(amm_data_decoded.poolCoinTokenAccount),
                "quote_vault": Pubkey.from_bytes(amm_data_decoded.poolPcTokenAccount),
                "withdrawQueue": Pubkey.from_bytes(amm_data_decoded.poolWithdrawQueue),
                "lpVault": Pubkey.from_bytes(amm_data_decoded.poolTempLpTokenAccount),
                "marketProgramId": OPEN_BOOK_PROGRAM,
                "market_id": marketId,
                "market_authority": Pubkey.create_program_address(
                    [bytes(marketId)]
                    + [bytes([market_decoded.vault_signer_nonce])]
                    + [bytes(7)],
                    OPEN_BOOK_PROGRAM,
                ),
                "market_base_vault": Pubkey.from_bytes(market_decoded.base_vault),
                "market_quote_vault": Pubkey.from_bytes(market_decoded.quote_vault),
                "bids": Pubkey.from_bytes(market_decoded.bids),
                "asks": Pubkey.from_bytes(market_decoded.asks),
                "event_queue": Pubkey.from_bytes(market_decoded.event_queue),
                "pool_open_time": amm_data_decoded.poolOpenTime
            }

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None

def get_token_account(owner: Pubkey, mint: Pubkey):
    try:
        account_data = client.get_token_accounts_by_owner(owner, TokenAccountOpts(mint))
        return account_data.value[0].pubkey, None
    except:
        token_account = get_associated_token_address(owner, mint)
        return token_account, create_associated_token_account(owner, owner, mint)


async def make_swap_instruction(amount_in: int, token_account_in: Pubkey, token_account_out: Pubkey, accounts: dict, owner: Pubkey) -> Instruction:
    try:
        keys = [
            AccountMeta(pubkey=TOKEN_PROGRAM, is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts["amm_id"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["authority"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=accounts["open_orders"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["target_orders"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["base_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["quote_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=OPEN_BOOK_PROGRAM, is_signer=False, is_writable=False), 
            AccountMeta(pubkey=accounts["market_id"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["bids"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["asks"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["event_queue"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["market_base_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["market_quote_vault"], is_signer=False, is_writable=True),
            AccountMeta(pubkey=accounts["market_authority"], is_signer=False, is_writable=False),
            AccountMeta(pubkey=token_account_in, is_signer=False, is_writable=True),  
            AccountMeta(pubkey=token_account_out, is_signer=False, is_writable=True), 
            AccountMeta(pubkey=owner.pubkey(), is_signer=True, is_writable=False) 
        ]
        
        data = SWAP_LAYOUT.build(
            dict(
                instruction=9,
                amount_in=int(amount_in),
                min_amount_out=0
            )
        )
        return Instruction(RAY_V4, data, keys)
    except:
        return None

def confirm_txn(txn_sig, max_retries=20, retry_interval=3):
    retries = 0
    txn_sig = Signature.from_string(txn_sig) if isinstance(txn_sig, str) else txn_sig
    for _ in range(max_retries):
        try:
            txn_res = client.get_transaction(txn_sig, encoding="json", commitment="confirmed", max_supported_transaction_version=0)
            txn_json = json.loads(txn_res.value.transaction.meta.to_json())
            if txn_json['err'] is None:
                logging.info(f"Transaction confirmed... try count: {retries+1}")
                return True
            logging.error("Error: Transaction not confirmed. Retrying...")
            if txn_json['err']:
                logging.error(f"Transaction failed. {txn_json['err']}")
                return False
        except Exception:
            logging.warning(f"Awaiting confirmation... try count: {retries+1}")
            retries += 1
            time.sleep(retry_interval)
    logging.error("Max retries reached. Transaction confirmation failed.")
    return None

async def raydium_buy(token_address, payer_keypair, swap_col, warning_text, token_balance_text, page):
    global global_pool_keys, global_decimals, global_pair_address
    pool_keys = global_pool_keys    
    amount_text_field = swap_col.controls[2]
    compute_unit_limit_text_field = swap_col.controls[3]
    compute_unit_price_text_field = swap_col.controls[4]
    
    if not amount_text_field.value or float(amount_text_field.value) == 0:
        warning_text.value, warning_text.color = "Please enter a valid amount", "RED"
        warning_text.update()
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        token_balance_text.value = f"{balance}" if balance else "0"
        token_balance_text.update()
        await asyncio.sleep(5)
        warning_text.value = ""
        warning_text.update()
        return
    warning_text.value, warning_text.color = "Processing txn", "#14F195"
    warning_text.update()
    
    try:
        if pool_keys is None:
            logging.error("No pools keys found")
            return None
        
        amount_in = int(float(amount_text_field.value) * LAMPORTS_PER_SOL)       
        token_account, token_account_instructions = get_token_account(payer_keypair.pubkey(), Pubkey.from_string(token_address))
        balance_needed = (await AsyncClient(rpc).get_minimum_balance_for_rent_exemption(ACCOUNT_LAYOUT.sizeof())).value
                
        wsol_account_keypair = Keypair()
        wsol_token_account = wsol_account_keypair.pubkey()  
                     
        instructions = [
            create_account(system_program.CreateAccountParams(
                from_pubkey=payer_keypair.pubkey(),
                to_pubkey=wsol_account_keypair.pubkey(),
                lamports=int(balance_needed + amount_in),
                space=ACCOUNT_LAYOUT.sizeof(),
                owner=TOKEN_PROGRAM,
            )),
            initialize_account(InitializeAccountParams(
                account=wsol_account_keypair.pubkey(),
                mint=WSOL,
                owner=payer_keypair.pubkey(),
                program_id=TOKEN_PROGRAM,
            ))
        ]
        
        if token_account_instructions:
            instructions.append(token_account_instructions)
        instructions.append(await make_swap_instruction(amount_in, wsol_token_account, token_account, pool_keys, payer_keypair))
        instructions.append(close_account(CloseAccountParams(TOKEN_PROGRAM, wsol_token_account, payer_keypair.pubkey(), payer_keypair.pubkey())))
                
        if compute_unit_limit_text_field.value and int(compute_unit_limit_text_field.value) != 0:
            instructions.append(set_compute_unit_limit(int(compute_unit_limit_text_field.value)))
        
        if compute_unit_price_text_field.value and float(compute_unit_price_text_field.value) != 0:
            instructions.append(set_compute_unit_price(int(compute_unit_price_text_field.value)))
        
        blockhash = await AsyncClient(rpc).get_latest_blockhash()
        transaction = VersionedTransaction(
            MessageV0.try_compile(payer_keypair.pubkey(), instructions, [], blockhash.value.blockhash),
            [payer_keypair, wsol_account_keypair]
        )
        txn = await AsyncClient(rpc).send_transaction(transaction, opts=TxOpts(skip_preflight=True, preflight_commitment="processed"))
        logging.info(f"sig: {txn.value}")
        if confirm_txn(txn.value):
            logging.info(f'Transaction landed: https://solscan.io/tx/{txn.value}')
            page.open(show_confirm_snackbar(txn.value))
        else:
            logging.error('Couldnt confirm transaction')

        warning_text.value = "Processed txn"
        warning_text.update()
        await asyncio.sleep(5)
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        token_balance_text.value = f"{balance}" if balance else "0"
        token_balance_text.update()
        await asyncio.sleep(5)
        warning_text.value = ""
        warning_text.update()
    except Exception as e:
        logging.error(e)

async def raydium_sell(token_address, payer_keypair, swap_col, warning_text, token_balance_text, page):
    global global_pool_keys, global_decimals, global_pair_address
    pool_keys, decimals = global_pool_keys, global_decimals
    amount_text_field = swap_col.controls[2]
    compute_unit_limit_text_field = swap_col.controls[3]
    compute_unit_price_text_field = swap_col.controls[4]
    
    if not amount_text_field.value or float(amount_text_field.value) == 0:
        warning_text.value = "Please enter a valid amount"
        warning_text.color = "RED"
        warning_text.update()
        await asyncio.sleep(5)
        warning_text.value = ""
        warning_text.update()
        return
    warning_text.value = "Processing txn"
    warning_text.color = "#14F195"
    warning_text.update()
    
    try:
        if pool_keys is None:
            logging.error("No pools keys found")
            return None
        
        if decimals is None:
            logging.error("No decimals found")
            return None
        
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        balance_lamports = int(balance_lamports)
        amount_in = int(float(amount_text_field.value) * (10**decimals))  
        wsol_token_account, wsol_token_account_instructions = get_token_account(payer_keypair.pubkey(), WSOL)
                    
        swap_instructions = await make_swap_instruction(amount_in, token_account, wsol_token_account, pool_keys, payer_keypair)        
        close_account_instructions = close_account(CloseAccountParams(TOKEN_PROGRAM, token_account, payer_keypair.pubkey(), payer_keypair.pubkey())) if amount_in == balance_lamports else None
        instructions = []
        if wsol_token_account_instructions:
            instructions.append(wsol_token_account_instructions)
        instructions.append(swap_instructions)
        if close_account_instructions:
            instructions.append(close_account_instructions)  
         
        if compute_unit_limit_text_field.value and int(compute_unit_limit_text_field.value) != 0:
            instructions.append(set_compute_unit_limit(int(compute_unit_limit_text_field.value)))
        
        if compute_unit_price_text_field.value and float(compute_unit_price_text_field.value) != 0:
            instructions.append(set_compute_unit_price(int(compute_unit_price_text_field.value)))     
        blockhash = await AsyncClient(rpc).get_latest_blockhash()
        transaction = VersionedTransaction(
            MessageV0.try_compile(payer_keypair.pubkey(), instructions, [], blockhash.value.blockhash),
            [payer_keypair]
        )
        txn = await AsyncClient(rpc).send_transaction(transaction, opts=TxOpts(skip_preflight=True, preflight_commitment="processed"))
        logging.info(f"sig: {txn.value}")
        if confirm_txn(txn.value):
            logging.info(f'Transaction landed: https://solscan.io/tx/{txn.value}')
            page.open(page.open(show_confirm_snackbar(txn.value)))
        else:
            logging.error('Couldnt confirm transaction')
        
        warning_text.value = "Processed txn"
        warning_text.update()
        await asyncio.sleep(5)
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        if balance:
            token_balance_text.value = f"{balance}"
        else:
            token_balance_text.value = "0"
        token_balance_text.update()
        await asyncio.sleep(5)
        warning_text.value = ""
        warning_text.update()
            
            
    except Exception as e:
        logging.error(e)

async def burn_tokens(token_address, payer_keypair, swap_col, warning_text, token_balance_text, page):
    global global_decimals
    amount_text_field = swap_col.controls[2]
    compute_unit_limit_text_field = swap_col.controls[3]
    compute_unit_price_text_field = swap_col.controls[4]

    if not amount_text_field.value or float(amount_text_field.value) == 0:
        warning_text.value = "Please enter a valid amount"
        warning_text.color = "RED"
        warning_text.update()
        await asyncio.sleep(5)
        warning_text.value = ""
        warning_text.update()
        return
    
    warning_text.value = "Processing txn"
    warning_text.color = "#14F195"
    warning_text.update()
    
    try:
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        if global_decimals is None:
            logging.error("No decimals found")
            return

        amount_in = int(float(amount_text_field.value) * (10 ** global_decimals))
        instructions = [burn(BurnParams(
            amount=amount_in,
            account=token_account,
            mint=Pubkey.from_string(token_address),
            owner=payer_keypair.pubkey(),
            program_id=TOKEN_PROGRAM,
        ))]

        if amount_in == int(balance_lamports):
            instructions.append(close_account(CloseAccountParams(TOKEN_PROGRAM, token_account, payer_keypair.pubkey(), payer_keypair.pubkey())))
        elif amount_in > int(balance_lamports):
            logging.error("Burn amount is greater than balance")
            return
        
        if compute_unit_limit_text_field.value and int(compute_unit_limit_text_field.value) != 0:
            instructions.append(set_compute_unit_limit(int(compute_unit_limit_text_field.value)))
        
        if compute_unit_price_text_field.value and float(compute_unit_price_text_field.value) != 0:
            instructions.append(set_compute_unit_price(int(compute_unit_price_text_field.value)))

        block_hash = await AsyncClient(rpc).get_latest_blockhash(commitment=Finalized)
        transaction = VersionedTransaction(
            MessageV0.try_compile(payer_keypair.pubkey(), instructions, [], block_hash.value.blockhash),
            [payer_keypair]
        )

        txn_sig = (await AsyncClient(rpc).send_transaction(transaction, opts=TxOpts(skip_preflight=True, preflight_commitment="processed"))).value

        if confirm_txn(txn_sig):
            logging.info(f'Transaction landed: https://solscan.io/tx/{txn_sig}')
            page.open(show_confirm_snackbar(txn_sig))
        else:
            logging.error('Couldnt confirm transaction')

        warning_text.value = "Processed txn"
        warning_text.update()
        await asyncio.sleep(5)
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        if balance:
            token_balance_text.value = f"{balance}"
        else:
            token_balance_text.value = "0"
        token_balance_text.update()
        await asyncio.sleep(5)
        warning_text.value = ""
        warning_text.update()

    except Exception as e:
        logging.error(e)


async def close_token_account(token_address, payer_keypair, swap_col, warning_text, token_balance_text, page):
    warning_text.value = "Processing txn"
    warning_text.color = "#14F195"
    warning_text.update()
    compute_unit_limit_text_field = swap_col.controls[3]
    compute_unit_price_text_field = swap_col.controls[4]
    
    try:
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        instructions = [close_account(CloseAccountParams(TOKEN_PROGRAM, token_account, payer_keypair.pubkey(), payer_keypair.pubkey()))]
        if compute_unit_limit_text_field.value and int(compute_unit_limit_text_field.value) != 0:
            instructions.append(set_compute_unit_limit(int(compute_unit_limit_text_field.value)))
        
        if compute_unit_price_text_field.value and float(compute_unit_price_text_field.value) != 0:
            instructions.append(set_compute_unit_price(int(compute_unit_price_text_field.value)))
        block_hash = await AsyncClient(rpc).get_latest_blockhash(commitment=Finalized)
        transaction = VersionedTransaction(
            MessageV0.try_compile(payer_keypair.pubkey(), instructions, [], block_hash.value.blockhash),
            [payer_keypair]
        )
        txn_sig = (await AsyncClient(rpc).send_transaction(transaction, opts=TxOpts(skip_preflight=True, preflight_commitment="processed"))).value
        logging.info(f'txn_sig: {txn_sig}')
        if confirm_txn(txn_sig):
            logging.info(f'Transaction landed: https://solscan.io/tx/{txn_sig}')
            page.open(show_confirm_snackbar(txn_sig))
        else:
            logging.error('Couldn\'t confirm transaction')

        warning_text.value = "Processed txn"
        warning_text.update()
        await asyncio.sleep(5)
        token_account, balance, balance_lamports, decimals = await get_token_account_info_from_rpc(payer_keypair, token_address)
        if balance:
            token_balance_text.value = f"{balance}"
        else:
            token_balance_text.value = "0"
        token_balance_text.update()
        await asyncio.sleep(5)
        warning_text.value = ""
        warning_text.update()

    except Exception as e:
        logging.error(e)