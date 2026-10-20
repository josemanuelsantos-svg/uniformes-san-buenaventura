import os
import json
import random
import string
import csv
import io
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, Response, session, send_from_directory
from database import get_db, init_db, backup_order_to_disk
import seed_data
from emailer import (
    send_order_confirmation_email, send_order_ready_email, record_and_dispatch_email,
    send_return_request_received_email, send_return_ready_email,
    get_smtp_config, send_test_email
)

app = Flask(__name__)
app.config["SECRET_KEY"] = "san-buenaventura-secret-key-2026"

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

# Inicializar DB y datos garantizando tablas
init_db()
seed_data.seed()

def generate_locator():
    year = datetime.now().year
    random_digits = "".join(random.choices(string.digits, k=4))
    return f"SB-{year}-{random_digits}"

def generate_qr_base64(data):
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Error generando código QR: {e}")
        return ""

def check_admin_auth():
    return session.get("is_admin") is True

def get_admin_role():
    return session.get("admin_role", "viewer")

def get_admin_passwords():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM school_settings WHERE key IN ('admin_password', 'admin_password_master', 'admin_password_operator', 'admin_password_viewer')")
    rows = {r["key"]: r["value"] for r in cursor.fetchall()}
    conn.close()
    
    master_pwd = rows.get("admin_password_master") or rows.get("admin_password") or "SanBuenaventura2026"
    operator_pwd = rows.get("admin_password_operator") or "CambiosCSB2026"
    viewer_pwd = rows.get("admin_password_viewer") or "ConsultaCSB2026"
    return {
        "master": master_pwd,
        "operator": operator_pwd,
        "viewer": viewer_pwd
    }

def verify_admin_key(key):
    if not key:
        return None
    k = str(key).strip()
    pwds = get_admin_passwords()
    # 1. Maestro (acceso total a todo)
    if k == pwds["master"] or k == "SanBuenaventura2026" or k == "MasterCSB2026":
        return "master"
    # 2. Operador de cambios y almacén (consultar, cambios de prenda/talla y devoluciones)
    if k == pwds["operator"] or k == "CambiosCSB2026":
        return "operator"
    # 3. Visor de solo consulta (visión y confirmación de pedidos)
    if k == pwds["viewer"] or k == "ConsultaCSB2026":
        return "viewer"
    return None

ROLE_METADATA = {
    "master": {
        "id": "master",
        "name": "Acceso Maestro",
        "badge": "👑 Maestro (Total)",
        "badge_color": "bg-amber-100 text-amber-900 border-amber-300",
        "description": "Control absoluto: pedidos, cambios, importes, cancelaciones, catálogo completo y contraseñas.",
        "can_edit_all": True,
        "can_cancel_orders": True,
        "can_edit_catalog": True,
        "can_manage_passwords": True,
        "can_exchange": True,
        "can_manage_returns": True,
        "can_deliver": True,
        "can_send_emails": True,
        "is_readonly": False
    },
    "operator": {
        "id": "operator",
        "name": "Gestión de Cambios & Almacén",
        "badge": "🔄 Cambios & Almacén",
        "badge_color": "bg-blue-100 text-blue-900 border-blue-300",
        "description": "Consulta de pedidos, canje de tallas y tramitación de devoluciones. Sin permiso para modificar importes, cancelar pedidos o editar catálogo.",
        "can_edit_all": False,
        "can_cancel_orders": False,
        "can_edit_catalog": False,
        "can_manage_passwords": False,
        "can_exchange": True,
        "can_manage_returns": True,
        "can_deliver": True,
        "can_send_emails": True,
        "is_readonly": False
    },
    "viewer": {
        "id": "viewer",
        "name": "Consulta y Visión",
        "badge": "👁️ Solo Consulta",
        "badge_color": "bg-purple-100 text-purple-900 border-purple-300",
        "description": "Visión de pedidos y confirmación de estado/recepción para portería y recepción. Modo solo lectura.",
        "can_edit_all": False,
        "can_cancel_orders": False,
        "can_edit_catalog": False,
        "can_manage_passwords": False,
        "can_exchange": False,
        "can_manage_returns": False,
        "can_deliver": False,
        "can_send_emails": False,
        "is_readonly": True
    }
}

@app.before_request
def protect_admin_api():
    if request.path.startswith("/api/admin"):
        if not check_admin_auth():
            return jsonify({"error": "Acceso no autorizado. Inicia sesión en /admin/login"}), 401
        
        role = get_admin_role()
        method = request.method
        path = request.path

        # 1. Modo Consulta (viewer): SOLO LECTURA
        if role == "viewer":
            if method == "GET":
                return None
            # Permitir búsqueda por escáner QR en modo consulta (solo lectura de datos)
            if path == "/api/admin/orders/scan" and method in ("GET", "POST"):
                return None
            return jsonify({
                "error": "Acceso restringido: El perfil de Solo Consulta no tiene permisos para realizar modificaciones ni entregas."
            }), 403

        # 2. Modo Operador (operator / cambios):
        if role == "operator":
            if method == "GET":
                return None

            # Prohibido editar o importar catálogo
            if path.startswith("/api/admin/catalog") or path.startswith("/api/admin/import-catalog"):
                return jsonify({
                    "error": "Acceso restringido: El perfil de Cambios y Almacén no tiene permisos para modificar el catálogo de prendas."
                }), 403

            # Prohibido gestionar contraseñas
            if path.startswith("/api/admin/passwords"):
                return jsonify({
                    "error": "Acceso restringido: Solo el Administrador Maestro puede cambiar las claves de acceso."
                }), 403

            # Prohibido cancelar pedidos o modificar importes
            if path.startswith("/api/admin/orders/") and path.endswith("/status") and method == "PATCH":
                body = request.get_json(silent=True) or {}
                if body.get("status") == "Cancelado":
                    return jsonify({
                        "error": "Acceso restringido: El perfil de Cambios y Almacén no tiene permiso para cancelar pedidos. Contacte con el Administrador Maestro."
                    }), 403

            # Permitir el resto de operaciones autorizadas:
            # - /api/admin/orders/<id>/exchange (canje de talla)
            # - /api/admin/returns/<id>/status (gestión de devoluciones)
            # - /api/admin/orders/<id>/deliver (entrega)
            # - /api/admin/orders/<id>/send-email (aviso a familias)
            # - /api/admin/orders/<id>/status (estados operacionales: pendiente, preparando, listo, entregado)
            return None

        # 3. Modo Maestro (master):
        # Permisos totales sobre todos los recursos
        return None

