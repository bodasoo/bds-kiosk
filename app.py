"""python app.py: 서버와 매장 화면을 관리하는 단일 실행 진입점."""
import argparse


def main():
    parser = argparse.ArgumentParser(description="보다수 키오스크 통합 실행")
    parser.add_argument("--mode", choices=("launcher", "server", "coffee", "gimbap", "kitchen", "mobile-demo"), default="launcher")
    args = parser.parse_args()
    if args.mode == 'mobile-demo':
        from kiosk.mobile_demo import run_demo
        run_demo()
        return
    if args.mode in ('launcher', 'kitchen'):
        from kiosk.clients.admin import require_login
        if not require_login():
            return
    if args.mode == "server":
        from kiosk.server import run_server
        run_server()
    elif args.mode == "coffee":
        from kiosk.clients.coffee import BodasuCoffeeKiosk
        BodasuCoffeeKiosk().mainloop()
    elif args.mode == "gimbap":
        from kiosk.clients.gimbap import GimbapKiosk
        GimbapKiosk().mainloop()
    elif args.mode == "kitchen":
        from kiosk.clients.kitchen import KitchenWindow
        KitchenWindow().mainloop()
    else:
        from kiosk.launcher import run_launcher
        run_launcher()


if __name__ == "__main__":
    main()
