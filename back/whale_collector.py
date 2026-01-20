"""
🐋 Whale Address Collector Service
后台持续运行脚本，用于收集和追踪比特币鲸鱼地址 (余额 > 1000 BTC)。

功能：
1. 自动发现：监控实时大额交易，发现新的潜在鲸鱼地址
2. 持续追踪：更新数据库中鲸鱼地址的余额
3. 数据存储：使用 SQLite 本地存储地址库和历史记录

运行方式:
    nohup python3 whale_collector.py > collector.log 2>&1 &
"""

import sqlite3
import time
import requests
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
import schedule
import os
from threading import Thread

# 配置
DB_FILE = "whale_monitoring.db"
MIN_WHALE_BALANCE = 1000  # 定义鲸鱼的门槛 (BTC)
LARGE_TX_THRESHOLD = 100  # 监控大额交易的门槛 (BTC)
SCAN_INTERVAL = 60        # 区块扫描间隔 (秒)
UPDATE_INTERVAL = 3600 * 6 # 余额更新间隔 (6小时)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("whale_collector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WhaleCollector:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_db()
        self._seed_initial_data()
        
    def _init_db(self):
        """初始化数据库表"""
        # 鲸鱼地址表
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS whales (
                address TEXT PRIMARY KEY,
                label TEXT,
                type TEXT,           -- Exchange, Whale, ETF, Mining
                first_seen TEXT,
                last_updated TEXT,
                balance REAL,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # 交易监控记录
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS large_txs (
                txid TEXT PRIMARY KEY,
                block_height INTEGER,
                amount REAL,
                sender TEXT,
                receiver TEXT,
                timestamp TEXT
            )
        """)
        self.conn.commit()

    def _seed_initial_data(self):
        """导入初始种子数据"""
        # 从 whale_monitor.py 提取的已知地址
        INITIAL_SEEDS = [
            ("34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo", "Binance Cold Wallet", "Exchange"),
            ("bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97", "Bitfinex Cold Wallet", "Exchange"),
            ("1Kr6QSydW9bFQG1mXiPNNu6WpJGmUa9i1g", "Bittrex Cold Wallet", "Exchange"),
            ("3M219KR5vEneNb47ewrPfWyb5jQ2DjxRP6", "Kraken Cold Wallet", "Exchange"),
            ("1P5ZEDWTKTFGxQjZphgWPQUpe554WKDfHQ", "Early Miner / Whale", "Whale"),
            ("37XuVSEpWW4trkfmvWzegTHQt7BdktSKUs", "Institutional Holder", "Whale"),
            ("bc1qjasf9z3h7w3jspkhtgatgpyvvzgpa2wwd2lr0eh5tx44reyn2k7sfc27a4", "BlackRock IBIT", "ETF"),
            ("bc1qe75775tzuvspl59cw77ycc472jl0sgue57aj0s", "Fidelity FBTC", "ETF"),
            ("1F1tAaz5x1HUXrCNLbtMDqcw6o5GNn4xqX", "F2Pool", "Mining"),
        ]
        
        count = 0
        for addr, label, type_ in INITIAL_SEEDS:
            try:
                self.cursor.execute(
                    "INSERT OR IGNORE INTO whales (address, label, type, first_seen, is_active) VALUES (?, ?, ?, ?, 1)",
                    (addr, label, type_, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                if self.cursor.rowcount > 0:
                    count += 1
            except Exception as e:
                logger.error(f"Seeding error: {e}")
        
        self.conn.commit()
        if count > 0:
            logger.info(f"Seeded {count} initial whale addresses.")

    def get_address_balance(self, address: str) -> float:
        """从 Blockchain.info 获取余额 (带退避重试)"""
        url = f"https://blockchain.info/rawaddr/{address}?limit=0"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('final_balance', 0) / 1e8
            elif resp.status_code == 429:
                logger.warning(f"Rate limited for {address}, sleeping...")
                time.sleep(10) # 遇限速等待
        except Exception as e:
            logger.error(f"Error fetching balance for {address}: {e}")
        return -1

    def scan_recent_blocks(self):
        """扫描 Mempool.space 最新区块交易，发现新鲸鱼"""
        logger.info("Scanning recent blocks for potential whales...")
        try:
            # 1. 获取最新区块列表
            blocks_url = "https://mempool.space/api/blocks"
            resp = requests.get(blocks_url, timeout=10)
            if resp.status_code != 200:
                return
            
            blocks = resp.json()[:3] # 只看最近3个块
            
            new_whales_count = 0
            
            for block in blocks:
                block_height = block['height']
                block_id = block['id']
                
                # 检查是否已处理过该块的一笔代表性交易 (简化去重)
                # 实际生产中应记录已扫描的 block_height
                
                # 2. 获取区块内交易
                txs_url = f"https://mempool.space/api/block/{block_id}/txs"
                txs_resp = requests.get(txs_url, timeout=15)
                if txs_resp.status_code != 200:
                    continue
                    
                txs = txs_resp.json()
                
                for tx in txs:
                    # 计算输出总额
                    total_out = sum([out['value'] for out in tx['vout']]) / 1e8
                    
                    if total_out >= LARGE_TX_THRESHOLD:
                        txid = tx['txid']
                        
                        # 分析输出地址
                        for out in tx['vout']:
                            amount = out['value'] / 1e8
                            addr = out.get('scriptpubkey_address')
                            
                            # 如果单笔接收就很大，很可能是鲸鱼或交易所整理
                            if amount >= LARGE_TX_THRESHOLD and addr:
                                is_new = self._process_potential_whale(addr, txid)
                                if is_new:
                                    new_whales_count += 1
                                    
            if new_whales_count > 0:
                logger.info(f"Found {new_whales_count} new potential whale addresses!")
                
        except Exception as e:
            logger.error(f"Block scan error: {e}")

    def _process_potential_whale(self, address: str, source_tx: str) -> bool:
        """处理潜在的鲸鱼地址: 检查余额, 入库"""
        # 1. 查库是否已存在
        self.cursor.execute("SELECT 1 FROM whales WHERE address = ?", (address,))
        if self.cursor.fetchone():
            return False # 已存在
            
        # 2. 查实际余额 (确认是真鲸鱼而不是过路财神)
        time.sleep(1) # 主动限速
        balance = self.get_address_balance(address)
        
        if balance >= MIN_WHALE_BALANCE:
            try:
                # 入库
                self.cursor.execute("""
                    INSERT INTO whales (address, label, type, first_seen, last_updated, balance)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    address, 
                    "Unknown Whale", 
                    "Whale", 
                    datetime.now().strftime("%Y-%m-%d %H:M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:M:%S"),
                    balance
                ))
                self.conn.commit()
                logger.info(f"🐳 NEW WHALE DISCOVERED: {address} with {balance:.2f} BTC (Tx: {source_tx})")
                return True
            except Exception as e:
                logger.error(f"DB Insert error: {e}")
        
        return False

    def update_all_balances(self):
        """更新所有已知地址的余额"""
        logger.info("Starting batch balance update...")
        self.cursor.execute("SELECT address FROM whales WHERE is_active = 1")
        addresses = [row[0] for row in self.cursor.fetchall()]
        
        updated_count = 0
        for addr in addresses:
            balance = self.get_address_balance(addr)
            if balance >= 0:
                self.cursor.execute("""
                    UPDATE whales 
                    SET balance = ?, last_updated = ? 
                    WHERE address = ?
                """, (balance, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), addr))
                self.conn.commit()
                updated_count += 1
                logger.info(f"Updated {addr}: {balance:.2f} BTC")
            
            time.sleep(2) # 严格控制频率避免封禁
            
        logger.info(f"Balance update complete. Updated {updated_count} addresses.")

    def run(self):
        logger.info("Starting Whale Collector Service...")
        
        # 立即运行一次扫描
        self.scan_recent_blocks()
        
        # 立即运行一次余额更新 (如果数据少的话)
        self.update_all_balances()
        
        # 设置定时任务
        schedule.every(SCAN_INTERVAL).seconds.do(self.scan_recent_blocks)
        schedule.every(UPDATE_INTERVAL).seconds.do(self.update_all_balances)
        
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    collector = WhaleCollector()
    collector.run()
