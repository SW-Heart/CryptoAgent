// Coin detection patterns and TradingView symbol mappings
export const COIN_DATA = {
    BTC: { patterns: ['BTC', 'Bitcoin', '比特币'], symbol: 'BINANCE:BTCUSDT', name: 'Bitcoin', color: '#F7931A' },
    ETH: { patterns: ['ETH', 'Ethereum', '以太坊'], symbol: 'BINANCE:ETHUSDT', name: 'Ethereum', color: '#627EEA' },
    SOL: { patterns: ['SOL', 'Solana', '索拉纳'], symbol: 'BINANCE:SOLUSDT', name: 'Solana', color: '#00FFA3' },
    BNB: { patterns: ['BNB', 'Binance Coin', '币安币'], symbol: 'BINANCE:BNBUSDT', name: 'BNB', color: '#F3BA2F' },
    XRP: { patterns: ['XRP', 'Ripple', '瑞波'], symbol: 'BINANCE:XRPUSDT', name: 'XRP', color: '#23292F' },
    DOGE: { patterns: ['DOGE', 'Dogecoin', '狗狗币'], symbol: 'BINANCE:DOGEUSDT', name: 'Dogecoin', color: '#C2A633' },
    ADA: { patterns: ['ADA', 'Cardano', '卡尔达诺'], symbol: 'BINANCE:ADAUSDT', name: 'Cardano', color: '#0033AD' },
    AVAX: { patterns: ['AVAX', 'Avalanche', '雪崩'], symbol: 'BINANCE:AVAXUSDT', name: 'Avalanche', color: '#E84142' },
    DOT: { patterns: ['DOT', 'Polkadot', '波卡'], symbol: 'BINANCE:DOTUSDT', name: 'Polkadot', color: '#E6007A' },
    MATIC: { patterns: ['MATIC', 'Polygon', 'POL'], symbol: 'BINANCE:MATICUSDT', name: 'Polygon', color: '#8247E5' },
    LINK: { patterns: ['LINK', 'Chainlink'], symbol: 'BINANCE:LINKUSDT', name: 'Chainlink', color: '#2A5ADA' },
    UNI: { patterns: ['UNI', 'Uniswap'], symbol: 'BINANCE:UNIUSDT', name: 'Uniswap', color: '#FF007A' },
    ATOM: { patterns: ['ATOM', 'Cosmos'], symbol: 'BINANCE:ATOMUSDT', name: 'Cosmos', color: '#2E3148' },
    LTC: { patterns: ['LTC', 'Litecoin', '莱特币'], symbol: 'BINANCE:LTCUSDT', name: 'Litecoin', color: '#BFBBBB' },
    ARB: { patterns: ['ARB', 'Arbitrum'], symbol: 'BINANCE:ARBUSDT', name: 'Arbitrum', color: '#28A0F0' },
    OP: { patterns: ['OP', 'Optimism'], symbol: 'BINANCE:OPUSDT', name: 'Optimism', color: '#FF0420' },
    APT: { patterns: ['APT', 'Aptos'], symbol: 'BINANCE:APTUSDT', name: 'Aptos', color: '#000000' },
    SUI: { patterns: ['SUI'], symbol: 'BINANCE:SUIUSDT', name: 'Sui', color: '#6FBCF0' },
    PEPE: { patterns: ['PEPE'], symbol: 'BINANCE:PEPEUSDT', name: 'Pepe', color: '#4CAF50' },
    WIF: { patterns: ['WIF', 'dogwifhat'], symbol: 'BINANCE:WIFUSDT', name: 'dogwifhat', color: '#D4A574' },
};

// Function to detect coins from text content
export const detectCoinsFromText = (text) => {
    const found = new Set();
    const upperText = text.toUpperCase();

    Object.entries(COIN_DATA).forEach(([coin, data]) => {
        data.patterns.forEach(pattern => {
            const regex = new RegExp(`\\b${pattern.toUpperCase()}\\b`, 'i');
            if (regex.test(upperText)) {
                found.add(coin);
            }
        });
    });

    return Array.from(found);
};