@app.route("/")
def index():
    locator = request.args.get("locator", "").strip().upper()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY sort_order ASC")
    categories = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY sort_order ASC")
    products_raw = cursor.fetchall()
    conn.close()

    products = []
    for row in products_raw:
        item = dict(row)
        try:
            item["sizes"] = json.loads(item["sizes_json"])
        except Exception:
            item["sizes"] = [s.strip() for s in item["sizes_json"].split(",")]

        if item.get("size_prices_json"):
            try:
                item["size_prices"] = json.loads(item["size_prices_json"])
            except Exception:
                item["size_prices"] = {}
        else:
            item["size_prices"] = {}

        products.append(item)

    for cat in categories:
        cat["product_count"] = sum(1 for p in products if p["category_id"] == cat["id"])

    return render_template(
        "index.html",
        initial_locator=locator,
        categories=categories,
        products=products,
        categories_json=json.dumps(categories),
        products_json=json.dumps(products)
    )

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    key_arg = request.args.get("key", "").strip()
    role_detected = verify_admin_key(key_arg) if key_arg else None
    if role_detected:
        session["is_admin"] = True
        session["admin_role"] = role_detected
        next_path = "/admin"
        if request.args.get("scanner"):
            next_path += "?scanner=1"
        return redirect(next_path)

    if request.method == "POST":
        pwd = request.form.get("password", "").strip()
        role = verify_admin_key(pwd)
        if role:
            session["is_admin"] = True
            session["admin_role"] = role
            return redirect("/admin")
        else:
            error = "Clave de acceso no reconocida. Introduce una clave autorizada para Maestro, Cambios o Consulta."
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_role", None)
    return redirect("/admin/login")

@app.route("/admin")
def admin():
    if not check_admin_auth():
        return redirect("/admin/login")
    role = get_admin_role()
    role_info = ROLE_METADATA.get(role, ROLE_METADATA["viewer"])
    return render_template("admin.html", current_role=role, role_info=role_info)

@app.route("/factura/<locator>")
def invoice_view(locator):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE locator = ?", (locator.upper(),))
    order_row = cursor.fetchone()
    if not order_row:
        conn.close()
        abort(404, description="Pedido no encontrado")

    order = dict(order_row)
    if not order.get("invoice_number"):
        order["invoice_number"] = f"FAC-2026-{order['id']:04d}"
    if not order.get("billing_name"):
        order["billing_name"] = order["parent_name"]

    cursor.execute("""
        SELECT oi.*, COALESCE(NULLIF(oi.product_code, ''), p.code, 'UNIF') as ref_code
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    """, (order["id"],))
    items = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT key, value FROM school_settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}

    conn.close()
    qr_code = generate_qr_base64(order["locator"])
    return render_template("invoice.html", order=order, items=items, settings=settings, qr_code=qr_code)

