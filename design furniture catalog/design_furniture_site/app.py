import os

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from db import connect_db

app = Flask(__name__)
app.secret_key = "super_secret_key_change_me"  # замени в реальном проекте

UPLOAD_FOLDER = os.path.join("static", "images", "products")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------------------------------------------------
# Вспомогательные функции
# -------------------------------------------------
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def login_required(view_func):
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Для выполнения этого действия необходимо войти в систему", "error")
            return redirect(url_for("login_page"))
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def get_or_create_cart_for_user(user_id):
    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM carts WHERE user_id = %s AND is_active = 1 ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            cart = cursor.fetchone()
            if cart:
                return cart

            cursor.execute(
                "INSERT INTO carts (user_id, is_active) VALUES (%s, 1)",
                (user_id,)
            )
            conn.commit()
            cart_id = cursor.lastrowid
            cursor.execute("SELECT * FROM carts WHERE id = %s", (cart_id,))
            return cursor.fetchone()
    finally:
        conn.close()


# -------------------------------------------------
# Авторизация / регистрация
# -------------------------------------------------
@app.route("/login", methods=["GET"])
def login_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
    finally:
        conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        flash("Неверный email или пароль", "error")
        return redirect(url_for("login_page"))

    session["user_id"] = user["id"]
    return redirect(url_for("home"))


@app.route("/register", methods=["POST"])
def register():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")

    if not full_name or not email or not password:
        flash("Заполните все обязательные поля", "error")
        return redirect(url_for("login_page"))

    if password != password_confirm:
        flash("Пароли не совпадают", "error")
        return redirect(url_for("login_page"))

    password_hash = generate_password_hash(password)

    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            # по умолчанию роль customer (id=3)
            cursor.execute(
                "INSERT INTO users (role_id, full_name, email, phone, password_hash) "
                "VALUES (%s, %s, %s, %s, %s)",
                (3, full_name, email, phone, password_hash)
            )
            conn.commit()
            new_user_id = cursor.lastrowid
    except Exception as e:
        conn.rollback()
        print("Register error:", e)
        flash("Пользователь с таким email уже существует или произошла ошибка", "error")
        return redirect(url_for("login_page"))
    finally:
        conn.close()

    session["user_id"] = new_user_id
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# -------------------------------------------------
# Основные страницы (доступны всем)
# -------------------------------------------------
@app.route("/")
def index():
    # При входе на сайт сразу главная
    return redirect(url_for("home"))


@app.route("/home")
def home():
    user = get_current_user()

    conn = connect_db()
    products = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.name, p.slug, p.short_desc,
                       pi.image_url
                FROM products p
                LEFT JOIN product_images pi
                    ON pi.product_id = p.id AND pi.is_main = 1
                WHERE p.is_active = 1
                ORDER BY RAND()
                LIMIT 5;
            """)
            products = cursor.fetchall()
    finally:
        conn.close()

    return render_template("home.html", user=user, products=products)


@app.route("/catalog")
def catalog():
    user = get_current_user()
    category_id = request.args.get("category", type=int)
    search_query = request.args.get("q", "", type=str).strip()
    price_from = request.args.get("price_from", type=float)
    price_to = request.args.get("price_to", type=float)

    conn = connect_db()
    categories = []
    products = []
    try:
        with conn.cursor() as cursor:
            # категории для фильтра слева
            cursor.execute(
                "SELECT id, name FROM categories WHERE is_visible = 1 ORDER BY sort_order, name"
            )
            categories = cursor.fetchall()

            # базовый запрос по товарам
            sql = """
                SELECT p.id, p.name, p.slug, p.short_desc, p.base_price,
                       pi.image_url
                FROM products p
                LEFT JOIN product_images pi
                    ON pi.product_id = p.id AND pi.is_main = 1
                WHERE p.is_active = 1
            """
            params = []

            if category_id:
                sql += " AND p.category_id = %s"
                params.append(category_id)

            if search_query:
                sql += " AND p.name LIKE %s"
                params.append(f"%{search_query}%")

            if price_from is not None:
                sql += " AND p.base_price >= %s"
                params.append(price_from)

            if price_to is not None:
                sql += " AND p.base_price <= %s"
                params.append(price_to)

            sql += " ORDER BY p.created_at DESC"

            cursor.execute(sql, params)
            products = cursor.fetchall()
    finally:
        conn.close()

    return render_template(
        "catalog.html",
        user=user,
        categories=categories,
        products=products,
        current_category_id=category_id,
        search_query=search_query,
        price_from=price_from,
        price_to=price_to
    )


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    user = get_current_user()

    conn = connect_db()
    product = None
    images = []
    in_cart = False

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM products WHERE id = %s AND is_active = 1", (product_id,))
            product = cursor.fetchone()
            if not product:
                abort(404)

            cursor.execute("""
                SELECT * FROM product_images
                WHERE product_id = %s
                ORDER BY is_main DESC, sort_order ASC, id ASC
            """, (product_id,))
            images = cursor.fetchall()

            if user:
                # проверяем, есть ли товар в активной корзине пользователя
                cursor.execute(
                    "SELECT id FROM carts WHERE user_id = %s AND is_active = 1 ORDER BY id DESC LIMIT 1",
                    (user["id"],)
                )
                cart = cursor.fetchone()
                if cart:
                    cursor.execute("""
                        SELECT id FROM cart_items
                        WHERE cart_id = %s AND product_id = %s
                        LIMIT 1
                    """, (cart["id"], product_id))
                    in_cart = cursor.fetchone() is not None
    finally:
        conn.close()

    return render_template(
        "product_detail.html",
        user=user,
        product=product,
        images=images,
        in_cart=in_cart
    )


# -------------------------------------------------
# Корзина / заказы
# -------------------------------------------------
@app.route("/cart")
@login_required
def cart():
    user = get_current_user()
    cart = get_or_create_cart_for_user(user["id"])

    conn = connect_db()
    items = []
    total_amount = 0
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    ci.id AS item_id,
                    ci.quantity,
                    ci.price_at_add,
                    p.id AS product_id,
                    p.name,
                    p.slug
                FROM cart_items ci
                JOIN carts c ON ci.cart_id = c.id
                JOIN products p ON ci.product_id = p.id
                WHERE c.id = %s
            """, (cart["id"],))
            items = cursor.fetchall()

        for item in items:
            total_amount += (item["quantity"] or 0) * float(item["price_at_add"] or 0)
    finally:
        conn.close()

    return render_template(
        "cart.html",
        user=user,
        items=items,
        total_amount=total_amount
    )


