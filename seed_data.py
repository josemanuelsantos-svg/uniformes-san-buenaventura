import json
from database import get_db, init_db

def make_tiered_sizes(p_2_10, p_12_18, p_20_plus, sizes=None):
    if sizes is None:
        sizes = ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20", "T.22", "T.24", "T.26", "T.28"]
    tier_map = {}
    for s in sizes:
        num_str = s.replace("T.", "").split()[0].strip()
        if num_str.isdigit():
            n = int(num_str)
            if n <= 10:
                tier_map[s] = float(p_2_10)
            elif 12 <= n <= 18:
                tier_map[s] = float(p_12_18)
            else:
                tier_map[s] = float(p_20_plus)
        else:
            tier_map[s] = float(p_20_plus)
    return sizes, tier_map

def seed():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Datos oficiales exactos del pie de la hoja del Colegio San Buenaventura
    settings = {
        "school_name": "Colegio San Buenaventura",
        "school_entity": "Franciscanos Conventuales",
        "school_cif": "R-2800045-G",
        "school_address": "c/ El Greco, 16",
        "school_city": "Madrid",
        "school_postal_code": "28011",
        "school_phone": "91 526 71 61",
        "school_email": "administracion@sanbuenaventura.org",
        "school_web": "www.sanbuenaventura.org",
        "pickup_location": "Conserjería / Secretaría del Colegio (c/ El Greco, 16)",
        "pickup_schedule": "Lunes a Viernes en horario de secretaría",
        "vat_rate": "21",
        "admin_password": "SanBuenaventura2026",
        "admin_password_master": "SanBuenaventura2026",
        "admin_password_operator": "CambiosCSB2026",
        "admin_password_viewer": "ConsultaCSB2026"
    }

    for k, v in settings.items():
        cursor.execute("INSERT OR REPLACE INTO school_settings (key, value) VALUES (?, ?)", (k, v))

    # Categorías adaptadas exactamente a la hoja oficial
    categories = [
        ("Uniforme de Diario", "uniforme-diario", "Faldas, pantalones de vestir, jerséis y polos oficiales", 1),
        ("Deporte / Chándal", "deporte-chandal", "Chándal completo, sudaderas, pantalones de deporte y camisetas técnicas", 2),
        ("Educación Infantil", "infantil", "Baby escolar, chándal infantil, sudadera y pantalón infantil (Tallas 2 a 6)", 3),
        ("Complementos y Calcetines", "complementos", "Leotardos y calcetines colegiales cortos y largos", 4)
    ]

    for name, slug, desc, sort_order in categories:
        cursor.execute("""
            INSERT OR IGNORE INTO categories (name, slug, description, sort_order)
            VALUES (?, ?, ?, ?)
        """, (name, slug, desc, sort_order))

    cursor.execute("SELECT id, slug FROM categories")
    cat_map = {row["slug"]: row["id"] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] >= 18:
        conn.close()
        return

    full_sizes = ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20", "T.22", "T.24", "T.26", "T.28"]

    products_spec = [
        # --- UNIFORME DE DIARIO ---
        {
            "category_id": cat_map["uniforme-diario"],
            "name": "Falda uniforme - CSB",
            "code": "FAL-CSB",
            "desc": "Falda oficial con tablas, tejido gris marengo con finos cuadros de líneas azules y tirantes en tallas infantiles.",
            "base_price": 43.00,
            "tier_data": make_tiered_sizes(43.00, 53.00, 56.00, full_sizes),
            "image": "/static/images/uniforms/falda.svg",
            "gender": "Niña",
            "order": 1
        },
        {
            "category_id": cat_map["uniforme-diario"],
            "name": "Jersey uniforme - CSB",
            "code": "JER-CSB",
            "desc": "Jersey oficial de punto azul petróleo con cuello en pico, remates en canalé y escudo bordado CSB.",
            "base_price": 34.00,
            "tier_data": make_tiered_sizes(34.00, 37.00, 40.00, full_sizes),
            "image": "/static/images/uniforms/jersey.svg",
            "gender": "Unisex",
            "order": 2
        },
        {
            "category_id": cat_map["uniforme-diario"],
            "name": "Polo M/corta - CSB",
            "code": "POL-MC-CSB",
            "desc": "Polo oficial azul celeste de manga corta con ribetes a contraste en cuello y mangas y escudo bordado CSB.",
            "base_price": 22.00,
            "tier_data": make_tiered_sizes(22.00, 23.00, 25.00, full_sizes),
            "image": "/static/images/uniforms/polo-mcorta.svg",
            "gender": "Unisex",
            "order": 3
        },
        {
            "category_id": cat_map["uniforme-diario"],
            "name": "Polo M/larga - CSB (Restos / Tallas sueltas)",
            "code": "POL-ML-CSB",
            "desc": "Polo oficial azul celeste de manga larga con cuello y puños elásticos con ribete y escudo bordado CSB. Prenda a extinguir disponible únicamente en restos de tallas sueltas hasta agotar existencias.",
            "base_price": 23.00,
            "tier_data": make_tiered_sizes(23.00, 24.00, 26.00, full_sizes),
            "image": "/static/images/uniforms/polo-mlarga.svg",
            "gender": "Unisex",
            "order": 4
        },
        {
            "category_id": cat_map["uniforme-diario"],
            "name": "Pantalón vestir largo - CSB",
            "code": "PAN-LG-CSB",
            "desc": "Pantalón largo gris marengo modelo chino oficial con cintura elástica ajustable y corte formal.",
            "base_price": 38.00,
            "tier_data": make_tiered_sizes(38.00, 40.00, 46.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-vestir-largo.svg",
            "gender": "Niño / Unisex",
            "order": 5
        },
        {
            "category_id": cat_map["uniforme-diario"],
            "name": "Pantalón vestir corto - CSB",
            "code": "PAN-CT-CSB",
            "desc": "Bermuda gris marengo oficial para meses cálidos con trabillas para cinturón y bolsillos laterales.",
            "base_price": 33.00,
            "tier_data": make_tiered_sizes(33.00, 36.00, 40.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-vestir-corto.svg",
            "gender": "Niño / Unisex",
            "order": 6
        },

        # --- DEPORTE / CHÁNDAL ---
        {
            "category_id": cat_map["deporte-chandal"],
            "name": "Chándal Completo - CSB (Últimas tallas en conjunto)",
            "code": "CHA-CSB",
            "desc": "Conjunto deportivo oficial completo (sudadera + pantalón). Aviso: La uniformidad actual se suministra por separado (sudadera y pantalón). Este conjunto completo solo se ofrece en restos de tallas sueltas hasta agotar existencias.",
            "base_price": 54.00,
            "tier_data": make_tiered_sizes(54.00, 56.00, 63.00, full_sizes),
            "image": "/static/images/uniforms/chandal-completo.svg",
            "gender": "Unisex",
            "order": 10
        },
        {
            "category_id": cat_map["deporte-chandal"],
            "name": "Sudadera de chándal (Pieza suelta) - CSB",
            "code": "SUD-CSB",
            "desc": "Chaqueta deportiva de chándal con cremallera, diseño bicolor azul marino y royal con franja blanca y escudo CSB. Suministro individual de prenda deportiva.",
            "base_price": 31.00,
            "tier_data": make_tiered_sizes(31.00, 31.00, 35.00, full_sizes),
            "image": "/static/images/uniforms/sudadera-chandal.svg",
            "gender": "Unisex",
            "order": 11
        },
        {
            "category_id": cat_map["deporte-chandal"],
            "name": "Pantalón de chándal (Pieza suelta) - CSB",
            "code": "PAN-DEP-CSB",
            "desc": "Pantalón de chándal oficial azul marino con paneles laterales royal/blanco, cintura elástica y puños. Suministro individual de prenda deportiva.",
            "base_price": 23.00,
            "tier_data": make_tiered_sizes(23.00, 28.00, 30.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-chandal.svg",
            "gender": "Unisex",
            "order": 12
        },
        {
            "category_id": cat_map["deporte-chandal"],
            "name": "Camiseta de deporte - CSB (Infantil, Primaria y ESO)",
            "code": "CAM-DEP-CSB",
            "desc": "Camiseta técnica oficial de deporte blanca con manga royal, franjas y escudo CSB. ¡Prenda obligatoria de educación física para TODAS las etapas (Educación Infantil, Primaria y Secundaria)!",
            "base_price": 17.00,
            "tier_data": make_tiered_sizes(17.00, 18.00, 19.00, full_sizes),
            "image": "/static/images/uniforms/camiseta-deporte.svg",
            "gender": "Unisex",
            "order": 13
        },
        {
            "category_id": cat_map["deporte-chandal"],
            "name": "Pantalón corto de deporte - CSB",
            "code": "BER-DEP-CSB",
            "desc": "Bermuda deportiva oficial azul royal con doble franja blanca en pernera izquierda y escudo CSB.",
            "base_price": 17.00,
            "tier_data": make_tiered_sizes(17.00, 18.00, 19.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-corto-deporte.svg",
            "gender": "Unisex",
            "order": 14
        },

        # --- EDUCACIÓN INFANTIL ---
        {
            "category_id": cat_map["infantil"],
            "name": "Chándal Completo - INFANTIL (Últimas tallas en conjunto)",
            "code": "CHA-INF",
            "desc": "Conjunto de chándal infantil completo con coderas y rodilleras a juego. Nota: actualmente se suministra separado (sudadera y pantalón). El conjunto completo queda solo para restos de tallas sueltas de almacén.",
            "base_price": 46.00,
            "tier_data": (["T.2", "T.3", "T.4", "T.5", "T.6"], {s: 46.00 for s in ["T.2", "T.3", "T.4", "T.5", "T.6"]}),
            "image": "/static/images/uniforms/chandal-infantil.svg",
            "gender": "Unisex",
            "order": 20
        },
        {
            "category_id": cat_map["infantil"],
            "name": "Sudadera Chándal INFANTIL (Pieza suelta)",
            "code": "SUD-INF",
            "desc": "Sudadera infantil de chándal azul con cuello polo marino, botones, coderas amarillas y escudo CSB. Suministro individual.",
            "base_price": 26.00,
            "tier_data": (["T.2", "T.3", "T.4", "T.5", "T.6"], {s: 26.00 for s in ["T.2", "T.3", "T.4", "T.5", "T.6"]}),
            "image": "/static/images/uniforms/sudadera-chandal-infantil.svg",
            "gender": "Unisex",
            "order": 21
        },
        {
            "category_id": cat_map["infantil"],
            "name": "Pantalón Chándal INFANTIL (Pieza suelta)",
            "code": "PAN-INF",
            "desc": "Pantalón deportivo infantil azul marino con rodilleras reforzadas (una amarilla y otra celeste) y cintura elástica. Suministro individual.",
            "base_price": 21.00,
            "tier_data": (["T.2", "T.3", "T.4", "T.5", "T.6"], {s: 21.00 for s in ["T.2", "T.3", "T.4", "T.5", "T.6"]}),
            "image": "/static/images/uniforms/pantalon-chandal-infantil.svg",
            "gender": "Unisex",
            "order": 22
        },
        {
            "category_id": cat_map["infantil"],
            "name": "Babi Escolar Oficial (Cuadro Pequeño) - CSB",
            "code": "BAB-CSB",
            "desc": "Babi oficial obligatorio para Educación Infantil (1º, 2º y 3º). Confeccionado en tejido de CUADRO VICHY PEQUEÑO reglamentario del colegio, canesú marino, bolsillo en contraste y escudo bordado CSB. ¡Atención! Evite prendas no oficiales del exterior con cuadros grandes no reglamentarios.",
            "base_price": 22.00,
            "tier_data": (["T.2", "T.3", "T.4", "T.5", "T.6", "T.8"], {s: 22.00 for s in ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8"]}),
            "image": "/static/images/uniforms/babi.svg",
            "gender": "Unisex",
            "order": 23
        },

        # --- COMPLEMENTOS Y CALCETINES ---
        {
            "category_id": cat_map["complementos"],
            "name": "Leotardo",
            "code": "LEO-CSB",
            "desc": "Leotardo de algodón elástico azul marino oficial, tacto suave, cálido y resistente.",
            "base_price": 7.70,
            "tier_data": make_tiered_sizes(7.70, 8.70, 9.70, ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16"]),
            "image": "/static/images/uniforms/leotardo.svg",
            "gender": "Unisex / Niña",
            "order": 30
        },
        {
            "category_id": cat_map["complementos"],
            "name": "Calcetín largo (unidad)",
            "code": "CAL-LG-CSB",
            "desc": "Calcetín alto o media canalé en azul marino oficial por unidad.",
            "base_price": 3.10,
            "tier_data": (
                ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20"],
                {s: 3.10 for s in ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20"]}
            ),
            "image": "/static/images/uniforms/calcetin-largo.svg",
            "gender": "Unisex",
            "order": 31
        },
        {
            "category_id": cat_map["complementos"],
            "name": "Calcetín corto (unidad)",
            "code": "CAL-CT-CSB",
            "desc": "Calcetín corto tobillero oficial de uniforme y deporte por unidad.",
            "base_price": 2.60,
            "tier_data": (
                ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20"],
                {s: 2.60 for s in ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20"]}
            ),
            "image": "/static/images/uniforms/calcetin-corto.svg",
            "gender": "Unisex",
            "order": 32
        }
    ]

    for p in products_spec:
        sizes_list, size_prices_map = p["tier_data"]
        cursor.execute("""
            INSERT INTO products (category_id, name, code, description, price, sizes_json, size_prices_json, image_url, gender, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["category_id"],
            p["name"],
            p["code"],
            p["desc"],
            p["base_price"],
            json.dumps(sizes_list),
            json.dumps(size_prices_map),
            p["image"],
            p["gender"],
            p["order"]
        ))

    conn.commit()
    conn.close()
    print("Catálogo oficial del Colegio San Buenaventura cargado exitosamente.")

if __name__ == "__main__":
    seed()