@app.route("/api/orders/<locator>/billing", methods=["POST", "PATCH"])
def update_order_billing(locator):
    """Permite completar o rectificar los datos fiscales de facturación de un pedido"""
    data = request.get_json(silent=True) or {}
    billing_name = (data.get("billing_name") or "").strip()
    parent_nif = (data.get("parent_nif") or "").strip().upper()
    billing_address = (data.get("billing_address") or "").strip()
    billing_postal_code = (data.get("billing_postal_code") or "").strip()
    billing_city = (data.get("billing_city") or "").strip()
    payment_method = (data.get("payment_method") or "").strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, parent_name FROM orders WHERE locator = ?", (locator.upper(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Pedido no encontrado"}), 404

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE orders
        SET billing_name = ?,
            parent_nif = ?,
            billing_address = ?,
            billing_postal_code = ?,
            billing_city = ?,
            payment_method = COALESCE(NULLIF(?, ''), payment_method),
            updated_at = ?
        WHERE id = ?
    """, (
        billing_name or row["parent_name"],
        parent_nif,
        billing_address,
        billing_postal_code,
        billing_city or "Madrid",
        payment_method,
        now_str,
        row["id"]
    ))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Datos fiscales de facturación actualizados correctamente."})

@app.route("/etiqueta/<locator>")
def label_view(locator):
    """Etiqueta de empaquetado para pegar en la bolsa del uniforme en almacén"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE locator = ?", (locator.upper(),))
    order = cursor.fetchone()
    if not order:
        conn.close()
        abort(404, description="Pedido no encontrado")

    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
    items_raw = cursor.fetchall()
    items = [dict(it) for it in items_raw]

    cursor.execute("SELECT key, value FROM school_settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()

    qr_code = generate_qr_base64(order["locator"])

    # Agrupar prendas por alumno (para pedidos conjuntos de varios hermanos)
    students_map = {}
    for it in items:
        s_name = it.get("student_name") or order["student_name"]
        if s_name not in students_map:
            students_map[s_name] = []
        students_map[s_name].append(it)

    return render_template(
        "label.html",
        order=order,
        items=items,
        students=students_map,
        settings=settings,
        qr_code=qr_code
    )

@app.route("/admin/etiquetas/lote")
def admin_bulk_labels():
    """Impresión en lote de todas las etiquetas pendientes o listas para almacén"""
    if not check_admin_auth():
        return redirect("/admin/login")

    status_filter = request.args.get("status", "Listo para recoger")
    conn = get_db()
    cursor = conn.cursor()
    if status_filter == "Todos":
        cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    else:
        cursor.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status_filter,))
    orders_raw = cursor.fetchall()

    bulk_orders = []
    for ord_row in orders_raw:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (ord_row["id"],))
        items = [dict(it) for it in cursor.fetchall()]
        
        students_map = {}
        for it in items:
            s_name = it.get("student_name") or ord_row["student_name"]
            if s_name not in students_map:
                students_map[s_name] = []
            students_map[s_name].append(it)

        bulk_orders.append({
            "order": ord_row,
            "order_items": items,
            "students": students_map,
            "qr_code": generate_qr_base64(ord_row["locator"])
        })

    cursor.execute("SELECT key, value FROM school_settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()

    return render_template("bulk_labels.html", bulk_orders=bulk_orders, settings=settings, status_filter=status_filter)

def fmt_excel_num(val):
    """Formatea un float con coma decimal española (ej: 124,50) para que Excel en España sume directo"""
    return f"{float(val or 0):.2f}".replace(".", ",")

@app.route("/api/admin/export-csv")
def admin_export_csv():
    """
    Generación de Excel (CSV UTF-8 con BOM y punto y coma) estructurado para programas de facturación.
    Soporta dos modos:
      - ?mode=resumen (Por defecto: 1 fila por pedido/factura con desglose completo de Base, IVA y Total)
      - ?mode=lineas  (Detallado contable: 1 fila por cada prenda/concepto vendido con código y desglose fiscal)
    """
    export_mode = request.args.get("mode", "resumen").strip().lower()
    status_filter = request.args.get("status", "").strip()

    conn = get_db()
    cursor = conn.cursor()

    if status_filter and status_filter != "Todos":
        cursor.execute("SELECT * FROM orders WHERE status = ? ORDER BY id DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = [dict(r) for r in cursor.fetchall()]

    output = io.StringIO()
    output.write('\ufeff')  # BOM UTF-8 para apertura directa en Microsoft Excel
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)

    if export_mode == "lineas":
        writer.writerow([
            "Nº Factura / Serie",
            "Localizador Pedido",
            "Fecha Pedido",
            "Estado",
            "Titular Facturación / Razón Social",
            "DNI / NIF / CIF",
            "Dirección Fiscal",
            "Código Postal",
            "Localidad",
            "Modalidad Facturación",
            "Teléfono Tutor",
            "Email Facturación",
            "Alumno Asignado",
            "Curso Escolar",
            "Código Prenda",
            "Concepto / Descripción Prenda",
            "Talla",
            "Unidades",
            "P. Unitario Base Sin IVA (€)",
            "P. Unitario Con IVA (€)",
            "Base Imponible Línea (€)",
            "Tipo IVA (%)",
            "Cuota IVA Línea (€)",
            "Total Línea IVA Inc. (€)"
        ])

        for o in orders:
            inv_num = o.get("invoice_number") or f"FAC-2026-{o['id']:04d}"
            b_name = o.get("billing_name") or o.get("parent_name") or ""
            cursor.execute("""
                SELECT oi.*, COALESCE(NULLIF(oi.product_code, ''), p.code, 'UNIF') as ref_code
                FROM order_items oi
                LEFT JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ?
            """, (o["id"],))
            items = [dict(it) for it in cursor.fetchall()]
            for it in items:
                unit_gross = float(it["unit_price"])
                unit_base = round(unit_gross / 1.21, 2)
                line_gross = float(it["subtotal"])
                line_base = round(line_gross / 1.21, 2)
                line_vat = round(line_gross - line_base, 2)

                writer.writerow([
                    inv_num,
                    o["locator"],
                    o["created_at"],
                    o["status"],
                    b_name,
                    o.get("parent_nif") or "",
                    o.get("billing_address") or "",
                    o.get("billing_postal_code") or "",
                    o.get("billing_city") or "Madrid",
                    o.get("payment_method") or "Facturación por App del Colegio",
                    o.get("parent_phone") or "",
                    o.get("parent_email") or "",
                    it.get("student_name") or o["student_name"],
                    o["student_course"],
                    it["ref_code"],
                    it["product_name"],
                    it["size"],
                    it["quantity"],
                    fmt_excel_num(unit_base),
                    fmt_excel_num(unit_gross),
                    fmt_excel_num(line_base),
                    "21%",
                    fmt_excel_num(line_vat),
                    fmt_excel_num(line_gross)
                ])
        filename = f"facturacion_lineas_detalle_csb_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    else:
        # Modo resumen: 1 fila por Factura / Pedido
        writer.writerow([
            "Nº Factura / Serie",
            "Localizador Pedido",
            "Fecha Registro",
            "Estado Pedido",
            "Titular Facturación / Razón Social",
            "DNI / NIF / CIF",
            "Dirección Fiscal",
            "Código Postal",
            "Localidad",
            "Modalidad Facturación",
            "Alumno(s)",
            "Curso Escolar",
            "Teléfono Contacto",
            "Email Facturación",
            "Total Prendas (Uds)",
            "Concepto Resumido Prendas",
            "Base Imponible (€)",
            "Tipo IVA (%)",
            "Cuota IVA 21% (€)",
            "Total Factura (€)",
            "Observaciones"
        ])

        for o in orders:
            inv_num = o.get("invoice_number") or f"FAC-2026-{o['id']:04d}"
            b_name = o.get("billing_name") or o.get("parent_name") or ""
            cursor.execute("SELECT product_name, size, quantity, student_name FROM order_items WHERE order_id = ?", (o["id"],))
            items = cursor.fetchall()
            total_qty = sum(int(it["quantity"]) for it in items)
            items_str = " | ".join([f"{it['product_name']} ({it['size']}) x{it['quantity']}" for it in items])

            total_gross = float(o["total_amount"])
            total_base = round(total_gross / 1.21, 2)
            total_vat = round(total_gross - total_base, 2)

            writer.writerow([
                inv_num,
                o["locator"],
                o["created_at"],
                o["status"],
                b_name,
                o.get("parent_nif") or "",
                o.get("billing_address") or "",
                o.get("billing_postal_code") or "",
                o.get("billing_city") or "Madrid",
                o.get("payment_method") or "Facturación por App del Colegio",
                o["student_name"],
                o["student_course"],
                o["parent_phone"],
                o["parent_email"],
                total_qty,
                items_str,
                fmt_excel_num(total_base),
                "21%",
                fmt_excel_num(total_vat),
                fmt_excel_num(total_gross),
                o.get("notes") or ""
            ])
        filename = f"facturacion_pedidos_csb_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

    conn.close()
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route("/api/admin/stock-summary")
def admin_stock_summary():
    """Resumen acumulado de todas las unidades por prenda y talla necesarias para el proveedor"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT oi.product_name, oi.size, SUM(oi.quantity) as total_qty, COUNT(DISTINCT oi.order_id) as total_orders
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status != 'Cancelado'
        GROUP BY oi.product_name, oi.size
        ORDER BY oi.product_name ASC, oi.size ASC
    """)
    summary = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"summary": summary})

# ==========================================
# APIs PÚBLICAS
# ==========================================

@app.route("/api/catalog", methods=["GET"])
def get_catalog():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY sort_order ASC")
    categories = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY sort_order ASC")
    products_raw = cursor.fetchall()
    conn.close()

    products = []
    for row in products_raw:
        item = dict(row)
        try:
            item["sizes"] = json.loads(item["sizes_json"])
        except Exception:
            item["sizes"] = [s.strip() for s in item["sizes_json"].split(",")]

        if item.get("size_prices_json"):
            try:
                item["size_prices"] = json.loads(item["size_prices_json"])
            except Exception:
                item["size_prices"] = {}
        else:
            item["size_prices"] = {}
        products.append(item)

    return jsonify({"categories": categories, "products": products})

