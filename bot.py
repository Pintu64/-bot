#!/usr/bin/env python3
"""
Telegram Crypto Price Bot for Bitget
"""

import os
import json
import hmac
import base64
import hashlib
import time
import asyncio
from datetime import datetime
from typing import Dict, Optional
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BitgetAPI:
    """Secure Bitget API wrapper"""
    
    def __init__(self):
        self.base_url = "https://api.bitget.com"
        self.api_key = os.getenv('BITGET_API_KEY')
        self.secret_key = os.getenv('BITGET_SECRET_KEY')
        self.passphrase = os.getenv('BITGET_PASSPHRASE')
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str) -> str:
        """Generate signature for authenticated requests"""
        if not self.secret_key:
            return ""
        message = timestamp + method + request_path
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def get_spot_price(self, symbol: str) -> Dict:
        """Get current spot price (no auth needed)"""
        url = f"{self.base_url}/api/v2/spot/market/tickers"
        params = {"symbol": symbol.upper()}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("code") == "00000" and data.get("data"):
                return data["data"][0]
            return {}
        except Exception as e:
            print(f"Error fetching price: {e}")
            return {}
    
    def get_multiple_prices(self, symbols: list) -> Dict:
        """Get prices for multiple symbols"""
        prices = {}
        for symbol in symbols:
            price_data = self.get_spot_price(symbol)
            if price_data:
                prices[symbol] = price_data
            time.sleep(0.1)  # Rate limit protection
        return prices


class CryptoTelegramBot:
    """Telegram bot for crypto price checks"""
    
    def __init__(self):
        self.bitget = BitgetAPI()
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message when /start is issued"""
        welcome_msg = """
🤖 *Welcome to Bitget Crypto Price Bot!*

I can help you check cryptocurrency prices in real-time from Bitget exchange.

*Available Commands:*
💰 `/price <symbol>` - Get current price (e.g., /price BTC)
📊 `/menu` - Open interactive menu with popular coins
📈 `/trending` - Show top gainers and losers
ℹ️ `/help` - Show detailed help

*Supported symbols:* BTC, ETH, SOL, XRP, DOGE, ADA, MATIC, LINK, and more!

*Examples:*
• `/price BTCUSDT`
• `/price ETHUSDT`
• `/price SOL`

