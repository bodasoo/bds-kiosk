"""UI와 독립적인 장바구니 병합 및 API 데이터 구성."""


def add_item(cart, menu, options, quantity=1):
    keys = ('temperature', 'exclude_carrot', 'exclude_cucumber')
    for item in cart:
        if item['menu_name'] == menu['menu_name'] and all(item.get(key) == options.get(key) for key in keys):
            item['quantity'] += quantity
            return
    cart.append({'menu_name': menu['menu_name'], 'price': int(menu['price']), 'quantity': quantity, **options})


def total(cart):
    return sum(item['price'] * item['quantity'] for item in cart)


def option_text(item):
    options = [item.get(key) for key in ('temperature', 'exclude_carrot', 'exclude_cucumber')]
    return ' · '.join(filter(None, options)) or '기본 옵션'


def order_payload(cart, store_id, store_name, order_type, spoon_needed):
    keys = ('menu_name', 'price', 'quantity', 'temperature', 'exclude_carrot', 'exclude_cucumber')
    return dict(store_id=store_id, store_name=store_name, order_type=order_type,
                spoon_needed=spoon_needed, items=[{key: item.get(key) for key in keys} for item in cart])