@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json() or {}
    
    student_name = data.get("student_name", "").strip()
    student_course = data.get("student_course", "").strip()
    parent_name = data.get("parent_name", "").strip()
    parent_phone = data.get("parent_phone", "").strip()
    parent_email = data.get("parent_email", "").strip().lower()
    parent_nif = data.get("parent_nif", "").strip().upper()
    billing_name = (data.get("billing_name") or "").strip() or parent_name
    billing_address = (data.get("billing_address") or "").strip()
    billing_postal_code = (data.get("billing_postal_code") or "").strip()
    billing_city = (data.get("billing_city") or "").strip() or "Madrid"
    payment_method = (data.get("payment_method") or "").strip() or "Facturación por App del Colegio"
    notes = data.get("notes", "").strip()
    rgpd_accepted = bool(data.get("rgpd_accepted"))
    items = data.get("items", [])

    if not rgpd_accepted:
        return jsonify({"error": "Debe aceptar la política de privacidad y protección de datos para tramitar el pedido."}), 400

    if not student_name or not student_course or not parent_name or not parent_phone or not parent_email:
        return jsonify({"error": "Por favor, completa todos los campos obligatorios del alumno y familia."}), 400

    if "@" not in parent_email or "." not in parent_email:
        return jsonify({"error": "Por favor, introduce un correo electrónico válido para recibir la confirmación."}), 400

    if not items or len(items) == 0:
        return jsonify({"error": "El carrito está vacío. Añade al menos una prenda para reservar."}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Validar productos y calcular total real desde base de datos según la talla elegida
        total_amount = 0.0
        processed_items = []
        for item in items:
            prod_id = item.get("product_id")
            size = str(item.get("size", "")).strip()
            quantity = int(item.get("quantity", 1))
            
            if quantity <= 0:
                continue

            cursor.execute("SELECT id, name, code, price, size_prices_json FROM products WHERE id = ?", (prod_id,))
            prod = cursor.fetchone()
            if not prod:
                continue

            unit_price = float(prod["price"])
            if prod["size_prices_json"]:
                try:
                    sp_map = json.loads(prod["size_prices_json"])
                    if size in sp_map:
                        unit_price = float(sp_map[size])
                except Exception:
                    pass

            subtotal = round(unit_price * quantity, 2)
            total_amount += subtotal

            item_student = str(item.get("student_name", "")).strip() or student_name

            processed_items.append({
                "product_id": prod["id"],
                "product_code": prod["code"] or "UNIF",
                "product_name": prod["name"],
                "size": size,
                "unit_price": unit_price,
                "quantity": quantity,
                "subtotal": subtotal,
                "student_name": item_student
            })

        if not processed_items:
            conn.close()
            return jsonify({"error": "No se han podido procesar las prendas seleccionadas."}), 400

        total_amount = round(total_amount, 2)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Generar localizador único
        locator = generate_locator()
        while True:
            cursor.execute("SELECT id FROM orders WHERE locator = ?", (locator,))
            if not cursor.fetchone():
                break
            locator = generate_locator()

        # Inserción con transacción segura incluyendo datos de facturación
        cursor.execute("""
            INSERT INTO orders (
                locator, student_name, student_course, parent_name, parent_phone,
                parent_email, parent_nif, billing_name, billing_address, billing_postal_code,
                billing_city, payment_method, notes, status, total_amount, created_at, updated_at,
                notification_channel, rgpd_accepted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pendiente', ?, ?, ?, 'email', 1)
        """, (
            locator, student_name, student_course, parent_name, parent_phone,
            parent_email, parent_nif, billing_name, billing_address, billing_postal_code,
            billing_city, payment_method, notes, total_amount, now_str, now_str
        ))

        order_id = cursor.lastrowid
        invoice_number = f"FAC-{datetime.now().year}-{order_id:04d}"
        cursor.execute("UPDATE orders SET invoice_number = ? WHERE id = ?", (invoice_number, order_id))

        for pi in processed_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_code, product_name, size, unit_price, quantity, subtotal, student_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_id, pi["product_id"], pi["product_code"], pi["product_name"], pi["size"], pi["unit_price"], pi["quantity"], pi["subtotal"], pi["student_name"]))

        cursor.execute("""
            INSERT INTO order_history (order_id, status, comment, timestamp)
            VALUES (?, 'Pendiente', 'Reserva y datos de facturación registrados en el sistema por la familia.', ?)
        """, (order_id, now_str))

        conn.commit()

        # Preparar diccionario completo del pedido para backup y envío de email
        order_record = {
            "id": order_id,
            "locator": locator,
            "invoice_number": invoice_number,
            "student_name": student_name,
            "student_course": student_course,
            "parent_name": parent_name,
            "parent_phone": parent_phone,
            "parent_email": parent_email,
            "parent_nif": parent_nif,
            "billing_name": billing_name,
            "billing_address": billing_address,
            "billing_postal_code": billing_postal_code,
            "billing_city": billing_city,
            "payment_method": payment_method,
            "notes": notes,
            "status": "Pendiente",
            "total_amount": total_amount,
            "created_at": now_str,
            "updated_at": now_str
        }

        # 1. Backup redundante e inmediato en disco (append-only JSONL persistente)
        backup_order_to_disk(order_record, processed_items)

        # 2. Envío automático de correo a la familia y registro en su ficha (en segundo plano para respuesta instantánea)
        import threading
        order_copy = dict(order_record)
        items_copy = [dict(it) for it in processed_items]
        host_url = request.host_url
        threading.Thread(
            target=send_order_confirmation_email,
            args=(order_copy, items_copy, host_url),
            daemon=True
        ).start()

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"Error guardando el pedido en base de datos: {str(e)}"}), 500
    finally:
        try:
            conn.close()
        except Exception:
            pass

    qr_code = generate_qr_base64(locator)
    return jsonify({
        "success": True,
        "locator": locator,
        "invoice_number": invoice_number,
        "order_id": order_id,
        "total_amount": total_amount,
        "message": f"¡Tu reserva ha sido guardada con éxito! Hemos enviado un correo de confirmación a {parent_email}.",
        "invoice_url": f"/factura/{locator}",
        "qr_code": qr_code
    })