*Note:* Add 'USDT' for USDT pairs (recommended)
        """
        
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send detailed help message"""
        help_text = """
📚 *Detailed Commands Guide*

*/price <symbol>* - Get real-time price
Example: `/price BTCUSDT`

*/menu* - Interactive price menu
Shows popular cryptocurrencies with buttons

*/trending* - Market trends
See which coins are moving

*/start* - Restart the bot
*/help* - Show this message

*Quick Tips:*
• Use USDT pairs for best results (BTCUSDT, ETHUSDT)
• Prices update every 2-3 seconds
• Data comes directly from Bitget exchange
• 24h change shows price movement percentage

*Need support?* Contact your administrator
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def get_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get cryptocurrency price"""
        if not context.args:
            await update.message.reply_text(
                "❌ *Please specify a trading pair!*\n\n"
                "Example: `/price BTCUSDT`\n"
                "Example: `/price ETHUSDT`\n"
                "Example: `/price SOL` (will add USDT automatically)",
                parse_mode='Markdown'
            )
            return
        
        symbol = context.args[0].upper()
        
        # Add USDT if not present (for common pairs)
        if not symbol.endswith('USDT') and len(symbol) <= 5:
            original = symbol
            symbol = f"{symbol}USDT"
            await update.message.reply_text(f"🔍 Fetching price for {original} ({symbol})...")
        else:
            await update.message.reply_text(f"🔍 Fetching price for {symbol}...")
        
        price_data = self.bitget.get_spot_price(symbol)
        
        if price_data:
            last_price = price_data.get('lastPr', 'N/A')
            change_24h = float(price_data.get('change24h', 0)) * 100
            high_24h = price_data.get('high24h', 'N/A')
            low_24h = price_data.get('low24h', 'N/A')
            volume = price_data.get('baseVolume', 'N/A')
            
            # Create price display
            emoji = "🟢" if change_24h >= 0 else "🔴"
            trend = "▲" if change_24h >= 0 else "▼"
            
            message = f"""
📊 *{symbol} Market Update*

💰 *Current Price:* `${float(last_price):,.2f}`

{emoji} *24h Change:* `{change_24h:+.2f}%` {trend}

📈 *24h High:* `${float(high_24h):,.2f}`
📉 *24h Low:* `${float(low_24h):,.2f}`

📊 *24h Volume:* `{float(volume):,.0f}` {symbol.replace('USDT', '')}

🕐 *Updated:* {datetime.now().strftime('%H:%M:%S')}
            """
            
            await update.message.reply_text(message, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                f"❌ *Could not find price for {symbol}*\n\n"
                "Please check:\n"
                "• Symbol is correct (e.g., BTCUSDT, ETHUSDT)\n"
                "• Trading pair exists on Bitget\n"
                "• Try `/menu` for popular options",
                parse_mode='Markdown'
            )
    
    async def show_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show interactive menu with popular coins"""
        keyboard = [
            [
                InlineKeyboardButton("₿ Bitcoin - BTC", callback_data="price_BTCUSDT"),
                InlineKeyboardButton("⟠ Ethereum - ETH", callback_data="price_ETHUSDT"),
            ],
            [
                InlineKeyboardButton("◎ Solana - SOL", callback_data="price_SOLUSDT"),
                InlineKeyboardButton("🔷 Ripple - XRP", callback_data="price_XRPUSDT"),
            ],
            [
                InlineKeyboardButton("🐕 Dogecoin - DOGE", callback_data="price_DOGEUSDT"),
                InlineKeyboardButton("🔶 Cardano - ADA", callback_data="price_ADAUSDT"),
            ],
            [
                InlineKeyboardButton("🟣 Polygon - MATIC", callback_data="price_MATICUSDT"),
                InlineKeyboardButton("⚡ Chainlink - LINK", callback_data="price_LINKUSDT"),
            ],
            [
                InlineKeyboardButton("🔄 Refresh All", callback_data="refresh_all"),
                InlineKeyboardButton("📈 Top Movers", callback_data="top_movers"),
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📊 *Select a cryptocurrency to check price:*\n\n"
            "Click any button to see real-time price",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button presses"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("price_"):
            symbol = query.data.replace("price_", "")
            price_data = self.bitget.get_spot_price(symbol)
            
            if price_data:
                last_price = price_data.get('lastPr', 'N/A')
                change_24h = float(price_data.get('change24h', 0)) * 100
                high_24h = price_data.get('high24h', 'N/A')
                low_24h = price_data.get('low24h', 'N/A')
                
                emoji = "🟢" if change_24h >= 0 else "🔴"
                message = f"""
💰 *{symbol}*

💵 Price: `${float(last_price):,.2f}`
{emoji} 24h: `{change_24h:+.2f}%`
📈 High: `${float(high_24h):,.2f}`
📉 Low: `${float(low_24h):,.2f}`

