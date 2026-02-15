import requests
import json
from datetime import datetime, timedelta

# ================= تنظیمات =================
# آیدی دسته‌بندی Pump.swap در GeckoTerminal
# اگر دقیقاً نمی‌دونی، می‌تونی از تابع auto_detect_category_id استفاده کنی
PUMP_SWAP_CATEGORY_ID = "pump-swap"  # حدس من اینه - اگه کار نکرد، ببین پایین توضیح دادم چطور پیدا کنی

# فیلترهای پیشرفته (مثل قبل)
MIN_FDV = 1000
MAX_FDV = 50000
MIN_VOLUME_H24 = 1000
MIN_LIQUIDITY = 5000
MIN_PRICE_CHANGE_H24 = 0
MAX_AGE_DAYS = 3
BUY_SELL_RATIO = 1.1
# ===========================================

def get_category_id_by_name(target_name="Pump Swap"):
    """
    اگر از آیدی دقیق مطمئن نیستی، این تابع لیست دسته‌بندی‌ها رو از API می‌گیره
    و اولین دسته‌ای که اسمش شبیه target_name باشه رو برمی‌گردونه
    """
    url = "https://api.geckoterminal.com/api/v2/categories"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        for cat in data.get('data', []):
            cat_name = cat['attributes']['name']
            if target_name.lower() in cat_name.lower():
                return cat['id']
        print(f"دسته‌بندی '{target_name}' پیدا نشد. از آیدی پیش‌فرض '{PUMP_SWAP_CATEGORY_ID}' استفاده می‌شه.")
        return PUMP_SWAP_CATEGORY_ID
    except Exception as e:
        print(f"خطا در گرفتن لیست دسته‌بندی‌ها: {e}")
        return PUMP_SWAP_CATEGORY_ID

def main():
    # (اختیاری) اگر می‌خوای خودکار دسته‌بندی رو تشخیص بده، خط زیر رو فعال کن
    # category_id = get_category_id_by_name("Pump Swap")
    category_id = PUMP_SWAP_CATEGORY_ID  # یا همون مقداری که خودت می‌دونی

    # ساخت URL برای گرفتن استخرهای این دسته
    url = f"https://api.geckoterminal.com/api/v2/categories/{category_id}/pools"
    params = {
        "page": 1,
        "sort": "created_at_desc",   # جدیدترین‌ها اول
        "top": 250,                  # ۲۵۰ تا استخر آخر
    }

    low_caps = []
    now = datetime.utcnow()

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        for pool in data.get('data', []):
            attr = pool['attributes']

            # استخر حتماً روی سولانا باشه (اختیاری، چون خود دسته ممکنه مختص سولانا باشه)
            network = pool['relationships']['network']['data']['id']
            if network != 'solana':
                continue

            # گرفتن مقادیر
            fdv = float(attr.get('fdv_usd', 0) or 0)
            liquidity = float(attr.get('reserve_in_usd', 0) or 0)
            volume_h24 = float(attr.get('volume_usd', {}).get('h24', 0) or 0)
            price_change_h24 = float(attr.get('price_change_percentage', {}).get('h24', 0) or 0)
            buys_h24 = int(attr.get('txns', {}).get('h24', {}).get('buys', 0))
            sells_h24 = int(attr.get('txns', {}).get('h24', {}).get('sells', 0))

            created_at_str = attr.get('created_at')
            if not created_at_str:
                continue
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            age = now - created_at

            # اعمال فیلترها
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
                    "age_days": age.days + age.seconds / 86400,
                    "network": network,
                    "pool_address": attr['address'],
                    "gecko_link": f"https://www.geckoterminal.com/{network}/pools/{attr['address']}"
                })

    except Exception as e:
        print(f"خطا در دریافت از Pump.swap: {e}")

    # مرتب‌سازی بر اساس بیشترین تغییر قیمت (پمپ‌ترین‌ها اول)
    low_caps.sort(key=lambda x: x['price_change_h24'], reverse=True)

    # فقط ۳۰ تا برتر
    output = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M UTC"),
        "tokens": low_caps[:30]
    }

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"آپدیت شد: {len(low_caps)} جم low-cap از Pump.swap پیدا شد.")

if __name__ == "__main__":
    main()