@app.route("/cart/add/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    user = get_current_user()
    cart = get_or_create_cart_for_user(user["id"])

    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            # проверяем, есть ли уже этот товар в корзине
            cursor.execute("""
                SELECT id, quantity FROM cart_items
                WHERE cart_id = %s AND product_id = %s
                LIMIT 1
            """, (cart["id"], product_id))
            item = cursor.fetchone()
            if item:
                # уже в корзине — ничего не делаем
                flash("Товар уже в корзине", "error")
                return redirect(url_for("product_detail", product_id=product_id))

            # берём базовую цену товара
            cursor.execute("SELECT base_price FROM products WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            if not product:
                abort(404)

            price = product["base_price"] or 0

            cursor.execute("""
                INSERT INTO cart_items (cart_id, product_id, quantity, price_at_add)
                VALUES (%s, %s, %s, %s)
            """, (cart["id"], product_id, 1, price))
            conn.commit()
    finally:
        conn.close()

    flash("Товар добавлен в корзину", "success")
    return redirect(url_for("product_detail", product_id=product_id))


@app.route("/cart/update_item", methods=["POST"])
@login_required
def update_cart_item():
    user = get_current_user()
    cart = get_or_create_cart_for_user(user["id"])

    item_id = request.form.get("item_id", type=int)
    quantity = request.form.get("quantity", type=int)

    if not item_id or not quantity or quantity < 1:
        flash("Некорректное количество", "error")
        return redirect(url_for("cart"))

    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE cart_items ci
                JOIN carts c ON ci.cart_id = c.id
                SET ci.quantity = %s
                WHERE ci.id = %s AND c.id = %s
            """, (quantity, item_id, cart["id"]))
            conn.commit()
    finally:
        conn.close()

    flash("Количество обновлено", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove_item", methods=["POST"])
@login_required
def remove_cart_item():
    user = get_current_user()
    cart = get_or_create_cart_for_user(user["id"])

    item_id = request.form.get("item_id", type=int)
    if not item_id:
        return redirect(url_for("cart"))

    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                DELETE ci FROM cart_items ci
                JOIN carts c ON ci.cart_id = c.id
                WHERE ci.id = %s AND c.id = %s
            """, (item_id, cart["id"]))
            conn.commit()
    finally:
        conn.close()

    flash("Товар удалён из корзины", "success")
    return redirect(url_for("cart"))


@app.route("/cart/checkout", methods=["POST"])
@login_required
def cart_checkout():
    user = get_current_user()
    cart = get_or_create_cart_for_user(user["id"])

    conn = connect_db()
    try:
        with conn.cursor() as cursor:
            # забираем позиции корзины
            cursor.execute("""
                SELECT
                    ci.id AS item_id,
                    ci.product_id,
                    ci.quantity,
                    ci.price_at_add,
                    p.name AS product_name
                FROM cart_items ci
                JOIN products p ON ci.product_id = p.id
                WHERE ci.cart_id = %s
            """, (cart["id"],))
            items = cursor.fetchall()

            if not items:
                flash("Корзина пуста", "error")
                return redirect(url_for("cart"))

            items_total = 0
            for it in items:
                items_total += (it["quantity"] or 0) * float(it["price_at_add"] or 0)

            discount_amount = 0
            delivery_price = 0
            total_amount = items_total - discount_amount + delivery_price

            # создаём заказ (статус new=1, способ оплаты card_online=1)
            cursor.execute("""
                INSERT INTO orders (
                    user_id, cart_id, status_id, payment_method_id, delivery_method_id,
                    customer_name, customer_email, customer_phone,
                    items_total, discount_amount, delivery_price, total_amount
                )
                VALUES (%s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s)
            """, (
                user["id"], cart["id"], 1, 1, None,
                user["full_name"], user["email"], user["phone"],
                items_total, discount_amount, delivery_price, total_amount
            ))
            order_id = cursor.lastrowid

            # позиции заказа
            for it in items:
                cursor.execute("""
                    INSERT INTO order_items (
                        order_id, product_id, variant_id,
                        product_name, variant_info,
                        quantity, price, total_price
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    order_id,
                    it["product_id"],
                    None,
                    it["product_name"],
                    None,
                    it["quantity"],
                    it["price_at_add"],
                    (it["quantity"] or 0) * float(it["price_at_add"] or 0)
                ))

            # корзину помечаем как неактивную
            cursor.execute("UPDATE carts SET is_active = 0 WHERE id = %s", (cart["id"],))
            conn.commit()
    finally:
        conn.close()

    flash("Заказ успешно создан", "success")
    return redirect(url_for("profile"))


# -------------------------------------------------
# Профиль пользователя
# -------------------------------------------------
@app.route("/profile")
@login_required
def profile():
    user = get_current_user()

    conn = connect_db()
    orders = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT o.id, o.created_at, o.total_amount,
                       s.name AS status_name
                FROM orders o
                JOIN order_statuses s ON o.status_id = s.id
                WHERE o.user_id = %s
                ORDER BY o.created_at DESC
            """, (user["id"],))
            orders = cursor.fetchall()
    finally:
        conn.close()

    return render_template("profile.html", user=user, orders=orders)


# -------------------------------------------------
# Администрирование
# -------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin_page():
    user = get_current_user()
    if not user or user["role_id"] != 1:
        abort(403)

    conn = connect_db()
    try:
        if request.method == "POST":
            form_type = request.form.get("form_type")

            # ---------- Создание нового товара ----------
            if form_type == "create_product":
                name = request.form.get("name", "").strip()
                category_id = request.form.get("category_id", type=int)
                collection_id = request.form.get("collection_id", type=int)
                short_desc = request.form.get("short_desc", "").strip()
                base_price = request.form.get("base_price", type=float)

                if not name or not category_id:
                    flash("Название и категория обязательны", "error")
                else:
                    with conn.cursor() as cursor:
                        # создаём товар
                        cursor.execute("""
                            INSERT INTO products (
                                category_id, collection_id, name, slug,
                                short_desc, full_desc, base_price,
                                is_active, is_new, is_bestseller
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 0, 0)
                        """, (
                            category_id,
                            collection_id if collection_id else None,
                            name,
                            name.lower().replace(" ", "-"),
                            short_desc,
                            None,
                            base_price if base_price is not None else 0
                        ))
                        conn.commit()
                        product_id = cursor.lastrowid

                        # загружаем до 5 изображений
                        files = request.files.getlist("images")
                        files = [f for f in files if f and f.filename]  # убрать пустые
                        files = files[:5]  # максимум 5 файлов

                        sort_order = 1
                        for i, file in enumerate(files):
                            filename = secure_filename(file.filename)
                            # чтобы не перезаписать существующие — добавим id товара и порядковый номер
                            name_part, ext = os.path.splitext(filename)
                            filename = f"{product_id}_{sort_order}{ext.lower()}"
                            save_path = os.path.join(UPLOAD_FOLDER, filename)
                            file.save(save_path)

                            image_url = f"/images/products/{filename}"

                            cursor.execute("""
                                INSERT INTO product_images (
                                    product_id, image_url, is_main, sort_order
                                )
                                VALUES (%s, %s, %s, %s)
                            """, (
                                product_id,
                                image_url,
                                1 if i == 0 else 0,  # первое изображение — основное
                                sort_order
                            ))
                            sort_order += 1

                        conn.commit()

                    flash("Товар создан", "success")

            # ---------- Обновление пользователя ----------
            elif form_type == "update_user":
                user_id = request.form.get("user_id", type=int)
                role_id = request.form.get("role_id", type=int)
                is_active = 1 if request.form.get("is_active") == "on" else 0

                if user_id and role_id:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE users
                            SET role_id = %s, is_active = %s
                            WHERE id = %s
                        """, (role_id, is_active, user_id))
                        conn.commit()
                    flash("Пользователь обновлён", "success")

        # ---------- GET: загрузка данных для форм ----------
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name
                FROM categories
                WHERE is_visible = 1
                ORDER BY sort_order, name
            """)
            categories = cursor.fetchall()

            cursor.execute("""
                SELECT id, name
                FROM collections
                WHERE is_active = 1
                ORDER BY year_from DESC, name
            """)
            collections = cursor.fetchall()

            cursor.execute("SELECT id, name FROM roles ORDER BY id")
            roles = cursor.fetchall()

            cursor.execute("""
                SELECT u.*, r.name AS role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                ORDER BY u.id
            """)
            users = cursor.fetchall()

    finally:
        conn.close()

    return render_template(
        "admin.html",
        user=user,
        categories=categories,
        collections=collections,
        roles=roles,
        users=users
    )



if __name__ == "__main__":
    app.run(debug=True)
