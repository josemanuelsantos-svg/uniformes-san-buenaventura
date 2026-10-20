import sqlite3
import os
import json
from datetime import datetime

import shutil

DB_ORIGINAL_PATH = os.path.join(os.path.dirname(__file__), "uniformes.db")
if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/uniformes.db"
    if not os.path.exists(DB_PATH) and os.path.exists(DB_ORIGINAL_PATH):
        try:
            shutil.copy2(DB_ORIGINAL_PATH, DB_PATH)
        except Exception as e:
            print(f"Error copying DB to /tmp on Vercel: {e}")
else:
    DB_PATH = DB_ORIGINAL_PATH

BACKUP_FILE = os.path.join(os.path.dirname(DB_PATH), "orders_backup.jsonl")

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Habilitar modo WAL para máxima durabilidad y concurrencia sin bloqueos
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Tabla de Categorías
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        description TEXT,
        sort_order INTEGER DEFAULT 0
    )
    """)

    # Tabla de Productos / Prendas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        code TEXT UNIQUE,
        description TEXT,
        price REAL NOT NULL,
        sizes_json TEXT NOT NULL, -- Lista de tallas ['T.2', 'T.4', ...]
        size_prices_json TEXT, -- Mapeo opcional talla -> precio {'T.2': 43.0, 'T.12': 53.0}
        image_url TEXT,
        gender TEXT DEFAULT 'Unisex', -- Unisex, Niño, Niña
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    """)
    
    # Auto-migración por si la base de datos ya existía
    cursor.execute("PRAGMA table_info(products)")
    existing_cols = [r[1] for r in cursor.fetchall()]
    if "size_prices_json" not in existing_cols:
        cursor.execute("ALTER TABLE products ADD COLUMN size_prices_json TEXT")

    # Tabla de Pedidos / Reservas (Persistencia garantizada)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        locator TEXT UNIQUE NOT NULL, -- Código único: SB-2026-XXXX
        student_name TEXT NOT NULL,
        student_course TEXT NOT NULL,
        parent_name TEXT NOT NULL,
        parent_phone TEXT NOT NULL,
        parent_email TEXT NOT NULL,
        parent_nif TEXT DEFAULT '',
        notes TEXT,
        status TEXT DEFAULT 'Pendiente', -- Pendiente, En preparación, Listo para recoger, Entregado, Cancelado
        total_amount REAL NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        notification_sent_at TEXT,
        notification_channel TEXT DEFAULT 'email'
    )
    """)

    # Tabla de Líneas de Pedido
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER,
        product_name TEXT NOT NULL,
        size TEXT NOT NULL,
        unit_price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    )
    """)

    # Tabla de Historial de Estados y Acciones en la Ficha del Pedido
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        comment TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    )
    """)

    # Tabla de Emails Enviados a la Familia (Registro inmutable en la Ficha)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_emails (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        body_text TEXT NOT NULL,
        email_type TEXT NOT NULL, -- 'confirmacion_reserva', 'listo_para_recoger', 'estado_actualizado'
        sent_at TEXT NOT NULL,
        status TEXT DEFAULT 'ENVIADO',
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    )
    """)

    # Tabla de Solicitudes de Cambio de Talla y Devoluciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        locator TEXT NOT NULL,
        ticket_code TEXT UNIQUE NOT NULL, -- CAMBIO-2026-XXXX o DEV-2026-XXXX
        request_type TEXT NOT NULL, -- 'cambio_talla', 'devolucion', 'mixto'
        status TEXT DEFAULT 'PENDIENTE', -- PENDIENTE, APROBADO_PREPARANDO, LISTO_RECOGIDA, COMPLETADO, RECHAZADO
        items_json TEXT NOT NULL, -- Lista JSON de prendas a cambiar/devolver
        reason TEXT,
        family_notes TEXT,
        admin_notes TEXT,
        refund_amount REAL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
    )
    """)

    # Tabla de Configuración del Colegio
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS school_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Valores por defecto para SMTP (Google Workspace San Buenaventura)
    default_smtp = [
        ("smtp_host", "smtp.gmail.com"),
        ("smtp_port", "465"),
        ("smtp_user", "uniformes@sanbuenaventura.org"),
        ("smtp_pass", "ateessoohsmkwctd"),
        ("smtp_from", "uniformes@sanbuenaventura.org"),
        ("smtp_from_name", "Colegio San Buenaventura"),
        ("smtp_ssl", "1"),
    ]
    for sk, sv in default_smtp:
        cursor.execute("INSERT INTO school_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING", (sk, sv))

    # Migración de columnas en tabla orders si no existen
    cursor.execute("PRAGMA table_info(orders)")
    orders_cols = [r[1] for r in cursor.fetchall()]
    if "rgpd_accepted" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN rgpd_accepted INTEGER DEFAULT 1")
    if "return_status" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN return_status TEXT DEFAULT ''")
    if "billing_name" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN billing_name TEXT DEFAULT ''")
    if "billing_address" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN billing_address TEXT DEFAULT ''")
    if "billing_postal_code" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN billing_postal_code TEXT DEFAULT ''")
    if "billing_city" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN billing_city TEXT DEFAULT 'Madrid'")
    if "payment_method" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'Facturación por App del Colegio'")
    if "invoice_number" not in orders_cols:
        cursor.execute("ALTER TABLE orders ADD COLUMN invoice_number TEXT DEFAULT ''")

    # Migración de columnas en tabla order_items
    cursor.execute("PRAGMA table_info(order_items)")
    item_cols = [r[1] for r in cursor.fetchall()]
    if "student_name" not in item_cols:
        cursor.execute("ALTER TABLE order_items ADD COLUMN student_name TEXT DEFAULT ''")
    if "product_code" not in item_cols:
        cursor.execute("ALTER TABLE order_items ADD COLUMN product_code TEXT DEFAULT ''")

    # Rellenar datos fiscales y número de factura correlativo en pedidos existentes que no lo tengan
    cursor.execute("SELECT id, parent_name, invoice_number, billing_name FROM orders ORDER BY id ASC")
    for row in cursor.fetchall():
        oid = row["id"]
        inv_num = row["invoice_number"] or f"FAC-2026-{oid:04d}"
        b_name = row["billing_name"] or row["parent_name"]
        cursor.execute("UPDATE orders SET invoice_number = ?, billing_name = ? WHERE id = ?", (inv_num, b_name, oid))

    conn.commit()
    conn.close()

def backup_order_to_disk(order_dict, items_list):
    """Guarda inmediatamente cada pedido en un archivo append-only JSONL redundante con fsync"""
    record = {
        "order": order_dict,
        "items": items_list,
        "backup_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(BACKUP_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"Error escribiendo en archivo de backup: {e}")

if __name__ == "__main__":
    init_db()
    print("Base de datos y tablas de persistencia verificadas correctamente.")