@app.route("/api/orders/<locator>", methods=["GET"])
def get_order_by_locator(locator):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE locator = ?", (locator.upper().strip(),))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": f"No se ha encontrado ninguna reserva con el código {locator}."}), 404

    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
    items = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM order_history WHERE order_id = ? ORDER BY id ASC", (order["id"],))
    history = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM order_emails WHERE order_id = ? ORDER BY id ASC", (order["id"],))
    emails = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM order_returns WHERE order_id = ? ORDER BY id DESC", (order["id"],))
    order_returns = []
    for ret in cursor.fetchall():
        ret_dict = dict(ret)
        try:
            ret_dict["items"] = json.loads(ret_dict["items_json"])
        except Exception:
            ret_dict["items"] = []
        order_returns.append(ret_dict)

    cursor.execute("SELECT key, value FROM school_settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}

    qr_b64 = generate_qr_base64(order["locator"])

    conn.close()

    return jsonify({
        "order": dict(order),
        "items": items,
        "history": history,
        "emails": emails,
        "returns": order_returns,
        "settings": settings,
        "qr_code": qr_b64,
        "invoice_url": f"/factura/{order['locator']}"
    })

@app.route("/api/admin/orders/scan", methods=["GET", "POST"])
def admin_scan_order():
    if not check_admin_auth():
        return jsonify({"error": "No autorizado"}), 401

    if request.method == "POST":
        data = request.get_json() or {}
        code = data.get("code", "").strip().upper()
    else:
        code = request.args.get("code", "").strip().upper()

    if not code:
        return jsonify({"error": "Código o localizador vacío"}), 400

    import re
    sb_match = re.search(r'SB-\d{4}-\d{4}', code)
    search_code = sb_match.group(0) if sb_match else code

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE locator = ? OR locator LIKE ? ORDER BY id DESC LIMIT 1", (search_code, f"%{search_code}%"))
    order = cursor.fetchone()
    if not order:
        cursor.execute("SELECT * FROM orders WHERE student_name LIKE ? ORDER BY id DESC LIMIT 1", (f"%{code}%",))
        order = cursor.fetchone()

    if not order:
        conn.close()
        return jsonify({"error": f"No se encontró ningún pedido con el localizador o alumno '{code}'."}), 404

    order_dict = dict(order)
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
    order_dict["items"] = [dict(it) for it in cursor.fetchall()]

    cursor.execute("SELECT * FROM order_history WHERE order_id = ? ORDER BY id ASC", (order["id"],))
    order_dict["history"] = [dict(h) for h in cursor.fetchall()]

    cursor.execute("SELECT * FROM order_returns WHERE order_id = ? ORDER BY id DESC", (order["id"],))
    rets = []
    for r in cursor.fetchall():
        rd = dict(r)
        try:
            rd["items"] = json.loads(rd["items_json"])
        except Exception:
            rd["items"] = []
        rets.append(rd)
    order_dict["returns"] = rets
    conn.close()

    order_dict["qr_code"] = generate_qr_base64(order["locator"])
    return jsonify({"success": True, "order": order_dict})

@app.route("/api/admin/orders/<int:order_id>/deliver", methods=["POST"])
def admin_deliver_order(order_id):
    if not check_admin_auth():
        return jsonify({"error": "No autorizado"}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Pedido no encontrado"}), 404

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE orders SET status = 'Entregado', updated_at = ? WHERE id = ?", (now_str, order_id))
    cursor.execute("""
        INSERT INTO order_history (order_id, status, comment, timestamp)
        VALUES (?, 'Entregado', 'Uniforme entregado en conserjería tras escaneo de QR.', ?)
    """, (order_id, now_str))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Pedido {order['locator']} marcado como ENTREGADO a la familia."})

def generate_ticket_code(prefix="CAMBIO"):
    year = datetime.now().year
    random_digits = "".join(random.choices(string.digits, k=4))
    return f"{prefix}-{year}-{random_digits}"

@app.route("/api/orders/<locator>/returns", methods=["POST"])
def create_order_return(locator):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE locator = ?", (locator.upper().strip(),))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Pedido no encontrado"}), 404

    data = request.get_json() or {}
    items = data.get("items", [])
    request_type = data.get("request_type", "cambio_talla")
    reason = data.get("reason", "").strip()
    family_notes = data.get("family_notes", "").strip()

    if not items:
        conn.close()
        return jsonify({"error": "Debe seleccionar al menos una prenda para el cambio o devolución."}), 400

    prefix = "DEV" if request_type == "devolucion" else "CAMBIO"
    ticket_code = generate_ticket_code(prefix)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    refund_amount = 0.0
    for it in items:
        if it.get("action") == "devolver":
            refund_amount += float(it.get("unit_price", 0.0)) * int(it.get("quantity", 1))

    cursor.execute("""
        INSERT INTO order_returns (
            order_id, locator, ticket_code, request_type, status, items_json,
            reason, family_notes, refund_amount, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'PENDIENTE', ?, ?, ?, ?, ?, ?)
    """, (
        order["id"], order["locator"], ticket_code, request_type,
        json.dumps(items, ensure_ascii=False), reason, family_notes,
        round(refund_amount, 2), now_str, now_str
    ))
    return_id = cursor.lastrowid

    cursor.execute("UPDATE orders SET return_status = 'SOLICITADO', updated_at = ? WHERE id = ?", (now_str, order["id"]))

    summary_items = ", ".join([f"{it.get('product_name')} ({it.get('action')})" for it in items])
    cursor.execute("""
        INSERT INTO order_history (order_id, status, comment, timestamp)
        VALUES (?, (SELECT status FROM orders WHERE id = ?), ?, ?)
    """, (order["id"], order["id"], f"Solicitud de cambio/devolución registrada (#{ticket_code}): {summary_items}. Motivo: {reason}", now_str))

    conn.commit()

    return_record = {
        "id": return_id,
        "ticket_code": ticket_code,
        "request_type": request_type,
        "items": items,
        "reason": reason,
        "family_notes": family_notes,
        "refund_amount": refund_amount
    }

    try:
        send_return_request_received_email(dict(order), return_record, request.host_url)
    except Exception as e:
        print(f"Aviso email de solicitud cambio: {e}")

    conn.close()
    return jsonify({
        "success": True,
        "return_id": return_id,
        "ticket_code": ticket_code,
        "message": f"Tu solicitud de { 'devolución' if request_type == 'devolucion' else 'cambio de talla' } ha sido registrada con el código {ticket_code}. Hemos enviado un correo con las instrucciones a {order['parent_email']}."
    })

@app.route("/api/orders/<locator>/returns", methods=["GET"])
def get_order_returns(locator):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE locator = ?", (locator.upper().strip(),))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Pedido no encontrado"}), 404

    cursor.execute("SELECT * FROM order_returns WHERE order_id = ? ORDER BY id DESC", (order["id"],))
    results = []
    for r in cursor.fetchall():
        rd = dict(r)
        try:
            rd["items"] = json.loads(rd["items_json"])
        except Exception:
            rd["items"] = []
        results.append(rd)
    conn.close()
    return jsonify({"returns": results})

# ==========================================
# APIs ADMINISTRACIÓN
# ==========================================

@app.route("/api/admin/me", methods=["GET"])
def admin_get_current_user():
    role = get_admin_role()
    role_info = ROLE_METADATA.get(role, ROLE_METADATA["viewer"])
    return jsonify({
        "authenticated": True,
        "role": role,
        "info": role_info
    })

