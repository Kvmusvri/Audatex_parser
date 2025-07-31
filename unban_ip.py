#!/usr/bin/env python3
"""
Скрипт для разблокировки IP адресов
"""

import sys
import argparse
from core.security.rate_limiter import rate_limiter

def unban_ip(ip: str) -> bool:
    """Разблокировка IP адреса"""
    success = rate_limiter.unban_ip(ip)
    if success:
        print(f"✅ IP {ip} успешно разблокирован")
    else:
        print(f"❌ Ошибка разблокировки IP {ip}")
    return success

def list_banned_ips():
    """Показать список заблокированных IP"""
    banned_ips = rate_limiter.get_banned_ips()
    if banned_ips:
        print(f"📋 Заблокированные IP адреса ({len(banned_ips)}):")
        for ip in banned_ips:
            print(f"  - {ip}")
    else:
        print("✅ Нет заблокированных IP адресов")

def main():
    parser = argparse.ArgumentParser(description="Управление блокировкой IP адресов")
    parser.add_argument("--list", action="store_true", help="Показать список заблокированных IP")
    parser.add_argument("--unban", type=str, help="Разблокировать IP адрес")
    parser.add_argument("--unban-all", action="store_true", help="Разблокировать все IP адреса")
    
    args = parser.parse_args()
    
    if args.list:
        list_banned_ips()
    elif args.unban:
        unban_ip(args.unban)
    elif args.unban_all:
        banned_ips = rate_limiter.get_banned_ips()
        if banned_ips:
            print(f"🔄 Разблокировка {len(banned_ips)} IP адресов...")
            for ip in banned_ips:
                unban_ip(ip)
            print("✅ Все IP адреса разблокированы")
        else:
            print("✅ Нет заблокированных IP адресов")
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 