# update_lowcap.py
import requests
import json
from datetime import datetime, timedelta

# شبکه‌های اصلی برای جستجو (می‌تونی اضافه کنی: eth, bsc, base و ...)
networks = ['solana', 'eth', 'bnb']

# فیلترهای پیشرفته
MIN_FDV = 1000          # حداقل FDV (برای جلوگیری از scam خیلی کوچک)
MAX_FDV = 50000         # حداکثر FDV (low-cap)
MIN_VOLUME_H24 = 1000   # حداقل حجم معاملات ۲۴ ساعته (نشانه فعالیت)
MIN_LIQUIDITY = 5000    # حداقل لیکوئیدیتی (برای امنیت)
MIN_PRICE_CHANGE_H24 = 0  # حداقل تغییر قیمت (برای پمپ مثبت)
MAX_AGE_DAYS = 3        # حداکثر عمر (تازه لانچ‌شده)
BUY_SELL_RATIO = 1.1    # نسبت خرید به فروش > 1.1 (نشانه خرید بیشتر و پمپ احتمالی)

low_caps = []
now = datetime.utcnow()

for network in networks:
    url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools"
    params = {
        "page": 1,
        "sort": "created_at_desc",  # مرتب بر اساس تازه‌ترین
        "top": 250,                 # ۲۵۰ تا برتر (برای پوشش بیشتر)
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        for pool in data.get('data', []):
            attr = pool['attributes']
            fdv = float(attr.get('fdv_usd', '0')) if attr.get('fdv_usd') else 0
            liquidity = float(attr.get('reserve_in_usd', '0')) if attr.get('reserve_in_usd') else 0
            volume_h24 = float(attr.get('volume_usd', {}).get('h24', '0'))
            price_change_h24 = float(attr.get('price_change_percentage', {}).get('h24', '0'))
            buys_h24 = int(attr.get('txns', {}).get('h24', {}).get('buys', 0))
            sells_h24 = int(attr.get('txns', {}).get('h24', {}).get('sells', 0))
            created_at_str = attr.get('created_at')
            if not created_at_str:
                continue
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            age = now - created_at

            # فیلترهای پیشرفته
            if (MIN_FDV < fdv < MAX_FDV and
                volume_h24 > MIN_VOLUME_H24 and
                liquidity > MIN_LIQUIDITY and
                price_change_h24 > MIN_PRICE_CHANGE_H24 and
                age < timedelta(days=MAX_AGE_DAYS) and
                (buys_h24 > 0 and buys_h24 / max(sells_h24, 1) > BUY_SELL_RATIO)):

                low_caps.append({
                    "name": attr['name'],
                    "fdv_usd": fdv,
                    "liquidity_usd": liquidity,
                    "volume_h24": volume_h24,
                    "price_change_h24": price_change_h24,
                    "buy_sell_ratio": buys_h24 / max(sells_h24, 1),
                    "age_days": age.days + age.seconds / 86400,  # به روز
                    "network": network,
                    "pool_address": attr['address'],
                    "gecko_link": f"https://www.geckoterminal.com/{network}/pools/{attr['address']}"
                })

    except Exception as e:
        print(f"خطا در شبکه {network}: {e}")

# مرتب‌سازی بر اساس تغییر قیمت (بالاترین پمپ اول)
low_caps.sort(key=lambda x: x['price_change_h24'], reverse=True)

# فقط ۳۰ تا برتر نگه دار (برای جلوگیری از لیست طولانی)
output = {
    "timestamp": now.strftime("%Y-%m-%d %H:%M UTC"),
    "tokens": low_caps[:30]
}

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"آپدیت شد: {len(low_caps)} جم low-cap پیدا شد")