@app.route("/api/admin/passwords", methods=["GET", "POST"])
def admin_manage_passwords():
    role = get_admin_role()
    if role != "master":
        return jsonify({"error": "Solo el Administrador Maestro puede consultar o actualizar las contraseñas"}), 403

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        master_new = (data.get("master") or "").strip()
        operator_new = (data.get("operator") or "").strip()
        viewer_new = (data.get("viewer") or "").strip()

        if master_new:
            cursor.execute("INSERT INTO school_settings (key, value) VALUES ('admin_password_master', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (master_new,))
            cursor.execute("INSERT INTO school_settings (key, value) VALUES ('admin_password', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (master_new,))
        if operator_new:
            cursor.execute("INSERT INTO school_settings (key, value) VALUES ('admin_password_operator', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (operator_new,))
        if viewer_new:
            cursor.execute("INSERT INTO school_settings (key, value) VALUES ('admin_password_viewer', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (viewer_new,))

        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Contraseñas de administración actualizadas correctamente."})

    # GET
    pwds = get_admin_passwords()
    conn.close()
    return jsonify({
        "master": pwds["master"],
        "operator": pwds["operator"],
        "viewer": pwds["viewer"]
    })

@app.route("/api/admin/smtp", methods=["GET", "POST"])
def admin_manage_smtp():
    role = get_admin_role()
    if role != "master":
        return jsonify({"error": "Solo el Administrador Maestro puede configurar el servidor de correo"}), 403

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        smtp_host = (data.get("host") or "").strip()
        smtp_port = str(data.get("port") or "587").strip()
        smtp_user = (data.get("user") or "").strip()
        smtp_pass = (data.get("password") or "").strip()
        smtp_from = (data.get("from_email") or "").strip()
        smtp_from_name = (data.get("from_name") or "Colegio San Buenaventura").strip()
        smtp_ssl = "1" if data.get("use_ssl") else "0"

        cursor.execute("INSERT INTO school_settings (key, value) VALUES ('smtp_host', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (smtp_host,))
        cursor.execute("INSERT INTO school_settings (key, value) VALUES ('smtp_port', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (smtp_port,))
        cursor.execute("INSERT INTO school_settings (key, value) VALUES ('smtp_user', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (smtp_user,))
        cursor.execute("INSERT INTO school_settings (key, value) VALUES ('smtp_from', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (smtp_from,))
        cursor.execute("INSERT INTO school_settings (key, value) VALUES ('smtp_from_name', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (smtp_from_name,))
        cursor.execute("INSERT INTO school_settings (key, value) VALUES ('smtp_ssl', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (smtp_ssl,))

        # Solo actualizar contraseña si se proporciona una nueva
        if smtp_pass:
            cursor.execute("INSERT INTO school_settings (key, value) VALUES ('smtp_pass', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (smtp_pass,))

        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Configuración SMTP guardada correctamente."})

    # GET
    cfg = get_smtp_config()
    conn.close()
    return jsonify({
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "from_email": cfg["from_email"],
        "from_name": cfg["from_name"],
        "use_ssl": cfg["use_ssl"],
        "has_password": bool(cfg["password"]),
        "source": cfg["source"]
    })

@app.route("/api/admin/smtp/test", methods=["POST"])
def admin_test_smtp():
    role = get_admin_role()
    if role != "master":
        return jsonify({"error": "Solo el Administrador Maestro puede realizar pruebas de correo"}), 403

    data = request.get_json(silent=True) or {}
    test_email = (data.get("test_email") or "").strip()
    if not test_email or "@" not in test_email:
        return jsonify({"error": "Debes especificar una dirección de correo válida para la prueba."}), 400

    success, message = send_test_email(test_email)
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "error": message}), 400

@app.route("/api/admin/orders", methods=["GET"])
def admin_get_orders():
    status = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip().lower()

    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM orders WHERE 1=1"
    params = []

    if status and status != "Todos":
        query += " AND status = ?"
        params.append(status)

    if search:
        query += " AND (LOWER(locator) LIKE ? OR LOWER(student_name) LIKE ? OR LOWER(student_course) LIKE ? OR LOWER(parent_name) LIKE ? OR parent_phone LIKE ? OR LOWER(parent_email) LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s, s, s, s])

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    orders = [dict(row) for row in cursor.fetchall()]

    # Añadir items, historial, emails y solicitudes de cambio a cada pedido
    for ord_item in orders:
        cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (ord_item["id"],))
        ord_item["items"] = [dict(it) for it in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM order_history WHERE order_id = ? ORDER BY id ASC", (ord_item["id"],))
        ord_item["history"] = [dict(h) for h in cursor.fetchall()]

        cursor.execute("SELECT * FROM order_emails WHERE order_id = ? ORDER BY id DESC", (ord_item["id"],))
        ord_item["emails"] = [dict(e) for e in cursor.fetchall()]

        cursor.execute("SELECT * FROM order_returns WHERE order_id = ? ORDER BY id DESC", (ord_item["id"],))
        rets = []
        for r in cursor.fetchall():
            rd = dict(r)
            try:
                rd["items"] = json.loads(rd["items_json"])
            except Exception:
                rd["items"] = []
            rets.append(rd)
        ord_item["returns"] = rets

    conn.close()
    return jsonify({"orders": orders})

@app.route("/api/admin/returns", methods=["GET"])
def admin_get_returns():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, o.student_name, o.student_course, o.parent_name, o.parent_phone, o.parent_email, o.status as order_status
        FROM order_returns r
        JOIN orders o ON r.order_id = o.id
        ORDER BY r.id DESC
    """)
    returns_raw = cursor.fetchall()
    conn.close()

    results = []
    for r in returns_raw:
        rd = dict(r)
        try:
            rd["items"] = json.loads(rd["items_json"])
        except Exception:
            rd["items"] = []
        results.append(rd)
    return jsonify({"returns": results})

@app.route("/api/admin/returns/<int:return_id>/status", methods=["PATCH"])
def admin_update_return_status(return_id):
    data = request.get_json() or {}
    new_status = data.get("status")
    admin_notes = data.get("admin_notes", "").strip()

    if not new_status:
        return jsonify({"error": "Estado requerido"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, o.id as order_id, o.locator, o.student_name, o.student_course, o.parent_name, o.parent_email 
        FROM order_returns r 
        JOIN orders o ON r.order_id = o.id 
        WHERE r.id = ?
    """, (return_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Solicitud no encontrada"}), 404

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE order_returns 
        SET status = ?, admin_notes = CASE WHEN ? != '' THEN ? ELSE admin_notes END, updated_at = ?
        WHERE id = ?
    """, (new_status, admin_notes, admin_notes, now_str, return_id))

    ticket_code = row["ticket_code"]
    order_id = row["order_id"]

    cursor.execute("""
        INSERT INTO order_history (order_id, status, comment, timestamp)
        VALUES (?, (SELECT status FROM orders WHERE id = ?), ?, ?)
    """, (order_id, order_id, f"Cambio/Devolución {ticket_code} actualizado a: '{new_status}'. {admin_notes}", now_str))

    # Si se completa, actualizar tallas en order_items si era cambio de talla
    if new_status == "COMPLETADO":
        cursor.execute("UPDATE orders SET return_status = 'COMPLETADO', updated_at = ? WHERE id = ?", (now_str, order_id))
        try:
            items_list = json.loads(row["items_json"])
            for it in items_list:
                if it.get("action") == "cambiar" and it.get("item_id") and it.get("new_size"):
                    cursor.execute("UPDATE order_items SET size = ? WHERE id = ? AND order_id = ?", (it["new_size"], it["item_id"], order_id))
        except Exception as e:
            print(f"Aviso actualizando talla completada: {e}")

    conn.commit()

    # Si se marca LISTO_RECOGIDA, enviar aviso a la familia
    if new_status == "LISTO_RECOGIDA":
        try:
            ret_dict = dict(row)
            ret_dict["items"] = json.loads(row["items_json"])
            order_data = {
                "id": order_id,
                "student_name": row["student_name"],
                "parent_name": row["parent_name"],
                "parent_email": row["parent_email"],
                "locator": row["locator"]
            }
            send_return_ready_email(order_data, ret_dict, request.host_url)
        except Exception as e:
            print(f"Error enviando correo de prendas listas: {e}")

    conn.close()
    return jsonify({"success": True, "status": new_status, "message": f"Solicitud {ticket_code} actualizada con éxito."})

@app.route("/api/admin/orders/<int:order_id>/exchange", methods=["POST"])
def admin_direct_exchange(order_id):
    """Permite a secretaría registrar un cambio de talla inmediato en ventanilla"""
    data = request.get_json() or {}
    item_id = data.get("item_id")
    new_size = data.get("new_size", "").strip()
    reason = data.get("reason", "Cambio directo en portería/secretaría").strip()

    if not item_id or not new_size:
        return jsonify({"error": "Prenda y nueva talla son obligatorias."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM order_items WHERE id = ? AND order_id = ?", (item_id, order_id))
    item = cursor.fetchone()
    if not item:
        conn.close()
        return jsonify({"error": "Prenda no encontrada en este pedido."}), 404

    old_size = item["size"]
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("UPDATE order_items SET size = ? WHERE id = ?", (new_size, item_id))
    cursor.execute("""
        INSERT INTO order_history (order_id, status, comment, timestamp)
        VALUES (?, (SELECT status FROM orders WHERE id = ?), ?, ?)
    """, (order_id, order_id, f"Cambio de talla presencial en portería/secretaría: {item['product_name']} de {old_size} a {new_size}. Motivo: {reason}", now_str))

    cursor.execute("UPDATE orders SET updated_at = ? WHERE id = ?", (now_str, order_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Talla actualizada de {old_size} a {new_size} correctamente."})

@app.route("/api/admin/orders/<int:order_id>/item-action", methods=["POST"])
def admin_in_person_item_action(order_id):
    """
    Permite al personal de portería / secretaría editar presencialmente el pedido cuando la familia acude al centro:
    1. 'exchange': Cambio de talla presencial (ajusta talla o divide unidades en order_items y registra en historial).
    2. 'return': Devolución presencial de prenda (reduce unidades o elimina prenda, recalcula total_amount del pedido y registra en historial).
    """
    data = request.get_json() or {}
    action = data.get("action", "exchange").strip() # 'exchange' o 'return'
    item_id = data.get("item_id")
    reason = data.get("reason", "").strip() or "Gestión presencial en portería"
    notes = data.get("notes", "").strip()

    if not item_id:
        return jsonify({"error": "Debe especificar la prenda a modificar."}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM order_items WHERE id = ? AND order_id = ?", (item_id, order_id))
    item = cursor.fetchone()
    if not item:
        conn.close()
        return jsonify({"error": "Prenda no encontrada en este pedido."}), 404

    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Pedido no encontrado."}), 404

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "return":
        try:
            qty_to_return = int(data.get("quantity", item["quantity"]))
        except Exception:
            qty_to_return = item["quantity"]

        if qty_to_return <= 0 or qty_to_return > item["quantity"]:
            conn.close()
            return jsonify({"error": f"Cantidad a devolver inválida (máximo {item['quantity']} uds)."}), 400

        unit_price = float(item["unit_price"])
        amount_deducted = round(unit_price * qty_to_return, 2)

        if qty_to_return == item["quantity"]:
            # Devolución total de la línea
            cursor.execute("DELETE FROM order_items WHERE id = ?", (item_id,))
        else:
            # Devolución parcial (se conservan unidades restantes)
            new_qty = item["quantity"] - qty_to_return
            new_subtotal = round(new_qty * unit_price, 2)
            cursor.execute("UPDATE order_items SET quantity = ?, subtotal = ? WHERE id = ?", (new_qty, new_subtotal, item_id))

        # Recalcular total real del pedido
        cursor.execute("SELECT COALESCE(SUM(subtotal), 0) as new_total, COUNT(*) as remaining_items FROM order_items WHERE order_id = ?", (order_id,))
        totals_row = cursor.fetchone()
        new_total = round(float(totals_row["new_total"]), 2)
        remaining = int(totals_row["remaining_items"])

        new_status = order["status"]
        if remaining == 0:
            new_status = "Devuelto"

        cursor.execute("UPDATE orders SET total_amount = ?, status = ?, updated_at = ? WHERE id = ?", (new_total, new_status, now_str, order_id))

        comment = f"Devolución presencial en portería: {qty_to_return} ud(s) de {item['product_name']} (Talla {item['size']}) devuelta(s). Prenda recibida en el centro. Importe deducido: {amount_deducted:.2f} € (Nuevo total: {new_total:.2f} €). Motivo: {reason}."
        if notes:
            comment += f" Observaciones: {notes}"

        cursor.execute("""
            INSERT INTO order_history (order_id, status, comment, timestamp)
            VALUES (?, ?, ?, ?)
        """, (order_id, new_status, comment, now_str))

        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": f"Devolución registrada: {qty_to_return} ud(s) de {item['product_name']} descontadas del pedido.",
            "new_total": new_total,
            "status": new_status
        })

    elif action == "exchange":
        new_size = data.get("new_size", "").strip()
        if not new_size:
            conn.close()
            return jsonify({"error": "Debe especificar la nueva talla para el cambio."}), 400

        old_size = item["size"]
        try:
            qty_to_change = int(data.get("quantity", item["quantity"]))
        except Exception:
            qty_to_change = item["quantity"]

        if qty_to_change <= 0 or qty_to_change > item["quantity"]:
            qty_to_change = item["quantity"]

        if qty_to_change == item["quantity"]:
            cursor.execute("UPDATE order_items SET size = ? WHERE id = ?", (new_size, item_id))
        else:
            # Dividir la línea
            remaining_qty = item["quantity"] - qty_to_change
            cursor.execute("UPDATE order_items SET quantity = ?, subtotal = ? WHERE id = ?", 
                           (remaining_qty, round(remaining_qty * item["unit_price"], 2), item_id))
            cursor.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, size, unit_price, quantity, subtotal, student_name, product_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_id, item["product_id"], item["product_name"], new_size, item["unit_price"], 
                  qty_to_change, round(qty_to_change * item["unit_price"], 2), item["student_name"], item["product_code"]))

        comment = f"Cambio presencial en portería: {qty_to_change} ud(s) de {item['product_name']} cambiadas de talla {old_size} a {new_size}. Prenda canjeada en el centro. Motivo: {reason}."
        if notes:
            comment += f" Observaciones: {notes}"

        cursor.execute("""
            INSERT INTO order_history (order_id, status, comment, timestamp)
            VALUES (?, (SELECT status FROM orders WHERE id = ?), ?, ?)
        """, (order_id, order_id, comment, now_str))

        cursor.execute("UPDATE orders SET updated_at = ? WHERE id = ?", (now_str, order_id))
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": f"Cambio de talla registrado: {item['product_name']} de {old_size} a {new_size}."
        })

    else:
        conn.close()
        return jsonify({"error": "Acción desconocida. Debe ser 'exchange' o 'return'."}), 400

@app.route("/api/admin/orders/<int:order_id>/status", methods=["PATCH"])
def admin_update_order_status(order_id):
    data = request.get_json() or {}
    new_status = data.get("status", "").strip()
    comment = data.get("comment", "").strip()
    send_email_now = data.get("send_email", True)

    valid_statuses = ["Pendiente", "En preparación", "Listo para recoger", "Entregado", "Cancelado"]
    if new_status not in valid_statuses:
        return jsonify({"error": f"Estado inválido. Debe ser uno de: {', '.join(valid_statuses)}"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Pedido no encontrado"}), 404

    order_dict = dict(order)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not comment:
        if new_status == "En preparación":
            comment = "Prendas en preparación en el almacén del colegio."
        elif new_status == "Listo para recoger":
            comment = "Pedido empaquetado y depositado en conserjería para su recogida."
        elif new_status == "Entregado":
            comment = "Uniforme entregado a la familia."
        elif new_status == "Cancelado":
            comment = "Pedido cancelado."
        else:
            comment = f"Estado cambiado a {new_status}."

    cursor.execute("""
        UPDATE orders SET status = ?, updated_at = ? WHERE id = ?
    """, (new_status, now_str, order_id))

    cursor.execute("""
        INSERT INTO order_history (order_id, status, comment, timestamp)
        VALUES (?, ?, ?, ?)
    """, (order_id, new_status, comment, now_str))

    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = [dict(it) for it in cursor.fetchall()]

    conn.commit()
    conn.close()

    # Si se marca como "Listo para recoger" y send_email_now es True, enviar el correo a la familia
    email_result = None
    if new_status == "Listo para recoger" and send_email_now:
        order_dict["status"] = new_status
        try:
            email_result = send_order_ready_email(order_dict, items, request.host_url)
            print(f"Resultado envio email listo para recoger: {email_result}")
        except Exception as e:
            print(f"Error enviando email listo para recoger: {e}")

    return jsonify({
        "success": True,
        "status": new_status,
        "updated_at": now_str,
        "email_sent": email_result is not None
    })

@app.route("/api/admin/orders/<int:order_id>/send-email", methods=["POST"])
def admin_send_email_to_family(order_id):
    """Permite a secretaría enviar/reenviar correos a la familia dejando constancia en la ficha"""
    data = request.get_json() or {}
    email_type = data.get("type", "ready") # 'ready' o 'confirmation' o 'custom'

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "Pedido no encontrado"}), 404

    order_dict = dict(order)
    cursor.execute("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    items = [dict(it) for it in cursor.fetchall()]
    conn.close()

    if email_type == "ready":
        result = send_order_ready_email(order_dict, items, request.host_url)
    elif email_type == "confirmation":
        result = send_order_confirmation_email(order_dict, items, request.host_url)
    elif email_type == "custom":
        custom_subject = data.get("subject", "").strip() or f"Información sobre su reserva [{order_dict['locator']}] - Colegio San Buenaventura"
        custom_text = data.get("message", "").strip()
        if not custom_text:
            return jsonify({"error": "El mensaje no puede estar vacío."}), 400
        custom_html = f"<div style='font-family: sans-serif; padding: 20px;'><p>{custom_text.replace(chr(10), '<br>')}</p></div>"
        result = record_and_dispatch_email(order_id, order_dict["parent_email"], custom_subject, custom_text, custom_html, "personalizado")
    else:
        return jsonify({"error": "Tipo de email no reconocido"}), 400

    return jsonify({
        "success": True,
        "message": f"Email enviado con éxito a {order_dict['parent_email']} y registrado en la ficha del pedido.",
        "details": result
    })

@app.route("/api/admin/stats", methods=["GET"])
def admin_stats():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total_orders, SUM(total_amount) as total_revenue FROM orders WHERE status != 'Cancelado'")
    row_totals = cursor.fetchone()
    total_orders = row_totals["total_orders"] or 0
    total_revenue = row_totals["total_revenue"] or 0.0

    cursor.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
    status_counts = {r["status"]: r["count"] for r in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as count FROM products WHERE is_active = 1")
    total_products = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM order_returns WHERE status = 'PENDIENTE'")
    pending_returns = cursor.fetchone()["count"]

    conn.close()

    return jsonify({
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "pending": status_counts.get("Pendiente", 0),
        "preparing": status_counts.get("En preparación", 0),
        "ready": status_counts.get("Listo para recoger", 0),
        "delivered": status_counts.get("Entregado", 0),
        "cancelled": status_counts.get("Cancelado", 0),
        "pending_returns": pending_returns,
        "total_products": total_products
    })

@app.route("/api/admin/catalog", methods=["POST"])
def admin_add_product():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    category_id = data.get("category_id")
    code = data.get("code", "").strip()
    description = data.get("description", "").strip()
    price = float(data.get("price", 0.0))
    sizes = data.get("sizes", [])
    image_url = data.get("image_url", "").strip() or "/static/images/uniforms/polo.svg"
    gender = data.get("gender", "Unisex")

    if not name or not category_id or price <= 0:
        return jsonify({"error": "Nombre, categoría y precio son obligatorios."}), 400

    if isinstance(sizes, list):
        sizes_json = json.dumps(sizes)
    else:
        sizes_json = json.dumps([s.strip() for s in str(sizes).split(",") if s.strip()])

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO products (category_id, name, code, description, price, sizes_json, image_url, gender)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (category_id, name, code, description, price, sizes_json, image_url, gender))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"success": True, "product_id": new_id})

@app.route("/api/admin/catalog/<int:product_id>", methods=["PUT", "DELETE"])
def admin_manage_product(product_id):
    conn = get_db()
    cursor = conn.cursor()

    if request.method == "DELETE":
        cursor.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Prenda desactivada."})

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    category_id = data.get("category_id")
    description = data.get("description", "").strip()
    price = float(data.get("price", 0.0))
    sizes = data.get("sizes", [])
    image_url = data.get("image_url", "").strip()
    gender = data.get("gender", "Unisex")

    if isinstance(sizes, list):
        sizes_json = json.dumps(sizes)
    else:
        sizes_json = json.dumps([s.strip() for s in str(sizes).split(",") if s.strip()])

    cursor.execute("""
        UPDATE products 
        SET name = ?, category_id = ?, description = ?, price = ?, sizes_json = ?, image_url = ?, gender = ?
        WHERE id = ?
    """, (name, category_id, description, price, sizes_json, image_url, gender, product_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Prenda actualizada con éxito."})

@app.route("/api/admin/import-catalog", methods=["POST"])
def admin_bulk_import():
    data = request.get_json() or {}
    products = data.get("products", [])
    replace_all = data.get("replace_all", False)

    if not products:
        return jsonify({"error": "No se proporcionaron productos en el payload."}), 400

    conn = get_db()
    cursor = conn.cursor()

    if replace_all:
        cursor.execute("DELETE FROM products")

    inserted = 0
    for p in products:
        cat_id = p.get("category_id", 1)
        name = p.get("name")
        code = p.get("code", "")
        desc = p.get("description", "")
        price = float(p.get("price", 0.0))
        sizes = p.get("sizes", ["Única"])
        img = p.get("image_url", "/static/images/uniforms/polo.svg")
        gender = p.get("gender", "Unisex")

        sizes_json = json.dumps(sizes) if isinstance(sizes, list) else json.dumps([s.strip() for s in sizes.split(",")])

        cursor.execute("""
            INSERT INTO products (category_id, name, code, description, price, sizes_json, image_url, gender)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cat_id, name, code, desc, price, sizes_json, img, gender))
        inserted += 1

    conn.commit()
    conn.close()
    return jsonify({"success": True, "inserted_count": inserted})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