🕐 {datetime.now().strftime('%H:%M:%S')}
                """
                await query.edit_message_text(message, parse_mode='Markdown')
                # Restore menu after 30 seconds
                await asyncio.sleep(30)
                await query.edit_message_text(
                    "📊 *Select a cryptocurrency to check price:*",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("₿ Bitcoin", callback_data="price_BTCUSDT"),
                            InlineKeyboardButton("⟠ Ethereum", callback_data="price_ETHUSDT"),
                        ],
                        [
                            InlineKeyboardButton("◎ Solana", callback_data="price_SOLUSDT"),
                            InlineKeyboardButton("🔷 XRP", callback_data="price_XRPUSDT"),
                        ]
                    ])
                )
            else:
                await query.edit_message_text(f"❌ Error fetching {symbol}")
        
        elif query.data == "refresh_all":
            await query.edit_message_text("🔄 Fetching latest prices...")
            
            popular_coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
            message = "📊 *Current Market Prices*\n\n"
            
            for coin in popular_coins:
                price_data = self.bitget.get_spot_price(coin)
                if price_data:
                    last_price = price_data.get('lastPr', 'N/A')
                    change = float(price_data.get('change24h', 0)) * 100
                    emoji = "🟢" if change >= 0 else "🔴"
                    coin_name = coin.replace("USDT", "")
                    message += f"*{coin_name}*: `${float(last_price):,.2f}` {emoji} `{change:+.1f}%`\n"
                await asyncio.sleep(0.1)
            
            message += f"\n🕐 Updated: {datetime.now().strftime('%H:%M:%S')}"
            await query.edit_message_text(message, parse_mode='Markdown')
        
        elif query.data == "top_movers":
            await query.edit_message_text("📈 *Top Movers (24h)*\n\nFetching data...")
            # This would require additional API calls
            await query.edit_message_text(
                "📈 *Top Movers*\n\n"
                "🟢 *Top Gainers:*\n"
                "• Check using `/price` command\n\n"
                "🔴 *Top Losers:*\n"
                "• Check using `/price` command\n\n"
                "Use `/menu` for interactive price checking!",
                parse_mode='Markdown'
            )
    
    async def trending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show trending cryptocurrencies"""
        message = """
📈 *Market Overview*

*Top Cryptocurrencies:*
₿ *BTC*: Checking...
⟠ *ETH*: Checking...
◎ *SOL*: Checking...

Use `/menu` to check prices interactively!

*Quick Commands:*
• `/price BTCUSDT` - Bitcoin price
• `/price ETHUSDT` - Ethereum price
• `/price SOLUSDT` - Solana price
        """
        await update.message.reply_text(message, parse_mode='Markdown')
        
        # Fetch and update with actual prices
        popular = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        prices = self.bitget.get_multiple_prices(popular)
        
        if prices:
            updated_msg = "📈 *Market Overview*\n\n"
            for symbol, data in prices.items():
                last_price = data.get('lastPr', 'N/A')
                change = float(data.get('change24h', 0)) * 100
                emoji = "🟢" if change >= 0 else "🔴"
                name = symbol.replace("USDT", "")
                updated_msg += f"*{name}*: `${float(last_price):,.2f}` {emoji} `{change:+.1f}%`\n"
            
            updated_msg += f"\n🕐 {datetime.now().strftime('%H:%M:%S')}\n\nUse `/menu` for more options!"
            await update.message.reply_text(updated_msg, parse_mode='Markdown')
    
    def run(self):
        """Start the bot"""
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("price", self.get_price))
        application.add_handler(CommandHandler("menu", self.show_menu))
        application.add_handler(CommandHandler("trending", self.trending))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Start bot
        print("🤖 Bot is starting...")
        print(f"Bot token: {self.token[:10]}...")
        print("Press Ctrl+C to stop")
        print("=" * 50)
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point"""
    print("=" * 50)
    print("🤖 Telegram Crypto Price Bot")
    print("=" * 50)
    
    # Check environment variables
    if not os.getenv('TELEGRAM_BOT_TOKEN'):
        print("\n❌ TELEGRAM_BOT_TOKEN not found!")
        print("\n📝 Create a .env file with:")
        print("TELEGRAM_BOT_TOKEN=your_token_here")
        print("BITGET_API_KEY=your_api_key_here")
        print("BITGET_SECRET_KEY=your_secret_key_here")
        print("BITGET_PASSPHRASE=your_passphrase_here")
        print("\nThen run: python bot.py")
        return
    
    if not os.getenv('BITGET_API_KEY'):
        print("\n⚠️ Warning: BITGET_API_KEY not found!")
        print("Price checking will still work but some features may be limited.\n")
    
    # Run bot
    try:
        bot = CryptoTelegramBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
