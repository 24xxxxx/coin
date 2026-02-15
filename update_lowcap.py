import requests
import json
from datetime import datetime, timedelta

# ================= تنظیمات =================
NETWORK = "solana"                # شبکه مورد نظر
DEX = "pumpswap"                  # صرافی غیرمتمرکز (pumpswap)
MIN_FDV = 1000
MAX_FDV = 50000
MIN_VOLUME_H24 = 1000
MIN_LIQUIDITY = 5000
MIN_PRICE_CHANGE_H24 = 0
MIN_AGE_DAYS = 3                   # حداقل عمر (۳ روز)
MAX_AGE_DAYS = 30                  # حداکثر عمر (۱ ماه)
BUY_SELL_RATIO = 1.1
# ===========================================

def fetch_pools_from_geckoterminal():
    """
    دریافت استخرها از API جیکوترمینال با فیلتر شبکه و DEX
    """
    base_url = "https://api.geckoterminal.com/api/v2/networks/solana/pools"
    
    all_pools = []
    page = 1
    has_more = True
    
    while has_more and page <= 5:  # حداکثر ۵ صفحه (هر صفحه ۱۰۰ استخر)
        params = {
            "page": page,
            "sort": "created_at_desc",  # جدیدترین‌ها
            "include": "dex",           # شامل اطلاعات DEX
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=15)
            data = response.json()
            
            pools = data.get('data', [])
            if not pools:
                break
            
            for pool in pools:
                dex_info = pool.get('relationships', {}).get('dex', {}).get('data', {})
                dex_id = dex_info.get('id', '').lower()
                
                if dex_id != DEX:
                    continue
                
                all_pools.append(pool)
            
            if len(pools) < 100:
                has_more = False
            else:
                page += 1
                
        except Exception as e:
            print(f"خطا در صفحه {page}: {e}")
            break
    
    return all_pools

def main():
    print("در حال دریافت استخرهای PumpSwap از شبکه سولانا...")
    pools = fetch_pools_from_geckoterminal()
    
    low_caps = []
    now = datetime.utcnow()
    
    for pool in pools:
        attr = pool['attributes']
        
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
        
        # اعمال فیلترهای اصلی + شرط جدید عمر بین ۳ روز تا ۳۰ روز
        if (MIN_FDV < fdv < MAX_FDV and
            volume_h24 > MIN_VOLUME_H24 and
            liquidity > MIN_LIQUIDITY and
            price_change_h24 > MIN_PRICE_CHANGE_H24 and
            timedelta(days=MIN_AGE_DAYS) < age < timedelta(days=MAX_AGE_DAYS) and
            (buys_h24 > 0 and buys_h24 / max(sells_h24, 1) > BUY_SELL_RATIO)):
            
            low_caps.append({
                "name": attr['name'],
                "fdv_usd": fdv,
                "liquidity_usd": liquidity,
                "volume_h24": volume_h24,
                "price_change_h24": price_change_h24,
                "buy_sell_ratio": buys_h24 / max(sells_h24, 1),
                "age_days": age.days + age.seconds / 86400,
                "network": "solana",
                "pool_address": attr['address'],
                "gecko_link": f"https://www.geckoterminal.com/solana/pools/{attr['address']}"
            })
    
    low_caps.sort(key=lambda x: x['price_change_h24'], reverse=True)
    
    output = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M UTC"),
        "tokens": low_caps[:30]
    }
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"آپدیت شد: {len(low_caps)} جم low-cap (عمر بین ۳ روز تا ۱ ماه) از PumpSwap روی سولانا پیدا شد.")

if __name__ == "__main__":
    main()
